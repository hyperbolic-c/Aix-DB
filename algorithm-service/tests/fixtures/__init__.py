"""
测试数据Fixtures

提供预置的术语和SQL示例，用于填充测试请求体
"""

import yaml
import json
from pathlib import Path
from typing import List, Dict, Any


def load_terminologies(category: str = None) -> List[Dict[str, Any]]:
    """
    加载术语数据
    
    Args:
        category: 术语类别，None表示加载所有
        
    Returns:
        术语列表
    """
    fixtures_dir = Path(__file__).parent
    
    # 尝试加载YAML格式
    yaml_file = fixtures_dir / "terminologies.yaml"
    if yaml_file.exists():
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            terminologies = data.get("terminologies", [])
            
        if category:
            terminologies = [t for t in terminologies if t.get("category") == category]
        
        return terminologies
    
    # 尝试加载JSON格式
    json_file = fixtures_dir / "terminologies.json"
    if json_file.exists():
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            terminologies = data.get("terminologies", [])
            
        if category:
            terminologies = [t for t in terminologies if t.get("category") == category]
        
        return terminologies
    
    return []


def load_sql_examples(category: str = None) -> List[Dict[str, Any]]:
    """
    加载SQL示例数据
    
    Args:
        category: 示例类别，None表示加载所有
        
    Returns:
        SQL示例列表
    """
    fixtures_dir = Path(__file__).parent
    
    # 尝试加载YAML格式
    yaml_file = fixtures_dir / "sql_examples.yaml"
    if yaml_file.exists():
        with open(yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            examples = data.get("sql_examples", [])
            
        if category:
            examples = [e for e in examples if e.get("category") == category]
        
        return examples
    
    # 尝试加载JSON格式
    json_file = fixtures_dir / "sql_examples.json"
    if json_file.exists():
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            examples = data.get("sql_examples", [])
            
        if category:
            examples = [e for e in examples if e.get("category") == category]
        
        return examples
    
    return []


def get_terminology_by_term(term: str) -> Dict[str, Any]:
    """根据术语名称获取术语定义"""
    terminologies = load_terminologies()
    for t in terminologies:
        if t.get("term") == term or term in t.get("synonyms", []):
            return t
    return None


def get_examples_by_table(table_name: str) -> List[Dict[str, Any]]:
    """根据表名获取相关SQL示例"""
    examples = load_sql_examples()
    related = []
    
    # 提取表名前缀
    prefix = table_name.split('_')[0] if '_' in table_name else table_name
    
    for example in examples:
        # 检查示例中的表名是否匹配
        sql = example.get("sql", "")
        if prefix.lower() in sql.lower():
            related.append(example)
    
    return related
