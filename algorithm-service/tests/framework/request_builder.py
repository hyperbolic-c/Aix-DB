"""
测试请求构建器

从target_db/competition构建测试请求体
Schema来源: finalTableSchema.xlsx (而非final.db)

保持与算法内部实现解耦，只负责构建标准化的HTTP请求体
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class SchemaInfo:
    """Schema信息数据类"""
    name: str
    comment: str
    fields: List[Dict[str, str]]


class ExcelSchemaLoader:
    """
    从finalTableSchema.xlsx加载Schema信息
    
    Excel格式:
    - 序号不为NaN的行是新表的开始
    - 后续NaN的行属于同一个表
    """
    
    def __init__(self, excel_path: str):
        self.excel_path = Path(excel_path)
        self._schema_cache: Optional[Dict[str, Any]] = None
    
    def load_schema(self) -> Dict[str, Any]:
        """
        加载完整Schema
        
        Returns:
            {
                "database": "final",
                "db_type": "sqlite",
                "tables": [
                    {
                        "name": "表名",
                        "comment": "表描述",
                        "fields": [
                            {"name": "字段名", "type": "字段类型", "comment": "字段描述"}
                        ]
                    }
                ]
            }
        """
        if self._schema_cache:
            return self._schema_cache
        
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Schema文件不存在: {self.excel_path}")
        
        df = pd.read_excel(self.excel_path)
        schema = {"database": "final", "db_type": "sqlite", "tables": []}
        current_table = None
        
        for _, row in df.iterrows():
            # 序号不为NaN表示新表开始
            if pd.notna(row['序号']):
                # 保存之前的表
                if current_table:
                    schema["tables"].append(current_table)
                
                # 创建新表
                current_table = {
                    "name": row['表名'],
                    "comment": row['表描述'] if pd.notna(row['表描述']) else "",
                    "fields": []
                }
            
            # 添加字段到当前表
            if current_table and pd.notna(row['字段名']):
                field = {
                    "name": row['字段名'],
                    "type": row['字段类型'] if pd.notna(row['字段类型']) else "TEXT",
                    "comment": row['字段描述'] if pd.notna(row['字段描述']) else ""
                }
                current_table["fields"].append(field)
        
        # 保存最后一个表
        if current_table:
            schema["tables"].append(current_table)
        
        self._schema_cache = schema
        return schema
    
    def get_table_schema(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取指定表的Schema"""
        schema = self.load_schema()
        for table in schema["tables"]:
            if table["name"] == table_name:
                return table
        return None
    
    def get_related_tables(self, primary_table: str) -> List[Dict[str, Any]]:
        """
        获取与主表相关的所有表
        
        策略: 前缀匹配
        例如: item_callback_total_day -> 匹配所有以item开头的表
        """
        schema = self.load_schema()
        
        # 提取主表前缀
        prefix = primary_table.split('_')[0] if '_' in primary_table else primary_table
        
        related = []
        for table in schema["tables"]:
            if table["name"].startswith(prefix):
                related.append(table)
        
        return related
    
    def list_all_tables(self) -> List[str]:
        """列出所有表名"""
        schema = self.load_schema()
        return [t["name"] for t in schema["tables"]]
    
    def get_table_count(self) -> int:
        """获取表数量"""
        schema = self.load_schema()
        return len(schema["tables"])


