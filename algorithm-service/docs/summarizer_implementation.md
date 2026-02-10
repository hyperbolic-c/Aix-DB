# 结果总结功能实现文档

## 概述

本文档详细描述了基于LLM的查询结果总结功能的完整实现，包括代码结构、提示词设计和调用流程。

---

## 1. 整体架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   SQL执行结果    │────→│   结果总结模块   │────→│   自然语言总结   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ↓
                        ┌─────────────────┐
                        │   LLM服务调用   │
                        │  (数据趋势分析师) │
                        └─────────────────┘
```

---

## 2. 核心实现代码

### 2.1 总结生成入口函数

**文件位置**: `agent.py` (或主Agent文件)

```python
def _generate_summary(
    self,
    query: str,
    execution_result: Dict[str, Any],
) -> str:
    """
    生成结果总结
    
    Args:
        query: 用户原始问题
        execution_result: SQL执行结果，包含以下字段:
            - success: bool, 执行是否成功
            - rows: List[List], 查询结果数据
            - row_count: int, 返回行数
            - columns: List[str], 列名列表
            - error: str, 错误信息(如果失败)
    
    Returns:
        str: 自然语言总结文本
    """
    # 1. 检查执行是否成功
    if not execution_result.get("success"):
        return f"查询执行失败: {execution_result.get('error', '未知错误')}"
    
    try:
        # 2. 使用LLM生成总结
        llm_service = get_llm_service()
        data_result = json.dumps(execution_result, ensure_ascii=False, default=str)
        
        summary = llm_service.generate_summary(data_result, query)
        return summary
        
    except Exception as e:
        # 3. 降级到默认总结
        return self._generate_default_summary(execution_result, query)


def _generate_default_summary(
    self,
    execution_result: Dict[str, Any],
    query: str
) -> str:
    """生成默认总结(LLM失败时使用)"""
    rows = execution_result.get("rows", [])
    row_count = execution_result.get("row_count", 0)
    
    if rows and len(rows) > 0:
        first_row = rows[0]
        if len(first_row) > 0:
            # 单行单列：直接返回答案
            if len(rows) == 1 and len(first_row) == 1:
                return f"根据查询结果，{query}的答案是 {first_row[0]}"
            else:
                return f"查询成功，共返回 {row_count} 条数据"
    
    return f"查询执行成功，返回 {row_count} 行数据"
```

### 2.2 LLM服务实现

**文件位置**: `llm_service.py`

```python
class LLMService:
    """LLM服务封装"""
    
    def __init__(
        self,
        base_url: str = 'https://api-inference.modelscope.cn/v1',
        api_key: str = 'your-api-key',
        model: str = 'Qwen/Qwen3-235B-A22B-Instruct-2507',
    ):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.model = model
    
    def generate_summary(
        self,
        data_result: str,
        user_query: str,
        temperature: float = 0.3,
    ) -> str:
        """
        生成结果总结
        
        Args:
            data_result: 数据结果(JSON字符串)
            user_query: 用户问题
            temperature: 温度参数(建议0.3，保持稳定性)
        
        Returns:
            总结文本
        """
        try:
            # 构建提示词
            prompt_builder = PromptBuilder()
            full_prompt = prompt_builder.build_summarizer_prompt(
                data_result=data_result,
                user_query=user_query,
            )
            
            # 分割系统提示词和用户提示词
            parts = full_prompt.split("\n\n", 1)
            system_prompt = parts[0] if len(parts) > 0 else ""
            user_prompt = parts[1] if len(parts) > 1 else full_prompt
            
            # 调用LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                stream=False,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"总结生成失败: {str(e)}")
```

### 2.3 提示词构建器

**文件位置**: `prompt_builder.py`

```python
class PromptBuilder:
    """提示词构建器"""
    
    def __init__(self, template_path: str = None):
        """
        初始化提示词构建器
        
        Args:
            template_path: YAML模板文件路径
        """
        if template_path is None:
            template_path = Path(__file__).parent / "yaml" / "template.yaml"
        
        with open(template_path, 'r', encoding='utf-8') as f:
            self.base_template = yaml.safe_load(f)
    
    def build_summarizer_prompt(
        self,
        data_result: str,
        user_query: str,
        current_time: Optional[str] = None,
    ) -> str:
        """
        构建数据总结提示词
        
        Args:
            data_result: 数据结果(JSON格式字符串)
            user_query: 用户问题
            current_time: 当前时间(格式：YYYY-MM-DD HH:MM:SS)
        
        Returns:
            完整的提示词字符串
        """
        if current_time is None:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        summarizer_template = self.base_template['template']['summarizer']
        
        # 构建系统提示词
        system_prompt = summarizer_template['system']
        
        # 构建用户提示词
        user_prompt = summarizer_template['user'].format(
            data_result=data_result,
            user_query=user_query,
            current_time=current_time,
        )
        
        # 返回完整的提示词
        return f"{system_prompt}\n\n{user_prompt}"
