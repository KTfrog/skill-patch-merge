# -*- coding: utf-8 -*-
"""SvnDiffParser - SVN diff格式解析器"""

import re
from diff_parser.base import DiffParser


class SvnDiffParser(DiffParser):
    """解析SVN格式的diff文件（按 Index: 分割）"""

    @staticmethod
    def can_parse(diff_text):
        """检测是否有 SVN Index: 标记"""
        return bool(re.search(r'^Index: ', diff_text, re.MULTILINE))

    def parse(self, diff_text):
        """按 Index: 分割SVN补丁，按文件路径分组"""
        blocks = re.split(r'^(?=Index: )', diff_text, flags=re.MULTILINE)
        return self._group_file_blocks(blocks)

    def get_filename_from_block(self, block):
        """从 Index: 行提取文件路径"""
        m = re.match(r'^Index: (.+)', block)
        if m:
            return m.group(1).strip()
        return None
