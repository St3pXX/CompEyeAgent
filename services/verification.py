"""Provenance guard and verification logic shared by runner.py and per-node executors."""

from __future__ import annotations

import json
import re
from typing import Any


SOURCE_MARKERS = ("[来源:", "source_references", "provenance", "来源 URL", "来源:")
SOURCE_BLOCK_MARKERS = ("Provenance 索引", "provenance 索引", "来源索引", "参考来源")


def verification_issues(report: str, verifier_result: str) -> list[str]:
    """Check provenance guard + verifier JSON and return a list of issues."""
    issues: list[str] = []
    issues.extend(provenance_guard(report))

    verdict = parse_verifier_result(verifier_result)
    if verdict:
        passed = verdict.get("passed")
        confidence = verdict.get("confidence")
        if passed is False:
            issues.append("Verifier 判定未通过")
        if isinstance(confidence, (int, float)) and confidence < 60:
            issues.append(f"Verifier 置信度低于阈值: {confidence}")
        for item in verdict.get("issues", []) or []:
            if isinstance(item, dict):
                description = item.get("description") or item.get("type")
                if description:
                    issues.append(str(description))

    return issues


def provenance_guard(report: str) -> list[str]:
    """Regex-based checks on the final report for source annotations."""
    issues: list[str] = []
    urls = re.findall(r"https?://[^\s\])>，。；,]+", report)

    if not any(marker in report for marker in SOURCE_BLOCK_MARKERS):
        issues.append("最终报告缺少 provenance / 来源索引区块")

    if not urls:
        issues.append("最终报告缺少可访问 URL")

    source_tag_count = len(re.findall(r"\[来源:\s*[^\]]+\]", report))
    claim_like = claim_like_lines(report)
    if claim_like and source_tag_count < len(claim_like):
        issues.append(
            f"来源标注不足：检测到 {len(claim_like)} 条结论式条目，但只有 {source_tag_count} 个 [来源: ...] 标注"
        )

    if "待核实" in report and source_tag_count == 0:
        issues.append("报告包含待核实内容，但没有提供来源标注或复核入口")

    return issues


def claim_like_lines(report: str) -> list[str]:
    """Extract bullet-point lines that look like claims needing source tags."""
    lines: list[str] = []
    for raw_line in report.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^#{1,6}\s+", line) or "|" in line:
            continue
        if re.match(r"^([-*]|\d+[.)])\s+", line) and len(line) >= 18:
            lines.append(line)
    return lines


def parse_verifier_result(verifier_result: str) -> dict[str, Any] | None:
    """Parse verifier JSON output, handling raw JSON or embedded JSON in text."""
    text = verifier_result.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
