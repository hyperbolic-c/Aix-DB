"""
交互式终端模块
提供命令行交互界面
"""

import os
import sys
import json
import logging
from typing import List, Optional
from pathlib import Path

from .config import Config
from .chat_client import ChatClient
from .renderer import EventRenderer

# 配置日志
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InteractiveCLI:
    """
    交互式命令行界面
    """
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化交互式CLI
        
        Args:
            config: 配置对象
        """
        self.config = config or Config()
        self.client = ChatClient(self.config)
        self.renderer = EventRenderer(
            use_color=True,
            raw_mode=self.config.raw_mode
        )
        self.history: List[str] = []
        self.history_index = 0
        self.running = False
    
    def _load_history(self):
        """加载历史记录"""
        if self.config.history_file and Path(self.config.history_file).exists():
            try:
                with open(self.config.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                self.history_index = len(self.history)
            except Exception as e:
                logger.warning(f"加载历史记录失败: {e}")
    
    def _save_history(self):
        """保存历史记录"""
        if self.config.history_file:
            try:
                recent_history = self.history[-self.config.max_history:]
                with open(self.config.history_file, 'w', encoding='utf-8') as f:
                    json.dump(recent_history, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"保存历史记录失败: {e}")
    
    def _add_to_history(self, question: str):
        """添加到历史记录"""
        if question and question not in self.history:
            self.history.append(question)
            if len(self.history) > self.config.max_history:
                self.history.pop(0)
            self.history_index = len(self.history)
            self._save_history()
    
    def _handle_command(self, command: str) -> bool:
        """
        处理命令
        
        Args:
            command: 命令字符串
            
        Returns:
            是否继续运行
        """
        cmd = command.lower().strip()
        
        # 退出命令
        if cmd in ['/quit', '/q', '/exit']:
            print(self.renderer.render_footer())
            self.running = False
            return False
        
        # 帮助命令
        if cmd in ['/help', '/h', '?']:
            print(self.renderer.render_help())
            return True
        
        # 调试模式切换
        if cmd == '/debug':
            self.config.debug = not self.config.debug
            status = "开启" if self.config.debug else "关闭"
            print(self.renderer.render_info(f"调试模式已{status}"))
            return True
        
        # 原始模式切换
        if cmd == '/raw':
            self.config.raw_mode = not self.config.raw_mode
            self.renderer.raw_mode = self.config.raw_mode
            status = "开启" if self.config.raw_mode else "关闭"
            print(self.renderer.render_info(f"原始JSON模式已{status}"))
            return True
        
        # 清屏
        if cmd == '/clear':
            os.system('clear' if os.name != 'nt' else 'cls')
            print(self.renderer.render_header(self.config))
            return True
        
        # 健康检查
        if cmd == '/health':
            print(self.renderer.render_info("检查服务健康状态..."))
            health = self.client.health_check()
            if health.get("status") == "healthy":
                print(self.renderer.render_success(f"服务健康: {health}"))
            else:
                print(self.renderer.render_error(f"服务异常: {health}"))
            return True
        
        # 创建新会话
        if cmd == '/new':
            try:
                session = self.client.create_session()
                print(self.renderer.render_success(f"创建新会话: {session['title']} (ID: {session['id']})"))
            except Exception as e:
                print(self.renderer.render_error(f"创建会话失败: {e}"))
            return True
        
        # 列出所有会话
        if cmd in ['/sessions', '/list']:
            sessions = self.client.list_sessions()
            if not sessions:
                print(self.renderer.render_info("暂无会话"))
            else:
                print(self.renderer.render_info("会话列表:"))
                current_id = self.client.current_session_id
                for s in sessions:
                    marker = "👉 " if s['id'] == current_id else "   "
                    print(f"{marker}[{s['id']}] {s['title']} ({s['message_count']}条消息)")
            return True
        
        # 切换会话
        if cmd.startswith('/switch '):
            try:
                session_id = int(cmd.split()[1])
                if self.client.switch_session(session_id):
                    session = self.client.get_session(session_id)
                    print(self.renderer.render_success(f"切换到会话: {session['title']}"))
                else:
                    print(self.renderer.render_error(f"会话不存在: {session_id}"))
            except (ValueError, IndexError):
                print(self.renderer.render_error("用法: /switch <session_id>"))
            return True
        
        # 显示当前会话历史
        if cmd == '/history':
            messages = self.client.get_history()
            if not messages:
                print(self.renderer.render_info("当前会话暂无历史记录"))
            else:
                session_id = self.client.current_session_id
                print(self.renderer.render_info(f"会话 {session_id} 的历史记录:"))
                print()
                for msg in messages:
                    role_icon = "👤" if msg['role'] == "user" else "🤖"
                    ts = msg.get('timestamp', '')[:19] if msg.get('timestamp') else ''
                    print(f"{role_icon} [{ts}]")
                    content = msg.get('content', '')
                    print(f"   {content[:100]}{'...' if len(content) > 100 else ''}")
                    if msg.get('sql'):
                        sql = msg['sql']
                        print(f"   SQL: {sql[:80]}...")
                    print()
            return True
        
        # 清空当前会话历史
        if cmd == '/clear_history':
            if self.client.clear_history():
                print(self.renderer.render_success("已清空当前会话历史"))
            else:
                print(self.renderer.render_error("清空历史失败"))
            return True
        
        # 删除会话
        if cmd.startswith('/delete '):
            try:
                session_id = int(cmd.split()[1])
                if self.client.delete_session(session_id):
                    print(self.renderer.render_success(f"删除会话: {session_id}"))
                else:
                    print(self.renderer.render_error(f"删除会话失败"))
            except (ValueError, IndexError):
                print(self.renderer.render_error("用法: /delete <session_id>"))
            return True
        
        # 重命名会话
        if cmd.startswith('/rename '):
            parts = cmd.split(' ', 1)
            if len(parts) < 2:
                print(self.renderer.render_error("用法: /rename <新标题>"))
            else:
                new_title = parts[1]
                session_id = self.client.current_session_id
                if session_id and self.client.rename_session(session_id, new_title):
                    print(self.renderer.render_success(f"重命名会话为: {new_title}"))
                else:
                    print(self.renderer.render_error("重命名失败"))
            return True
        
        # 未知命令
        print(self.renderer.render_error(f"未知命令: {command}"))
        print("输入 /help 查看可用命令")
        return True
    
    def _process_question(self, question: str):
        """
        处理问题
        
        Args:
            question: 用户问题
        """
        print(self.renderer.render_separator())
        print(self.renderer.render_info(f"处理: {question}"))
        
        # 显示当前会话信息
        if self.client.current_session_id:
            print(self.renderer.render_info(f"会话ID: {self.client.current_session_id}"))
        print()
        
        try:
            # 发送请求并接收流式响应
            for event in self.client.send_message(question):
                output = self.renderer.render_event(event)
                if output:
                    print(output)
                
                # 检查是否完成或出错
                event_type = event.get("event_type", "")
                if event_type in ["complete", "error"]:
                    break
            
            print()
            
        except KeyboardInterrupt:
            print()
            print(self.renderer.render_info("用户取消"))
        except Exception as e:
            print(self.renderer.render_error(f"处理失败: {e}"))
    
    def _get_input(self) -> str:
        """
        获取用户输入
        
        Returns:
            用户输入的字符串
        """
        prompt = self.renderer.render_prompt()
        return input(prompt)
    
    def run(self):
        """运行交互式终端"""
        self.running = True
        
        # 显示头部信息
        print(self.renderer.render_header(self.config))
        
        # 检查服务健康状态
        health = self.client.health_check()
        if health.get("status") != "healthy":
            print(self.renderer.render_error(f"无法连接到服务: {self.config.host}"))
            print(self.renderer.render_info("请确保服务已启动，或使用 --host 指定正确的地址"))
            return
        
        print(self.renderer.render_success("已连接到服务"))
        
        # 检查是否有现有会话，如果没有则创建新会话
        sessions = self.client.list_sessions(limit=1)
        if sessions:
            # 恢复最近的会话
            self.client.switch_session(sessions[0]['id'])
            session = self.client.get_session(self.client.current_session_id)
            print(self.renderer.render_info(f"已恢复会话: {session['title']} (ID: {session['id']}, {session['message_count']}条消息)"))
        else:
            # 创建新会话
            try:
                session = self.client.create_session()
                print(self.renderer.render_info(f"已创建新会话: {session['title']} (ID: {session['id']})"))
            except Exception as e:
                print(self.renderer.render_error(f"创建会话失败: {e}"))
        
        print()
        
        # 主循环
        while self.running:
            try:
                # 获取输入
                user_input = self._get_input()
                
                # 跳过空输入
                if not user_input.strip():
                    continue
                
                # 处理命令
                if user_input.startswith('/'):
                    if not self._handle_command(user_input):
                        break
                    continue
                
                # 处理问题
                self._add_to_history(user_input)
                self._process_question(user_input)
                
            except KeyboardInterrupt:
                print()
                print(self.renderer.render_info("使用 /quit 退出程序"))
            except EOFError:
                print()
                break
            except Exception as e:
                print(self.renderer.render_error(f"错误: {e}"))
        
        # 清理
        self.client.close()
        self._save_history()
    
    def run_single(self, question: str):
        """
        运行单次查询
        
        Args:
            question: 问题字符串
        """
        print(self.renderer.render_header(self.config))
        self._process_question(question)
        self.client.close()
