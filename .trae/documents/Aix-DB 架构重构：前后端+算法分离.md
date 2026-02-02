# Aix-DB 算法端HTTP服务规划（含流式响应处理）

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           算法服务 (Algorithm Service)                       │
│                              FastAPI + LangGraph                            │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  HTTP API Layer                                               │         │
│  │  POST /api/v1/text2sql/analyze  (SSE流式响应)                 │         │
│  └──────────────────────────────────────────────────────────────┘         │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  Text2SQL Agent (LangGraph工作流)                            │         │
│  │  ├── schema_inspector  ──▶ 步骤事件: step_start/step_complete │         │
│  │  ├── sql_generator     ──▶ 数据事件: sql_generated            │         │
│  │  ├── permission_filter ──▶ 数据事件: sql_filtered             │         │
│  │  ├── sql_executor      ──▶ 数据事件: sql_executed             │         │
│  │  ├── chart_generator   ──▶ 数据事件: chart_generated          │         │
│  │  ├── summarizer        ──▶ 数据事件: summary                  │         │
│  │  └── recommender       ──▶ 数据事件: recommendations          │         │
│  └──────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ SSE Stream
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        流式响应提取模块 (Stream Processor)                   │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  功能:                                                        │         │
│  │  1. 接收SSE流式数据块                                         │         │
│  │  2. 按事件类型分类存储                                        │         │
│  │  3. 实时打印/显示处理进度                                     │         │
│  │  4. 最终组装完整响应                                          │         │
│  └──────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 二、流式响应事件设计

### 2.1 事件类型定义

```python
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class EventType(str, Enum):
    """流式响应事件类型"""
    # 步骤进度事件
    STEP_START = "step_start"           # 步骤开始
    STEP_COMPLETE = "step_complete"     # 步骤完成
    
    # 数据生成事件
    SQL_GENERATED = "sql_generated"     # SQL生成完成
    SQL_FILTERED = "sql_filtered"       # SQL权限过滤完成
    SQL_EXECUTED = "sql_executed"       # SQL执行完成
    CHART_GENERATED = "chart_generated" # 图表配置生成
    SUMMARY = "summary"                 # 结果总结
    RECOMMENDATIONS = "recommendations" # 推荐问题
    
    # 状态事件
    ERROR = "error"                     # 错误
    COMPLETE = "complete"               # 全部完成

class AlgorithmEvent(BaseModel):
    """算法服务流式响应事件"""
    event_type: EventType
    step_name: Optional[str] = None     # 步骤名称(用于步骤事件)
    data: Optional[Dict[str, Any]] = None  # 事件数据
    timestamp: datetime
    message: Optional[str] = None       # 可读消息
```

### 2.2 各事件数据格式

```json
// 步骤开始
{
  "event_type": "step_start",
  "step_name": "schema_inspector",
  "timestamp": "2024-01-15T10:30:00Z",
  "message": "开始检索表结构..."
}

// 步骤完成
{
  "event_type": "step_complete",
  "step_name": "schema_inspector",
  "timestamp": "2024-01-15T10:30:02Z",
  "data": {
    "tables_found": 3,
    "table_names": ["orders", "users", "products"]
  }
}

// SQL生成
{
  "event_type": "sql_generated",
  "timestamp": "2024-01-15T10:30:05Z",
  "data": {
    "sql": "SELECT COUNT(*) FROM orders WHERE order_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)",
    "chart_type": "table"
  }
}

// SQL执行
{
  "event_type": "sql_executed",
  "timestamp": "2024-01-15T10:30:06Z",
  "data": {
    "success": true,
    "row_count": 1,
    "execution_time_ms": 45
  }
}

// 图表生成
{
  "event_type": "chart_generated",
  "timestamp": "2024-01-15T10:30:07Z",
  "data": {
    "chart_type": "table",
    "config": { /* AntV配置 */ },
    "render_data": {
      "columns": [{"title": "订单量", "dataIndex": "count"}],
      "data": [{"count": 150}]
    }
  }
}

// 结果总结
{
  "event_type": "summary",
  "timestamp": "2024-01-15T10:30:08Z",
  "data": {
    "text": "最近7天的订单量为150单"
  }
}

// 推荐问题
{
  "event_type": "recommendations",
  "timestamp": "2024-01-15T10:30:09Z",
  "data": {
    "questions": [
      "最近30天的订单量是多少？",
      "订单量最多的日期是哪一天？",
      "平均订单金额是多少？"
    ]
  }
}

// 完成
{
  "event_type": "complete",
  "timestamp": "2024-01-15T10:30:10Z"
}

// 错误
{
  "event_type": "error",
  "timestamp": "2024-01-15T10:30:05Z",
  "data": {
    "error_type": "sql_generation_failed",
    "message": "无法生成有效的SQL语句"
  }
}
```

