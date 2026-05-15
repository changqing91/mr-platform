# ms-swift Windows 训练方案

> 系统：Windows 10/11 + NVIDIA 显卡（推荐）
> 
> 模型：Qwen3.5-4B-Base
> 
> 任务：颜色值预测 LoRA 微调
> 
> 数据格式：alpaca（instruction / input / output）

---

## 1. 环境准备

建议使用 Python 3.11（兼容性更稳）：

```powershell
conda create -n swift311 python=3.11 -y
conda activate swift311

pip install -U ms-swift
```

安装完成后检查：

```powershell
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available())"
```

如果 `cuda: True`，说明 GPU 可用。

---

## 2. 数据准备

确认训练数据为 alpaca JSON，例如：

```json
[
  {
    "instruction": "Infer the HEX, RGB, Hue, Saturation and Lightness values for the given color.",
    "input": "Color Name: Sage Green\nCategory: ...",
    "output": "HEX: #8FBC8F\nRGB: 143, 188, 143\n..."
  }
]
```

将文件放到固定路径，例如：

- `C:\\LlamaFactory\\data\\color_train_alpaca.json`

---

## 3. 训练命令（Windows CUDA）

在 PowerShell 中执行：

```powershell
swift sft ^
  --model Qwen/Qwen3.5-4B-Base ^
  --model_type qwen3_5 ^
  --dataset C:\\train\\color_train_alpaca.json ^
  --split_dataset_ratio 0.1 ^
  --tuner_type lora ^
  --lora_rank 16 ^
  --lora_alpha 32 ^
  --lora_dropout 0.05 ^
  --target_modules all-linear ^
  --num_train_epochs 5 ^
  --learning_rate 5e-5 ^
  --lr_scheduler_type cosine ^
  --warmup_steps 50 ^
  --per_device_train_batch_size 2 ^
  --gradient_accumulation_steps 8 ^
  --max_length 512 ^
  --torch_dtype bfloat16 ^
  --logging_steps 5 ^
  --save_steps 100 ^
  --output_dir C:\\color_lora ^
  --report_to none ^
  --enable_thinking false
```

说明：

- 这里使用的是 Swift 实际参数名：
  - `--split_dataset_ratio`（不是 `--dataset_test_ratio`）
  - `--tuner_type`（不是 `--train_type`）
  - `--per_device_train_batch_size`（不是 `--batch_size`）

- 若显卡不支持 bf16（如部分 30 系以前卡），把 `--torch_dtype bfloat16` 改为：
  - `--torch_dtype float16`

---

## 4. 推理验证

训练完成后，选择最新 checkpoint：

```powershell
swift infer ^
  --model Qwen/Qwen3.5-4B-Base ^
  --adapters C:\\LlamaFactory\\output\\color_lora\\checkpoint-XXX ^
  --stream true ^
  --torch_dtype bfloat16
```

若训练时使用的是 fp16，推理也改成：

```powershell
--torch_dtype float16
```

---

## 5. 2000 样本下训练规模预估

- 总样本：2000
- 训练集：2000 x 0.9 = 1800
- 等效 batch：2 x 8 = 16
- 每 epoch 步数：1800 / 16 ≈ 113
- 5 epoch 总步数：约 565

---

## 6. 常见报错与处理

1. 参数报 `ambiguous option` 或 `remaining_argv`

- 原因：使用了旧参数名。
- 处理：按本文件命令改为 `split_dataset_ratio` / `tuner_type` / `per_device_train_batch_size`。

2. 显存不足 OOM

- 把 `--per_device_train_batch_size` 改成 `1`
- 把 `--gradient_accumulation_steps` 改成 `16`（保持等效 batch 不变）

3. 数据集字段识别失败

- 确认 JSON 每条数据都包含 `instruction`、`input`、`output` 三个字段。

4. 训练很慢

- 确认 `torch.cuda.is_available()` 为 `True`。
- 若是 `False`，说明未走 GPU，需要修复 CUDA / 驱动环境。

---

## 7. 推荐版本

- Python：3.11
- ms-swift：最新版
- PyTorch：与本机 CUDA 对应版本
