import unittest

from graph.prompts import collect_prompt


class CollectPromptTest(unittest.TestCase):
    """The collect prompt must prefer indexed evidence before web search."""

    def _prompt(self) -> str:
        return collect_prompt(
            product_name="飞书",
            competitors="钉钉、企业微信",
            dimensions="定价、功能",
            analysis_type="SWOT",
            evidence_index="some evidence index",
        )

    def test_prompt_prefers_evidence_index_before_web_search(self) -> None:
        description = self._prompt()

        self.assertIn("Evidence Index", description)
        self.assertIn("优先使用 Evidence Index", description)
        self.assertIn("证据不足时再使用网络搜索", description)
        self.assertIn("信息来源允许稀疏覆盖", description)


if __name__ == "__main__":
    unittest.main()
