from crewai import Task
from crew.agents.collector import collector


collect_info_task = Task(
    description=(
        "根据用户提供的竞品列表和维度，使用网络搜索工具采集每个竞品的公开信息。\n"
        "用户输入：\n"
        "- 目标产品：{productName}\n"
        "- 竞品列表：{competitors}\n"
        "- 分析维度：{dimensions}\n"
        "- 分析类型：{analysisType}\n\n"
        "输入格式示例：\n"
        '{"productName": "产品A", "competitors": ["产品B", "产品C"], '
        '"dimensions": [{"name": "定价", "indicators": ["价格", "免费试用"]}]}\n\n'
        "可用的 Evidence Index：\n"
        "{evidenceIndex}\n"
        "优先使用 Evidence Index 中已有的结构化证据；证据不足时再使用网络搜索补充。\n"
        "使用 Evidence Index 时必须保留其中的 source URL、snippet、confidence 和 provider。\n\n"
        "信息来源允许稀疏覆盖：不要求官方网站、新闻、博客、GitHub、社交媒体、财务、专利等每类来源都查到信息。\n"
        "如果某个结论已经能被其他可信来源支撑，可以综合采用；只有结论本身缺少可核验证据时才标记为“待核实”。\n\n"
        "执行步骤：\n"
        "1. 先检查 Evidence Index 中是否已有匹配竞品和维度的证据\n"
        "2. Evidence Index 证据不足时，对每个竞品使用网络搜索，采集维度的公开信息\n"
        "3. 跨来源综合时按来源可信度和原文相关性判断，不把单一来源缺失视为失败\n"
        "4. 每条数据必须记录来源 URL 和关键原文片段\n"
        "5. 以结构化 JSON 格式输出每条采集结果，包含 source_references 信息\n\n"
        "输出格式必须是 JSON 数组，数组项遵循 Evidence Schema：\n"
        "{\n"
        '  "competitor": "竞品名",\n'
        '  "dimension": "维度名",\n'
        '  "indicator": "指标名",\n'
        '  "summary": "采集摘要，不能编造",\n'
        '  "source_references": [\n'
        '    {"uri": "https://...", "snippet": "支撑摘要的原文片段"}\n'
        "  ]\n"
        "}\n"
        "禁止输出没有 source_references 的采集项；无法找到来源时，将 summary 标记为“待核实”，并说明缺口。"
    ),
    agent=collector,
    expected_output=(
        "结构化 Evidence JSON 数组，每条数据附有 provenance "
        "(source_references: [{uri, snippet}])"
    ),
)
