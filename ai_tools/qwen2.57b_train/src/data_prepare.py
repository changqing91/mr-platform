"""
爱色丽色卡数据预处理脚本
将原始色卡JSON数据转换为Qwen2.5-7B微调所需的指令-响应格式
"""

import json
import os
import random
import math
from pathlib import Path
from typing import List, Dict, Any


RAW_DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
SAMPLES_DATA_DIR = Path(__file__).parent.parent / "data" / "samples"


def lab_to_str(lab: Dict) -> str:
    return f"L*={lab['L']:.2f}, a*={lab['a']:.2f}, b*={lab['b']:.2f}"


def rgb_to_str(rgb: Dict) -> str:
    return f"R={rgb['R']}, G={rgb['G']}, B={rgb['B']}"


def delta_e_2000_approx(lab1: Dict, lab2: Dict) -> float:
    """简化版ΔE2000计算（用于数据增强）"""
    dL = lab1["L"] - lab2["L"]
    da = lab1["a"] - lab2["a"]
    db = lab1["b"] - lab2["b"]
    return math.sqrt(dL**2 + da**2 + db**2)


def load_colorchecker_classic() -> List[Dict]:
    path = RAW_DATA_DIR / "xrite_colorchecker_classic.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_colorchecker_sg() -> List[Dict]:
    path = RAW_DATA_DIR / "xrite_colorchecker_sg.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    patches = []
    for chart in data:
        patches.extend(chart.get("patches", []))
    return patches


def build_qa_pairs(patches: List[Dict]) -> List[Dict[str, str]]:
    """为每个色块生成多种问答对"""
    qa_pairs = []

    for patch in patches:
        name_en = patch.get("name", "")
        name_zh = patch.get("name_zh", name_en)
        lab = patch.get("Lab", {})
        rgb = patch.get("RGB_sRGB", {})
        hex_code = patch.get("hex", "")
        category = patch.get("category", "")
        description = patch.get("description", "")

        if not lab or not rgb:
            continue

        lab_str = lab_to_str(lab)
        rgb_str = rgb_to_str(rgb)

        # QA 1: 给定色块名称，查询其色彩参数
        qa_pairs.append({
            "instruction": f"请提供爱色丽色卡中"{name_zh}（{name_en}）"色块的完整色彩参数。",
            "input": "",
            "output": (
                f"爱色丽ColorChecker色卡中"{name_zh}（{name_en}）"的标准色彩参数如下：\n"
                f"- CIE Lab值：{lab_str}\n"
                f"- sRGB值：{rgb_str}\n"
                + (f"- HEX色码：{hex_code}\n" if hex_code else "")
                + f"- 色彩类别：{category}\n"
                + (f"- 描述：{description}" if description else "")
            )
        })

        # QA 2: 给定Lab值，反查色块名称
        qa_pairs.append({
            "instruction": f"爱色丽色卡中Lab值为（{lab_str}）的色块是哪个？请说明其色彩特征。",
            "input": "",
            "output": (
                f"该Lab值对应的是爱色丽ColorChecker色卡中的"{name_zh}（{name_en}）"色块。\n"
                f"该色块属于{category}类别，sRGB值为{rgb_str}。"
                + (f"\n描述：{description}" if description else "")
            )
        })

        # QA 3: RGB转换说明
        qa_pairs.append({
            "instruction": f"爱色丽色卡"{name_zh}"的sRGB值是多少？如何将其转换为HEX色码？",
            "input": "",
            "output": (
                f"爱色丽色卡"{name_zh}（{name_en}）"的sRGB值为：{rgb_str}。\n"
                f"转换为HEX色码的方法：将R、G、B各分量转换为两位十六进制数拼接，"
                f"结果为 {hex_code if hex_code else '#{:02X}{:02X}{:02X}'.format(rgb['R'], rgb['G'], rgb['B'])}。"
            )
        })

        # QA 4: 色彩感知描述
        if lab:
            lightness_desc = "高亮度" if lab["L"] > 70 else ("中等亮度" if lab["L"] > 40 else "低亮度")
            chroma = math.sqrt(lab["a"] ** 2 + lab["b"] ** 2)
            chroma_desc = "高饱和度" if chroma > 40 else ("中等饱和度" if chroma > 15 else "低饱和度/近中性")

            qa_pairs.append({
                "instruction": f"从色彩感知角度描述爱色丽色卡中"{name_zh}"的视觉特征。",
                "input": "",
                "output": (
                    f""{name_zh}（{name_en}）"在视觉上表现为{lightness_desc}、{chroma_desc}的色彩。\n"
                    f"其L*值为{lab['L']:.2f}，表示{lightness_desc}；"
                    f"a*值为{lab['a']:.2f}（{'偏红' if lab['a'] > 0 else '偏绿'}），"
                    f"b*值为{lab['b']:.2f}（{'偏黄' if lab['b'] > 0 else '偏蓝'}）。\n"
                    f"彩度C*≈{chroma:.2f}，属于{chroma_desc}色彩。"
                )
            })

    return qa_pairs


