# -*- coding: utf-8 -*-
"""GitDiffParser - git diff / 通用unified diff 格式解析器"""

import re
from diff_parser.base import DiffParser


class GitDiffParser(DiffParser):
    """解析 git diff 和通用 unified diff 格式"""

    @staticmethod
    def can_parse(diff_text):
        """检测是否有 diff --git 或 diff - 标记"""
        return bool(re.search(r'^diff (--git |-)', diff_text, re.MULTILINE))

    def parse(self, diff_text):
        """按 diff --git 标记分割补丁，按文件路径分组"""
        # 优先按 git 风格分割
        blocks = re.split(r'^(?=diff --git )', diff_text, flags=re.MULTILINE)

        # 如果没有 diff --git，尝试通用 unified diff 格式
        if len(blocks) <= 1:
            blocks = re.split(r'^(?=diff )', diff_text, flags=re.MULTILINE)

        return self._group_file_blocks(blocks)

    def get_filename_from_block(self, block):
        """从 diff 块中提取文件路径

        优先匹配 diff --git a/path b/path 格式，
        否则匹配 +++ b/path 或 +++ a/path。
        """
        # Git 格式: diff --git a/path b/path
        m = re.search(r'^diff --git a/(.+) b/(.+)$', block, re.MULTILINE)
        if m:
            return m.group(2)

        # 通用 unified diff: +++ 行包含路径，a/b/ 前缀可选
        m = re.search(r'^\+{3} (?:[ab]/)?(.+?)(?:\t|$)', block, re.MULTILINE)
        if m:
            return m.group(1).rstrip()

        return None
