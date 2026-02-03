# 算法服务测试框架

基于 `target_db/competition` 的测试框架，支持从 `finalTableSchema.xlsx` 和 `gold.jsonl` 构建测试请求。

## 特点

- **Schema来源**: 从 `finalTableSchema.xlsx` 提取（非 `final.db`）
- **算法无关**: 不依赖算法内部功能（检索/重排/改写），保持兼容性
- **多种测试模式**: HTTP接口测试、CLI交互测试、批量测试
- **预置数据**: 30+ 术语和 30+ SQL 示例填充请求体
- **Schema加载模式**: 支持三种加载策略（主表/前缀匹配/所有表）

## 快速开始

### 1. 安装依赖

```bash
pip install openpyxl httpx pandas pyyaml
```

### 2. 运行测试

```bash
# Gold用例测试（默认前缀匹配模式）
python tests/test_gold_cases.py --limit 10

# HTTP接口测试
python tests/test_api.py --gold --limit 10

# CLI交互测试
python -m tests.cli
```

## 测试脚本说明

### test_gold_cases.py

直接测试算法核心，无需启动HTTP服务。

```bash
# 基本用法
python tests/test_gold_cases.py --limit 10

# 指定用例
python tests/test_gold_cases.py --case-id 1

# 指定难度
python tests/test_gold_cases.py --level 1

# Schema加载模式
python tests/test_gold_cases.py --case-id 1 --schema-mode primary   # 只加载主表
python tests/test_gold_cases.py --case-id 1 --schema-mode related   # 前缀匹配（默认）
python tests/test_gold_cases.py --case-id 1 --schema-mode all       # 加载所有表

# 其他选项
python tests/test_gold_cases.py --limit 10 --no-execution  # 不验证SQL执行
```

### test_api.py

测试HTTP接口，需要启动算法服务。

```bash
# 标准测试
python tests/test_api.py

# Gold用例测试
python tests/test_api.py --gold
python tests/test_api.py --gold --case-id 1
python tests/test_api.py --gold --limit 10
python tests/test_api.py --gold --level 1

# 自定义问题
python tests/test_api.py --custom "查询昨天的订单量"

# 指定服务地址
python tests/test_api.py --gold --case-id 1 --url http://localhost:8002
```

### CLI交互测试

```bash
# 启动CLI
python -m tests.cli

# 常用命令
> connect http://localhost:8002    # 连接服务
> load-competition                 # 加载测试数据
> case 1                           # 查看用例详情
> inspect 1                        # 检查请求构建
> test 1                           # 测试单个用例
> test-suite --level 1             # 运行测试套件
> test-custom "查询订单量"          # 自定义问题
> fixtures                         # 查看预置数据
> help                             # 显示帮助
```

## Schema加载模式

### 三种模式对比

| 模式 | 表数量 | Prompt长度 | 适用场景 |
|------|--------|------------|----------|
| `primary` | 1个 | ~7500 | 简单查询，表结构清晰 |
| `related` (默认) | 4个 | ~8200 | 相关业务表，推荐 |
| `all` | 20个 | ~13000 | 复杂跨表查询 |

### 匹配策略

**前缀匹配**（`related` 模式）：

```
主表: item_callback_total_day
提取前缀: "item"

匹配结果:
✓ items_total_day          (item开头)
✓ item_bmh_total_day       (item开头)
✓ item_callback_total_day  (item开头，主表本身)
✓ item_overdue_total_day   (item开头)
✗ order_flow_total_day     (order开头，不匹配)
✗ sub_accept_total_day     (sub开头，不匹配)
```

### 代码中配置

```python
from tests.framework.request_builder import CompetitionRequestBuilder

builder = CompetitionRequestBuilder("target_db/competition")

# 只加载主表
request = builder.build_request(
    case_id=1,
    include_related_tables=False,
    include_all_tables=False
)

# 前缀匹配（默认）
request = builder.build_request(
    case_id=1,
    include_related_tables=True,
    include_all_tables=False
)

# 加载所有表
request = builder.build_request(
    case_id=1,
    include_all_tables=True
)
```

## 目录结构

```
tests/
├── framework/                    # 核心框架
│   ├── request_builder.py       # 从xlsx+gold.jsonl构建请求
│   └── validators.py            # SQL验证器
├── fixtures/                     # 预置数据
│   ├── terminologies.yaml       # 30+业务术语
│   └── sql_examples.yaml        # 30+SQL示例
├── cli/                          # CLI交互工具
│   ├── interactive_shell.py     # 交互式Shell
│   └── commands.py              # 命令处理器
├── test_api.py                   # HTTP接口测试
├── test_gold_cases.py           # Gold用例测试
├── demo_schema_loading.py       # Schema加载模式演示
└── conftest.py                  # pytest配置
```

## 指定不同的算法服务

### 方式1: 命令行参数

```bash
python tests/test_api.py --gold --case-id 1 --url http://localhost:8002
```

### 方式2: 环境变量

```bash
export ALGO_SERVICE_URL=http://localhost:8002
python tests/test_api.py --gold --case-id 1
```

### 方式3: CLI交互

```bash
python -m tests.cli
> connect http://localhost:8002
```

### 测试不同环境

```bash
# 本地开发
python tests/test_api.py --url http://localhost:8001

# 测试环境
python tests/test_api.py --url http://test-server:8001

# 生产环境
python tests/test_api.py --url https://api.example.com
```

## Fixtures预置数据

### 术语 (terminologies.yaml)

包含30+业务术语，用于填充请求体：

- **工单相关**: 工单量、回访发起量、满意率、逾期率等
- **订单相关**: 订单量、销售额、平均订单金额等
- **用户相关**: 用户数、新用户、老用户等
- **时间相关**: 昨天、最近7天、本月、环比、同比等
- **统计相关**: 占比、排名、TOP N、累计等

### SQL示例 (sql_examples.yaml)

包含30+SQL示例，用于Few-shot学习：

- **基础查询**: 时间筛选、条件查询
- **分组聚合**: GROUP BY、聚合函数
- **占比计算**: 百分比、窗口函数
- **联表查询**: JOIN、多表关联
- **排序限制**: TOP N、分页

## 注意事项

1. **路径问题**: 确保在正确的工作目录运行测试脚本
   ```bash
   cd /Users/liam/LLMPro/Aix-DB
   python algorithm-service/tests/test_gold_cases.py --limit 10
   ```

2. **虚拟环境**: 使用项目的虚拟环境
   ```bash
   source .venv/bin/activate
   ```

3. **服务启动**: HTTP测试需要先启动算法服务
   ```bash
   python -m app.main
   ```

4. **Schema文件**: 确保 `target_db/competition/finalTableSchema.xlsx` 存在
