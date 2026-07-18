"""python -m hermes_universal 入口"""
import sys
import os

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hermes_universal.cli import main
main()
