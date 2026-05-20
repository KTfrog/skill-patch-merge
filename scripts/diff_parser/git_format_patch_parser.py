# -*- coding: utf-8 -*-
"""GitFormatPatchParser - git format-patch 格式解析器"""

import re
from diff_parser.base import DiffParser


class GitFormatPatchParser(DiffParser):
    """解析 git format-patch 生成的补丁（含提交信息）"""

    def __init__(self):
        super().__init__()
        # parse() 阶段存储: filepath -> commit metadata dict
        self._commit_meta_map = {}

    @staticmethod
    def can_parse(diff_text):
        """检测 From <40位hex hash> 特征"""
        return bool(re.search(r'^From [0-9a-f]{40} ', diff_text, re.MULTILINE))

    def parse(self, diff_text):
        """按 From <hash> 分割为 commit 块，再按 diff --git 分割为文件块"""
        self._commit_meta_map = {}

        commit_blocks = re.split(
            r'^(?=From [0-9a-f]{40} )', diff_text, flags=re.MULTILINE
        )

        file_blocks = {}
        file_order = []

        for commit_block in commit_blocks:
            commit_block = commit_block.rstrip('\n')
            if not commit_block:
                continue

            meta = self._extract_commit_meta(commit_block)

            # 在 commit 块内按 diff --git 分割出各文件
            parts = re.split(r'^(?=diff --git )', commit_block, flags=re.MULTILINE)
            parts = [p for p in parts if p.startswith('diff --git ')]

            before_count = len(file_order)
            file_blocks, file_order = self._group_file_blocks(
                parts, file_blocks, file_order
            )

            # 为本次 commit 新增的文件记录元数据
            for filepath in file_order[before_count:]:
                self._commit_meta_map[filepath] = meta

        return file_blocks, file_order

    def get_filename_from_block(self, block):
        """从 diff --git a/path b/path 提取 b/ 侧路径"""
        m = re.search(r'^diff --git a/(.+) b/(.+)$', block, re.MULTILINE)
        if m:
            return m.group(2)
        return None

    def extract_commit_metadata(self, blocks):
        """返回此文件关联的 commit 元数据"""
        if not blocks:
            return None
        block = blocks[0]
        filepath = self.get_filename_from_block(block)
        if filepath:
            return self._commit_meta_map.get(filepath)
        return None

    def _extract_commit_meta(self, block):
        """从 format-patch 邮件头中提取 commit 信息"""
        meta = {}

        m = re.match(r'^From ([0-9a-f]{40}) ', block)
        if m:
            meta['hash'] = m.group(1)

        m = re.search(r'^From: (.+)', block, re.MULTILINE)
        if m:
            meta['author'] = m.group(1).strip()

        m = re.search(r'^Date: (.+)', block, re.MULTILINE)
        if m:
            meta['date'] = m.group(1).strip()

        m = re.search(r'^Subject: (.+)', block, re.MULTILINE)
        if m:
            meta['subject'] = m.group(1).strip()

        return meta
