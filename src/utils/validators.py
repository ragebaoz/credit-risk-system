"""
数据验证工具
"""
import re
from typing import Optional


def validate_credit_code(code: str) -> bool:
    """验证统一社会信用代码（18位）"""
    if not code or len(code) != 18:
        return False
    pattern = r'^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}$'
    return bool(re.match(pattern, code.upper()))


def validate_phone(phone: str) -> bool:
    """验证手机号码"""
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


def safe_float(value, default: float = 0.0) -> float:
    """安全转换为浮点数"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    """安全转换为整数"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
