"""
Voice Control Service for VRED
-------------------------------
Pipeline:
  Browser (push-to-talk) → POST /voice-command (audio bytes)
  → faster-whisper (ASR) → transcript
  → LM Studio / OpenAI-compatible API (Qwen3.5-9B) → intent JSON
  → POST Strapi /processes/execute-python → VRED vrVariantSets.activateVariantSet(...)
  ← result JSON → Browser

Endpoints:
  POST /voice-command   main pipeline
  GET  /variant-sets    list available variant sets from VRED
  GET  /health          service status
"""

import os
import re
import json
import logging
import tempfile
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import quote
from urllib.request import urlopen
from urllib.error import URLError

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Config ─────────────────────────────────────────────────────────────────────
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
LMSTUDIO_MODEL    = os.getenv("LMSTUDIO_MODEL", "qwen/qwen2.5-vl-7b")
LMSTUDIO_API_KEY  = os.getenv("LMSTUDIO_API_KEY", "lm-studio")   # LM Studio ignores key
LMSTUDIO_TIMEOUT  = float(os.getenv("LMSTUDIO_TIMEOUT", "180"))  # seconds per attempt
WHISPER_MODEL_SIZE= os.getenv("WHISPER_MODEL_SIZE", "paraformer-zh")
WHISPER_DEVICE    = os.getenv("WHISPER_DEVICE", "cpu")
STRAPI_BASE_URL   = os.getenv("STRAPI_BASE_URL", "http://localhost:1337")
VRED_IP           = os.getenv("VRED_IP", "localhost")
VRED_PORT         = os.getenv("VRED_PORT", "8888")
SERVICE_PORT      = int(os.getenv("SERVICE_PORT", "8765"))
# IP of this Mac as seen from VRED (Windows machine on same LAN)
SERVER_IP         = os.getenv("SERVER_IP", "192.168.7.81")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Global state ───────────────────────────────────────────────────────────────
_whisper_model = None

# Callback channel: VRED POSTs variant-set data back to us
_vred_callback_event: Optional[asyncio.Event] = None
_vred_callback_data: Optional[list] = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from funasr import AutoModel
        log.info("Loading FunASR model '%s' on %s …", WHISPER_MODEL_SIZE, WHISPER_DEVICE)
        _whisper_model = AutoModel(
            model=WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            disable_update=True,
        )
        log.info("FunASR ready")
    return _whisper_model


# ── VRED helpers ───────────────────────────────────────────────────────────────
async def _vred_exec(ip: str, port: int, code: str, timeout: int = 30) -> str:
    """
    Execute Python code directly on VRED via its built-in HTTP interface:
      GET http://<ip>:<port>/python?value=<urlencoded_code>
    Returns the response text (VRED stdout output).
    """
    # Keep parens/quotes unencoded – VRED's HTTP server doesn't decode %28/%29.
    _safe = "()',:@!/"
    url = f"http://{ip}:{port}/python?value={quote(code, safe=_safe)}"
    log.info("_vred_exec → %s", url[:200])
    def _do_request():
        with urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    try:
        body = await asyncio.get_event_loop().run_in_executor(None, _do_request)
        log.info("_vred_exec ← body=%r", body[:200])
        return body
    except Exception as e:
        log.error("_vred_exec %s:%s failed: %s | type=%s", ip, port, repr(e), type(e).__name__)
        raise


async def fetch_variant_sets(vred_ip: str = None, vred_port: int = None) -> list[str]:
    """Ask VRED directly for all variant set names via callback."""
    global _vred_callback_event, _vred_callback_data
    ip   = vred_ip   or VRED_IP
    port = vred_port or int(VRED_PORT)

    # VRED's /python HTTP response body is always empty.
    # Instead, tell VRED to POST the data back to our /vred-callback endpoint.
    _vred_callback_event = asyncio.Event()
    _vred_callback_data = None

    callback_url = f"http://{SERVER_IP}:{SERVICE_PORT}/vred-callback"
    # Single-line code using only semicolons and __import__ to avoid issues
    code = (
        "import urllib.request,json;"
        f"urllib.request.urlopen(urllib.request.Request('{callback_url}',"
        "json.dumps(list(vrVariantSets.getVariantSets())).encode(),"
        "{'Content-Type':'application/json'}),timeout=5)"
    )
    try:
        await _vred_exec(ip, port, code, timeout=15)
        await asyncio.wait_for(_vred_callback_event.wait(), timeout=10)
        result = _vred_callback_data or []
        log.info("fetch_variant_sets got %d sets via callback", len(result))
        return result
    except asyncio.TimeoutError:
        log.warning("fetch_variant_sets callback timed out")
    except Exception as e:
        log.warning("fetch_variant_sets failed: %s", repr(e))
    return []