def build_comparison_pairs(patches: List[Dict]) -> List[Dict[str, str]]:
    """生成色块对比问答对"""
    qa_pairs = []
    chromatic = [p for p in patches if p.get("category") in ("chromatic", "primary", "nature", "skin")]

    for i in range(min(len(chromatic) - 1, 30)):
        p1 = chromatic[i]
        p2 = chromatic[i + 1]
        if not p1.get("Lab") or not p2.get("Lab"):
            continue
        de = delta_e_2000_approx(p1["Lab"], p2["Lab"])
        qa_pairs.append({
            "instruction": (
                f"比较爱色丽色卡中"{p1.get('name_zh', p1['name'])}"和"
                f""{p2.get('name_zh', p2['name'])}"的色差。"
            ),
            "input": "",
            "output": (
                f""{p1.get('name_zh', p1['name'])}"的Lab值为（{lab_to_str(p1['Lab'])}），"
                f""{p2.get('name_zh', p2['name'])}"的Lab值为（{lab_to_str(p2['Lab'])}）。\n"
                f"两者的欧氏色差ΔE≈{de:.2f}。"
                + ("\n该色差在视觉上较为明显，人眼可轻易区分。" if de > 5 else
                   "\n该色差较小，需仔细观察才能区分。")
            )
        })

    return qa_pairs


def build_colorimetry_knowledge_pairs() -> List[Dict[str, str]]:
    """生成色度学知识问答对"""
    return [
        {
            "instruction": "什么是CIE Lab色彩空间？爱色丽色卡为什么使用Lab值作为标准参数？",
            "input": "",
            "output": (
                "CIE Lab（CIELAB）是国际照明委员会（CIE）定义的感知均匀色彩空间，由三个分量组成：\n"
                "- L*：亮度（Lightness），范围0（黑）到100（白）\n"
                "- a*：红绿轴，正值偏红，负值偏绿\n"
                "- b*：黄蓝轴，正值偏黄，负值偏蓝\n\n"
                "爱色丽色卡使用Lab值的原因：\n"
                "1. 感知均匀性：Lab空间中数值差异与人眼感知的色差高度相关\n"
                "2. 设备无关性：Lab值不依赖于具体显示设备或打印介质\n"
                "3. 色差计算：可直接用欧氏距离计算ΔE色差，便于质量控制"
            )
        },
        {
            "instruction": "爱色丽ColorChecker Classic色卡包含哪些类型的色块？各有什么用途？",
            "input": "",
            "output": (
                "爱色丽ColorChecker Classic包含24个色块，分为以下类别：\n\n"
                "1. 皮肤色调（Skin Tones）：深肤色、浅肤色——用于人像摄影肤色还原校准\n"
                "2. 自然色彩（Nature Colors）：蓝天、植被、蓝色花卉、蓝绿色——用于自然场景色彩校准\n"
                "3. 饱和色彩（Chromatic Colors）：橙、紫蓝、中等红、紫、黄绿、橙黄——覆盖常见色域范围\n"
                "4. 原色（Primary Colors）：蓝、绿、红、黄、品红、青——用于色彩空间特性化\n"
                "5. 中性色（Neutral Scale）：从白到黑的6级灰阶——用于色调响应曲线和白平衡校准"
            )
        },
        {
            "instruction": "如何使用爱色丽色卡进行相机色彩校准？",
            "input": "",
            "output": (
                "使用爱色丽色卡进行相机色彩校准的标准流程：\n\n"
                "1. 拍摄准备：在目标光源下将色卡正对相机，确保均匀照明，避免反光\n"
                "2. 原始拍摄：以RAW格式拍摄色卡，保持曝光准确（白色块不过曝）\n"
                "3. 参考值对比：将拍摄的色块RGB值与X-Rite提供的标准Lab参考值对比\n"
                "4. 生成ICC Profile：使用软件（如X-Rite ColorChecker Passport、DCamProf等）\n"
                "   计算色彩校正矩阵或创建ICC色彩描述文件\n"
                "5. 应用校准：将生成的Profile应用于后续在相同光源下拍摄的RAW文件\n\n"
                "关键指标：校准后各色块ΔE值应小于2.0，中性灰阶的色偏应小于1.0"
            )
        },
        {
            "instruction": "ΔE（色差）的含义是什么？不同ΔE值对应的视觉感知是怎样的？",
            "input": "",
            "output": (
                "ΔE（Delta E）是量化两种颜色视觉差异的色差指标，基于CIE Lab色彩空间计算：\n\n"
                "常用公式：\n"
                "- ΔE76（CIE 1976）：ΔE = √[(ΔL*)² + (Δa*)² + (Δb*)²]\n"
                "- ΔE2000：改进版，更符合人眼感知，加入了明度、彩度、色调的加权\n\n"
                "视觉感知对应关系：\n"
                "- ΔE < 1.0：人眼无法察觉的差异\n"
                "- 1.0 ≤ ΔE < 2.0：专家仔细观察才能察觉\n"
                "- 2.0 ≤ ΔE < 3.5：普通人在中等条件下可察觉\n"
                "- 3.5 ≤ ΔE < 5.0：明显差异，一般人可轻易看出\n"
                "- ΔE ≥ 5.0：颜色显著不同\n\n"
                "印刷行业通常要求ΔE < 2.0，摄影后期要求ΔE < 1.0"
            )
        }
    ]


