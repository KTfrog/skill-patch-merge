#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补丁合并工具：读取 files_info.json，检查目标项目中存在的文件，合并对应补丁到 need_merge.diff。

用法: python merge_patches.py [目标项目根目录]
"""

import json
import os
import sys


def main():
    # 目标项目根目录，默认当前目录
    target_root = sys.argv[1] if len(sys.argv) > 1 else "./"
    target_root = os.path.abspath(target_root)

    # 脚本所在目录，364302-head 应与其同级
    script_dir = os.path.dirname(os.path.abspath(__file__))
    patch_dir = os.path.join(script_dir, "364302-head")
    json_path = os.path.join(patch_dir, "files_info.json")
    output_file = os.path.join(target_root, "need_merge.diff")

    if not os.path.exists(json_path):
        print("错误: 找不到补丁索引文件 {}".format(json_path))
        sys.exit(1)

    # 读取补丁索引
    with open(json_path, 'r', encoding='utf-8') as f:
        file_infos = json.load(f)

    matched = 0
    skipped = 0
    merged_contents = []

    for info in file_infos:
        filepath = info['filepath']
        patch_file = info['patch_file']

        target_path = os.path.join(target_root, filepath)
        patch_path = os.path.join(patch_dir, patch_file)

        if os.path.exists(target_path):
            if os.path.exists(patch_path):
                with open(patch_path, 'rb') as f:
                    content = f.read()
                merged_contents.append((filepath, content))
                print("[匹配] {}".format(filepath))
                matched += 1
            else:
                print("[警告] 补丁文件不存在: {}".format(patch_file))
                skipped += 1
        else:
            print("[跳过] 目标文件不存在: {}".format(filepath))
            skipped += 1

    # 写入 need_merge.diff
    with open(output_file, 'wb') as f:
        for i, (filepath, content) in enumerate(merged_contents):
            f.write(content)
            # 补丁之间加换行分隔
            if content and not content.endswith(b'\n'):
                f.write(b'\n')
            if i < len(merged_contents) - 1:
                f.write(b'\n')

    print("\n=== 完成 ===")
    print("匹配并合并: {} 个补丁".format(matched))
    print("跳过: {} 个文件".format(skipped))
    print("输出文件: {}".format(output_file))


if __name__ == '__main__':
    main()
