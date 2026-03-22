"""Paper mode 纯函数单元测试。"""

from backend.services.parser_engine import (
    _count_heading_hits,
    _is_ref_heading,
    _looks_like_paper,
    trim_references_if_paper,
)


# ---------------------------------------------------------------------------
# _is_ref_heading
# ---------------------------------------------------------------------------


def test_is_ref_heading_english() -> None:
    assert _is_ref_heading("## References")
    assert _is_ref_heading("# References")
    assert _is_ref_heading("References")
    assert _is_ref_heading("## Bibliography")
    assert _is_ref_heading("# 7. REFERENCES")
    assert _is_ref_heading("# 7. References")
    assert _is_ref_heading("## 5) References")


def test_is_ref_heading_chinese() -> None:
    assert _is_ref_heading("## 参考文献")
    assert _is_ref_heading("参考文献")
    assert _is_ref_heading("# 参考资料")


def test_is_ref_heading_negative() -> None:
    assert not _is_ref_heading("")
    assert not _is_ref_heading("## Introduction")
    assert not _is_ref_heading("Some plain text")
    assert not _is_ref_heading("## Reference Implementation")


# ---------------------------------------------------------------------------
# _count_heading_hits
# ---------------------------------------------------------------------------


def test_count_heading_hits() -> None:
    md = "# Abstract\n\nSome text\n\n## Introduction\n\nMore text\n\n## Methods\n"
    hits = _count_heading_hits(md, ["abstract", "introduction", "methods"])
    assert hits == 3


def test_count_heading_hits_no_match() -> None:
    md = "# Preface\n\nSome text\n"
    hits = _count_heading_hits(md, ["abstract", "introduction"])
    assert hits == 0


# ---------------------------------------------------------------------------
# _looks_like_paper
# ---------------------------------------------------------------------------


_PAPER_MD = """\
# Title of Paper

## Abstract

This is an abstract.

## Introduction

Some intro text.

## Methods

The methods section.

## Results

Results here.

## References

[1] Author A, "A paper", 2021.
[2] Author B, "B paper", 2022.
[3] Author C, "C paper", 2023.
"""


def test_looks_like_paper_positive() -> None:
    assert _looks_like_paper(_PAPER_MD)


def test_looks_like_paper_negative() -> None:
    md = "# User Guide\n\n## Installation\n\nInstall with pip.\n"
    assert not _looks_like_paper(md)


# ---------------------------------------------------------------------------
# trim_references_if_paper
# ---------------------------------------------------------------------------


def test_trim_references_auto_paper() -> None:
    text, trimmed, reason = trim_references_if_paper(_PAPER_MD, "auto")
    assert trimmed
    assert "References" not in text
    assert "Author A" not in text
    assert "Abstract" in text


def test_trim_references_off() -> None:
    text, trimmed, _ = trim_references_if_paper(_PAPER_MD, "off")
    assert not trimmed
    assert "References" in text


def test_trim_references_on_non_paper() -> None:
    """paper_mode='on' 强制裁剪，即使不像论文。"""
    md = "# Some Doc\n\nContent.\n\n## References\n\n[1] A ref.\n"
    text, trimmed, _ = trim_references_if_paper(md, "on")
    assert trimmed
    assert "[1] A ref" not in text


def test_trim_references_no_heading() -> None:
    md = "# Some Doc\n\nContent without reference heading.\n"
    text, trimmed, reason = trim_references_if_paper(md, "auto")
    assert not trimmed
    assert reason == "no references heading"
