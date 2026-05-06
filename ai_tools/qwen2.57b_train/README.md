# Qwen2.5-7B 爱色丽色卡色彩专家微调项目

基于 X-Rite 爱色丽色卡标准数据，对 Qwen2.5-7B-Instruct 模型进行领域微调，使模型具备专业的色彩管理和色卡知识问答能力。

## 项目结构

```
qwen2.57b_train/
├── data/
│   ├── raw/                          # 原始色卡数据
│   │   ├── xrite_colorchecker_classic.json   # ColorChecker Classic 24色
│   │   └── xrite_colorchecker_sg.json        # ColorChecker SG 140色（部分）
│   ├── processed/                    # 预处理后的训练数据
│   │   ├── alpaca/                   # Alpaca指令格式
│   │   │   ├── train.jsonl
│   │   │   ├── val.jsonl
│   │   │   └── test.jsonl
│   │   └── sharegpt/                 # ShareGPT对话格式
│   └── samples/                      # 数据样本
├── config/
│   ├── lora_train.json               # LoRA训练配置（推荐）
│   └── qlora_train.json              # QLoRA训练配置（低显存）
├── src/
│   ├── data_prepare.py               # 数据预处理脚本
│   ├── train.py                      # 模型训练脚本
│   ├── evaluate.py                   # 评估脚本
│   └── inference.py                  # 推理脚本（交互式）
├── scripts/
│   ├── run_train.sh                  # 单卡训练一键脚本
│   └── run_distributed.sh            # 多卡分布式训练脚本
├── outputs/
│   ├── checkpoints/                  # 模型检查点
│   ├── logs/                         # TensorBoard日志
│   └── eval/                         # 评估结果
└── requirements.txt
```

## 环境配置

```bash
# 建议使用 Python 3.10+，CUDA 11.8+
pip install -r requirements.txt
```

## 快速开始

### 1. 数据准备

```bash
python src/data_prepare.py
```

自动从 `data/raw/` 读取色卡数据，生成以下类型的问答对：
- 色块参数查询（Lab、RGB、HEX）
- Lab值反查色块名称
- 色差对比
- 色度学知识问答

### 2. 模型训练

**LoRA微调（推荐，需要16GB+显存）：**
```bash
bash scripts/run_train.sh
```

**QLoRA微调（12GB显存可用）：**
```bash
python src/train.py \
  --model_name_or_path Qwen/Qwen2.5-7B-Instruct \
  --use_lora \
  --load_in_4bit \
  --lora_rank 32 \
  --train_file data/processed/alpaca/train.jsonl \
  --output_dir outputs/checkpoints/qlora \
  --num_train_epochs 3 \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --learning_rate 2e-4 \
  --bf16
```

**多卡分布式训练：**
```bash
NUM_GPUS=2 bash scripts/run_distributed.sh
```

### 3. 模型评估

```bash
python src/evaluate.py \
  --model_path outputs/checkpoints/lora \
  --use_lora \
  --base_model_path Qwen/Qwen2.5-7B-Instruct \
  --test_file data/processed/alpaca/test.jsonl \
  --output_file outputs/eval/eval_results.json
```

### 4. 交互推理

```bash
# 交互式对话
python src/inference.py \
  --model_path outputs/checkpoints/lora \
  --use_lora \
  --base_model_path Qwen/Qwen2.5-7B-Instruct

# 单次推理
python src/inference.py \
  --model_path outputs/checkpoints/lora \
  --use_lora \
  --base_model_path Qwen/Qwen2.5-7B-Instruct \
  --prompt "爱色丽色卡中深肤色的Lab值是多少？"
```

## 硬件需求

| 训练方式 | 最低显存 | 推荐显存 |
|---------|---------|---------|
| LoRA（bf16） | 24GB | 40GB |
| QLoRA（4bit） | 12GB | 16GB |
| 全量微调 | 80GB | 80GB×2 |

## 数据格式

训练数据采用 Alpaca 指令格式：

```json
{
  "instruction": "请提供爱色丽色卡中"深肤色"色块的完整色彩参数。",
  "input": "",
  "output": "爱色丽ColorChecker色卡中"深肤色（Dark Skin）"的标准色彩参数如下：\n- CIE Lab值：L*=37.99, a*=13.56, b*=14.06\n- sRGB值：R=115, G=82, B=68\n- HEX色码：#735244"
}
```

## 扩展数据

如需添加更多色卡数据，在 `data/raw/` 目录下放置 JSON 文件，并在 `src/data_prepare.py` 中添加对应的加载函数。支持的色卡类型：

- X-Rite ColorChecker Classic (24色)
- X-Rite ColorChecker SG (140色)
- X-Rite ColorChecker Digital SG
- Pantone色卡（需自行收集数据）

## 参考资料

- [Qwen2.5 官方文档](https://qwen.readthedocs.io/)
- [X-Rite ColorChecker 标准参考值](https://www.xrite.com/service-support/new_standards_for_colorchecker_color_rendition_chart)
- [CIE 色差公式 ΔE2000](http://www.ece.rochester.edu/~gsharma/ciede2000/)
