#!/usr/bin/env bash
# 一键运行训练流程（LoRA模式）
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Step 1: 数据预处理 ==="
cd "$PROJECT_DIR"
python src/data_prepare.py

echo ""
echo "=== Step 2: 模型训练（LoRA）==="
python src/train.py \
  --model_name_or_path "Qwen/Qwen2.5-7B-Instruct" \
  --use_lora \
  --lora_rank 64 \
  --lora_alpha 128 \
  --lora_dropout 0.05 \
  --train_file "data/processed/alpaca/train.jsonl" \
  --val_file "data/processed/alpaca/val.jsonl" \
  --max_seq_length 2048 \
  --data_format alpaca \
  --output_dir "outputs/checkpoints/lora" \
  --num_train_epochs 3 \
  --per_device_train_batch_size 4 \
  --gradient_accumulation_steps 4 \
  --learning_rate 2e-4 \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.05 \
  --weight_decay 0.01 \
  --logging_steps 10 \
  --save_steps 100 \
  --eval_steps 100 \
  --evaluation_strategy steps \
  --save_total_limit 3 \
  --load_best_model_at_end \
  --bf16 \
  --report_to tensorboard \
  --logging_dir "outputs/logs/lora" \
  --seed 42 \
  --remove_unused_columns False

echo ""
echo "=== Step 3: 评估 ==="
python src/evaluate.py \
  --model_path "outputs/checkpoints/lora" \
  --use_lora \
  --base_model_path "Qwen/Qwen2.5-7B-Instruct" \
  --test_file "data/processed/alpaca/test.jsonl" \
  --output_file "outputs/eval/eval_results.json"

echo ""
echo "=== 训练完成！==="
