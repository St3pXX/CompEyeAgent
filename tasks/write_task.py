from crewai import Task
from crew.agents.writer import writer
from tasks.analyze_task import analyze_task


write_task = Task(
    description=(
        "将分析结论组织为可读的 Markdown 竞品分析报告。\n"
        "执行步骤：\n"
        "1. 按照报告规范组织内容（SWOT 框架或对比表格）\n"
        "2. 每个分析结论必须在同一条 bullet 内附带来源标注，格式严格为 [来源: https://...]\n"
        "3. 在报告末尾附上标题为 “Provenance 索引” 的来源索引表\n"
        "4. 没有来源支撑的结论必须删除或标记为“待核实”，不能写成确定结论\n\n"
        "输入：analyze_task 的输出（结构化分析结论）\n"
        "输出：Markdown 格式竞品分析报告，每条结论有来源标注。"
    ),
    agent=writer,
    expected_output=(
        "Markdown 格式竞品分析报告，包含 SWOT 或对比表格，"
        "每条结论附有来源标注，末尾附 provenance 索引"
    ),
    context=[analyze_task],
)
