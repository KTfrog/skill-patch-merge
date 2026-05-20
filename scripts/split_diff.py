#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
split_diff.py - 拆分SVN大补丁为独立小补丁

用法:
    python3 split_diff.py <补丁文件> [输出目录]

功能:
    1. 读取一个大而全的SVN补丁文件
    2. 创建以补丁名命名的目录
    3. 将每个文件的改动提取为独立的小补丁
    4. 标记每个文件的修改状态(修改/新增/删除)和文件类型(文本/二进制)
    5. 将元数据写入 files_info.json
"""

import json
import os
import re
import sys


def parse_svn_diff(diff_text):
    """解析SVN diff，按文件分组所有Index块"""
    # 按 "Index: " 分割，保留每个块的完整内容
    blocks = re.split(r'^(?=Index: )', diff_text, flags=re.MULTILINE)

    file_blocks = {}  # filepath -> list of blocks (同一文件可能有多个Index块)
    file_order = []   # 保持文件出现顺序

    for block in blocks:
        block = block.rstrip('\n')
        if not block:
            continue

        # 提取文件路径
        m = re.match(r'^Index: (.+)', block)
        if not m:
            continue

        filepath = m.group(1).strip()

        if filepath not in file_blocks:
            file_blocks[filepath] = []
            file_order.append(filepath)
        file_blocks[filepath].append(block)

    return file_blocks, file_order


def detect_file_info(blocks):
    """
    从文件的所有Index块中判断修改状态和文件类型

    返回: (change_type, file_type)
        change_type: "修改" | "新增" | "删除"
        file_type:   "文本" | "二进制"
    """
    has_binary = False
    has_diff_content = False
    is_added = False
    is_deleted = False

    for block in blocks:
        lines = block.split('\n')
        has_cannot_display = any('Cannot display' in l for l in lines[:5])
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

        if has_minus_line and has_plus_line:
            has_diff_content = True
        if has_cannot_display:
            has_binary = True

    # change_type: 新增/删除/修改
    if is_deleted:
        change_type = "删除"
    elif is_added:
        change_type = "新增"
    elif has_diff_content:
        change_type = "修改"
    else:
        # 纯二进制无---/+++行，默认为修改
        change_type = "修改"

    # file_type: 文本/二进制
    file_type = "二进制" if has_binary else "文本"

    return change_type, file_type


def make_patch_filename(idx, filepath):
    """生成小补丁文件名: idx-路径分隔符替换为__.diff"""
    safe_name = filepath.replace('/', '__').replace('\\', '__')
    return f"{idx:06d}-{safe_name}.diff"


def split_diff(patch_file, output_dir=None):
    """主函数：拆分补丁文件"""
    # 补丁名（去掉扩展名）
    patch_name = os.path.splitext(os.path.basename(patch_file))[0]

    # 输出目录默认为补丁名
    if output_dir is None:
        output_dir = patch_name

    # 读取补丁文件
    # 尝试多种编码，优先UTF-8
    diff_text = None
    for enc in ('utf-8', 'gbk', 'gb2312', 'latin-1'):
        try:
            with open(patch_file, 'r', encoding=enc) as f:
                diff_text = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if diff_text is None:
        print(f"错误: 无法读取补丁文件 {patch_file}", file=sys.stderr)
        sys.exit(1)

    # 解析
    file_blocks, file_order = parse_svn_diff(diff_text)

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 处理每个文件
    files_info = []
    for idx, filepath in enumerate(file_order, start=1):
        blocks = file_blocks[filepath]
        change_type, file_type = detect_file_info(blocks)

        # 合并所有块写入小补丁
        patch_filename = make_patch_filename(idx, filepath)
        patch_path = os.path.join(output_dir, patch_filename)

        combined = '\n'.join(blocks) + '\n'
        with open(patch_path, 'w', encoding='utf-8') as f:
            f.write(combined)

        files_info.append({
            "idx": idx,
            "filepath": filepath,
            "change_type": change_type,
            "file_type": file_type,
            "patch_file": patch_filename,
        })

    # 写入 files_info.json
    json_path = os.path.join(output_dir, "files_info.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(files_info, f, ensure_ascii=False, indent=2)

    # 统计
    change_stats = {}
    file_stats = {}
    for info in files_info:
        change_stats[info['change_type']] = change_stats.get(info['change_type'], 0) + 1
        file_stats[info['file_type']] = file_stats.get(info['file_type'], 0) + 1

    print(f"拆分完成: {len(files_info)} 个文件")
    print("修改状态:")
    for t, count in sorted(change_stats.items()):
        print(f"  {t}: {count}")
    print("文件类型:")
    for t, count in sorted(file_stats.items()):
        print(f"  {t}: {count}")
    print(f"输出目录: {output_dir}")
    print(f"元数据:   {json_path}")

    return files_info


def main():
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <补丁文件> [输出目录]", file=sys.stderr)
        sys.exit(1)

    patch_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(patch_file):
        print(f"错误: 文件不存在 {patch_file}", file=sys.stderr)
        sys.exit(1)

    split_diff(patch_file, output_dir)


if __name__ == '__main__':
    main()
