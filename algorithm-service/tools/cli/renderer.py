"""
终端渲染器模块
美化显示流式数据，支持颜色格式化和JSON美化
"""

import json
import shutil
from typing import Dict, Any, Optional
from datetime import datetime


# 颜色代码
class Colors:
    """ANSI颜色代码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # 前景色
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # 背景色
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


# 事件类型到颜色和图标的映射
EVENT_STYLES = {
    "step_start": {"icon": "🔄", "color": Colors.YELLOW, "label": "开始"},
    "step_complete": {"icon": "✅", "color": Colors.GREEN, "label": "完成"},
    "sql_generated": {"icon": "📝", "color": Colors.CYAN, "label": "SQL生成"},
    "sql_filtered": {"icon": "🔒", "color": Colors.MAGENTA, "label": "权限过滤"},
    "sql_executed": {"icon": "⚡", "color": Colors.GREEN, "label": "SQL执行"},
    "chart_generated": {"icon": "📊", "color": Colors.BLUE, "label": "图表配置"},
    "summary": {"icon": "📋", "color": Colors.WHITE, "label": "结果总结"},
    "recommendations": {"icon": "💡", "color": Colors.YELLOW, "label": "推荐问题"},
    "complete": {"icon": "🎉", "color": Colors.GREEN, "label": "完成"},
    "error": {"icon": "❌", "color": Colors.RED, "label": "错误"},
}


class EventRenderer:
    """
    事件渲染器
    将算法服务返回的事件格式化为终端友好的输出
    """
    
    def __init__(self, use_color: bool = True, raw_mode: bool = False):
        """
        初始化渲染器
        
        Args:
            use_color: 是否使用颜色
            raw_mode: 是否显示原始JSON
        """
        self.use_color = use_color and self._supports_color()
        self.raw_mode = raw_mode
        self.terminal_width = self._get_terminal_width()
    
    def _supports_color(self) -> bool:
        """检查终端是否支持颜色"""
        try:
            import sys
            return sys.stdout.isatty()
        except:
            return False
    
    def _get_terminal_width(self) -> int:
        """获取终端宽度"""
        try:
            return shutil.get_terminal_size().columns
        except:
            return 80
    
    def _colorize(self, text: str, color: str) -> str:
        """添加颜色"""
        if self.use_color:
            return f"{color}{text}{Colors.RESET}"
        return text
    
    def _format_json(self, data: Any, indent: int = 2) -> str:
        """格式化JSON"""
        return json.dumps(data, ensure_ascii=False, indent=indent)
    
    def _truncate(self, text: str, max_length: int = None) -> str:
        """截断文本"""
        if max_length is None:
            max_length = self.terminal_width - 10
        if len(text) > max_length:
            return text[:max_length - 3] + "..."
        return text
    
    def render_event(self, event: Dict[str, Any]) -> str:
        """
        渲染单个事件
        
        Args:
            event: 事件字典
            
        Returns:
            格式化后的字符串
        """
        if self.raw_mode:
            return self._format_json(event)
        
        event_type = event.get("event_type", "unknown")
        style = EVENT_STYLES.get(event_type, {"icon": "📌", "color": Colors.WHITE, "label": event_type})
        
        # 构建输出行
        lines = []
        
        # 事件标题行
        icon = style["icon"]
        label = style["label"]
        message = event.get("message", "")
        
        header = f"{icon} [{label}]"
        if message:
            header += f" {message}"
        
        lines.append(self._colorize(header, style["color"]))
        
        # 渲染事件特定的数据
        data_lines = self._render_event_data(event_type, event.get("data", {}))
        lines.extend(data_lines)
        
        return "\n".join(lines)
    
    def _render_event_data(self, event_type: str, data: Dict[str, Any]) -> list:
        """渲染事件特定的数据"""
        lines = []
        
        if not data:
            return lines
        
        if event_type == "sql_generated":
            sql = data.get("sql", "")
            if sql:
                lines.append(self._colorize("   SQL:", Colors.DIM))
                lines.append(f"   {self._colorize(sql, Colors.CYAN)}")
            
            chart_type = data.get("chart_type", "")
            if chart_type:
                lines.append(f"   图表类型: {chart_type}")
        
        elif event_type == "sql_executed":
            if data.get("success"):
                row_count = data.get("row_count", 0)
                columns = data.get("columns", [])
                lines.append(f"   返回 {row_count} 行数据")
                if columns:
                    lines.append(f"   列: {', '.join(columns[:5])}")
                    if len(columns) > 5:
                        lines.append(f"   ... 还有 {len(columns) - 5} 列")
                
                # 显示前几行数据
                rows = data.get("rows", [])
                if rows:
                    lines.append(self._colorize("   数据预览:", Colors.DIM))
                    for i, row in enumerate(rows[:3]):
                        row_str = json.dumps(row, ensure_ascii=False)
                        lines.append(f"     {self._truncate(row_str)}")
                    if len(rows) > 3:
                        lines.append(f"     ... 还有 {len(rows) - 3} 行")
            else:
                error = data.get("error", "未知错误")
                lines.append(self._colorize(f"   错误: {error}", Colors.RED))
        
        elif event_type == "chart_generated":
            chart_type = data.get("chart_type", "")
            if chart_type:
                lines.append(f"   图表类型: {chart_type}")
            
            config = data.get("config", {})
            if config:
                lines.append(self._colorize("   配置:", Colors.DIM))
                config_str = self._format_json(config, indent=4)
                for line in config_str.split("\n")[:5]:
                    lines.append(f"     {line}")
        
        elif event_type == "summary":
            text = data.get("text", "")
            if text:
                # 自动换行
                wrapped = self._wrap_text(text, width=self.terminal_width - 6)
                for line in wrapped:
                    lines.append(f"   {line}")
        
        elif event_type == "recommendations":
            questions = data.get("questions", [])
            if questions:
                lines.append(self._colorize("   推荐问题:", Colors.DIM))
                for i, q in enumerate(questions, 1):
                    lines.append(f"     {i}. {q}")
        
        elif event_type == "error":
            error_type = data.get("error_type", "")
            error_msg = data.get("message", "")
            if error_type:
                lines.append(f"   错误类型: {error_type}")
            if error_msg:
                lines.append(f"   错误信息: {error_msg}")
        
        else:
            # 默认渲染其他数据
            if data:
                data_str = self._format_json(data, indent=4)
                lines.append(self._colorize("   数据:", Colors.DIM))
                for line in data_str.split("\n")[:10]:
                    lines.append(f"     {line}")
        
        return lines
    
    def _wrap_text(self, text: str, width: int = 80) -> list:
        """自动换行"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                if current_line:
                    current_line += " "
                current_line += word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def render_header(self, config: Any) -> str:
        """渲染头部信息"""
        lines = [
            "",
            self._colorize("=" * 50, Colors.CYAN),
            self._colorize("🤖 算法服务调试终端", Colors.BOLD + Colors.CYAN),
            self._colorize("=" * 50, Colors.CYAN),
            f"服务地址: {config.host}",
            f"数据库: {config.db_path}",
            "",
            "输入 /help 查看帮助，/quit 退出",
            "",
        ]
        return "\n".join(lines)
    
    def render_footer(self) -> str:
        """渲染底部信息"""
        return "\n" + self._colorize("👋 再见!", Colors.GREEN)
    
    def render_help(self) -> str:
        """渲染帮助信息"""
        lines = [
            "",
            self._colorize("📖 可用命令:", Colors.BOLD),
            "",
            "  /quit, /q       - 退出程序",
            "  /help, /h       - 显示帮助",
            "  /debug          - 切换调试模式",
            "  /raw            - 切换原始JSON显示模式",
            "  /clear          - 清屏",
            "  /health         - 检查服务健康状态",
            "",
            self._colorize("💬 会话管理:", Colors.BOLD),
            "",
            "  /new            - 创建新会话",
            "  /sessions       - 列出所有会话",
            "  /switch <id>    - 切换到指定会话",
            "  /history        - 显示当前会话历史",
            "  /clear_history  - 清空当前会话历史",
            "  /delete <id>    - 删除指定会话",
            "  /rename <title> - 重命名当前会话",
            "",
            self._colorize("📊 事件类型说明:", Colors.BOLD),
            "",
        ]

        for event_type, style in EVENT_STYLES.items():
            icon = style["icon"]
            label = style["label"]
            color = style["color"]
            lines.append(f"  {icon} {self._colorize(label, color)}")

        lines.append("")
        return "\n".join(lines)
    
    def render_prompt(self) -> str:
        """渲染输入提示符"""
        return self._colorize("> ", Colors.GREEN)
    
    def render_error(self, message: str) -> str:
        """渲染错误信息"""
        return self._colorize(f"❌ 错误: {message}", Colors.RED)
    
    def render_success(self, message: str) -> str:
        """渲染成功信息"""
        return self._colorize(f"✅ {message}", Colors.GREEN)
    
    def render_info(self, message: str) -> str:
        """渲染信息"""
        return self._colorize(f"ℹ️  {message}", Colors.BLUE)
    
    def render_separator(self) -> str:
        """渲染分隔线"""
        return self._colorize("-" * self.terminal_width, Colors.DIM)
