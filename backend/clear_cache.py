#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清除 Python 缓存并重启服务
"""

import os
import shutil
import subprocess
import sys

def clear_pycache():
    """清除所有 __pycache__ 目录和 .pyc 文件"""
    print("正在清除 Python 缓存...")

    root_dir = os.path.dirname(os.path.abspath(__file__))

    # 清除 __pycache__ 目录
    for root, dirs, files in os.walk(root_dir):
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            try:
                shutil.rmtree(cache_dir)
                print(f"已删除: {cache_dir}")
            except Exception as e:
                print(f"删除失败 {cache_dir}: {e}")

        # 清除 .pyc 文件
        for file in files:
            if file.endswith(".pyc"):
                pyc_file = os.path.join(root, file)
                try:
                    os.remove(pyc_file)
                    print(f"已删除: {pyc_file}")
                except Exception as e:
                    print(f"删除失败 {pyc_file}: {e}")

    print("Python 缓存清除完成！")

if __name__ == "__main__":
    clear_pycache()
