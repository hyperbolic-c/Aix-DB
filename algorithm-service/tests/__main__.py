"""
测试框架主入口

用法:
    python -m tests                    # 运行交互式CLI
    python -m tests.api --gold         # 运行API测试
    python -m tests.gold --limit 10    # 运行Gold用例测试
"""

import sys
import asyncio


def run_cli():
    """运行CLI"""
    from tests.cli.interactive_shell import main
    asyncio.run(main())


def run_api_test():
    """运行API测试"""
    from tests.test_api import main
    asyncio.run(main())


def run_gold_test():
    """运行Gold测试"""
    from tests.test_gold_cases import main
    main()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        # 移除子命令，保留其他参数
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        
        if command == "api":
            run_api_test()
        elif command == "gold":
            run_gold_test()
        else:
            print(f"未知命令: {command}")
            print("可用命令: cli, api, gold")
    else:
        # 默认运行CLI
        run_cli()
