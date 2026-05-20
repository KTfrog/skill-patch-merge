#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补丁蒸馏工具：拆分SVN大补丁为独立小补丁，再合并目标项目中存在的文件到 need_merge.diff

用法: python distill_patches.py <原始补丁文件> [目标项目根目录]

流程:
    阶段1 - 拆分：解析大补丁，按Index分块，识别修改状态和文件类型，
            生成小补丁目录和 files_info.json
    阶段2 - 合并：读取 files_info.json，检查目标项目文件，匹配的写入 need_merge.diff
"""

import json
import os
import re
import sys


def parse_svn_diff(diff_text):
    """解析SVN diff，按文件分组所有Index块"""
    blocks = re.split(r'^(?=Index: )', diff_text, flags=re.MULTILINE)

    file_blocks = {}  # filepath -> list of blocks
    file_order = []   # 保持文件出现顺序

    for block in blocks:
        block = block.rstrip('\n')
        if not block:
            continue

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

    if is_deleted:
        change_type = "删除"
    elif is_added:
        change_type = "新增"
    elif has_diff_content:
        change_type = "修改"
    else:
        change_type = "修改"

    file_type = "二进制" if has_binary else "文本"

    return change_type, file_type


def make_patch_filename(idx, filepath):
    """生成小补丁文件名: idx-路径分隔符替换为__.diff"""
    safe_name = filepath.replace('/', '__').replace('\\', '__')
    return "{:06d}-{}.diff".format(idx, safe_name)


def main():
    if len(sys.argv) < 2:
        print("用法: {} <原始补丁文件> [目标项目根目录]".format(sys.argv[0]), file=sys.stderr)
        sys.exit(1)

    patch_file = sys.argv[1]
    target_root = sys.argv[2] if len(sys.argv) > 2 else "./"
    target_root = os.path.abspath(target_root)

    if not os.path.isfile(patch_file):
        print("错误: 补丁文件不存在 {}".format(patch_file), file=sys.stderr)
        sys.exit(1)

    # 补丁名（去掉扩展名），用作中间目录名
    patch_name = os.path.splitext(os.path.basename(patch_file))[0]
    output_dir = patch_name

    # ========== 阶段1: 拆分补丁 ==========
    print("=" * 50)
    print("阶段1: 拆分补丁")
    print("=" * 50)

    diff_text = None
    used_encoding = None
    for enc in ('utf-8', 'gbk', 'gb2312', 'latin-1'):
        try:
            with open(patch_file, 'r', encoding=enc) as f:
                diff_text = f.read()
            used_encoding = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if diff_text is None:
        print("错误: 无法读取补丁文件 {}".format(patch_file), file=sys.stderr)
        sys.exit(1)

    print("使用编码: {}".format(used_encoding))

    # 解析
    file_blocks, file_order = parse_svn_diff(diff_text)
    print("解析到 {} 个文件".format(len(file_order)))

    # 创建中间输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 处理每个文件，写出小补丁和元数据
    files_info = []
    change_stats = {}
    file_stats = {}

    for idx, filepath in enumerate(file_order, start=1):
        blocks = file_blocks[filepath]
        change_type, file_type = detect_file_info(blocks)

        change_stats[change_type] = change_stats.get(change_type, 0) + 1
        file_stats[file_type] = file_stats.get(file_type, 0) + 1

        # 写出小补丁文件
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

    # 写出 files_info.json
    json_path = os.path.join(output_dir, "files_info.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(files_info, f, ensure_ascii=False, indent=2)

    print("修改状态:")
    for t, count in sorted(change_stats.items()):
        print("  {}: {}".format(t, count))
    print("文件类型:")
    for t, count in sorted(file_stats.items()):
        print("  {}: {}".format(t, count))
    print("中间目录: {}".format(output_dir))
    print("元数据:    {}".format(json_path))

    # ========== 阶段2: 合并补丁 ==========
    print("")
    print("=" * 50)
    print("阶段2: 合并补丁")
    print("=" * 50)

    output_file = os.path.join(output_dir, "need_merge.diff")
    matched = 0
    skipped = 0
    matched_change_stats = {}
    matched_file_stats = {}
    matched_files_info = []

    with open(output_file, 'wb') as out_f:
        for i, info in enumerate(files_info):
            filepath = info['filepath']
            target_path = os.path.join(target_root, filepath)

            if os.path.exists(target_path):
                # 从磁盘读取小补丁文件，二进制追加写入
                patch_path = os.path.join(output_dir, info['patch_file'])
                with open(patch_path, 'rb') as patch_f:
                    content = patch_f.read()

                out_f.write(content)
                if content and not content.endswith(b'\n'):
                    out_f.write(b'\n')
                if i < len(files_info) - 1:
                    out_f.write(b'\n')

                print("[匹配] {} ({}, {})".format(filepath, info['change_type'], info['file_type']))
                matched += 1
                matched_change_stats[info['change_type']] = matched_change_stats.get(info['change_type'], 0) + 1
                matched_file_stats[info['file_type']] = matched_file_stats.get(info['file_type'], 0) + 1
                matched_files_info.append(info)
            else:
                # 删除未匹配的小补丁文件
                patch_path = os.path.join(output_dir, info['patch_file'])
                if os.path.isfile(patch_path):
                    os.remove(patch_path)
                print("[跳过] 目标文件不存在，已删除: {}".format(filepath))
                skipped += 1

    # 写出匹配文件的索引
    merge_json_path = os.path.join(output_dir, "files_need_merge.json")
    with open(merge_json_path, 'w', encoding='utf-8') as f:
        json.dump(matched_files_info, f, ensure_ascii=False, indent=2)
    print("匹配索引:  {}".format(merge_json_path))

    # ========== 最终统计 ==========
    print("")
    print("=" * 50)
    print("完成")
    print("=" * 50)
    print("补丁总数: {} 个文件".format(len(files_info)))
    # 拆分阶段统计
    print("--- 全部补丁 ---")
    print("修改状态:")
    for t, count in sorted(change_stats.items()):
        print("  {}: {}".format(t, count))
    print("文件类型:")
    for t, count in sorted(file_stats.items()):
        print("  {}: {}".format(t, count))
    # 合并阶段统计
    print("--- 合并结果 ---")
    print("匹配并合并: {} 个补丁".format(matched))
    if matched_change_stats:
        print("  修改状态:")
        for t, count in sorted(matched_change_stats.items()):
            print("    {}: {}".format(t, count))
        print("  文件类型:")
        for t, count in sorted(matched_file_stats.items()):
            print("    {}: {}".format(t, count))
    print("跳过: {} 个文件".format(skipped))
    print("输出文件: {}".format(output_file))


if __name__ == '__main__':
    main()
