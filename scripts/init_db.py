#!/usr/bin/env python3
"""
数据库初始化脚本
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.utils.database import init_database

if __name__ == "__main__":
    print("正在初始化数据库...")
    init_database()
    print("完成！")
