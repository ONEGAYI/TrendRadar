#!/usr/bin/env python3
# coding=utf-8
"""
手动从远程存储拉取新闻数据的脚本

使用方法:
  python pull_remote_news.py [选项]

示例:
  # 拉取最近7天的数据
  python pull_remote_news.py --days 7

  # 拉取指定日期范围的数据
  python pull_remote_news.py --start 2025-12-10 --end 2025-12-17

  # 仅显示远程存储状态
  python pull_remote_news.py --status

  # 强制重新拉取已存在的数据
  python pull_remote_news.py --days 7 --force
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
import yaml


def load_config():
    """加载配置文件（支持三级优先级）"""
    try:
        # 尝试使用新的配置加载器
        sys.path.insert(0, str(Path(__file__).parent))
        from trendradar.utils.config_loader import load_tiered_config, get_remote_storage_config

        # 使用三级优先级加载配置，显式传入项目根目录
        project_root = Path(__file__).parent
        config = load_tiered_config(project_root=project_root)
        return config
    except ImportError:
        # 回退到原有的加载方式
        print("⚠️ 警告: 使用传统配置加载方式")
        config_path = Path("config/config.yaml")
        if not config_path.exists():
            print("❌ 错误: 找不到配置文件 config/config.yaml")
            print("请确保在项目根目录下运行此脚本")
            sys.exit(1)

        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)


def check_remote_config(config):
    """检查远程存储配置（使用三级优先级配置）"""
    try:
        # 使用新的配置加载器获取远程配置
        from trendradar.utils.config_loader import get_remote_storage_config, validate_remote_config, get_missing_remote_fields

        remote_config = get_remote_storage_config(config)

        if validate_remote_config(remote_config):
            return True
        else:
            missing_fields = get_missing_remote_fields(remote_config)
            print("❌ 错误: 远程存储配置不完整")
            print(f"缺少字段: {', '.join(missing_fields)}")
            print("\n配置优先级:")
            print("  1. config/config.yaml")
            print("  2. config/hide_config.yaml")
            print("  3. 环境变量")
            print("\n请在任一配置源中提供缺少的字段")
            return False

    except ImportError:
        # 回退到原有的检查方式
        print("⚠️ 警告: 使用传统配置检查方式")
        import os

        storage_config = config.get("storage", {})
        remote_config = storage_config.get("remote", {})

        # 检查必要的配置项（配置文件或环境变量）
        field_env_map = {
            "endpoint_url": "S3_ENDPOINT_URL",
            "bucket_name": "S3_BUCKET_NAME",
            "access_key_id": "S3_ACCESS_KEY_ID",
            "secret_access_key": "S3_SECRET_ACCESS_KEY"
        }

        missing_fields = []

        for field, env_var in field_env_map.items():
            # 检查配置文件或环境变量
            if not remote_config.get(field) and not os.environ.get(env_var):
                missing_fields.append(field)

        if missing_fields:
            print("❌ 错误: 远程存储配置不完整")
            print(f"缺少字段: {', '.join(missing_fields)}")
            print("\n请检查 config/config.yaml 或设置环境变量:")
            for field in missing_fields:
                env_var = field.upper()
                print(f"  - {env_var}")
            return False

        return True


def show_storage_status():
    """显示存储状态"""
    try:
        from trendradar.storage import get_storage_manager

        print("\n📊 存储状态检查")
        print("=" * 50)

        # 加载配置
        config = load_config()
        storage_config = config.get("storage", {})
        pull_config = storage_config.get("pull", {})

        # 创建存储管理器
        manager = get_storage_manager(
            backend_type=storage_config.get("backend", "auto"),
            data_dir=storage_config.get("local", {}).get("data_dir", "output"),
            remote_config=storage_config.get("remote", {}),
            pull_enabled=pull_config.get("enabled", False),
            pull_days=pull_config.get("days", 7),
            timezone=config.get("app", {}).get("timezone", "Asia/Shanghai")
        )

        # 使用 MCP 工具获取状态
        try:
            sys.path.insert(0, str(Path(__file__).parent / "mcp_server"))
            from mcp_server.tools.storage_sync import StorageSyncTools

            storage_tools = StorageSyncTools()
            status = storage_tools.get_storage_status()

            print("\n📋 本地存储:")
            local_status = status.get("local", {})
            print(f"  - 数据目录: {local_status.get('data_dir', 'N/A')}")
            print(f"  - 可用日期数: {local_status.get('date_count', 0)}")
            if local_status.get("date_range"):
                dr = local_status["date_range"]
                print(f"  - 日期范围: {dr.get('start', 'N/A')} 至 {dr.get('end', 'N/A')}")

            print("\n☁️ 远程存储:")
            remote_status = status.get("remote", {})
            print(f"  - 已配置: {'是' if remote_status.get('configured') else '否'}")
            if remote_status.get("configured"):
                print(f"  - 服务端点: {remote_status.get('endpoint_url', 'N/A')}")
                print(f"  - 存储桶: {remote_status.get('bucket_name', 'N/A')}")
                print(f"  - 可用日期数: {remote_status.get('date_count', 0)}")
                if remote_status.get("date_range"):
                    dr = remote_status["date_range"]
                    print(f"  - 日期范围: {dr.get('start', 'N/A')} 至 {dr.get('end', 'N/A')}")

            print("\n🔄 拉取配置:")
            pull_status = status.get("pull", {})
            print(f"  - 自动拉取: {'启用' if pull_status.get('enabled') else '禁用'}")
            print(f"  - 拉取天数: {pull_status.get('days', 0)}")

        except ImportError:
            print("⚠️ 警告: 无法导入 MCP 工具，显示基础状态")
            print(f"存储后端: {manager.backend_name}")
            print(f"本地目录: {manager.data_dir}")

        return True

    except Exception as e:
        print(f"❌ 获取存储状态失败: {e}")
        return False


def pull_from_remote(days=7, date_range=None, force=False):
    """从远程存储拉取数据"""
    try:
        print(f"\n🚀 开始从远程拉取数据")
        print("=" * 50)

        # 加载配置
        config = load_config()

        # 检查远程配置
        if not check_remote_config(config):
            return False

        # 使用 MCP 工具进行拉取
        sys.path.insert(0, str(Path(__file__).parent / "mcp_server"))
        from mcp_server.tools.storage_sync import StorageSyncTools

        storage_tools = StorageSyncTools()

        # 执行拉取
        if date_range:
            # 如果指定了日期范围，计算天数
            start = datetime.strptime(date_range["start"], "%Y-%m-%d")
            end = datetime.strptime(date_range["end"], "%Y-%m-%d")
            days = (end - start).days + 1
            print(f"拉取日期范围: {date_range['start']} 至 {date_range['end']} ({days}天)")
        else:
            print(f"拉取最近 {days} 天的数据")

        if force:
            print("⚠️ 注意: 强制模式将覆盖本地已存在的数据")

        # 调用同步方法
        result = storage_tools.sync_from_remote(days=days)

        # 显示结果
        if result.get("success"):
            print("\n✅ 拉取成功!")
            print(f"  - 同步文件数: {result.get('synced_files', 0)}")
            synced_dates = result.get("synced_dates", [])
            if synced_dates:
                print(f"  - 同步日期: {', '.join(synced_dates)}")

            skipped_dates = result.get("skipped_dates", [])
            if skipped_dates:
                print(f"  - 跳过日期: {', '.join(skipped_dates)} (本地已存在)")

            failed_dates = result.get("failed_dates", [])
            if failed_dates:
                print(f"  - 失败日期: {', '.join([d['date'] for d in failed_dates])}")
                for item in failed_dates:
                    print(f"    - {item['date']}: {item.get('error', '未知错误')}")
        else:
            print("\n❌ 拉取失败!")
            error = result.get("error", {})
            print(f"  - 错误代码: {error.get('code', 'UNKNOWN')}")
            print(f"  - 错误信息: {error.get('message', '未知错误')}")
            suggestion = error.get("suggestion")
            if suggestion:
                print(f"  - 建议: {suggestion}")
            return False

        return True

    except Exception as e:
        print(f"❌ 拉取过程出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def list_available_dates():
    """列出可用的日期"""
    try:
        print("\n📅 可用日期列表")
        print("=" * 50)

        sys.path.insert(0, str(Path(__file__).parent / "mcp_server"))
        from mcp_server.tools.storage_sync import StorageSyncTools

        storage_tools = StorageSyncTools()
        result = storage_tools.list_available_dates()

        if result.get("success"):
            print("\n本地可用日期:")
            local_dates = result.get("local_dates", [])
            if local_dates:
                for date in local_dates:
                    print(f"  - {date}")
            else:
                print("  (无)")

            print("\n远程可用日期:")
            remote_dates = result.get("remote_dates", [])
            if remote_dates:
                for date in remote_dates:
                    print(f"  - {date}")
            else:
                print("  (无)")
        else:
            error = result.get("error", {})
            print(f"❌ 获取日期列表失败: {error.get('message', '未知错误')}")

    except Exception as e:
        print(f"❌ 查询可用日期失败: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="手动从远程存储拉取新闻数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --days 7                 # 拉取最近7天的数据
  %(prog)s --start 2025-12-10 --end 2025-12-17  # 拉取指定范围
  %(prog)s --status                 # 显示存储状态
  %(prog)s --list-dates             # 列出可用日期
  %(prog)s --days 7 --force         # 强制重新拉取
        """
    )

    # 拉取选项
    pull_group = parser.add_argument_group("拉取选项")
    pull_group.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="拉取最近 N 天的数据 (默认: 7)"
    )
    pull_group.add_argument(
        "--start",
        type=str,
        help="开始日期 (YYYY-MM-DD)"
    )
    pull_group.add_argument(
        "--end",
        type=str,
        help="结束日期 (YYYY-MM-DD)"
    )
    pull_group.add_argument(
        "--force", "-f",
        action="store_true",
        help="强制覆盖本地已存在的数据"
    )

    # 查询选项
    query_group = parser.add_argument_group("查询选项")
    query_group.add_argument(
        "--status", "-s",
        action="store_true",
        help="显示存储状态"
    )
    query_group.add_argument(
        "--list-dates", "-l",
        action="store_true",
        help="列出所有可用的日期"
    )

    args = parser.parse_args()

    # 检查是否在正确的目录
    if not Path("config/config.yaml").exists():
        print("❌ 错误: 请在项目根目录下运行此脚本")
        print("当前目录应包含 config/config.yaml 文件")
        sys.exit(1)

    # 执行相应操作
    success = True

    if args.status:
        # 显示存储状态
        success = show_storage_status()
    elif args.list_dates:
        # 列出可用日期
        list_available_dates()
    else:
        # 拉取数据
        date_range = None
        if args.start and args.end:
            date_range = {"start": args.start, "end": args.end}
        elif args.start or args.end:
            print("❌ 错误: --start 和 --end 必须同时使用")
            sys.exit(1)

        success = pull_from_remote(
            days=args.days,
            date_range=date_range,
            force=args.force
        )

    # 根据结果设置退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()