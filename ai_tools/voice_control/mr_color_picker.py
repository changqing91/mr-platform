"""
MR 改色工具 - 语音对话流程演示
输入：自然语言（模拟语音 ASR 结果）
输出：HEX 颜色列表

完整流程：
  语音输入 → ASR → 文本 → ColorSearcher → HEX 列表 → MR 场景改色

依赖：pip install sentence-transformers faiss-cpu
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from color_search import ColorSearcher


def mr_color_picker(query: str, top_k: int = 6, use_llm: bool = None) -> list[str]:
    """
    MR 改色工具主入口。
    Args:
        query:    用户语音识别结果（自然语言）
        top_k:    返回颜色数量
        use_llm:  是否启用 LLM 查询扩展（默认跟随 ColorSearcher 实例设置）
    Returns:
        HEX 颜色列表，如 ['#D62559', '#FF4500', ...]
    """
    searcher = mr_color_picker._searcher
    results = searcher.search(query, top_k=top_k, use_llm=use_llm)

    print(f'\n[MR 改色] 用户说："{query}"')
    if results and results[0].get("expanded_query"):
        print(f"[LLM 扩展] {results[0]['expanded_query']}")
    print(f"推荐颜色（{len(results)} 个）：")
    hex_list = []
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['hex']}  {r['name']}")
        print(f"     情绪：{r['emotion']}  心情：{r['mood']}")
        hex_list.append(r["hex"])

    return hex_list


# 单例搜索器（避免重复加载模型）
mr_color_picker._searcher = None


def init(index_dir=None, llm_expand: bool = True):
    """初始化（首次调用时加载模型，约 10~30 秒）"""
    from color_search import ColorSearcher, INDEX_DIR
    mr_color_picker._searcher = ColorSearcher(
        index_dir=index_dir or INDEX_DIR,
        llm_expand=llm_expand,
    )


# ========= 演示 =========
if __name__ == "__main__":
    print("初始化颜色检索引擎...")
    init()

    # 模拟语音输入
    test_queries = [
        "热烈的红色",
        "宁静的颜色",
        "青米色",
        "大海的蓝色",
        "秋天温暖的感觉",
        "高端商务风格",
        "充满活力的颜色",
        "calm and peaceful",
        "Teal Green",
        "A vibrant yet serene light blue color."
    ]

    for q in test_queries:
        hex_list = mr_color_picker(q, top_k=5)
        print(f"  → HEX list: {hex_list}\n")

    # 交互式测试
    print("\n" + "="*50)
    print("交互式测试（输入 q 退出）")
    while True:
        user_input = input("\n请描述颜色需求（语音 ASR 结果）：").strip()
        if user_input.lower() in ("q", "quit", "exit", ""):
            break
        hex_list = mr_color_picker(user_input, top_k=50)
        print(f"返回 HEX 列表：{hex_list}")
