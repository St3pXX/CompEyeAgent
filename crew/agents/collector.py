from crewai import Agent
from crewai.tools import BaseTool
from pydantic import Field
import os
from config.settings import COLLECTOR_MODEL, MIMO_BASE_URL, create_llm


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
        os.environ["OPENAI_API_BASE"] = MIMO_BASE_URL

        try:
            litellm_model = COLLECTOR_MODEL
            if not litellm_model.startswith("openai/"):
                litellm_model = f"openai/{litellm_model}"

            response = litellm.completion(
                model=litellm_model,
                messages=[{"role": "user", "content": f"请搜索以下内容并返回结果：{query}"}],
                api_key=os.getenv("MIMO_API_KEY"),
                base_url=MIMO_BASE_URL,
                temperature=0.7,
                top_p=0.95,
                max_completion_tokens=2048,
                extra_body={"thinking": {"type": "disabled"}},
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
    llm=create_llm(COLLECTOR_MODEL),
    tools=[WebSearchTool()],
    verbose=True,
)
