@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM Qwen2.5-7B 全量微调脚本 - RTX 6000 Ada (48GB)
REM ============================================================

set PROJECT_DIR=%~dp0..
cd /d "%PROJECT_DIR%"

REM ---- 本地模型路径（请修改为实际路径）----
set MODEL_PATH=C:\models\Qwen2.5-7B-Instruct

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 python，请确认已激活 conda/venv 环境。
    pause & exit /b 1
)

echo ============================================================
echo  RTX 6000 Ada - Qwen2.5-7B Full Fine-tuning
echo ============================================================

echo.
echo [Step 1] 数据预处理...
python src\data_prepare.py
if %errorlevel% neq 0 ( echo [ERROR] 数据预处理失败。 & pause & exit /b 1 )

echo.
echo [Step 2] 全量微调训练...
python src\train.py --model_name_or_path "%MODEL_PATH%" --train_file data/processed/alpaca/train.jsonl --val_file data/processed/alpaca/val.jsonl --max_seq_length 2048 --data_format alpaca --output_dir outputs/checkpoints/full_finetune --num_train_epochs 3 --per_device_train_batch_size 2 --per_device_eval_batch_size 2 --gradient_accumulation_steps 8 --learning_rate 2e-5 --lr_scheduler_type cosine --warmup_ratio 0.03 --weight_decay 0.01 --max_grad_norm 1.0 --logging_steps 10 --save_steps 100 --eval_steps 100 --evaluation_strategy steps --save_total_limit 3 --load_best_model_at_end --metric_for_best_model eval_loss --bf16 --tf32 True --gradient_checkpointing True --optim adamw_bnb_8bit --dataloader_num_workers 4 --dataloader_pin_memory True --report_to tensorboard --logging_dir outputs/logs/full_finetune --seed 42 --remove_unused_columns False
if %errorlevel% neq 0 ( echo [ERROR] 训练失败。 & pause & exit /b 1 )

echo.
echo [Step 3] 模型评估...
python src\evaluate.py --model_path outputs/checkpoints/full_finetune --test_file data/processed/alpaca/test.jsonl --output_file outputs/eval/eval_results.json --max_new_tokens 512

echo.
echo ============================================================
echo  训练完成！
echo  TensorBoard: tensorboard --logdir outputs/logs/full_finetune
echo ============================================================
pause
