from crewai import Agent
from config.settings import create_llm, COLLECTOR_MODEL

collector = Agent(
    role="搜集专家",
    goal="全面、准确地采集竞品的公开信息，确保每条数据均可溯源",
    backstory=(
        "你是一名专业的竞品分析数据采集专家，擅长利用网络搜索工具获取产品定价、功能、"
        "用户评价等公开信息。你严格遵循溯源要求，每条结论必须附带来源 URL 和原文片段，"
        "并以结构化 JSON 格式输出。"
    ),
    llm=create_llm(COLLECTOR_MODEL),
    verbose=True,
)