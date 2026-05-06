#!/usr/bin/env bash
# 多卡分布式训练脚本（使用 torchrun）
set -e

NUM_GPUS=${NUM_GPUS:-2}
MASTER_PORT=${MASTER_PORT:-29500}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== Step 1: 数据预处理 ==="
python src/data_prepare.py

echo ""
echo "=== Step 2: 分布式训练（${NUM_GPUS}卡）==="
torchrun \
  --nproc_per_node=$NUM_GPUS \
  --master_port=$MASTER_PORT \
  src/train.py \
  --model_name_or_path "Qwen/Qwen2.5-7B-Instruct" \
  --use_lora \
  --lora_rank 64 \
  --lora_alpha 128 \
  --train_file "data/processed/alpaca/train.jsonl" \
  --val_file "data/processed/alpaca/val.jsonl" \
  --max_seq_length 2048 \
  --output_dir "outputs/checkpoints/lora_distributed" \
  --num_train_epochs 3 \
  --per_device_train_batch_size 4 \
  --gradient_accumulation_steps 2 \
  --learning_rate 2e-4 \
  --bf16 \
  --report_to tensorboard \
  --logging_dir "outputs/logs/lora_distributed" \
  --ddp_find_unused_parameters False \
  --seed 42 \
  --remove_unused_columns False

echo ""
echo "=== 分布式训练完成！==="
