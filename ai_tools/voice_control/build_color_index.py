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

# 保存颜色元数据
meta = df[["Color Name", "HEX Code", "Category", "Emotion", "Mood",
           "Description", "Keywords", "R", "G", "B",
           "Hue", "Saturation", "Lightness"]].to_dict(orient="records")

with open(os.path.join(OUTPUT_DIR, "colors_meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print(f"索引已保存到：{OUTPUT_DIR}")
print(f"  embeddings.npy  shape={embeddings.shape}")
print(f"  colors_meta.json  {len(meta)} 条")
