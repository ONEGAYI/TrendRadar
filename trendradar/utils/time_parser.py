# coding=utf-8
"""
时间解析工具

专门处理 HH-MM 格式的时间戳，解决数据库存储格式与期望格式不匹配的问题。
"""

from datetime import datetime, date, time
from typing import Union, Optional
import re


def parse_hhmm_time(time_str: str) -> int:
    """
    将 HH-MM 格式的时间字符串转换为 Unix 时间戳

    Args:
        time_str: HH-MM 格式的时间字符串（如 "13-44"）

    Returns:
        int: Unix 时间戳
    """
    if not time_str:
        return 0

    try:
        # 支持多种分隔符：HH-MM, HH:MM, HHMM
        if '-' in time_str:
            parts = time_str.split('-')
        elif ':' in time_str:
            parts = time_str.split(':')
        elif len(time_str) == 4:
            parts = [time_str[:2], time_str[2:]]
        else:
            # 无法解析的格式
            return 0

        if len(parts) != 2:
            return 0

        hour = int(parts[0])
        minute = int(parts[1])

        # 验证时间范围
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return 0

        # 创建今天指定时间的 datetime 对象
        today = date.today()
        dt = datetime.combine(today, time(hour, minute))

        # 返回 Unix 时间戳
        return int(dt.timestamp())

    except (ValueError, TypeError):
        # 解析失败返回 0
        return 0


def format_hhmm_time(timestamp: Union[int, str, datetime]) -> str:
    """
    将各种格式的时间转换为 HH-MM 格式

    Args:
        timestamp: 可以是 Unix 时间戳（int）、HH-MM 字符串或 datetime 对象

    Returns:
        str: HH-MM 格式的时间字符串
    """
    if isinstance(timestamp, datetime):
        # 已经是 datetime 对象
        return timestamp.strftime("%H-%M")
    elif isinstance(timestamp, int):
        # Unix 时间戳
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%H-%M")
        except (ValueError, OSError):
            return "00-00"  # 无效时间戳
    elif isinstance(timestamp, str):
        # 字符串格式，检查是否已经是 HH-MM 格式
        if re.match(r'^\d{1,2}-\d{1,2}$', timestamp):
            return timestamp
        elif ':' in timestamp:
            # HH:MM 格式，转换为 HH-MM
            return timestamp.replace(':', '-')
        else:
            # 尝试作为 Unix 时间戳解析
            try:
                ts = int(timestamp)
                dt = datetime.fromtimestamp(ts)
                return dt.strftime("%H-%M")
            except (ValueError, OSError):
                return timestamp  # 返回原字符串
    else:
        return "00-00"


def safe_parse_time(time_value: Union[str, int, datetime, None]) -> datetime:
    """
    安全地解析时间值为 datetime 对象

    Args:
        time_value: 各种格式的时间值

    Returns:
        datetime: 解析后的 datetime 对象，失败则返回当前时间
    """
    if time_value is None:
        return datetime.now()

    if isinstance(time_value, datetime):
        return time_value

    if isinstance(time_value, int):
        # Unix 时间戳
        try:
            return datetime.fromtimestamp(time_value)
        except (ValueError, OSError):
            return datetime.now()

    if isinstance(time_value, str):
        # 尝试解析 HH-MM 格式
        timestamp = parse_hhmm_time(time_value)
        if timestamp > 0:
            return datetime.fromtimestamp(timestamp)

        # 尝试解析其他格式
        try:
            # 尝试作为 Unix 时间戳
            return datetime.fromtimestamp(int(time_value))
        except (ValueError, OSError):
            pass

        # 尝试解析标准时间格式
        formats = ["%H:%M", "%H-%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        for fmt in formats:
            try:
                return datetime.strptime(time_value, fmt)
            except ValueError:
                continue

    # 所有解析都失败，返回当前时间
    return datetime.now()


def convert_time_for_db(time_value: Union[datetime, int, str]) -> str:
    """
    将时间值转换为数据库存储格式（HH-MM）

    Args:
        time_value: 各种格式的时间值

    Returns:
        str: HH-MM 格式的字符串，用于数据库存储
    """
    return format_hhmm_time(time_value)


def convert_time_from_db(time_str: str) -> datetime:
    """
    从数据库读取的时间字符串转换为 datetime 对象

    Args:
        time_str: 数据库中的时间字符串（HH-MM 格式）

    Returns:
        datetime: datetime 对象
    """
    timestamp = parse_hhmm_time(time_str)
    if timestamp > 0:
        return datetime.fromtimestamp(timestamp)
    else:
        # 如果解析失败，返回当前时间
        return datetime.now()