async def activate_variant_set(name: str, vred_ip: str = None, vred_port: int = None) -> dict:
    """Tell VRED to activate the given variant set."""
    ip   = vred_ip   or VRED_IP
    port = vred_port or int(VRED_PORT)
    safe_name = name.replace("'", "\\'")
    code = f"selectVariantSet('{safe_name}')"
    try:
        output = await _vred_exec(ip, port, code, timeout=30)
        return {"ok": True, "output": output}
    except Exception as e:
        log.error("activate_variant_set failed: %s", e)
        return {"ok": False, "error": str(e)}


# ── ASR ────────────────────────────────────────────────────────────────────────
def transcribe_audio(audio_path: str) -> str:
    """Run FunASR on the given audio file. Returns transcript text."""
    model = get_whisper_model()
    result = model.generate(input=audio_path, batch_size_s=300)
    # result is a list of dicts with 'text' key
    text = "".join(r.get("text", "") for r in result).strip()
    log.info("ASR → '%s'", text)
    return text


# ── LLM intent parsing ─────────────────────────────────────────────────────────
SYSTEM_PROMPT_TEMPLATE = """你是一个语音控制助手，负责解析用户指令并切换VRED中的变量集（Variant Sets）。

当前可用的变量集列表：
{variant_sets}

请根据用户的语音指令，判断用户想切换到哪个变量集。
- 只能从上面列出的变量集名称中选择，必须精确匹配。
- 用户可能用中文或英文描述变量集名称或其含义（如颜色名、视角名等）。
- 如果无法确定，返回 action: "none"。

请以JSON格式输出，不要包含其他内容：
{{"action": "activate_variant", "name": "<精确的变量集名称>", "confidence": 0.9}}
或
{{"action": "none", "reason": "<原因>"}}
"""


def _direct_match(transcript: str, variant_sets: list[str]) -> Optional[str]:
    """
    Try to match transcript directly to a variant set name without LLM.
    Returns the matched name or None.
    """
    t = transcript.strip()
    # Exact match
    if t in variant_sets:
        return t
    # Case-insensitive exact
    lower_map = {v.lower(): v for v in variant_sets}
    if t.lower() in lower_map:
        return lower_map[t.lower()]
    # Substring: variant name appears in transcript, or transcript appears in variant name
    for v in variant_sets:
        if v.lower() in t.lower() or t.lower() in v.lower():
            return v
    return None


def _llm_request(url: str, payload: dict) -> dict:
    """Blocking urllib call to LM Studio. Run via executor to stay non-blocking."""
    import urllib.request as _ur
    body = json.dumps(payload).encode()
    req = _ur.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LMSTUDIO_API_KEY}",
        },
        method="POST",
    )
    with _ur.urlopen(req, timeout=LMSTUDIO_TIMEOUT) as r:
        return json.loads(r.read().decode())


