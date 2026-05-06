"""
模型评估脚本：在测试集上评估微调后的Qwen2.5-7B模型表现
"""

import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALPACA_PROMPT_TEMPLATE = (
    "Below is an instruction that describes a task. "
    "Write a response that appropriately completes the request.\n\n"
    "### Instruction:\n{instruction}\n\n"
    "### Response:\n"
)


def load_model(model_path: str):
    logger.info(f"Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    logger.info(f"Loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
        device_map="auto",
    )

    model.eval()
    return model, tokenizer


def generate_response(
    model, tokenizer, instruction: str, max_new_tokens: int = 512
) -> str:
    prompt = ALPACA_PROMPT_TEMPLATE.format(instruction=instruction)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id,
        )

    generated = outputs[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


def compute_exact_match(pred: str, gold: str) -> float:
    return 1.0 if pred.strip() == gold.strip() else 0.0


def compute_token_overlap_f1(pred: str, gold: str) -> float:
    pred_tokens = set(pred.lower().split())
    gold_tokens = set(gold.lower().split())
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = pred_tokens & gold_tokens
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gold_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def evaluate(
    model,
    tokenizer,
    test_file: str,
    output_file: str,
    max_new_tokens: int = 512,
):
    with open(test_file, "r", encoding="utf-8") as f:
        test_data = [json.loads(l) for l in f if l.strip()]

    logger.info(f"Evaluating on {len(test_data)} samples...")

    results = []
    total_em = 0.0
    total_f1 = 0.0

    for i, item in enumerate(test_data):
        instruction = item["instruction"]
        gold = item["output"]

        pred = generate_response(model, tokenizer, instruction, max_new_tokens)

        em = compute_exact_match(pred, gold)
        f1 = compute_token_overlap_f1(pred, gold)

        total_em += em
        total_f1 += f1

        results.append({
            "id": i,
            "instruction": instruction,
            "gold": gold,
            "pred": pred,
            "exact_match": em,
            "token_f1": f1,
        })

        if (i + 1) % 10 == 0:
            logger.info(f"Progress: {i+1}/{len(test_data)}, "
                        f"avg EM={total_em/(i+1):.3f}, avg F1={total_f1/(i+1):.3f}")

    avg_em = total_em / len(test_data)
    avg_f1 = total_f1 / len(test_data)

    summary = {
        "total_samples": len(test_data),
        "avg_exact_match": avg_em,
        "avg_token_f1": avg_f1,
    }

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)

    logger.info(f"\n{'='*40}")
    logger.info(f"Evaluation Summary:")
    logger.info(f"  Total Samples: {len(test_data)}")
    logger.info(f"  Avg Exact Match: {avg_em:.4f}")
    logger.info(f"  Avg Token F1:    {avg_f1:.4f}")
    logger.info(f"Results saved to: {output_file}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="评估微调后的Qwen2.5-7B模型")
    parser.add_argument("--model_path", required=True, help="微调后的模型路径")
    parser.add_argument(
        "--test_file",
        default="data/processed/alpaca/test.jsonl",
        help="测试数据文件路径"
    )
    parser.add_argument(
        "--output_file",
        default="outputs/eval/eval_results.json",
        help="评估结果保存路径"
    )
    parser.add_argument("--max_new_tokens", type=int, default=512)
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent
    test_file = str(base_dir / args.test_file)
    output_file = str(base_dir / args.output_file)

    model, tokenizer = load_model(args.model_path)

    evaluate(model, tokenizer, test_file, output_file, args.max_new_tokens)


if __name__ == "__main__":
    main()
