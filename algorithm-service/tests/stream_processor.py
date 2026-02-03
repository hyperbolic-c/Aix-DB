"""
流式响应处理器
用于接收算法服务的SSE流式响应，提取并组装成便于观看的内容
"""

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Callable, Any


@dataclass
class ProcessResult:
    """处理结果聚合"""
    sql: Optional[str] = None
    filtered_sql: Optional[str] = None
    execution_result: Optional[Dict] = None
    chart_config: Optional[Dict] = None
    render_data: Optional[Dict] = None
    summary: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    steps: List[Dict] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "sql": self.sql,
            "filtered_sql": self.filtered_sql,
            "execution_result": self.execution_result,
            "chart_config": self.chart_config,
            "render_data": self.render_data,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "steps": self.steps,
            "errors": self.errors,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class AlgorithmEvent:
    """算法事件"""
    
    def __init__(self, event_dict: Dict):
        self.event_type = event_dict.get("event_type", "unknown")
        self.step_name = event_dict.get("step_name")
        self.data = event_dict.get("data", {})
        self.timestamp = event_dict.get("timestamp", datetime.utcnow().isoformat())
        self.message = event_dict.get("message", "")
    
    def __repr__(self):
        return f"AlgorithmEvent(type={self.event_type}, step={self.step_name})"


