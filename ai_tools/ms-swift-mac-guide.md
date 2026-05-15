# ms-swift Mac 训练方案

> 环境：Apple Silicon Mac，统一内存 24GB  
> 模型：Qwen3.5-4B-Base  
> 任务：颜色值预测 LoRA 微调  
> 数据：alpaca 格式（instruction / input / output）

---

## 1. 安装环境

```bash
# 创建 conda 环境
conda create -n swift python=3.12
    conda activate swift

# 安装 ms-swift
pip install ms-swift

# 验证 MPS 可用
python -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
```

---

## 2. 准备数据

运行数据生成脚本：

```bash
cd ai_tools/datasets_transform
python csv_to_json.py
# 输出：/Users/mujunhan/Downloads/color_train_alpaca.json
```

数据为 alpaca 格式，ms-swift 原生支持，无需额外配置：

```json
[
  {
    "instruction": "Infer the HEX, RGB, Hue, Saturation and Lightness values for the given color.",
    "input": "Color Name: Sage Green\nCategory: ...",
    "output": "HEX: #8FBC8F\nRGB: 143, 188, 143\n..."
  }
]
```

---

## 3. 训练命令

```bash
conda activate swift

# PYTORCH_ENABLE_MPS_FALLBACK=1 允许不支持的算子回退到 CPU
PYTORCH_ENABLE_MPS_FALLBACK=1 swift sft \
  --model Qwen/Qwen3.5-4B-Base \
  --model_type qwen3_5 \
  --dataset /Users/mujunhan/Downloads/color_train_alpaca.json \
  --split_dataset_ratio 0.1 \
  --tuner_type lora \
  --lora_rank 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --target_modules all-linear \
  --num_train_epochs 5 \
  --learning_rate 5e-5 \
  --lr_scheduler_type cosine \
  --warmup_steps 50 \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --max_length 512 \
  --torch_dtype float16 \
  --logging_steps 5 \
  --save_steps 100 \
  --output_dir ./output/color_lora \
  --report_to none \
  --enable_thinking false
```

> **注意**：  
> - ms-swift 无 `--device` 参数，MPS 通过环境变量 `PYTORCH_ENABLE_MPS_FALLBACK=1` 启用，框架自动检测 Apple Silicon。  
> - MPS 不支持 bf16，必须使用 `float16`。  
> - 等效 batch size = `batch_size(2) × gradient_accumulation(8)` = **16**，与 LLaMA Factory 配置一致。

---

## 4. 训练步数预估

| 项目 | 数值 |
|------|------|
| 训练集样本数 | 2000 × 0.9 = 1800 条 |
| 等效 batch size | 2 × 8 = 16 |
| 每 epoch 步数 | 1800 ÷ 16 ≈ 113 步 |
| 5 epochs 总步数 | ≈ 565 步 |
| 预计耗时（24GB Mac） | 约 2~3 小时 |

---

## 5. 模型下载说明

ms-swift 默认从 ModelScope 下载，国内网络无需翻墙：

```bash
# 自动下载到 ~/.cache/modelscope/

# 若已有本地模型（如从 Windows 复制过来），使用本地路径：
swift sft --model /path/to/Qwen3.5-4B-Base ...
```

---

## 6. 推理验证

训练完成后找到最新 checkpoint 目录。

**方式一：批量推理（推荐，无 event loop 崩溃问题）**

先创建推理输入文件 `/tmp/infer_input.json`：
```json
[{"query": "Color Name: Deep Maroon\nCategory: Red Family (Ruby Red)\nEmotion: Passionate, Intense\nDescription: A vibrant and deep shade of maroon.\nKeywords: Powerful, Passionate, Bold, Deep, Strong, Intense, Maroon, Ruby Red."}]
```

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 swift infer \
  --model Qwen/Qwen3.5-4B-Base \
  --adapters /Users/mujunhan/projects/output/color_lora/checkpoint-XXX \
  --torch_dtype float16 \
  --enable_thinking false \
  --val_dataset /tmp/infer_input.json \
  --system "You are a color value prediction assistant. Output exactly 5 lines:\nHEX: #xxxxxx\nRGB: r, g, b\nHue: x.xx\nSaturation: x.xx\nLightness: x.xx"
```

**方式二：交互式（只输入一次，勿连续输入）**

```bash
PYTORCH_ENABLE_MPS_FALLBACK=1 swift infer \
  --model Qwen/Qwen3.5-4B-Base \
  --adapters /Users/mujunhan/projects/output/color_lora/checkpoint-XXX \
  --torch_dtype float16 \
  --enable_thinking false \
  --system "You are a color value prediction assistant. Output exactly 5 lines:\nHEX: #xxxxxx\nRGB: r, g, b\nHue: x.xx\nSaturation: x.xx\nLightness: x.xx"
```

> **注意**：`--query` 不是 ms-swift 的有效参数；`--stream` 在 Python 3.12 下会触发 event loop 崩溃，不要使用。

输入时使用完整字段（与训练格式一致）：

```
<<< Color Name: Deep Maroon
Category: Red Family (Ruby Red)
Emotion: Passionate, Intense
Description: A vibrant and deep shade of maroon.
Keywords: Powerful, Passionate, Bold, Deep, Strong, Intense, Maroon, Ruby Red.
```

期望输出：

```
HEX: #D62559
RGB: 214, 37, 89
Hue: 342.37
Saturation: 70.52
Lightness: 49.22
```

---

## 7. 参数对比（vs LLaMA Factory）

| 参数 | LLaMA Factory (Windows/CUDA) | ms-swift (Mac/MPS) |
|------|------------------------------|--------------------|
| compute_type | bf16 | **float16** |
| device | cuda | **mps** |
| batch_size | 2 | 2 |
| gradient_accumulation | 8 | 8 |
| 其余参数 | — | 完全一致 |

---

## 8. 常见问题

**Q: 训练中出现 OOM**  
A: 将 `--batch_size` 改为 1，`--gradient_accumulation_steps` 改为 16。

**Q: MPS 报错 `operation not supported`**  
A: 升级 PyTorch：`pip install --upgrade torch`

**Q: 训练速度慢**  
A: MPS 比 NVIDIA A100 慢约 5~10 倍，属正常现象。可先跑 1 epoch 验证效果后再决定是否完整训练。
