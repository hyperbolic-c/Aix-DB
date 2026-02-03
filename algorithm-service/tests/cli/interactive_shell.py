"""
交互式Shell

提供交互式命令行界面
"""

import asyncio
import shlex
from typing import List

from .commands import CommandHandler


class InteractiveShell:
    """交互式Shell"""
    
    def __init__(self):
        self.handler = CommandHandler()
        self.running = False
        
    def parse_command(self, input_line: str) -> tuple:
        """
        解析命令
        
        Returns:
            (command, args)
        """
        parts = shlex.split(input_line.strip())
        if not parts:
            return None, []
        return parts[0], parts[1:]
        
    async def execute_command(self, command: str, args: List[str]):
        """执行命令"""
        if command == "connect":
            if args:
                self.handler.set_base_url(args[0])
            else:
                print("用法: connect <url>")
                
        elif command == "load-competition":
            self.handler.load_competition()
            
        elif command == "fixtures":
            self.handler.show_fixtures()
            
        elif command == "case":
            if args:
                try:
                    case_id = int(args[0])
                    self.handler.show_case(case_id)
                except ValueError:
                    print("用法: case <id>")
            else:
                print("用法: case <id>")
                
        elif command == "inspect":
            if args:
                try:
                    case_id = int(args[0])
                    self.handler.inspect_case(case_id)
                except ValueError:
                    print("用法: inspect <id>")
            else:
                print("用法: inspect <id>")
                
        elif command == "test":
            if args:
                try:
                    case_id = int(args[0])
                    await self.handler.test_case(case_id)
                except ValueError:
                    print("用法: test <id>")
            else:
                print("用法: test <id>")
                
        elif command == "test-custom":
            if args:
                question = " ".join(args)
                await self.handler.test_custom(question)
            else:
                print('用法: test-custom "问题"')
                
        elif command == "test-suite":
            level = None
            limit = None
            
            # 解析参数
            i = 0
            while i < len(args):
                if args[i] == "--level" and i + 1 < len(args):
                    level = int(args[i + 1])
                    i += 2
                elif args[i] == "--limit" and i + 1 < len(args):
                    limit = int(args[i + 1])
                    i += 2
                elif args[i].isdigit():
                    level = int(args[i])
                    i += 1
                else:
                    i += 1
                    
            await self.handler.test_suite(level=level, limit=limit)
            
        elif command == "help":
            self.handler.show_help()
            
        elif command == "exit" or command == "quit":
            self.running = False
            print("再见!")
            
        elif command:
            print(f"未知命令: {command}")
            print("输入 'help' 查看可用命令")
            
    async def run(self):
        """运行Shell"""
        print("\n" + "=" * 60)
        print("算法测试 CLI v1.0")
        print("=" * 60)
        print("\n输入 'help' 查看可用命令，'exit' 退出\n")
        
        self.running = True
        
        while self.running:
            try:
                # 读取输入
                user_input = input("algorithm-test> ").strip()
                
                if not user_input:
                    continue
                    
                # 解析命令
                command, args = self.parse_command(user_input)
                
                if command:
                    # 执行命令
                    await self.execute_command(command, args)
                    
            except KeyboardInterrupt:
                print("\n")
                continue
            except EOFError:
                print("\n再见!")
                break
            except Exception as e:
                print(f"错误: {e}")


async def main():
    """主入口"""
    shell = InteractiveShell()
    await shell.run()


if __name__ == "__main__":
    asyncio.run(main())
