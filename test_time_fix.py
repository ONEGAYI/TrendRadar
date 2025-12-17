#!/usr/bin/env python3
# coding=utf-8
"""
测试时间戳修复效果
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from trendradar.utils.time_parser import parse_hhmm_time

def test_time_parsing():
    """测试时间解析功能"""
    print("测试时间戳解析功能：")
    print("-" * 40)

    test_cases = [
        ("09-00", "上午9点"),
        ("13-44", "下午13点44分"),
        ("23-59", "晚上11点59分"),
        ("00-00", "午夜0点"),
        ("", "空字符串"),
        ("invalid", "无效格式"),
    ]

    for time_str, description in test_cases:
        timestamp = parse_hhmm_time(time_str)
        if timestamp > 0:
            from datetime import datetime
            dt = datetime.fromtimestamp(timestamp)
            print(f"{description:10} ({time_str:5}) -> {timestamp} -> {dt.strftime('%H:%M')}")
        else:
            print(f"{description:10} ({time_str:5}) -> 解析失败")

def test_time_comparison():
    """测试时间比较功能"""
    print("\n测试时间比较逻辑：")
    print("-" * 40)

    times = ["09-00", "13-44", "23-59", "00-00"]

    print("直接字符串比较（错误）：")
    for i in range(len(times)):
        for j in range(len(times)):
            if times[i] > times[j]:
                print(f"  {times[i]} > {times[j]}")

    print("\n解析后比较（正确）：")
    for i in range(len(times)):
        for j in range(len(times)):
            ts1 = parse_hhmm_time(times[i])
            ts2 = parse_hhmm_time(times[j])
            if ts1 > 0 and ts2 > 0 and ts1 > ts2:
                print(f"  {times[i]} > {times[j]}")

if __name__ == "__main__":
    test_time_parsing()
    test_time_comparison()

    print("\n" + "=" * 40)
    print("如果看到正确的时间比较结果，说明修复生效！")