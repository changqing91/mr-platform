"""
颜色语义检索服务
输入：自然语言描述（中文/英文）
输出：匹配的 HEX 颜色列表，按相似度排序

流程：
  query → LLM 扩展（中文/场景词 → 英文颜色关键词）
        → Embedding 检索（过采样 top_k×5）
        → HSL 色相一致性重排
        → top_k 结果

依赖：pip install sentence-transformers numpy python-dotenv
用法：
    from color_search import ColorSearcher
    searcher = ColorSearcher()
    results = searcher.search("冰川", top_k=6)
"""

import os
import json
import math
import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_DIR = os.path.join(os.path.dirname(__file__), "color_index")
MODEL_NAME = "BAAI/bge-m3"

# ── LLM 配置（从 .env 读取，与 server.py 保持一致）────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

_LLM_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
_LLM_MODEL    = os.getenv("LMSTUDIO_MODEL", "qwen3.5-9b")
_LLM_API_KEY  = os.getenv("LMSTUDIO_API_KEY", "lm-studio")
_LLM_TIMEOUT  = float(os.getenv("LMSTUDIO_TIMEOUT", "15"))

# query 扩展 system prompt
_LLM_SYSTEM = (
    "You are a color search assistant. "
    "Translate the user's input into a concise English color attribute description for semantic search. "
    "Include relevant terms from: hue direction (e.g. blue, red, purple-red, cyan, teal, green, "
    "orange, yellow, violet), lightness (very dark / dark / medium / light / very light), "
    "saturation (highly saturated / moderately saturated / low saturation / vivid / muted), "
    "and mood/scene keywords. "
    "Output ONE plain English line only. No JSON, no markdown, no explanation.\n"
    "Examples:\n"
    "冰川 → icy pale cyan light blue arctic cold clear crisp very light low saturation\n"
    "深红色 热情 奢华 → deep dark purple-red hue highly saturated passionate dramatic luxurious intense maroon\n"
    "秋天温暖 → warm orange golden amber autumn earthy medium lightness moderately saturated\n"
    "大海 → deep ocean blue teal cyan highly saturated medium dark\n"
    "高端商务 → dark navy charcoal grey sophisticated neutral low saturation\n"
    "Teal Green → teal green cyan moderately saturated medium lightness calm fresh"
)


