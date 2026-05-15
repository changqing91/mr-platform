"""
颜色语义检索服务
输入：自然语言描述（中文/英文）
输出：匹配的 HEX 颜色列表，按相似度排序

依赖：pip install sentence-transformers faiss-cpu numpy
用法：
    from color_search import ColorSearcher
    searcher = ColorSearcher()
    results = searcher.search("热烈的红色", top_k=6)
"""

import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_DIR = os.path.join(os.path.dirname(__file__), "color_index")
MODEL_NAME = "BAAI/bge-m3"


class ColorSearcher:
    def __init__(self, index_dir: str = INDEX_DIR, model_name: str = MODEL_NAME):
        print(f"加载 Embedding 模型：{model_name}")
        self.model = SentenceTransformer(model_name)

        emb_path = os.path.join(index_dir, "embeddings.npy")
        meta_path = os.path.join(index_dir, "colors_meta.json")

        if not os.path.exists(emb_path) or not os.path.exists(meta_path):
            raise FileNotFoundError(
                f"索引文件不存在，请先运行 build_color_index.py\n缺失路径：{index_dir}"
            )

        self.embeddings = np.load(emb_path).astype(np.float32)   # [N, D]
        with open(meta_path, encoding="utf-8") as f:
            self.meta = json.load(f)

        print(f"颜色库已加载：{len(self.meta)} 种颜色")

    def search(self, query: str, top_k: int = 6) -> list[dict]:
        """
        根据自然语言描述检索最匹配的颜色。

        Args:
            query:  自然语言描述，如 "热烈的红色" 或 "calm ocean blue"
            top_k:  返回颜色数量

        Returns:
            list of dict，每个 dict 包含：
                hex:        HEX 代码（如 #D62559）
                name:       颜色名称
                score:      余弦相似度（0~1，越高越匹配）
                category:   颜色分类
                emotion:    情绪
                mood:       心情
                description: 描述
        """
        # 查询向量化
        q_emb = self.model.encode([query], normalize_embeddings=True).astype(np.float32)

        # 余弦相似度（已 normalize，直接点积）
        scores = (self.embeddings @ q_emb.T).flatten()

        # Top-K
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            color = self.meta[idx]
            results.append({
                "hex": color["HEX Code"],
                "name": color["Color Name"],
                "score": float(scores[idx]),
                "category": color.get("Category", ""),
                "emotion": color.get("Emotion", ""),
                "mood": color.get("Mood", ""),
                "description": color.get("Description", ""),
                "rgb": (int(color.get("R", 0)),
                        int(color.get("G", 0)),
                        int(color.get("B", 0))),
            })

        return results

    def search_hex_list(self, query: str, top_k: int = 6) -> list[str]:
        """只返回 HEX 列表，适合直接传给 MR 场景。"""
        results = self.search(query, top_k=top_k)
        return [r["hex"] for r in results]


# ========= 命令行快速测试 =========
if __name__ == "__main__":
    import sys

    searcher = ColorSearcher()

    queries = sys.argv[1:] if len(sys.argv) > 1 else [
        "热烈的红色",
        "宁静的颜色",
        "青米色",
        "大海的蓝色",
        "秋天的感觉",
        "高端商务风格",
    ]

    for q in queries:
        print(f"\n{'='*50}")
        print(f"查询：{q}")
        results = searcher.search(q, top_k=5)
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['hex']}  {r['name']}  (score={r['score']:.3f})")
            print(f"     {r['emotion']} / {r['mood']}")
