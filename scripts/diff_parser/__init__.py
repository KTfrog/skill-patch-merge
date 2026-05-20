# -*- coding: utf-8 -*-
"""diff_parser - 多格式diff解析器包"""

from diff_parser.base import DiffParser, ChangeType, FileType
from diff_parser.svn_parser import SvnDiffParser
from diff_parser.git_diff_parser import GitDiffParser
from diff_parser.git_format_patch_parser import GitFormatPatchParser


def detect_format(diff_text):
    """自动检测diff格式并返回对应的解析器实例

    检测优先级:
    1. SVN diff: 包含 Index: 行
    2. Git format-patch: 包含 From <40位hex hash>
    3. Git/unified diff: 包含 diff --git 或 diff -
    4. 兜底: SvnDiffParser
    """
    head = diff_text[:2048]

    if SvnDiffParser.can_parse(head):
        return SvnDiffParser()

    if GitFormatPatchParser.can_parse(head):
        return GitFormatPatchParser()

    if GitDiffParser.can_parse(head):
        return GitDiffParser()

    # 兜底
    return SvnDiffParser()