def _llm_expand_query(query: str) -> str:
    """
    用 LLM 将自然语言 query 扩展为英文颜色关键词描述。
    失败/超时时静默降级，返回原始 query。
    """
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "model": _LLM_MODEL,
        "messages": [
            {"role": "system", "content": _LLM_SYSTEM},
            {"role": "user",   "content": query},
        ],
        "max_tokens": 80,
        "temperature": 0.2,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        f"{_LLM_BASE_URL}/chat/completions",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {_LLM_API_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        expanded = data["choices"][0]["message"]["content"].strip()
        # 有些模型输出 <think>...</think> 思维链，剥离掉
        if "<think>" in expanded:
            expanded = expanded.split("</think>")[-1].strip()
        return expanded if expanded else query
    except Exception:
        return query


# ── HSL 工具函数 ───────────────────────────────────────────────────────────────

def _hue_diff(h1: float, h2: float) -> float:
    """两个色相值的最小角度差（结果 0~180）"""
    diff = abs(h1 - h2) % 360
    return min(diff, 360 - diff)


def _circular_mean(hues: list) -> float:
    """色相环形均值（处理 0°/360° 环绕）"""
    sin_sum = sum(math.sin(math.radians(h)) for h in hues)
    cos_sum = sum(math.cos(math.radians(h)) for h in hues)
    return math.degrees(math.atan2(sin_sum, cos_sum)) % 360


class ColorSearcher:
    def __init__(self, index_dir: str = INDEX_DIR, model_name: str = MODEL_NAME,
                 llm_expand: bool = True):
        """
        Args:
            index_dir:   颜色索引目录
            model_name:  Embedding 模型名称
            llm_expand:  是否默认启用 LLM 查询扩展
        """
        print(f"加载 Embedding 模型：{model_name}")
        self.model = SentenceTransformer(model_name)
        self.llm_expand = llm_expand

        emb_path  = os.path.join(index_dir, "embeddings.npy")
        meta_path = os.path.join(index_dir, "colors_meta.json")

        if not os.path.exists(emb_path) or not os.path.exists(meta_path):
            raise FileNotFoundError(
                f"索引文件不存在，请先运行 build_color_index.py\n缺失路径：{index_dir}"
            )

        self.embeddings = np.load(emb_path).astype(np.float32)  # [N, D]
        with open(meta_path, encoding="utf-8") as f:
            self.meta = json.load(f)

        print(f"颜色库已加载：{len(self.meta)} 种颜色")

    def search(self, query: str, top_k: int = 6, use_llm: bool = True) -> list[dict]:
        """
        根据自然语言描述检索最匹配的颜色。

        Args:
            query:    自然语言描述，如 "冰川" 或 "calm ocean blue"
            top_k:    返回颜色数量
            use_llm:  是否启用 LLM 查询扩展（默认跟随实例的 llm_expand 设置）

        Returns:
            list of dict，每个 dict 包含：
                hex, name, score, category, emotion, mood,
                description, keywords, rgb, expanded_query
        """
        do_expand = self.llm_expand if use_llm is None else use_llm

        if do_expand:
            expanded = _llm_expand_query(query)
            # 原始 query + 扩展结果拼接，保留原始语义同时加入颜色方向
            search_text = f"{query} {expanded}" if expanded != query else query
        else:
            expanded = query
            search_text = query

        # 向量化
        q_emb = self.model.encode([search_text], normalize_embeddings=True).astype(np.float32)

        # 余弦相似度（已 normalize，直接点积）
        scores = (self.embeddings @ q_emb.T).flatten()

        # 过采样：取 top_k×5 候选，再做 HSL 重排
        oversample_k = min(top_k * 5, len(self.meta))
        top_indices = np.argsort(scores)[::-1][:oversample_k]
        candidates = [(int(idx), float(scores[idx])) for idx in top_indices]

        # HSL 色相一致性重排
        candidates = self._hsl_rerank(candidates, top_k)

        results = []
        for idx, score in candidates:
            color = self.meta[idx]
            results.append({
                "hex":            color["HEX Code"],
                "name":           color["Color Name"],
                "score":          score,
                "category":       color.get("Category", ""),
                "emotion":        color.get("Emotion", ""),
                "mood":           color.get("Mood", ""),
                "description":    color.get("Description", ""),
                "keywords":       color.get("Keywords", ""),
                "rgb":            (int(color.get("R", 0)),
                                   int(color.get("G", 0)),
                                   int(color.get("B", 0))),
                "expanded_query": expanded if (do_expand and expanded != query) else None,
            })

        return results

    def _hsl_rerank(self, candidates: list, top_k: int) -> list:
        """
        对过采样候选集做 HSL 色相一致性重排。

        策略：取分数最高的前 top_k//2 候选的 Hue 环形均值作为参考色相，
        给与参考色相接近的候选按距离加分（±30° 内 +5%，±60° 内 +2.5%）。
        若所有候选无 Hue 数据，退化为纯向量排名。
        """
        if len(candidates) <= top_k:
            return candidates[:top_k]

        ref_count = max(2, top_k // 2)
        ref_hues = []
        for idx, _ in candidates[:ref_count]:
            h = self.meta[idx].get("Hue")
            if h is not None and str(h).strip():
                try:
                    ref_hues.append(float(h))
                except ValueError:
                    pass

        if not ref_hues:
            return candidates[:top_k]

        ref_hue = _circular_mean(ref_hues)

        reranked = []
        for idx, score in candidates:
            h = self.meta[idx].get("Hue")
            if h is not None and str(h).strip():
                try:
                    diff = _hue_diff(float(h), ref_hue)
                    if diff <= 30:
                        score *= 1.05
                    elif diff <= 60:
                        score *= 1.025
                except ValueError:
                    pass
            reranked.append((idx, score))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked[:top_k]

    def search_hex_list(self, query: str, top_k: int = 6) -> list[str]:
        """只返回 HEX 列表，适合直接传给 MR 场景。"""
        return [r["hex"] for r in self.search(query, top_k=top_k)]


# ========= 命令行快速测试 =========
if __name__ == "__main__":
    import sys

    searcher = ColorSearcher()

    queries = sys.argv[1:] if len(sys.argv) > 1 else [
        "冰川",
        "橙子的颜色",
        "热烈的红色",
        "宁静的颜色",
        "大海的蓝色",
        "秋天的感觉",
        "高端商务风格",
        "Pastel, Yellow A bright yet soft shade of yellow. Playful, vibrant, cheerful. Friendly, sunny, optimistic. Sunny, energetic, inviting. It may symbolize warmth, sunshine, happiness, and freshness. Ideal for creating a cheerful, lively atmosphere in designs such as children's products, outdoor brands, or summer-themed designs. Bright, pastel, yellow, playful, vibrant, sunny, fresh, energetic, optimistic, summer, cheerful.",
        "深红色、热情、戏剧性、优雅、奢华、浓烈",
    ]

    for q in queries:
        print(f"\n{'='*50}")
        print(f"查询：{q}")
        results = searcher.search(q, top_k=5)
        if results and results[0]["expanded_query"]:
            print(f"LLM 扩展：{results[0]['expanded_query']}")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['hex']}  {r['name']}  (score={r['score']:.3f})")
            print(f"     {r['emotion']} / {r['mood']}")
