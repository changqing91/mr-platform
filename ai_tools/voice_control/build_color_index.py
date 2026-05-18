"""
颜色向量库构建脚本
将 color_pedia.csv 中每种颜色的语义信息向量化，存储为本地索引。
依赖：pip install sentence-transformers faiss-cpu pandas numpy
"""

import os
import json
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

# ========= 配置 =========
CSV_PATH = "/Users/mujunhan/Downloads/color_pedia.csv"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "color_index")
MODEL_NAME = "BAAI/bge-m3"   # 中英文双语，适合语义检索

# ========= 读取数据 =========
df = pd.read_csv(CSV_PATH, on_bad_lines="skip")
df = df.fillna("")

# 去重：同一 HEX Code 只保留第一条
df = df.drop_duplicates(subset=["HEX Code"])
df = df.reset_index(drop=True)

print(f"载入颜色数量：{len(df)}")

# ========= 构建语义文本 =========
# 把颜色的多维属性拼成一段语义丰富的描述，用于 Embedding

def _hue_label(h: float) -> str:
    if h < 15 or h >= 345:  return "pure red hue"
    elif h < 45:            return "orange-red hue"
    elif h < 75:            return "orange hue"
    elif h < 105:           return "yellow hue"
    elif h < 150:           return "green hue"
    elif h < 195:           return "cyan hue"
    elif h < 255:           return "blue hue"
    elif h < 285:           return "blue-purple hue"
    else:                   return "purple-red hue"

def _sat_label(s: float) -> str:
    if s > 70:   return "highly saturated"
    elif s > 40: return "moderately saturated"
    else:        return "low saturation"

def _light_label(l: float) -> str:
    if l < 20:   return "very dark"
    elif l < 35: return "dark"
    elif l < 55: return "medium lightness"
    elif l < 75: return "light"
    else:        return "very light"

def build_semantic_text(row):
    parts = []
    if row["Color Name"]:
        parts.append(f"Color: {row['Color Name']}")
    if row["Category"]:
        parts.append(f"Category: {row['Category']}")
    if row["Description"]:
        parts.append(f"Description: {row['Description']}")
    if row["Emotion"]:
        parts.append(f"Emotion: {row['Emotion']}")
    if row["Mood"]:
        parts.append(f"Mood: {row['Mood']}")
    if row["Personality"]:
        parts.append(f"Personality: {row['Personality']}")
    if row["Symbolism"]:
        parts.append(f"Symbolism: {row['Symbolism']}")
    if row["Use Case"]:
        parts.append(f"Use Case: {row['Use Case']}")
    if row["Keywords"]:
        parts.append(f"Keywords: {row['Keywords']}")
    # HSL 文字描述：让同情绪/同分类但色相不同的颜色在向量空间中区分开
    try:
        h = float(row["Hue"]) if str(row["Hue"]).strip() else None
        s = float(row["Saturation"]) if str(row["Saturation"]).strip() else None
        l = float(row["Lightness"]) if str(row["Lightness"]).strip() else None
        if h is not None:
            parts.append(f"Hue: {_hue_label(h)}")
        if s is not None:
            parts.append(f"Saturation: {_sat_label(s)}")
        if l is not None:
            parts.append(f"Lightness: {_light_label(l)}")
    except (ValueError, TypeError):
        pass
    return ". ".join(parts)

df["semantic_text"] = df.apply(build_semantic_text, axis=1)

# ========= 向量化 =========
print(f"加载 Embedding 模型：{MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME)

print("向量化中...")
texts = df["semantic_text"].tolist()
embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

# ========= 保存索引 =========
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 保存向量
np.save(os.path.join(OUTPUT_DIR, "embeddings.npy"), embeddings.astype(np.float32))

# 保存颜色元数据（含 Personality / Symbolism / Use Case 供调试用）
extra_cols = [c for c in ["Personality", "Symbolism", "Use Case"] if c in df.columns]
meta_cols = ["Color Name", "HEX Code", "Category", "Emotion", "Mood",
             "Description", "Keywords", "R", "G", "B",
             "Hue", "Saturation", "Lightness"] + extra_cols
meta = df[meta_cols].to_dict(orient="records")

with open(os.path.join(OUTPUT_DIR, "colors_meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print(f"索引已保存到：{OUTPUT_DIR}")
print(f"  embeddings.npy  shape={embeddings.shape}")
print(f"  colors_meta.json  {len(meta)} 条")
