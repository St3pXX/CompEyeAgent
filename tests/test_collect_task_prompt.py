import unittest
from pathlib import Path


class CollectTaskPromptTest(unittest.TestCase):
    def test_prompt_prefers_evidence_index_before_web_search(self) -> None:
        description = Path("tasks/collect_task.py").read_text(encoding="utf-8")

        self.assertIn("Evidence Index", description)
        self.assertIn("优先使用 Evidence Index", description)
        self.assertIn("证据不足时再使用网络搜索", description)
        self.assertIn("信息来源允许稀疏覆盖", description)
        self.assertIn("不要求官方网站、新闻、博客、GitHub、社交媒体、财务、专利等每类来源都查到信息", description)


if __name__ == "__main__":
    unittest.main()
