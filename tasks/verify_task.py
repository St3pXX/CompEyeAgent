from crewai import Task
from crew.agents.verifier import verifier
from tasks.write_task import write_task


verify_task = Task(
    description=(
        "独立校验报告草稿的准确性，主动寻找问题。\n"
        "检查项：\n"
        "1. 逻辑矛盾检测（同一竞品不同维度结论是否一致）\n"
        "2. 数据一致性验证（报告数据与原始采集数据是否匹配）\n"
        "3. 幻觉检测（结论是否有对应的证据支持）\n"
        "4. 缺失关键维度检测（是否有关键维度未覆盖）\n\n"
        "质检策略（Phase 1）：\n"
        "- confidence >= 90：报告通过\n"
        "- 60 <= confidence < 90：标记待复核，高亮问题段落\n"
        "- confidence < 60：触发重试（最多1次）\n\n"
        "输入：write_task 的输出（报告草稿）+ provenance 索引\n"
        "输出：质检结果 JSON {passed, confidence, issues}。"
    ),
    agent=verifier,
    expected_output=(
        "质检结果 JSON：{passed: bool, confidence: 0-100, "
        "issues: [{type, description, suggested_action}]}"
    ),
    context=[write_task],
)