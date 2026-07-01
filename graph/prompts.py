"""Prompt templates for the graph nodes.

System prompts preserve the CrewAI agent role/backstory/goal; task prompts are
lifted from services/node_executors.py so node behavior is unchanged.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# System prompts (from crew/agents/*.py role + backstory + goal)
# ---------------------------------------------------------------------------

COLLECTOR_SYSTEM = (
    "你是一名专业的竞品分析数据采集专家（搜集专家），擅长利用网络搜索工具获取产品定价、功能、"
    "用户评价等公开信息。你的目标是全面、准确地采集竞品的公开信息，确保每条数据均可溯源。"
    "你严格遵循溯源要求，每条结论必须附带来源 URL 和原文片段，并以结构化 JSON 格式输出。"
)

ANALYZER_SYSTEM = (
    "你是一名专业的数据分析师，擅长从杂乱的市场信息中提炼出结构化的竞品分析结论。"
    "你使用 SWOT 或对比表格等框架，对采集的数据进行深度分析。"
    "你严格遵循溯源要求，每条分析结论必须附带 provenance（指向原始数据来源）。"
)

WRITER_SYSTEM = (
    "你是一名专业的商业报告撰写师，擅长将复杂的市场分析结论转化为清晰、专业的报告。"
    "你生成的报告需要分维度呈现，每个分析结论必须附带来源标注，"
    "确保读者可以追溯每条信息的原始来源。"
)

VERIFIER_SYSTEM = (
    "你是一名严格的质量检测员。你收到的报告草稿可能包含错误——逻辑矛盾、数据不一致、"
    "幻觉（结论无证据支持）或遗漏关键维度。你的任务不是确认它正确，而是主动寻找问题。"
    "你进行深度逻辑校验，不继承任何撰写者的对话历史，以确保客观公正。"
    "输出 JSON 格式：{passed(bool), confidence(0-100), issues(array)}。"
)


# ---------------------------------------------------------------------------
# Task prompt builders (from services/node_executors.py)
# ---------------------------------------------------------------------------

def collect_prompt(*, product_name: str, competitors: str, dimensions: str,
                   analysis_type: str, evidence_index: str) -> str:
    return (
        "根据用户提供的竞品列表和维度，使用网络搜索工具采集每个竞品的公开信息。\n"
        "用户输入：\n"
        f"- 目标产品：{product_name}\n"
        f"- 竞品列表：{competitors}\n"
        f"- 分析维度：{dimensions}\n"
        f"- 分析类型：{analysis_type}\n\n"
        "可用的 Evidence Index：\n"
        f"{evidence_index}\n"
        "优先使用 Evidence Index 中已有的结构化证据；证据不足时再使用网络搜索补充。\n"
        "使用 Evidence Index 时必须保留其中的 source URL、snippet、confidence 和 provider。\n\n"
        "信息来源允许稀疏覆盖：不要求每类来源都查到信息。\n"
        "如果某个结论已经能被其他可信来源支撑，可以综合采用；只有结论本身缺少可核验证据时才标记为“待核实”。\n\n"
        "执行步骤：\n"
        "1. 先检查 Evidence Index 中是否已有匹配竞品和维度的证据\n"
        "2. Evidence Index 证据不足时，对每个竞品使用网络搜索\n"
        "3. 跨来源综合时按来源可信度和原文相关性判断\n"
        "4. 每条数据必须记录来源 URL 和关键原文片段\n"
        "5. 以结构化 JSON 格式输出每条采集结果\n\n"
        "输出格式必须是 JSON 数组，数组项遵循 Evidence Schema：\n"
        '{"competitor": "竞品名", "dimension": "维度名", "indicator": "指标名", '
        '"summary": "采集摘要", "source_references": [{"uri": "https://...", "snippet": "原文片段"}]}\n'
        "禁止输出没有 source_references 的采集项。"
    )


def collect_web_search_prompt(*, product_name: str, competitors: str, dimensions: str) -> str:
    """Query string for the web_search call inside the collect node."""
    return (
        f"目标产品 {product_name} 的竞品 {competitors} 在以下维度的公开信息："
        f"{dimensions}。请给出定价、功能、用户评价等要点，并附来源 URL。"
    )


def analyze_prompt(*, raw_data: str) -> str:
    return (
        "读取采集的原始数据，执行结构化分析（SWOT 或对比表格）。\n\n"
        f"以下是 Collector 采集的原始数据：\n\n{raw_data}\n\n"
        "执行步骤：\n"
        "1. 分析每个竞品在各维度上的表现\n"
        "2. 生成结构化分析结论（Strengths/Weaknesses/Opportunities/Threats）\n"
        "3. 每条分析结论必须附带 provenance（指向原始数据来源）\n\n"
        "输出：结构化分析结论 JSON，每条结论附有 provenance。"
    )


def write_prompt(*, findings: str) -> str:
    return (
        "将分析结论组织为可读的 Markdown 竞品分析报告。\n\n"
        f"以下是 Analyzer 的结构化分析结论：\n\n{findings}\n\n"
        "执行步骤：\n"
        "1. 按照报告规范组织内容（SWOT 框架或对比表格）\n"
        "2. 每个分析结论必须在同一条 bullet 内附带来源标注，格式严格为 [来源: https://...]\n"
        "3. 在报告末尾附上标题为“Provenance 索引”的来源索引表\n"
        "4. 没有来源支撑的结论必须删除或标记为“待核实”\n\n"
        "输出：Markdown 格式竞品分析报告，每条结论有来源标注。"
    )


def rewrite_prompt(*, findings: str, issues: str) -> str:
    """Write prompt augmented with prior verification issues (one rewrite pass)."""
    return (
        write_prompt(findings=findings)
        + "\n\n上一次质检未通过，请只重写报告并修复以下问题：\n"
        + f"{issues}\n"
        + "必须保留每条结论后的来源标注，并在末尾输出 provenance 索引。"
    )


def verify_prompt(*, report: str) -> str:
    return (
        "独立校验报告草稿的准确性，主动寻找问题。\n\n"
        f"以下是 Writer 生成的报告草稿：\n\n{report}\n\n"
        "检查项：\n"
        "1. 逻辑矛盾检测（同一竞品不同维度结论是否一致）\n"
        "2. 数据一致性验证（报告数据与原始采集数据是否匹配）\n"
        "3. 幻觉检测（结论是否有对应的证据支持）\n"
        "4. 缺失关键维度检测（是否有关键维度未覆盖）\n\n"
        "质检策略：\n"
        "- confidence >= 90：报告通过\n"
        "- 60 <= confidence < 90：标记待复核\n"
        "- confidence < 60：不通过\n\n"
        "输出：质检结果 JSON {passed, confidence, issues: [{type, description}]}。"
    )
