#!/usr/bin/env python3
"""竞品分析 Agent 协作系统 — CLI 入口"""

import sys
import json
from crew import analysis_crew
from models.schema import CompetitorInput


def main():
    if len(sys.argv) < 2:
        print("用法: python main.py '<竞品分析需求 JSON>'")
        print()
        print("示例:")
        example = {
            "productName": "飞书",
            "competitors": ["钉钉", "企业微信"],
            "dimensions": [
                {"name": "定价", "indicators": ["免费套餐", "付费套餐"]},
                {"name": "功能", "indicators": ["即时通讯", "文档协作", "视频会议"]},
            ],
            "analysisType": "SWOT",
        }
        print(f"python main.py '{json.dumps(example, ensure_ascii=False)}'")
        sys.exit(1)

    try:
        user_input = json.loads(sys.argv[1])
        inputs = CompetitorInput(**user_input).model_dump()
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"输入验证错误: {e}")
        sys.exit(1)

    print("=" * 60)
    print("竞品分析 Agent 协作系统启动")
    print("=" * 60)
    print(f"目标产品: {inputs['productName']}")
    print(f"竞品列表: {', '.join(inputs['competitors'])}")
    print(f"分析维度: {', '.join(d['name'] for d in inputs['dimensions'])}")
    print(f"分析类型: {inputs['analysisType']}")
    print("=" * 60)
    print()

    result = analysis_crew.kickoff(inputs=inputs)

    print()
    print("=" * 60)
    print("分析完成")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()