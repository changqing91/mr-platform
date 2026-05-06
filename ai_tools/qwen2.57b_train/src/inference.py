"""
推理脚本：使用微调后的Qwen2.5-7B模型进行色彩知识问答
"""

import argparse
import logging
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位专业的色彩管理专家，精通爱色丽（X-Rite）色卡体系、CIE色彩科学和色彩管理工作流程。"
    "请根据用户的问题提供准确、专业的色彩知识解答。"
)

ALPACA_TEMPLATE = (
    "Below is an instruction that describes a task. "
    "Write a response that appropriately completes the request.\n\n"
    "### Instruction:\n{instruction}\n\n"
    "### Response:\n"
)


class ColorExpert:
    def __init__(self, model_path: str, use_chat_template: bool = True):
        self.use_chat_template = use_chat_template

        logger.info("Loading tokenizer...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        logger.info("Loading model...")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
            device_map="auto",
        )

        self.model.eval()
        logger.info("Model ready.")

    def chat(
        self,
        user_message: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        use_sampling: bool = True,
    ) -> str:
        if self.use_chat_template:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ]
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            text = ALPACA_TEMPLATE.format(instruction=user_message)

        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=use_sampling,
                temperature=temperature if use_sampling else 1.0,
                top_p=top_p if use_sampling else 1.0,
                repetition_penalty=1.1,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(generated_ids, skip_special_tokens=True).strip()


def interactive_mode(expert: ColorExpert):
    print("\n" + "="*60)
    print("爱色丽色彩专家助手 (输入 'quit' 或 'exit' 退出)")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("您的问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n退出。")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "退出"):
            print("退出。")
            break

        response = expert.chat(user_input)
        print(f"\n助手: {response}\n")
        print("-" * 40)


def main():
    parser = argparse.ArgumentParser(description="Qwen2.5-7B 色彩专家推理")
    parser.add_argument("--model_path", required=True, help="模型路径")
    parser.add_argument("--no_chat_template", action="store_true",
                        help="使用Alpaca格式而非chat template")
    parser.add_argument("--prompt", default=None, help="单次推理的问题（不填则进入交互模式）")
    parser.add_argument("--max_new_tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--no_sampling", action="store_true", help="使用贪婪解码")
    args = parser.parse_args()

    expert = ColorExpert(
        model_path=args.model_path,
        use_chat_template=not args.no_chat_template,
    )

    if args.prompt:
        response = expert.chat(
            args.prompt,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            use_sampling=not args.no_sampling,
        )
        print(f"\n问题: {args.prompt}")
        print(f"\n回答: {response}")
    else:
        interactive_mode(expert)


if __name__ == "__main__":
    main()
