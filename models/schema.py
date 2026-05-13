from pydantic import BaseModel
from typing import List, Literal


class Dimension(BaseModel):
    name: Literal["定价", "功能", "用户体验", "市场策略", "性能"]
    indicators: List[str]


class CompetitorInput(BaseModel):
    productName: str
    competitors: List[str]
    dimensions: List[Dimension]
    analysisType: Literal["SWOT", "对比表格", "综合报告"] = "SWOT"