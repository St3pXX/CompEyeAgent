from crewai import Task
from crew.agents.collector import collector


collect_info_task = Task(
    description=(
        "根据用户提供的竞品列表和维度，使用网络搜索工具采集每个竞品的公开信息。\n"
        "输入格式示例：\n"
        '{"productName": "产品A", "competitors": ["产品B", "产品C"], '
        '"dimensions": [{"name": "定价", "indicators": ["价格", "免费试用"]}]}\n\n'
        "执行步骤：\n"
        "1. 对每个竞品使用网络搜索，采集维度的公开信息\n"
        "2. 每条数据必须记录来源 URL 和关键原文片段\n"
        "3. 以结构化 JSON 格式输出每条采集结果，包含 provenance 信息\n\n"
        "输出格式：JSON数组，每项包含竞品名、维度、数据内容、来源URL、原文片段。"
    ),
    agent=collector,
    expected_output=(
        "结构化的竞品原始信息 JSON，每条数据附有 provenance "
        "(source_references: [{uri, snippet}])"
    ),
)