```

---

## 3. 提示词模板

**文件位置**: `template.yaml`

```yaml
template:
  summarizer:
    system: |
      # Role: 数据趋势分析师
      
      ## Profile
      - language: 简体中文
      - description: 专注于从复杂数据中提取关键趋势与结构信号，将数据洞察转化为可执行的业务建议
      - expertise: 时间序列分析、结构洞察、异常检测、模式识别、趋势推断、业务驱动分析
      
      ## Core Skills
      - **趋势识别**：判断时间序列数据的变动方向、拐点、周期性及持续性
      - **结构洞察**：识别分布特征、集中度、异常值及关键维度差异
      - **模式归纳**：提炼可解释的业务信号，形成业务洞察
      - **异常检测**：发现偏离常规趋势、比例或预期的异常数值
      - **指标构建**：提取关键业务指标（客单价、转化率、集中度等）
      - **驱动分析**：定位主导整体表现的核心因素
      
      ## Rules
      
      ### 基本原则
      1. **数据驱动**：所有结论必须基于实际数据，避免主观臆断
      2. **逻辑闭环**：分析过程与结论之间需具备可验证的因果关系
      3. **业务贴合**：结合业务常识进行推断，确保结论具备可解释性与可操作性
      4. **精炼表达**：语言简洁、重点突出、结构清晰、易于理解
      
      ### 行为准则
      1. **动态响应**：根据输入数据类型（时间序列/截面数据）自动切换分析策略
      2. **分层输出**：先整体概括，再分项列出关键发现（2-3项）
      3. **视觉引导**：合理使用Unicode图标提升信息传达效率
      4. **格式统一**：保持输出风格一致性，确保层级结构清晰
      
      ### 限制条件
      1. **语言**：仅使用简体中文，避免专业术语或复杂表达
      2. **长度**：总输出控制在300字以内，关键发现控制在2-3项
      3. **图标**：仅使用Unicode图标，层级一致，避免冗余
      4. **输出**：仅输出结构化分析内容，不包含引导语或解释性语句
      
      ## Workflow
      1. 识别数据结构（时间序列 / 截面数据），动态选择分析策略
      2. 提取关键指标与核心趋势，识别异常信号与关键变动
      3. 结合业务背景与数据逻辑，归纳驱动因素与潜在风险
      4. 输出结构清晰、重点突出、逻辑闭环的数据分析报告
      
      ## Output Format
      
      ### 格式要求
      - **format**: markdown
      - **structure**: "整体概括 - 关键发现"结构
      - **style**: 简洁、专业、数据驱动，结合图标提升可读性
      - **禁用**: 代码块、HTML标签
      
      ### 格式规范
      - 使用标准Markdown语法
      - 包含"数据分析"主标题，下设"关键发现"子项
      - 关键词使用加粗，图标与文字之间保留1个空格
      
      ### 示例
      ```
      ## 🧩 数据分析  
      当前销售数据呈现明显的集中趋势，前**10**名商品中饮料类占据主导，但高单价商品占比较低。
      
      ## **📌 关键发现**  
      - 🔍 **销售额环比增长6.2%**，低于前两周平均**12.5%**，存在增速放缓迹象  
      - 📈 **订单密度下降5.3%**，表明用户活跃度可能减弱  
      - 📦 **客单价提升11%**，主要由高单价商品销量增加驱动
      ```
      
      ## Initialization
      作为数据趋势分析师，你必须遵守上述Rules，按照Workflow执行任务，并按照Output Format输出。
    
    user: |
      ## INPUT_DATA
      {data_result}
      
      ### QUESTION ###
      User's Question: {user_query}
      Current Time: {current_time}
      
      请根据以上数据和问题，生成结构化的数据分析总结。
```

---

## 4. 调用流程

### 4.1 完整调用链

```python
# 1. 主Agent调用
agent = Text2SQLAgent()
result = agent.analyze(query="查询2024年1月销售数据")

# 2. 内部执行SQL后生成总结
# agent.py
summary = self._generate_summary(
    query=query,
    execution_result={
        "success": True,
        "rows": [["2024-01", 100000], ["2024-02", 120000]],
        "row_count": 2,
        "columns": ["月份", "销售额"]
    }
)

# 3. LLM服务生成总结
# llm_service.py
summary = llm_service.generate_summary(
    data_result='{"rows": [...], "row_count": 2}',
    user_query="查询2024年1月销售数据"
)

