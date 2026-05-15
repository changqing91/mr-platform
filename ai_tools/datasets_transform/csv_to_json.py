import pandas as pd
import json
import random
import re

def clean_color_name(name):
    name = str(name)
    # 去掉带 # 的 HEX，如 #356A40
    name = re.sub(r'\s*#[0-9A-Fa-f]{3,6}\b', '', name)
    # 去掉不带 # 的纯 HEX 颜色名（整个名称就是 HEX），如 F18D16 或 F94806 (Orange-Red)
    name = re.sub(r'^[0-9A-Fa-f]{6}\s*', '', name)
    # 去掉 "(Hex) or " 前缀
    name = re.sub(r'\s*\(Hex\)\s*or\s*', '', name)
    # 去掉任意位置的空括号 ()，如 "Dark Purple-Blue ()"
    name = re.sub(r'\s*\(\s*\)', '', name)
    # 去掉整体只剩空括号的情况
    name = re.sub(r'^\s*\(\s*\)\s*$', '', name)
    # 去掉名称开头多余的括号（如 "(Lime Green)" → "Lime Green"）
    name = re.sub(r'^\s*\((.+)\)\s*$', r'\1', name)
    return name.strip()

# ========= 配置 =========

CSV_PATH = "/Users/mujunhan/Downloads/color_pedia.csv"
OUTPUT_JSON = "/Users/mujunhan/Downloads/color_train_alpaca.json"
MAX_ROWS = 2000  # 设置为整数限制行数，例如 1000；None 表示使用全部数据

# ========= Prompt 模板（instruction, input 分离）=========
# 每个模板返回 (instruction, input) 元组

PROMPT_TEMPLATES = [
    lambda row: (
        "Infer the HEX, RGB, Hue, Saturation and Lightness values for the given color.",
        f"Color Name: {row['Color Name']}\nCategory: {row['Category']}\nEmotion: {row['Emotion']}\nDescription: {row['Description']}\nKeywords: {row['Keywords']}"
    ),

    lambda row: (
        "Given the color attributes below, provide the color space values (HEX, RGB, HSL).",
        f"Name: {row['Color Name']}\nCategory: {row['Category']}\nMood: {row['Mood']}\nPersonality: {row['Personality']}\nKeywords: {row['Keywords']}"
    ),

    lambda row: (
        "Generate the HEX, RGB, and HSL values for a color described below.",
        f"Description: {row['Description']}\nEmotion: {row['Emotion']}"
    ),

    lambda row: (
        "Infer the HEX, RGB, Hue, Saturation and Lightness values for the color described below.",
        f"Color Name: {row['Color Name']}\nCategory: {row['Category']}\nSymbolism: {row['Symbolism']}\nKeywords: {row['Keywords']}"
    ),

    lambda row: (
        "Provide the technical color values (HEX, RGB, HSL) for the following design color.",
        f"Color Name: {row['Color Name']}\nEmotion: {row['Emotion']}\nMood: {row['Mood']}\nDescription: {row['Description']}"
    ),
]

# ========= Assistant 输出模板（统一格式）=========

ANSWER_TEMPLATES = [
    lambda row: f"HEX: {row['HEX Code']}\nRGB: {row['R']}, {row['G']}, {row['B']}\nHue: {row['Hue']}\nSaturation: {row['Saturation']}\nLightness: {row['Lightness']}",
    lambda row: f"HEX: {row['HEX Code']}\nRGB: {row['R']}, {row['G']}, {row['B']}\nHue: {row['Hue']}\nSaturation: {row['Saturation']}\nLightness: {row['Lightness']}",
    lambda row: f"HEX: {row['HEX Code']}\nRGB: {row['R']}, {row['G']}, {row['B']}\nHue: {row['Hue']}\nSaturation: {row['Saturation']}\nLightness: {row['Lightness']}",
]

# ========= 读取 CSV =========

df = pd.read_csv(CSV_PATH, on_bad_lines='skip')
if MAX_ROWS is not None:
    df = df.head(MAX_ROWS)
print(f"Rows loaded: {len(df)}")

# ========= 构建 Alpaca 数据 =========

dataset = []

for i, (_, row) in enumerate(df.iterrows()):

    # 去除 NaN
    row = row.fillna("")
    row['Color Name'] = clean_color_name(row['Color Name'])

    # 跳过清洗后颜色名称为空的行
    if not row['Color Name']:
        continue

    instruction, input_text = PROMPT_TEMPLATES[i % len(PROMPT_TEMPLATES)](row)
    output = ANSWER_TEMPLATES[i % len(ANSWER_TEMPLATES)](row)

    sample = {
        "instruction": instruction,
        "input": input_text,
        "output": output
    }

    dataset.append(sample)

# ========= 保存 JSON =========

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(dataset, f, ensure_ascii=False, separators=(',', ':'))

print(f"Done!")
print(f"Generated samples: {len(dataset)}")
print(f"Saved to: {OUTPUT_JSON}")