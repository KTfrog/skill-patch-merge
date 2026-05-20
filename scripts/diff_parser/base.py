# -*- coding: utf-8 -*-
"""DiffParser 抽象基类 + 共享方法"""

from abc import ABC, abstractmethod


class ChangeType:
    """变更类型常量"""
    MODIFIED = "修改"
    ADDED = "新增"
    DELETED = "删除"


class FileType:
    """文件类型常量"""
    TEXT = "文本"
    BINARY = "二进制"


class DiffParser(ABC):
    """所有diff解析器的抽象基类"""

    @staticmethod
    @abstractmethod
    def can_parse(diff_text):
        """检查diff_text是否匹配此解析器的格式

        Args:
            diff_text: 补丁文本（通常只传前2KB用于快速检测）

        Returns:
            bool
        """
        ...

    @abstractmethod
    def parse(self, diff_text):
        """解析完整diff文本，提取各文件的修改块

        Args:
            diff_text: 完整的补丁文本

        Returns:
            (file_blocks, file_order)
            file_blocks: dict, filepath -> list of block strings
            file_order: list, 文件出现顺序
        """
        ...

    @abstractmethod
    def get_filename_from_block(self, block):
        """从单个diff块中提取文件路径

        Args:
            block: 单个diff块的文本

        Returns:
            str 或 None
        """
        ...

    def extract_commit_metadata(self, blocks):
        """提取commit元数据（仅Git format-patch覆写）"""
        return None

    def _group_file_blocks(self, blocks, file_blocks=None, file_order=None):
        """将 block 列表按文件路径分组

        Args:
            blocks: block 字符串列表
            file_blocks: 可选的已有 dict，用于跨批次累积
            file_order: 可选的已有 list，用于跨批次累积

        Returns:
            (file_blocks, file_order)
        """
        if file_blocks is None:
            file_blocks = {}
        if file_order is None:
            file_order = []

        for block in blocks:
            block = block.rstrip('\n')
            if not block:
                continue
            filepath = self.get_filename_from_block(block)
            if not filepath:
                continue
            if filepath not in file_blocks:
                file_blocks[filepath] = []
                file_order.append(filepath)
            file_blocks[filepath].append(block)

        return file_blocks, file_order

    def detect_file_info(self, blocks):
        """从文件的所有块中判断修改状态和文件类型

        支持 SVN 和 Git 两种标记体系:
        - SVN: Cannot display(二进制), ---/+++ (nonexistent)(新增/删除)
        - Git: Binary files(二进制), new file mode(新增), deleted file mode(删除)

        Returns:
            (change_type, file_type)
        """
        has_binary = False
        has_diff_content = False
        is_added = False
        is_deleted = False

        for block in blocks:
            lines = block.split('\n')

            # 二进制检测: SVN的Cannot display、Git的Binary files
            head_text = '\n'.join(lines[:10])
            if 'Cannot display' in head_text or 'Binary files' in head_text:
                has_binary = True

            has_minus_line = False
            has_plus_line = False

            for line in lines:
                if line.startswith('--- '):
                    has_minus_line = True
                    if '(nonexistent)' in line:
                        is_added = True
                elif line.startswith('+++ '):
                    has_plus_line = True
                    if '(nonexistent)' in line:
                        is_deleted = True
                elif 'new file mode' in line:
                    is_added = True
                elif 'deleted file mode' in line:
                    is_deleted = True

            if has_minus_line and has_plus_line:
                has_diff_content = True

        if is_deleted:
            change_type = ChangeType.DELETED
        elif is_added:
            change_type = ChangeType.ADDED
        elif has_diff_content:
            change_type = ChangeType.MODIFIED
        else:
            change_type = ChangeType.MODIFIED

        file_type = FileType.BINARY if has_binary else FileType.TEXT
        return change_type, file_type

    def make_patch_filename(self, idx, filepath):
        """生成小补丁文件名: 序号-路径分隔符替换为__.diff"""
        safe_name = filepath.replace('/', '__').replace('\\', '__')
        return "{:06d}-{}.diff".format(idx, safe_name)
