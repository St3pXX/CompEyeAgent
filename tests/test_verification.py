"""Tests for services.verification — provenance guard and verifier parsing."""

import unittest

from services.verification import (
    claim_like_lines,
    parse_verifier_result,
    provenance_guard,
    verification_issues,
)


class ProvenanceGuardTest(unittest.TestCase):
    def test_passes_when_report_has_sources_and_urls(self) -> None:
        report = (
            "## 竞品分析\n\n"
            "- 飞书定价更灵活 [来源: https://feishu.cn/pricing]\n\n"
            "## Provenance 索引\n"
            "| 来源 | URL |\n|------|-----|\n| 飞书官网 | https://feishu.cn/pricing |"
        )
        self.assertEqual(provenance_guard(report), [])

    def test_fails_when_no_source_block(self) -> None:
        report = "- 飞书定价更灵活 [来源: https://feishu.cn/pricing]"
        issues = provenance_guard(report)
        self.assertTrue(any("provenance" in i or "来源索引" in i for i in issues))

    def test_fails_when_no_urls(self) -> None:
        report = "## Provenance 索引\n\n没有 URL 的报告"
        issues = provenance_guard(report)
        self.assertTrue(any("URL" in i for i in issues))

    def test_fails_when_source_tags_insufficient(self) -> None:
        report = (
            "## Provenance 索引\n\n"
            "- 飞书定价更灵活，支持免费套餐和企业版 [来源: https://feishu.cn/pricing]\n"
            "- 钉钉功能更全面，覆盖了即时通讯和审批流\n"
            "- 企业微信体验更好，与微信生态深度整合\n"
        )
        issues = provenance_guard(report)
        self.assertTrue(any("来源标注不足" in i for i in issues))


class ClaimLikeLinesTest(unittest.TestCase):
    def test_extracts_bullets(self) -> None:
        report = "- 飞书定价更灵活，支持免费套餐和企业版"
        self.assertEqual(len(claim_like_lines(report)), 1)

    def test_skips_short_lines(self) -> None:
        report = "- 短句"
        self.assertEqual(len(claim_like_lines(report)), 0)

    def test_skips_headers_and_tables(self) -> None:
        report = "## 标题\n| 列1 | 列2 |\n|----|----|"
        self.assertEqual(len(claim_like_lines(report)), 0)


class ParseVerifierResultTest(unittest.TestCase):
    def test_parses_raw_json(self) -> None:
        result = parse_verifier_result('{"passed": true, "confidence": 85}')
        self.assertIsNotNone(result)
        self.assertTrue(result["passed"])
        self.assertEqual(result["confidence"], 85)

    def test_parses_embedded_json(self) -> None:
        text = '质检结果如下：\n{"passed": false, "confidence": 45, "issues": []}\n以上。'
        result = parse_verifier_result(text)
        self.assertIsNotNone(result)
        self.assertFalse(result["passed"])

    def test_returns_none_for_no_json(self) -> None:
        self.assertIsNone(parse_verifier_result("没有 JSON 的文本"))

    def test_returns_none_for_invalid_json(self) -> None:
        self.assertIsNone(parse_verifier_result("{invalid json}"))


class VerificationIssuesTest(unittest.TestCase):
    def test_returns_empty_when_all_pass(self) -> None:
        report = (
            "## 竞品分析\n"
            "- 飞书定价更灵活 [来源: https://feishu.cn/pricing]\n\n"
            "## Provenance 索引\n"
            "| 来源 | URL |\n|------|-----|\n| 飞书 | https://feishu.cn/pricing |"
        )
        verifier = '{"passed": true, "confidence": 90}'
        self.assertEqual(verification_issues(report, verifier), [])

    def test_catches_verifier_failed(self) -> None:
        report = (
            "## Provenance 索引\n"
            "- 飞书 [来源: https://feishu.cn]\n"
        )
        verifier = '{"passed": false, "confidence": 50}'
        issues = verification_issues(report, verifier)
        self.assertTrue(any("未通过" in i for i in issues))

    def test_catches_low_confidence(self) -> None:
        report = (
            "## Provenance 索引\n"
            "- 飞书 [来源: https://feishu.cn]\n"
        )
        verifier = '{"passed": true, "confidence": 40}'
        issues = verification_issues(report, verifier)
        self.assertTrue(any("置信度" in i for i in issues))

    def test_catches_verifier_issues(self) -> None:
        report = (
            "## Provenance 索引\n"
            "- 飞书 [来源: https://feishu.cn]\n"
        )
        verifier = '{"passed": true, "confidence": 80, "issues": [{"type": "missing_evidence", "description": "缺少定价数据"}]}'
        issues = verification_issues(report, verifier)
        self.assertTrue(any("缺少定价数据" in i for i in issues))


if __name__ == "__main__":
    unittest.main()
