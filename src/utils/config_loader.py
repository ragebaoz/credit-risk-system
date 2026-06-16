"""
配置加载工具
"""
import yaml
import os
from typing import Dict, Any

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")


def load_yaml(filename: str) -> Dict[str, Any]:
    """加载 YAML 配置文件"""
    path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_weights_config() -> Dict[str, Any]:
    """获取权重配置"""
    return load_yaml("weights.yaml")


def get_rules_config() -> Dict[str, Any]:
    """获取规则配置"""
    return load_yaml("rules.yaml")
