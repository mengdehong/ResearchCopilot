"""用 LLM 生成高质量对抗性 Discovery 排序训练数据。

策略:
1. 标题相关但摘要不相关的论文 (误导性高相关)
2. 标题不相关但方法与搜索意图高度相关的论文 (隐性相关)
3. 同领域不同子方向的论文 (需要细粒度区分)
4. 综述类 vs 原创研究的偏好差异
5. 新旧论文的时效性权衡
"""

import json
import os
import sys
from pathlib import Path

try:
    import dspy
except ImportError as exc:
    raise ImportError("dspy is required") from exc


GENERATION_PROMPT = """你是一个学术论文检索系统训练数据生成专家。

你需要为一个 Discovery 论文排序模型生成**有挑战性**的训练样本。
模型需要判断一篇论文对用户搜索意图的相关性 (0-1分)。

请生成 {batch_size} 组数据，每组包含一个搜索意图和 6 篇候选论文:
- 2 篇**高相关** (用户会选中): is_selected=true
- 2 篇**中等相关** (看起来相关但用户不会选): is_selected=false
- 2 篇**低相关/不相关** (明确不选): is_selected=false

学科: {discipline}

重点生成这些**挑战性场景**:
1. **误导性标题**: 标题含关键词但内容不相关
2. **隐性相关**: 标题不含关键词但方法高度相关
3. **细粒度区分**: 同子领域的论文，差异仅在方法/数据集
4. **综述 vs 原创**: 综述论文覆盖面广但用户可能不选
5. **过时研究**: 经典论文但方法已被取代

输出 JSON 数组，每个元素:
{{
  "discipline": "{discipline}",
  "user_search_intent": "<用户搜索意图>",
  "paper_title": "<论文标题>",
  "paper_abstract": "<论文摘要, 100-200字>",
  "is_selected": true/false,
  "challenge_type": "<misleading_title|hidden_relevance|fine_grained|survey_vs_original|outdated>"
}}

只输出 JSON 数组。"""


def generate_adversarial_batch(
    lm: dspy.LM,
    discipline: str,
    batch_size: int = 5,
) -> list[dict]:
    """用 LLM 生成一批对抗样本（每组 6 篇论文）。"""
    prompt = GENERATION_PROMPT.format(
        batch_size=batch_size,
        discipline=discipline,
    )
    response = lm(prompt)
    text = response[0] if isinstance(response, list) else str(response)

    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return [data]
    except json.JSONDecodeError:
        print(f"  WARN: JSON parse failed for {discipline}", file=sys.stderr)
        return []


DISCIPLINES = [
    "computer_science",
    "biology",
    "physics",
    "chemistry",
    "economics",
    "materials_science",
]


def generate_full_dataset(
    total: int = 200,
    seed: int = 42,
) -> list[dict]:
    """生成完整的对抗性 Discovery 数据集。"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY required")

    lm = dspy.LM("gemini/gemini-2.5-flash", temperature=0.8)
    dspy.configure(lm=lm)

    groups_per_discipline = max(3, total // (len(DISCIPLINES) * 6))
    dataset: list[dict] = []

    for discipline in DISCIPLINES:
        print(f"  Generating {groups_per_discipline} groups for {discipline}...")
        batch = generate_adversarial_batch(lm, discipline, groups_per_discipline)
        dataset.extend(batch)
        print(f"  Got {len(batch)} samples")

    # 统计分布
    challenge_types: dict[str, int] = {}
    selected = sum(1 for d in dataset if d.get("is_selected"))
    for d in dataset:
        ct = d.get("challenge_type", "unknown")
        challenge_types[ct] = challenge_types.get(ct, 0) + 1

    print(f"\nTotal: {len(dataset)} samples")
    print(f"Selected: {selected}, Not selected: {len(dataset) - selected}")
    print(f"Challenge types: {challenge_types}")

    return dataset


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--total", type=int, default=200)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    dataset = generate_full_dataset(total=args.total)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            for item in dataset:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"Saved to {args.output}")
    else:
        print(json.dumps(dataset[:3], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