def split_dataset(data: List[Dict], train_ratio=0.85, val_ratio=0.10):
    random.shuffle(data)
    n = len(data)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    return data[:train_end], data[train_end:val_end], data[val_end:]


def convert_to_alpaca_format(qa_pairs: List[Dict]) -> List[Dict]:
    """转换为Alpaca指令微调格式"""
    return [
        {
            "instruction": item["instruction"],
            "input": item.get("input", ""),
            "output": item["output"]
        }
        for item in qa_pairs
    ]


def convert_to_sharegpt_format(qa_pairs: List[Dict]) -> List[Dict]:
    """转换为ShareGPT对话格式"""
    result = []
    for item in qa_pairs:
        user_content = item["instruction"]
        if item.get("input"):
            user_content += f"\n\n{item['input']}"
        result.append({
            "conversations": [
                {"from": "human", "value": user_content},
                {"from": "gpt", "value": item["output"]}
            ]
        })
    return result


def save_jsonl(data: List[Dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Saved {len(data)} records -> {path}")


def main():
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 加载原始数据
    classic_patches = load_colorchecker_classic()
    sg_patches = load_colorchecker_sg()
    all_patches = classic_patches + sg_patches
    print(f"Loaded {len(all_patches)} color patches total")

    # 构建问答对
    qa_basic = build_qa_pairs(all_patches)
    qa_comparison = build_comparison_pairs(all_patches)
    qa_knowledge = build_colorimetry_knowledge_pairs()

    all_qa = qa_basic + qa_comparison + qa_knowledge
    print(f"Generated {len(all_qa)} QA pairs")

    # 划分数据集
    train, val, test = split_dataset(all_qa)
    print(f"Split: train={len(train)}, val={len(val)}, test={len(test)}")

    # 保存Alpaca格式
    alpaca_dir = PROCESSED_DATA_DIR / "alpaca"
    save_jsonl(convert_to_alpaca_format(train), alpaca_dir / "train.jsonl")
    save_jsonl(convert_to_alpaca_format(val),   alpaca_dir / "val.jsonl")
    save_jsonl(convert_to_alpaca_format(test),  alpaca_dir / "test.jsonl")

    # 保存ShareGPT格式
    sharegpt_dir = PROCESSED_DATA_DIR / "sharegpt"
    save_jsonl(convert_to_sharegpt_format(train), sharegpt_dir / "train.jsonl")
    save_jsonl(convert_to_sharegpt_format(val),   sharegpt_dir / "val.jsonl")
    save_jsonl(convert_to_sharegpt_format(test),  sharegpt_dir / "test.jsonl")

    # 保存样本用于验证
    sample_data = convert_to_alpaca_format(all_qa[:5])
    with open(SAMPLES_DATA_DIR / "sample_alpaca.json", "w", encoding="utf-8") as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=2)

    print("Data preparation complete.")


if __name__ == "__main__":
    random.seed(42)
    main()
