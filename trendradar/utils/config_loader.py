# coding=utf-8
"""
配置加载工具 - 支持三级优先级加载配置

优先级（从高到低）：
1. config/config.yaml - 主配置文件
2. config/hide_config.yaml - 隐藏配置文件（用于敏感信息）
3. 环境变量
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_tiered_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    加载三级优先级配置

    Args:
        project_root: 项目根目录，默认为当前文件的上两层目录

    Returns:
        合并后的配置字典
    """
    if project_root is None:
        current_file = Path(__file__)
        project_root = current_file.parent.parent

    # 1. 加载主配置文件
    main_config_path = project_root / "config" / "config.yaml"
    main_config = {}

    if main_config_path.exists():
        with open(main_config_path, "r", encoding="utf-8") as f:
            main_config = yaml.safe_load(f) or {}
    else:
        print(f"警告: 未找到主配置文件 {main_config_path}")

    # 2. 加载隐藏配置文件
    hide_config_path = project_root / "config" / "hide_config.yaml"
    hide_config = {}

    if hide_config_path.exists():
        with open(hide_config_path, "r", encoding="utf-8") as f:
            hide_config = yaml.safe_load(f) or {}
    else:
        print(f"提示: 未找到隐藏配置文件 {hide_config_path}")

    # 3. 合并配置（hide_config 覆盖 main_config）
    merged_config = merge_configs(main_config, hide_config)

    # 4. 加载环境变量作为第三级
    env_config = load_env_config()
    merged_config = merge_configs(merged_config, env_config)

    return merged_config


def merge_configs(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    深度合并两个配置字典

    Args:
        base_config: 基础配置
        override_config: 覆盖配置

    Returns:
        合并后的配置
    """
    result = base_config.copy()

    for key, value in override_config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # 递归合并嵌套字典
            result[key] = merge_configs(result[key], value)
        else:
            # 直接覆盖
            result[key] = value

    return result


def load_env_config() -> Dict[str, Any]:
    """
    加载环境变量配置

    只加载远程存储相关的环境变量

    Returns:
        环境变量配置字典
    """
    env_mappings = {
        # 远程存储配置
        "S3_ENDPOINT_URL": ["storage", "remote", "endpoint_url"],
        "S3_BUCKET_NAME": ["storage", "remote", "bucket_name"],
        "S3_ACCESS_KEY_ID": ["storage", "remote", "access_key_id"],
        "S3_SECRET_ACCESS_KEY": ["storage", "remote", "secret_access_key"],
        "S3_REGION": ["storage", "remote", "region"],

        # 可选：其他可能需要环境变量覆盖的配置
        "STORAGE_RETENTION_DAYS": ["storage", "local", "retention_days"],
        "REMOTE_RETENTION_DAYS": ["storage", "remote", "retention_days"],
        "TIMEZONE": ["app", "timezone"],
    }

    env_config = {}

    for env_var, config_path in env_mappings.items():
        env_value = os.environ.get(env_var)
        if env_value is not None:
            # 构建嵌套字典结构
            current = env_config
            for key in config_path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # 设置最终值（类型转换）
            final_key = config_path[-1]
            if env_var.endswith("_DAYS"):
                # 保留天数转换为整数
                try:
                    current[final_key] = int(env_value)
                except ValueError:
                    print(f"警告: 环境变量 {env_var} 的值 '{env_value}' 不是有效的整数")
                    current[final_key] = env_value
            else:
                current[final_key] = env_value

    return env_config


def get_remote_storage_config(config: Dict[str, Any]) -> Dict[str, str]:
    """
    获取远程存储配置（整合后的配置）

    Args:
        config: 完整的配置字典

    Returns:
        远程存储配置字典
    """
    storage_config = config.get("storage", {})
    remote_config = storage_config.get("remote", {})

    # 确保所有必要的字段都存在
    return {
        "endpoint_url": remote_config.get("endpoint_url", ""),
        "bucket_name": remote_config.get("bucket_name", ""),
        "access_key_id": remote_config.get("access_key_id", ""),
        "secret_access_key": remote_config.get("secret_access_key", ""),
        "region": remote_config.get("region", ""),
    }


def validate_remote_config(remote_config: Dict[str, str]) -> bool:
    """
    验证远程存储配置是否完整

    Args:
        remote_config: 远程存储配置

    Returns:
        是否配置完整
    """
    required_fields = ["endpoint_url", "bucket_name", "access_key_id", "secret_access_key"]

    for field in required_fields:
        if not remote_config.get(field):
            return False

    return True


def get_missing_remote_fields(remote_config: Dict[str, str]) -> list:
    """
    获取缺失的远程存储配置字段

    Args:
        remote_config: 远程存储配置

    Returns:
        缺失的字段列表
    """
    required_fields = ["endpoint_url", "bucket_name", "access_key_id", "secret_access_key"]
    missing = []

    for field in required_fields:
        if not remote_config.get(field):
            missing.append(field)

    return missing


# 兼容性函数，用于替换原有的 load_config
def load_config_with_tiers(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置（支持三级优先级）

    Args:
        config_path: 配置文件路径（可选，仅用于兼容性）

    Returns:
        合并后的配置字典
    """
    # 如果提供了 config_path，尝试加载它
    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}
    else:
        config = load_tiered_config()

    return config