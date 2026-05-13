from crewai import Task
from crew.agents.analyzer import analyzer
from tasks.collect_task import collect_info_task


analyze_task = Task(
    description=(
        "读取采集的原始数据，执行结构化分析（SWOT 或对比表格）。\n"
        "执行步骤：\n"
        "1. 分析每个竞品在各维度上的表现\n"
        "2. 生成结构化分析结论（Strengths/Weaknesses/Opportunities/Threats）\n"
        "3. 每条分析结论必须附带 provenance（指向原始数据来源）\n\n"
        "输入：collect_task 的输出（采集的原始信息）\n"
        "输出：结构化分析结论 JSON，每条结论附有 provenance。"
    ),
    agent=analyzer,
    expected_output=(
        "结构化分析结论 JSON（SWOT 格式），每条结论附有 provenance "
        "(source_references 指向原始采集数据)"
    ),
    context=[collect_info_task],
)