## 三、流式响应提取模块设计

### 3.1 模块功能

```python
# algorithm-service/tests/stream_processor.py

import json
from typing import AsyncGenerator, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

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

class StreamProcessor:
    """
    流式响应处理器
    
    功能:
    1. 接收SSE流并解析事件
    2. 实时显示处理进度
    3. 聚合所有事件为完整结果
    """
    
    def __init__(self, verbose: bool = True, use_rich: bool = True):
        self.verbose = verbose
        self.use_rich = use_rich
        self.console = Console() if use_rich else None
        self.result = ProcessResult()
        self._current_step: Optional[str] = None
        self._step_start_time: Optional[datetime] = None
        
    async def process(
        self, 
        stream: AsyncGenerator[str, None],
        callback: Optional[Callable[[AlgorithmEvent], None]] = None
    ) -> ProcessResult:
        """
        处理流式响应
        
        Args:
            stream: SSE流生成器
            callback: 事件回调函数(可选)
            
        Returns:
            ProcessResult: 聚合的处理结果
        """
        async for line in stream:
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
            event = AlgorithmEvent(**event_dict)
            
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
                print(f"[警告] 无法解析事件: {e}")
    
    def _update_result(self, event: AlgorithmEvent):
        """根据事件类型更新结果"""
        event_type = event.event_type
        data = event.data or {}
        
        if event_type == "step_start":
            self._current_step = event.step_name
            self._step_start_time = event.timestamp
            self.result.steps.append({
                "name": event.step_name,
                "status": "running",
                "start_time": event.timestamp.isoformat()
            })
            
        elif event_type == "step_complete":
            for step in self.result.steps:
                if step["name"] == event.step_name:
                    step["status"] = "completed"
                    step["end_time"] = event.timestamp.isoformat()
                    step.update(data or {})
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
        """显示事件(使用rich美化)"""
        if not self.use_rich or not self.console:
            # 简单文本输出
            self._simple_display(event)
            return
            
        # Rich美化输出
        event_type = event.event_type
        
        if event_type == "step_start":
            self.console.print(f"[cyan]▶[/cyan] {event.message or event.step_name}")
            
        elif event_type == "step_complete":
            self.console.print(f"[green]✓[/green] {event.step_name} 完成")
            
        elif event_type == "sql_generated":
            sql = event.data.get("sql", "")
            self.console.print(Panel(
                sql[:200] + "..." if len(sql) > 200 else sql,
                title="[bold blue]生成的SQL[/bold blue]",
                border_style="blue"
            ))
            
        elif event_type == "sql_executed":
            if event.data.get("success"):
                self.console.print(f"[green]✓[/green] SQL执行成功，返回 {event.data.get('row_count', 0)} 行")
            else:
                self.console.print(f"[red]✗[/red] SQL执行失败: {event.data.get('error', '未知错误')}")
                
        elif event_type == "summary":
            self.console.print(Panel(
                event.data.get("text", ""),
                title="[bold green]结果总结[/bold green]",
                border_style="green"
            ))
            
        elif event_type == "recommendations":
            questions = event.data.get("questions", [])
            if questions:
                table = Table(title="推荐问题", show_header=False)
                table.add_column("#", style="cyan", width=3)
                table.add_column("问题")
                for i, q in enumerate(questions, 1):
                    table.add_row(str(i), q)
                self.console.print(table)
                
        elif event_type == "error":
            self.console.print(Panel(
                event.data.get("message", "未知错误"),
                title="[bold red]错误[/bold red]",
                border_style="red"
            ))
            
        elif event_type == "complete":
            self.console.print("[bold green]✓ 处理完成[/bold green]")
    
    def _simple_display(self, event: AlgorithmEvent):
        """简单文本输出(无rich依赖)"""
        event_type = event.event_type
        
        if event_type == "step_start":
            print(f"[开始] {event.message or event.step_name}")
        elif event_type == "step_complete":
            print(f"[完成] {event.step_name}")
        elif event_type == "sql_generated":
            print(f"[SQL生成] {event.data.get('sql', '')[:100]}...")
        elif event_type == "sql_executed":
            success = "成功" if event.data.get("success") else "失败"
            print(f"[SQL执行] {success}")
        elif event_type == "summary":
            print(f"[总结] {event.data.get('text', '')}")
        elif event_type == "recommendations":
            print(f"[推荐问题] {event.data.get('questions', [])}")
        elif event_type == "error":
            print(f"[错误] {event.data.get('message', '')}")
        elif event_type == "complete":
            print("[完成] 全部处理结束")
    
    def print_final_report(self):
        """打印最终报告"""
        if not self.use_rich or not self.console:
            print("\n" + "="*50)
            print("最终报告:")
            print(f"SQL: {self.result.sql}")
            print(f"总结: {self.result.summary}")
            print(f"推荐问题: {self.result.recommendations}")
            return
            
        # Rich报告
        self.console.print("\n[bold cyan]="*50 + "[/bold cyan]")
        self.console.print("[bold cyan]最终报告[/bold cyan]")
        self.console.print("[bold cyan]="*50 + "[/bold cyan]\n")
        
        if self.result.sql:
            self.console.print(Panel(
                self.result.sql,
                title="[bold]SQL语句[/bold]",
                border_style="blue"
            ))
            
        if self.result.summary:
            self.console.print(Panel(
                self.result.summary,
                title="[bold]结果总结[/bold]",
                border_style="green"
            ))
            
        if self.result.recommendations:
            table = Table(title="推荐问题", show_header=False)
            table.add_column("#", style="cyan", width=3)
            table.add_column("问题")
            for i, q in enumerate(self.result.recommendations, 1):
                table.add_row(str(i), q)
            self.console.print(table)
```

