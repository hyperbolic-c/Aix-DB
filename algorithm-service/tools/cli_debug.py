#!/usr/bin/env python3
"""
算法服务调试工具 - 入口脚本

提供交互式终端，用于调试算法服务的Text2SQL功能

用法:
    python tools/cli_debug.py                    # 启动交互式终端
    python tools/cli_debug.py "查询问题"          # 单次查询
    python tools/cli_debug.py --host http://localhost:8002
    python tools/cli_debug.py --debug
    python tools/cli_debug.py --raw

命令:
    /quit, /q       - 退出程序
    /help, /h       - 显示帮助
    /debug          - 切换调试模式
    /raw            - 切换原始JSON显示模式
    /clear          - 清屏
    /health         - 检查服务健康状态
"""

import sys
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.cli import InteractiveCLI, Config


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="算法服务调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                           # 启动交互式终端
  %(prog)s "查询最近7天的工单总量"     # 单次查询
  %(prog)s --host http://localhost:8002
  %(prog)s --debug
  %(prog)s --raw

命令（在交互模式下使用）:
  /quit, /q       退出程序
  /help, /h       显示帮助
  /debug          切换调试模式
  /raw            切换原始JSON显示模式
  /clear          清屏
  /health         检查服务健康状态
        """
    )
    
    parser.add_argument(
        "question",
        nargs="?",
        help="要查询的问题（如果不提供则进入交互模式）"
    )
    
    parser.add_argument(
        "--host",
        default="http://localhost:8002/api/v1",
        help="算法服务地址（默认: http://localhost:8002/api/v1）"
    )
    
    parser.add_argument(
        "--db-path",
        default="/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db",
        help="数据库路径"
    )
    
    parser.add_argument(
        "--db-type",
        default="sqlite",
        help="数据库类型（默认: sqlite）"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )
    
    parser.add_argument(
        "--raw",
        action="store_true",
        help="显示原始JSON数据"
    )
    
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="禁用颜色输出"
    )
    
    args = parser.parse_args()
    
    # 创建配置
    config = Config(
        host=args.host,
        db_path=args.db_path,
        db_type=args.db_type,
        debug=args.debug,
        raw_mode=args.raw,
    )
    
    # 创建CLI
    cli = InteractiveCLI(config)
    
    # 运行
    if args.question:
        # 单次查询模式
        cli.run_single(args.question)
    else:
        # 交互式模式
        cli.run()


if __name__ == "__main__":
    main()