# 4. 构建提示词
# prompt_builder.py
prompt = prompt_builder.build_summarizer_prompt(
    data_result='{"rows": [...]}',
    user_query="查询2024年1月销售数据",
    current_time="2024-01-15 10:30:00"
)
```

### 4.2 执行时序图

```
用户提问
    │
    ↓
┌─────────────┐
│  生成SQL    │
└─────────────┘
    │
    ↓
┌─────────────┐
│  执行SQL    │
└─────────────┘
    │
    ↓
┌─────────────────┐
│  构建总结提示词  │◄──── 读取template.yaml
└─────────────────┘
    │
    ↓
┌─────────────────┐
│  调用LLM服务    │◄──── 数据趋势分析师角色
└─────────────────┘
    │
    ↓
┌─────────────────┐
│  返回自然语言总结 │
└─────────────────┘
```

---

## 5. 输出示例

### 输入数据
```json
{
  "success": true,
  "rows": [
    ["callback_type_1", 160],
    ["callback_type_2", 164],
    ["callback_type_3", 190]
  ],
  "row_count": 3,
  "columns": ["callback_type", "total_callback_cnt"]
}
```

### 输出总结
```markdown
## 🧩 数据分析  
2024年1月21日当天共产生**514**次回访，三种类型回访量分布相对均衡，其中类型3回访量略高。

## **📌 关键发现**  
- 📊 **类型3回访量最高**，达**190**次，占总量的**36.9%**
- 📈 **类型1和类型2回访量接近**，分别为**160**次和**164**次
- 🔍 **整体回访分布较为均匀**，未出现明显的类型集中现象
```

---

## 6. 配置参数

### 6.1 LLM参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| model | Qwen/Qwen3-235B-A22B-Instruct-2507 | 使用的模型 |
| temperature | 0.3 | 温度参数，越低越稳定 |
| max_tokens | 512 | 最大输出token数 |
| timeout | 30s | 调用超时时间 |

### 6.2 提示词参数

| 参数 | 说明 |
|------|------|
| data_result | SQL执行结果(JSON字符串) |
| user_query | 用户原始问题 |
| current_time | 当前时间(用于时间相关分析) |

---

## 7. 错误处理

### 7.1 执行失败处理
```python
if not execution_result.get("success"):
    return f"查询执行失败: {execution_result.get('error', '未知错误')}"
```

### 7.2 LLM调用失败处理
```python
try:
    summary = llm_service.generate_summary(...)
except Exception as e:
    # 降级到默认总结
    summary = self._generate_default_summary(execution_result, query)
```

### 7.3 默认总结策略

| 场景 | 输出 |
|------|------|
| 单行单列 | "根据查询结果，{query}的答案是 {value}" |
| 多行/多列 | "查询成功，共返回 {count} 条数据" |
| 空结果 | "查询执行成功，返回 0 行数据" |

---

## 8. 集成指南

### 8.1 最小集成示例

```python
import yaml
from openai import OpenAI
from datetime import datetime
from typing import Dict, Any

class SimpleSummarizer:
    """简化版结果总结器"""
    
    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        
        # 加载提示词模板
        with open('template.yaml', 'r', encoding='utf-8') as f:
            self.template = yaml.safe_load(f)
    
    def summarize(self, query: str, data: Dict[str, Any]) -> str:
        """生成总结"""
        # 1. 构建提示词
        system_prompt = self.template['template']['summarizer']['system']
        user_prompt = self.template['template']['summarizer']['user'].format(
            data_result=str(data),
            user_query=query,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        # 2. 调用LLM
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        
        return response.choices[0].message.content.strip()


# 使用示例
summarizer = SimpleSummarizer(
    api_key="your-api-key",
    model="gpt-4"
)

result = summarizer.summarize(
    query="查询2024年1月销售数据",
    data={
        "rows": [["2024-01", 100000]],
        "row_count": 1,
        "columns": ["月份", "销售额"]
    }
)
print(result)
```

### 8.2 依赖安装

```bash
pip install pyyaml openai
```

---

## 9. 注意事项

1. **数据安全**: 确保敏感数据在传递给LLM前进行脱敏处理
2. **Token限制**: 大数据集可能需要截断或采样
3. **超时处理**: 建议设置合理的超时时间(30-60秒)
4. **缓存机制**: 相同查询结果可以缓存总结，减少LLM调用
5. **模型选择**: 建议使用支持中文的模型(如Qwen、GPT-4等)

---

## 10. 扩展建议

1. **多语言支持**: 可根据用户语言自动切换提示词语言
2. **自定义模板**: 支持不同业务场景使用不同的分析模板
3. **流式输出**: 可实现流式总结生成，提升用户体验
4. **结果验证**: 添加总结质量评估机制，确保准确性