class CompetitionRequestBuilder:
    """
    从target_db/competition构建测试请求体
    
    构建的请求体兼容多个算法服务版本，不依赖特定算法实现
    """
    
    def __init__(self, base_path: str = "target_db/competition"):
        """
        初始化
        
        Args:
            base_path: competition目录路径
        """
        self.base_path = Path(base_path)
        self.excel_path = self.base_path / "finalTableSchema.xlsx"
        self.db_path = self.base_path / "final.db"
        self.gold_file = self.base_path / "testCase" / "gold.jsonl"
        
        # 初始化Schema加载器
        self.schema_loader = ExcelSchemaLoader(str(self.excel_path))
        
        # 缓存
        self._gold_cache: Optional[Dict[int, Dict]] = None
    
    def build_request(
        self, 
        case_id: int, 
        include_related_tables: bool = True,
        custom_terminologies: Optional[List[Dict]] = None,
        custom_sql_examples: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        为指定case_id构建完整的HTTP请求体
        
        Args:
            case_id: 测试用例ID
            include_related_tables: 是否包含相关表
            custom_terminologies: 自定义术语列表
            custom_sql_examples: 自定义SQL示例列表
            
        Returns:
            标准HTTP请求体，兼容多个算法服务版本
        """
        # 1. 加载gold用例
        case = self._load_gold_case(case_id)
        if not case:
            raise ValueError(f"找不到测试用例 #{case_id}")
        
        primary_table = case.get("table", "")
        
        # 2. 从Excel提取Schema
        if include_related_tables:
            related_tables = self.schema_loader.get_related_tables(primary_table)
            table_names = [t["name"] for t in related_tables]
        else:
            table_names = [primary_table]
        
        schema_info = self._build_schema_info(table_names)
        
        # 3. 构建标准请求体
        request = {
            "query": case["question"],
            "datasource_config": {
                "db_type": "sqlite",
                "db_path": str(self.db_path)
            },
            "schema_info": schema_info,
            "terminologies": custom_terminologies or [],
            "training_examples": custom_sql_examples or [],
            "chat_history": [],
            "user_id": 1,
            "datasource_id": 1
        }
        
        return request
    
    def build_request_by_question(
        self,
        question: str,
        table_hint: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        根据问题构建请求体（用于自定义测试）
        
        Args:
            question: 用户问题
            table_hint: 表名提示
            **kwargs: 其他参数
            
        Returns:
            标准HTTP请求体
        """
        # 如果没有表提示，使用所有表
        if table_hint:
            related_tables = self.schema_loader.get_related_tables(table_hint)
            table_names = [t["name"] for t in related_tables]
        else:
            # 使用所有表（可能太多，建议限制）
            table_names = self.schema_loader.list_all_tables()[:5]  # 限制前5张表
        
        schema_info = self._build_schema_info(table_names)
        
        return {
            "query": question,
            "datasource_config": {
                "db_type": "sqlite",
                "db_path": str(self.db_path)
            },
            "schema_info": schema_info,
            "terminologies": kwargs.get("terminologies", []),
            "training_examples": kwargs.get("sql_examples", []),
            "chat_history": [],
            "user_id": 1,
            "datasource_id": 1
        }
    
    def _build_schema_info(self, table_names: List[str]) -> Dict[str, Any]:
        """
        构建schema_info（用于HTTP请求）
        
        Args:
            table_names: 表名列表
            
        Returns:
            schema_info字典
        """
        tables = []
        
        for table_name in table_names:
            table_schema = self.schema_loader.get_table_schema(table_name)
            if table_schema:
                tables.append({
                    "name": table_schema["name"],
                    "comment": table_schema.get("comment", ""),
                    "fields": [
                        {
                            "name": f["name"],
                            "type": f["type"],
                            "comment": f.get("comment", "")
                        }
                        for f in table_schema["fields"]
                    ]
                })
        
        return {"tables": tables}
    
    def _load_gold_case(self, case_id: int) -> Dict[str, Any]:
        """
        加载指定case_id的gold用例
        
        Args:
            case_id: 测试用例ID
            
        Returns:
            测试用例字典
        """
        if self._gold_cache is None:
            self._gold_cache = {}
            if self.gold_file.exists():
                with open(self.gold_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        case = json.loads(line.strip())
                        self._gold_cache[case["id"]] = case
        
        return self._gold_cache.get(case_id, {})
    
    def load_all_gold_cases(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        加载所有gold用例
        
        Args:
            limit: 限制数量
            
        Returns:
            测试用例列表
        """
        cases = []
        if self.gold_file.exists():
            with open(self.gold_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if limit and i >= limit:
                        break
                    cases.append(json.loads(line.strip()))
        return cases
    
    def get_case_info(self, case_id: int) -> Dict[str, Any]:
        """
        获取测试用例信息（不包含完整请求）
        
        Args:
            case_id: 测试用例ID
            
        Returns:
            用例信息
        """
        case = self._load_gold_case(case_id)
        if not case:
            return {}
        
        return {
            "id": case["id"],
            "question": case["question"],
            "reference_sql": case.get("sql", ""),
            "level": case.get("level", 0),
            "is_order": case.get("is_order", 0),
            "table": case.get("table", ""),
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取测试数据统计
        
        Returns:
            统计信息
        """
        cases = self.load_all_gold_cases()
        
        levels = {}
        tables = {}
        for case in cases:
            level = case.get("level", 0)
            levels[level] = levels.get(level, 0) + 1
            
            table = case.get("table", "unknown")
            tables[table] = tables.get(table, 0) + 1
        
        return {
            "total_cases": len(cases),
            "level_distribution": levels,
            "table_distribution": tables,
            "schema_tables": self.schema_loader.get_table_count(),
        }


# 便捷函数
def build_request(case_id: int, **kwargs) -> Dict[str, Any]:
    """便捷函数：构建请求体"""
    builder = CompetitionRequestBuilder()
    return builder.build_request(case_id, **kwargs)


def load_case(case_id: int) -> Dict[str, Any]:
    """便捷函数：加载测试用例"""
    builder = CompetitionRequestBuilder()
    return builder.get_case_info(case_id)
