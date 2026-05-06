"""
Qwen2.5-7B 全量微调（Full Fine-tuning）训练脚本
针对 RTX 6000 Ada (48GB) 优化：梯度检查点 + 8-bit AdamW 优化器
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
    HfArgumentParser,
    set_seed,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALPACA_PROMPT_TEMPLATE = (
    "Below is an instruction that describes a task. "
    "Write a response that appropriately completes the request.\n\n"
    "### Instruction:\n{instruction}\n\n"
    "{input_section}"
    "### Response:\n"
)


@dataclass
class ModelArguments:
    model_name_or_path: str = field(
        default="Qwen/Qwen2.5-7B-Instruct",
        metadata={"help": "模型路径或HuggingFace模型ID"}
    )


@dataclass
class DataArguments:
    train_file: str = field(
        default="data/processed/alpaca/train.jsonl",
        metadata={"help": "训练数据文件路径（JSONL，Alpaca格式）"}
    )
    val_file: Optional[str] = field(
        default="data/processed/alpaca/val.jsonl",
        metadata={"help": "验证数据文件路径"}
    )
    max_seq_length: int = field(default=2048, metadata={"help": "最大序列长度"})
    data_format: str = field(
        default="alpaca",
        metadata={"help": "数据格式：alpaca 或 sharegpt"}
    )


class AlpacaDataset(Dataset):
    def __init__(self, data_path: str, tokenizer, max_length: int = 2048):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.data = []
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.data.append(json.loads(line))
        logger.info(f"Loaded {len(self.data)} samples from {data_path}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        instruction = item["instruction"]
        input_text = item.get("input", "")
        output = item["output"]

        input_section = f"### Input:\n{input_text}\n\n" if input_text else ""
        prompt = ALPACA_PROMPT_TEMPLATE.format(
            instruction=instruction,
            input_section=input_section
        )
        full_text = prompt + output + self.tokenizer.eos_token

        tokenized = self.tokenizer(
            full_text,
            max_length=self.max_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )

        # 只对response部分计算loss
        prompt_tokenized = self.tokenizer(
            prompt,
            max_length=self.max_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )
        prompt_len = len(prompt_tokenized["input_ids"])

        labels = [-100] * prompt_len + tokenized["input_ids"][prompt_len:]
        tokenized["labels"] = labels

        return tokenized


class ShareGPTDataset(Dataset):
    def __init__(self, data_path: str, tokenizer, max_length: int = 2048):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.data = []
        with open(data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.data.append(json.loads(line))
        logger.info(f"Loaded {len(self.data)} samples from {data_path}")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        conversations = item["conversations"]

        messages = []
        for conv in conversations:
            role = "user" if conv["from"] == "human" else "assistant"
            messages.append({"role": role, "content": conv["value"]})

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        tokenized = self.tokenizer(
            text,
            max_length=self.max_length,
            truncation=True,
            padding=False,
            return_tensors=None,
        )

        # 屏蔽user部分的loss
        labels = list(tokenized["input_ids"])
        in_assistant = False
        assistant_token = self.tokenizer.encode("<|im_start|>assistant", add_special_tokens=False)

        i = 0
        while i < len(labels):
            if labels[i:i+len(assistant_token)] == assistant_token:
                in_assistant = True
                i += len(assistant_token)
                continue
            if not in_assistant:
                labels[i] = -100
            i += 1

        tokenized["labels"] = labels
        return tokenized


def load_model_and_tokenizer(model_args: ModelArguments):
    logger.info(f"Loading tokenizer from {model_args.model_name_or_path}")
    tokenizer = AutoTokenizer.from_pretrained(
        model_args.model_name_or_path,
        trust_remote_code=True,
        padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    logger.info(f"Loading model from {model_args.model_name_or_path}")
    model = AutoModelForCausalLM.from_pretrained(
        model_args.model_name_or_path,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )

    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Total parameters: {total_params / 1e9:.2f}B (all trainable)")

    return model, tokenizer


def main():
    parser = HfArgumentParser((ModelArguments, DataArguments, TrainingArguments))
    model_args, data_args, training_args = parser.parse_args_into_dataclasses()

    set_seed(training_args.seed)

    model, tokenizer = load_model_and_tokenizer(model_args)

    base_dir = Path(__file__).parent.parent

    DatasetClass = AlpacaDataset if data_args.data_format == "alpaca" else ShareGPTDataset

    train_dataset = DatasetClass(
        str(base_dir / data_args.train_file),
        tokenizer,
        data_args.max_seq_length,
    )

    eval_dataset = None
    if data_args.val_file and os.path.exists(str(base_dir / data_args.val_file)):
        eval_dataset = DatasetClass(
            str(base_dir / data_args.val_file),
            tokenizer,
            data_args.max_seq_length,
        )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding=True,
        pad_to_multiple_of=8,
        label_pad_token_id=-100,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        tokenizer=tokenizer,
    )

    logger.info("Starting training...")
    trainer.train()

    logger.info("Saving model...")
    trainer.save_model()
    tokenizer.save_pretrained(training_args.output_dir)
    logger.info(f"Model saved to {training_args.output_dir}")


if __name__ == "__main__":
    main()