async def parse_intent(transcript: str, variant_sets: list[str]) -> dict:
    """Call LM Studio via urllib to parse user intent from transcript."""
    variant_list = "\n".join(f"- {v}" for v in variant_sets) if variant_sets else "（暂无可用变量集）"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(variant_sets=variant_list)

    payload = {
        "model": LMSTUDIO_MODEL,
        "conversations": [
            {"role": "system", "content": system_prompt},
            # /no_think suppresses Qwen3 chain-of-thought so content is never empty
            {"role": "user", "content": transcript + " /no_think"},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }
    url = LMSTUDIO_BASE_URL.rstrip("/") + "/chat/completions"
    raw = ""
    last_error: Exception = None
    for attempt in range(3):
        try:
            data = await asyncio.get_event_loop().run_in_executor(
                None, _llm_request, url, payload
            )
            raw = (data["choices"][0]["message"].get("content") or "").strip()
            log.info("LLM raw: %s", raw)

            # Strip <think>...</think> blocks (Qwen3 inline thinking tags)
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

            # Extract JSON even if wrapped in markdown code block
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            if not raw:
                log.error("LLM returned empty content")
                return {"action": "none", "reason": "LLM returned empty response"}

            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                log.error("LLM JSON parse error: %s | raw: %s", e, raw)
                return {"action": "none", "reason": f"LLM JSON parse error: {e}"}

        except URLError as e:
            last_error = e
            status = getattr(getattr(e, "reason", None), "status", None) or getattr(e, "code", None)
            if status in (502, 503, 504):
                log.warning("LLM gateway error (attempt %d/3): %s — retrying…", attempt + 1, e)
                await asyncio.sleep(2 * (attempt + 1))
                continue
            log.error("LLM call failed: %s", e)
            return {"action": "none", "reason": str(e)}
        except Exception as e:
            last_error = e
            log.error("LLM call failed: %s", e)
            return {"action": "none", "reason": str(e)}

    log.error("LLM call failed after 3 attempts: %s", last_error)
    return {"action": "none", "reason": f"LLM unavailable: {last_error}"}


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load Whisper at startup to avoid first-request latency
    try:
        get_whisper_model()
    except Exception as e:
        log.warning("Whisper pre-load failed (will retry on first request): %s", e)
    yield


app = FastAPI(title="VRED Voice Control", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Response models ────────────────────────────────────────────────────────────
class VoiceCommandResponse(BaseModel):
    transcript: str
    intent: dict
    vred_result: Optional[dict] = None
    error: Optional[str] = None


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "whisper_loaded": _whisper_model is not None,
        "lmstudio_url": LMSTUDIO_BASE_URL,
        "vred_default": f"{VRED_IP}:{VRED_PORT}",
        "server_ip": SERVER_IP,
    }


@app.post("/vred-callback")
async def vred_callback(request: Request):
    """VRED POSTs variant-set JSON back to this endpoint."""
    global _vred_callback_data, _vred_callback_event
    try:
        body = await request.body()
        _vred_callback_data = json.loads(body)
        log.info("vred_callback received %d sets", len(_vred_callback_data))
    except Exception as e:
        log.error("vred_callback parse error: %s", repr(e))
    if _vred_callback_event:
        _vred_callback_event.set()
    return {"ok": True}


@app.get("/test-vred")
async def test_vred(vred_ip: str = None, vred_port: int = None, code: str = "print('hello')"):
    """Low-level VRED connectivity test. Sends arbitrary code and returns raw response."""
    ip = vred_ip or VRED_IP
    port = int(vred_port or VRED_PORT)
    _safe = "()',:@!/"
    url = f"http://{ip}:{port}/python?value={quote(code, safe=_safe)}"
    log.info("test_vred URL: %s", url)
    def _do_request():
        with urlopen(url, timeout=10) as r:
            return r.read().decode("utf-8", errors="replace")
    try:
        body = await asyncio.get_event_loop().run_in_executor(None, _do_request)
        return {"body": body, "url": url}
    except Exception as e:
        return {"error": repr(e), "url": url}


@app.get("/variant-sets")
async def get_variant_sets(vred_ip: str = None, vred_port: int = None):
    names = await fetch_variant_sets(vred_ip, vred_port)
    return {"variant_sets": names}


async def _run_intent_pipeline(
    transcript: str,
    vred_ip: Optional[str],
    vred_port: Optional[int],
) -> VoiceCommandResponse:
    """Shared logic: parse intent from text and execute in VRED."""
    variant_sets = await fetch_variant_sets(vred_ip, vred_port)

    # 1. Try direct matching first (no LLM needed)
    direct = _direct_match(transcript, variant_sets)
    if direct:
        log.info("Direct match: %r → %r", transcript, direct)
        intent = {"action": "activate_variant", "name": direct, "confidence": 1.0, "method": "direct"}
    else:
        # 2. Fall back to LLM
        intent = await parse_intent(transcript, variant_sets)
        log.info("Intent: %s", intent)

    vred_result = None
    if intent.get("action") == "activate_variant" and intent.get("name"):
        target = intent["name"]
        if target not in variant_sets:
            lower_map = {v.lower(): v for v in variant_sets}
            target = lower_map.get(target.lower(), target)
        vred_result = await activate_variant_set(target, vred_ip, vred_port)

    return VoiceCommandResponse(transcript=transcript, intent=intent, vred_result=vred_result)


@app.post("/text-command", response_model=VoiceCommandResponse)
async def text_command(
    text: str = Form(...),
    vred_ip: Optional[str] = Form(None),
    vred_port: Optional[int] = Form(None),
):
    """Accept a plain-text command (skips ASR), parse intent, execute in VRED."""
    if not text.strip():
        return VoiceCommandResponse(
            transcript="",
            intent={"action": "none", "reason": "empty text"},
        )
    try:
        return await _run_intent_pipeline(text.strip(), vred_ip, vred_port)
    except Exception as e:
        log.exception("text_command error")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice-command", response_model=VoiceCommandResponse)
async def voice_command(
    audio: UploadFile = File(...),
    vred_ip: Optional[str] = Form(None),
    vred_port: Optional[int] = Form(None),
):
    """
    Accept an audio file (webm/opus from MediaRecorder, or wav/mp3),
    transcribe it, parse intent, and execute in VRED.
    """
    suffix = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if len(content) < 512:
            return VoiceCommandResponse(
                transcript="",
                intent={"action": "none", "reason": f"audio too short ({len(content)} bytes)"},
            )
        transcript = transcribe_audio(tmp_path)
        if not transcript:
            return VoiceCommandResponse(
                transcript="",
                intent={"action": "none", "reason": "empty transcript"},
            )
        return await _run_intent_pipeline(transcript, vred_ip, vred_port)
    except Exception as e:
        log.exception("voice_command error")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