### 3.2 使用示例

```python
# algorithm-service/tests/test_api.py

import asyncio
import httpx
from stream_processor import StreamProcessor, ProcessResult

async def test_analyze():
    """测试算法服务API"""
    
    # 准备请求数据
    request_data = {
        "query": "查询最近7天的订单量",
        "datasource_config": {
            "db_type": "mysql",
            "host": "localhost",
            "port": 3306,
            "database": "test_db",
            "username": "root",
            "password": "password"
        },
        "schema_info": {
            "tables": [
                {
                    "name": "orders",
                    "comment": "订单表",
                    "fields": [
                        {"name": "id", "type": "bigint", "comment": "订单ID", "is_primary": True},
                        {"name": "order_date", "type": "datetime", "comment": "订单日期"},
                        {"name": "amount", "type": "decimal", "comment": "订单金额"}
                    ]
                }
            ]
        },
        "terminologies": [
            {"word": "订单量", "description": "订单的数量，count(id)"}
        ]
    }
    
    # 创建流式处理器
    processor = StreamProcessor(verbose=True, use_rich=True)
    
    # 发送请求并处理流式响应
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8001/api/v1/text2sql/analyze",
            json=request_data,
            timeout=300.0
        ) as response:
            # 处理流式响应
            result: ProcessResult = await processor.process(response.aiter_lines())
    
    # 打印最终报告
    processor.print_final_report()
    
    # 获取完整结果数据
    print("\n完整结果数据:")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    
    return result

if __name__ == "__main__":
    asyncio.run(test_analyze())
```

## 四、实施步骤

### Step 1: 创建算法服务基础结构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           算法服务 (Algorithm Service)                       │
│                              FastAPI + LangGraph                            │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  HTTP API Layer                                               │         │
│  │  POST /api/v1/text2sql/analyze  (SSE流式响应)                 │         │
│  └──────────────────────────────────────────────────────────────┘         │
│                              │                                              │
│                              ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  Text2SQL Agent (LangGraph工作流)                            │         │
│  │  ├── schema_inspector  ──▶ 步骤事件: step_start/step_complete │         │
│  │  ├── sql_generator     ──▶ 数据事件: sql_generated            │         │
│  │  ├── permission_filter ──▶ 数据事件: sql_filtered             │         │
│  │  ├── sql_executor      ──▶ 数据事件: sql_executed             │         │
│  │  ├── chart_generator   ──▶ 数据事件: chart_generated          │         │
│  │  ├── summarizer        ──▶ 数据事件: summary                  │         │
│  │  └── recommender       ──▶ 数据事件: recommendations          │         │
│  └──────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ SSE Stream
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        流式响应提取模块 (Stream Processor)                   │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │  功能:                                                        │         │
│  │  1. 接收SSE流式数据块                                         │         │
│  │  2. 按事件类型分类存储                                        │         │
│  │  3. 实时打印/显示处理进度                                     │         │
│  │  4. 最终组装完整响应                                          │         │
│  └──────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Step 2: 实现流式响应API

* 使用FastAPI的`StreamingResponse`

* 实现SSE(Server-Sent Events)格式

* 每个节点触发对应的事件

### Step 3: 实现流式处理模块

* 解析SSE数据块

* 事件分类和聚合

* 实时显示处理进度

* 最终报告生成

### Step 4: 测试验证

* 使用测试脚本调用API

* 验证流式响应处理

* 检查最终组装结果

## 五、技术要点

1. **SSE格式**: `data: {json}\n\n`
2. **异步流处理**: 使用`AsyncGenerator`
3. **Rich显示**: 美化控制台输出(可选)
4. **事件聚合**: 维护`ProcessResult`状态
5. **错误处理**: 捕获并显示错误事件

请确认此规划，确认后我将开始实现算法服务的HTTP API和流式响应处理模块。
