"""用 LLM 生成高质量对抗性 Supervisor 路由训练数据。

策略:
1. 模糊意图: 用户指令可以映射到多个 workflow
2. 边界 case: 混合 chat + 工作流的指令
3. 多步计划: 需要 mode="plan" 的复杂任务
4. 否定/修正: 用户修改前一指令方向的 case
"""

import json
import os
import sys
from pathlib import Path

try:
    import dspy
except ImportError as exc:
    raise ImportError("dspy is required") from exc

DISCIPLINES = [
    "computer_science",
    "biology",
    "physics",
    "chemistry",
    "economics",
    "psychology",
    "materials_science",
    "medicine",
]

GENERATION_PROMPT = """你是一个学术研究助手训练数据生成专家。

你需要为一个 Supervisor Router 生成**高质量、有挑战性**的训练样本。Router 负责把用户指令路由到正确模式:
- mode="chat": 闲聊、打招呼、问通用问题
- mode="single" + target_workflow: 单一工作流任务
  - discovery: 搜索论文、检索文献
  - extraction: 精读分析已有论文、笔记生成
  - ideation: Research Gap 分析、实验设计
  - execution: 代码执行、公式验证、实验运行
  - critique: 审查成果、模拟审稿
  - publish: 生成报告、制作 PPT
- mode="plan" + steps: 需要多个工作流串联的复杂任务

请生成 {batch_size} 个**高难度**训练样本。重点包括:
1. **模糊意图** (30%): 看起来属于 A 但实际应路由到 B 的指令
2. **边界 case** (20%): chat 和 workflow 边界模糊的指令
3. **多步计划** (20%): 需要 2-4 步 workflow 串联的复杂指令
4. **领域特定** (15%): 特定学科的专业表述
5. **修正/追问** (15%): 基于 artifacts 上下文的追问

当前学科: {discipline}

以 JSON 数组格式输出，每个元素:
{{
  "discipline": "{discipline}",
  "chat_history": "Human: <用户指令>",
  "current_artifacts": "<当前 artifacts 的 JSON 摘要>",
  "routing_decision": {{
    "mode": "single|plan|chat",
    "target_workflow": "<仅 single 模式>",
    "plan": {{"steps": [{{"workflow": "<wf>", "objective": "<目标>"}}]}} 或 null,
    "reasoning": "<路由理由>",
    "reply_text": "<仅 chat 模式的回复>"
  }},
  "difficulty": "easy|medium|hard"
}}

只输出 JSON 数组，不要额外文字。"""


def generate_adversarial_batch(
    lm: dspy.LM,
    discipline: str,
    batch_size: int = 10,
) -> list[dict]:
    """用 LLM 生成一批高质量对抗样本。"""
    prompt = GENERATION_PROMPT.format(
        batch_size=batch_size,
        discipline=discipline,
    )
    response = lm(prompt)
    text = response[0] if isinstance(response, list) else str(response)

    # 清理 markdown code block
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
        print(f"  WARN: JSON parse failed for {discipline}, skipping", file=sys.stderr)
        return []


def generate_full_dataset(
    total: int = 200,
    seed: int = 42,
) -> list[dict]:
    """生成完整的对抗性数据集。"""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY required")

    lm = dspy.LM("gemini/gemini-2.5-flash", temperature=0.8)
    dspy.configure(lm=lm)

    batch_per_discipline = max(5, total // len(DISCIPLINES))
    dataset: list[dict] = []

    for discipline in DISCIPLINES:
        print(f"  Generating {batch_per_discipline} samples for {discipline}...")
        batch = generate_adversarial_batch(lm, discipline, batch_per_discipline)
        dataset.extend(batch)
        print(f"  Got {len(batch)} samples")

    # 统计难度分布
    difficulties = {}
    for d in dataset:
        diff = d.get("difficulty", "unknown")
        difficulties[diff] = difficulties.get(diff, 0) + 1
    print(f"\nTotal: {len(dataset)} samples")
    print(f"Difficulty distribution: {difficulties}")

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
        print(f"Saved {len(dataset)} samples to {args.output}")
    else:
        print(json.dumps(dataset[:3], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