class StreamProcessor:
    """
    流式响应处理器
    
    功能:
    1. 接收SSE流式数据块
    2. 按事件类型分类存储
    3. 实时打印/显示处理进度
    4. 最终组装完整响应
    """
    
    # 步骤名称映射(中文)
    STEP_NAME_MAP = {
        "schema_inspector": "表结构检索",
        "sql_generator": "SQL生成",
        "permission_filter": "权限过滤",
        "sql_executor": "SQL执行",
        "chart_generator": "图表配置生成",
        "summarizer": "结果总结",
        "recommender": "推荐问题生成",
    }
    
    # 事件类型显示配置
    EVENT_DISPLAY = {
        "step_start": {"icon": "▶", "color": "cyan"},
        "step_complete": {"icon": "✓", "color": "green"},
        "sql_generated": {"icon": "📝", "color": "blue"},
        "sql_filtered": {"icon": "🔒", "color": "yellow"},
        "sql_executed": {"icon": "⚡", "color": "green"},
        "chart_generated": {"icon": "📊", "color": "magenta"},
        "summary": {"icon": "📋", "color": "green"},
        "recommendations": {"icon": "💡", "color": "yellow"},
        "error": {"icon": "✗", "color": "red"},
        "complete": {"icon": "✓", "color": "green"},
    }
    
    def __init__(self, verbose: bool = True, use_colors: bool = True):
        self.verbose = verbose
        self.use_colors = use_colors
        self.result = ProcessResult()
        self._current_step: Optional[str] = None
        self._step_start_time: Optional[datetime] = None
        
        # ANSI颜色代码
        self.colors = {
            "reset": "\033[0m",
            "cyan": "\033[36m",
            "green": "\033[32m",
            "blue": "\033[34m",
            "yellow": "\033[33m",
            "magenta": "\033[35m",
            "red": "\033[31m",
            "bold": "\033[1m",
        } if use_colors else {k: "" for k in ["reset", "cyan", "green", "blue", "yellow", "magenta", "red", "bold"]}
    
    async def process(
        self, 
        stream: AsyncGenerator[str, None],
        callback: Optional[Callable[[AlgorithmEvent], None]] = None
    ) -> ProcessResult:
        """
        处理流式响应
        
        Args:
            stream: SSE流生成器(每行一个SSE数据)
            callback: 事件回调函数(可选)
            
        Returns:
            ProcessResult: 聚合的处理结果
        """
        async for line in stream:
            line = line.strip()
            if line.startswith("data:"):
                event_data = line[5:].strip()
                if event_data:
                    await self._handle_event(event_data, callback)
        
        return self.result
    
    async def _handle_event(
        self, 
        event_data: str, 
        callback: Optional[Callable[[AlgorithmEvent], None]]
    ):
        """处理单个事件"""
        try:
            event_dict = json.loads(event_data)
            event = AlgorithmEvent(event_dict)
            
            # 调用回调
            if callback:
                callback(event)
            
            # 更新结果
            self._update_result(event)
            
            # 显示进度
            if self.verbose:
                self._display_event(event)
                
        except json.JSONDecodeError as e:
            if self.verbose:
                print(f"{self.colors['yellow']}[警告]{self.colors['reset']} 无法解析事件: {e}")
        except Exception as e:
            if self.verbose:
                print(f"{self.colors['red']}[错误]{self.colors['reset']} 处理事件出错: {e}")
    
    def _update_result(self, event: AlgorithmEvent):
        """根据事件类型更新结果"""
        event_type = event.event_type
        data = event.data or {}
        
        if event_type == "step_start":
            self._current_step = event.step_name
            self._step_start_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            self.result.steps.append({
                "name": event.step_name,
                "display_name": self.STEP_NAME_MAP.get(event.step_name, event.step_name),
                "status": "running",
                "start_time": event.timestamp
            })
            
        elif event_type == "step_complete":
            for step in self.result.steps:
                if step["name"] == event.step_name:
                    step["status"] = "completed"
                    step["end_time"] = event.timestamp
                    if self._step_start_time:
                        end_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
                        duration = (end_time - self._step_start_time).total_seconds()
                        step["duration_ms"] = int(duration * 1000)
                    step.update(data)
                    break
                    
        elif event_type == "sql_generated":
            self.result.sql = data.get("sql")
            
        elif event_type == "sql_filtered":
            self.result.filtered_sql = data.get("sql")
            
        elif event_type == "sql_executed":
            self.result.execution_result = data
            
        elif event_type == "chart_generated":
            self.result.chart_config = data.get("config")
            self.result.render_data = data.get("render_data")
            
        elif event_type == "summary":
            self.result.summary = data.get("text")
            
        elif event_type == "recommendations":
            self.result.recommendations = data.get("questions", [])
            
        elif event_type == "error":
            self.result.errors.append(data)
    
    def _display_event(self, event: AlgorithmEvent):
        """显示事件"""
        event_type = event.event_type
        display_config = self.EVENT_DISPLAY.get(event_type, {"icon": "•", "color": "reset"})
        icon = display_config["icon"]
        color = self.colors.get(display_config["color"], "")
        reset = self.colors["reset"]
        
        if event_type == "step_start":
            step_cn = self.STEP_NAME_MAP.get(event.step_name, event.step_name)
            print(f"{color}{icon}{reset} {step_cn}...")
            
        elif event_type == "step_complete":
            step_cn = self.STEP_NAME_MAP.get(event.step_name, event.step_name)
            duration_info = ""
            for step in self.result.steps:
                if step["name"] == event.step_name and "duration_ms" in step:
                    duration_info = f" ({step['duration_ms']}ms)"
                    break
            print(f"{color}{icon}{reset} {step_cn}完成{duration_info}")
            
        elif event_type == "sql_generated":
            sql = event.data.get("sql", "")
            print(f"\n{color}{icon} 生成的SQL:{reset}")
            print(f"{self.colors['bold']}{sql}{reset}")
            print()
            
        elif event_type == "sql_filtered":
            sql = event.data.get("sql", "")
            print(f"\n{color}{icon} 权限过滤后的SQL:{reset}")
            print(f"{self.colors['bold']}{sql}{reset}")
            print()
            
        elif event_type == "sql_executed":
            if event.data.get("success"):
                row_count = event.data.get("row_count", 0)
                exec_time = event.data.get("execution_time_ms", 0)
                print(f"{color}{icon}{reset} SQL执行成功，返回 {row_count} 行 ({exec_time}ms)")
            else:
                error = event.data.get("error", "未知错误")
                print(f"{self.colors['red']}✗{reset} SQL执行失败: {error}")
                
        elif event_type == "chart_generated":
            chart_type = event.data.get("chart_type", "table")
            print(f"{color}{icon}{reset} 图表配置生成完成 (类型: {chart_type})")
            
        elif event_type == "summary":
            text = event.data.get("text", "")
            print(f"\n{color}{icon} 结果总结:{reset}")
            print(f"{self.colors['bold']}{text}{reset}")
            print()
            
        elif event_type == "recommendations":
            questions = event.data.get("questions", [])
            if questions:
                print(f"\n{color}{icon} 推荐问题:{reset}")
                for i, q in enumerate(questions, 1):
                    print(f"  {i}. {q}")
                print()
                
        elif event_type == "error":
            error_msg = event.data.get("message", "未知错误")
            print(f"\n{self.colors['red']}{icon} 错误:{reset}")
            print(f"{self.colors['red']}{error_msg}{reset}")
            print()
            
        elif event_type == "complete":
            print(f"\n{color}{icon} 处理完成{reset}\n")
    
    def print_final_report(self):
        """打印最终报告"""
        c = self.colors
        
        print(f"\n{c['bold']}{'='*60}{c['reset']}")
        print(f"{c['bold']}最终报告{c['reset']}")
        print(f"{c['bold']}{'='*60}{c['reset']}\n")
        
        # SQL
        if self.result.sql:
            print(f"{c['cyan']}【SQL语句】{c['reset']}")
            print(f"{self.result.sql}\n")
        
        if self.result.filtered_sql and self.result.filtered_sql != self.result.sql:
            print(f"{c['yellow']}【权限过滤后SQL】{c['reset']}")
            print(f"{self.result.filtered_sql}\n")
        
        # 执行结果
        if self.result.execution_result:
            print(f"{c['cyan']}【执行结果】{c['reset']}")
            if self.result.execution_result.get("success"):
                rows = self.result.execution_result.get("rows", [])
                columns = self.result.execution_result.get("columns", [])
                if rows and columns:
                    # 简单的表格输出
                    print(" | ".join(columns))
                    print("-" * (len(" | ".join(columns)) + 10))
                    for row in rows[:5]:  # 最多显示5行
                        print(" | ".join(str(cell) for cell in row))
                    if len(rows) > 5:
                        print(f"... 还有 {len(rows) - 5} 行 ...")
            else:
                print(f"{c['red']}执行失败: {self.result.execution_result.get('error', '未知错误')}{c['reset']}")
            print()
        
        # 总结
        if self.result.summary:
            print(f"{c['green']}【结果总结】{c['reset']}")
            print(f"{self.result.summary}\n")
        
        # 推荐问题
        if self.result.recommendations:
            print(f"{c['yellow']}【推荐问题】{c['reset']}")
            for i, q in enumerate(self.result.recommendations, 1):
                print(f"  {i}. {q}")
            print()
        
        # 处理步骤
        if self.result.steps:
            print(f"{c['cyan']}【处理步骤】{c['reset']}")
            for step in self.result.steps:
                status_icon = "✓" if step.get("status") == "completed" else "✗"
                duration = step.get("duration_ms", 0)
                duration_str = f" ({duration}ms)" if duration else ""
                print(f"  {status_icon} {step.get('display_name', step['name'])}{duration_str}")
            print()
        
        # 错误
        if self.result.errors:
            print(f"{c['red']}【错误信息】{c['reset']}")
            for error in self.result.errors:
                print(f"  ✗ {error.get('message', '未知错误')}")
            print()
        
        print(f"{c['bold']}{'='*60}{c['reset']}\n")
    
    def save_result(self, filepath: str):
        """保存结果到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.result.to_dict(), f, indent=2, ensure_ascii=False)
        if self.verbose:
            print(f"结果已保存到: {filepath}")


# 同步版本的处理器(用于非异步场景)
class SyncStreamProcessor(StreamProcessor):
    """同步流式响应处理器"""
    
    def process_sync(
        self, 
        lines: List[str],
        callback: Optional[Callable[[AlgorithmEvent], None]] = None
    ) -> ProcessResult:
        """
        同步处理流式响应
        
        Args:
            lines: SSE数据行列表
            callback: 事件回调函数(可选)
            
        Returns:
            ProcessResult: 聚合的处理结果
        """
        import asyncio
        
        async def async_generator():
            for line in lines:
                yield line
        
        return asyncio.run(self.process(async_generator(), callback))
