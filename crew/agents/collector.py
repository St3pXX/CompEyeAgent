from crewai import Agent
from crewai.tools import BaseTool
from pydantic import Field
import os


class WebSearchTool(BaseTool):
    """使用 MiMo 原生联网搜索能力"""

    name: str = Field(default="web_search")
    description: str = Field(
        default="搜索最新的公开网络信息，输入搜索查询，返回搜索结果摘要和来源 URL"
    )

    def _run(self, query: str) -> str:
        """执行搜索并返回结果"""
        import litellm

        os.environ["OPENAI_API_KEY"] = os.getenv("MIMO_API_KEY", "")
        os.environ["OPENAI_API_BASE"] = os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimmo.com/v1")

        try:
            response = litellm.completion(
                model="openai/xiaomi/mimo-v2.5",
                messages=[{"role": "user", "content": f"请搜索以下内容并返回结果：{query}"}],
                api_key=os.getenv("MIMO_API_KEY"),
                base_url=os.getenv("MIMO_BASE_URL"),
                timeout=30,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"搜索失败: {str(e)}"


collector = Agent(
    role="搜集专家",
    goal="全面、准确地采集竞品的公开信息，确保每条数据均可溯源",
    backstory=(
        "你是一名专业的竞品分析数据采集专家，擅长利用网络搜索工具获取产品定价、功能、"
        "用户评价等公开信息。你严格遵循溯源要求，每条结论必须附带来源 URL 和原文片段，"
        "并以结构化 JSON 格式输出。"
    ),
    llm="xiaomi/mimo-v2.5",
    tools=[WebSearchTool()],
    verbose=True,
)
