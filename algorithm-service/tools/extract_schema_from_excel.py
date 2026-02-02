"""
从Excel文件提取完整的Schema信息
finalTableSchema.xlsx 格式解析
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any


def parse_excel_schema(excel_path: str) -> Dict[str, Any]:
    """
    解析Excel格式的Schema文件
    
    Excel格式特点：
    - 序号不为NaN的行是新表的开始
    - 后续NaN的行属于同一个表
    
    Args:
        excel_path: Excel文件路径
        
    Returns:
        Schema字典
    """
    df = pd.read_excel(excel_path)
    
    schema = {
        "database": "final",
        "db_type": "sqlite",
        "tables": []
    }
    
    current_table = None
    
    for _, row in df.iterrows():
        # 如果序号不为NaN，说明是新表的开始
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
    
    return schema


def compare_with_database(excel_schema: Dict, db_path: str) -> Dict:
    """
    对比Excel Schema和数据库实际Schema
    
    Args:
        excel_schema: 从Excel解析的Schema
        db_path: 数据库路径
        
    Returns:
        对比结果
    """
    import sqlite3
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    comparison = {
        "excel_tables": len(excel_schema["tables"]),
        "db_tables": 0,
        "matched_tables": 0,
        "mismatched_tables": [],
        "details": []
    }
    
    # 获取数据库所有表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'")
    db_tables = {row[0] for row in cursor.fetchall()}
    comparison["db_tables"] = len(db_tables)
    
    for table in excel_schema["tables"]:
        table_name = table["name"]
        excel_fields = {f["name"] for f in table["fields"]}
        
        if table_name not in db_tables:
            comparison["mismatched_tables"].append({
                "table": table_name,
                "reason": "Table not found in database"
            })
            continue
        
        # 获取数据库表的字段
        cursor.execute(f"PRAGMA table_info({table_name})")
        db_fields = {row[1] for row in cursor.fetchall()}
        
        # 对比字段
        missing_in_excel = db_fields - excel_fields
        missing_in_db = excel_fields - db_fields
        
        if missing_in_excel or missing_in_db:
            comparison["mismatched_tables"].append({
                "table": table_name,
                "missing_in_excel": list(missing_in_excel),
                "missing_in_db": list(missing_in_db)
            })
        else:
            comparison["matched_tables"] += 1
        
        comparison["details"].append({
            "table": table_name,
            "excel_fields": len(excel_fields),
            "db_fields": len(db_fields),
            "match": len(missing_in_excel) == 0 and len(missing_in_db) == 0
        })
    
    conn.close()
    return comparison


def generate_m_schema(excel_schema: Dict) -> str:
    """
    生成M-Schema格式的字符串
    
    Args:
        excel_schema: Schema字典
        
    Returns:
        M-Schema字符串
    """
    lines = [f"【DB_ID】 {excel_schema['database']}", "【Schema】"]
    
    for table in excel_schema["tables"]:
        table_line = f"# Table: {table['name']}"
        if table.get("comment"):
            table_line += f", {table['comment']}"
        lines.append(table_line)
        lines.append("[")
        
        for field in table["fields"]:
            field_line = f"({field['name']}:{field['type']}"
            if field.get("comment"):
                field_line += f", {field['comment']}"
            field_line += "),"
            lines.append(field_line)
        
        lines.append("]")
    
    return "\n".join(lines)


def main():
    """主函数"""
    excel_path = "/Users/liam/LLMPro/Aix-DB/target_db/competition/finalTableSchema.xlsx"
    db_path = "/Users/liam/LLMPro/Aix-DB/target_db/competition/final.db"
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 80)
    print("从Excel提取Schema信息")
    print("=" * 80)
    
    # 解析Excel
    print(f"\n读取Excel文件: {excel_path}")
    schema = parse_excel_schema(excel_path)
    
    print(f"发现 {len(schema['tables'])} 张表:")
    for table in schema["tables"]:
        print(f"  - {table['name']}: {len(table['fields'])} 个字段")
    
    # 保存完整Schema
    schema_file = output_dir / "schema_from_excel.json"
    with open(schema_file, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"\nSchema已保存: {schema_file}")
    
    # 生成M-Schema
    m_schema = generate_m_schema(schema)
    m_schema_file = output_dir / "m_schema_from_excel.txt"
    with open(m_schema_file, 'w', encoding='utf-8') as f:
        f.write(m_schema)
    print(f"M-Schema已保存: {m_schema_file}")
    print(f"M-Schema长度: {len(m_schema)} 字符")
    
    # 对比数据库
    print("\n" + "=" * 80)
    print("与数据库对比")
    print("=" * 80)
    comparison = compare_with_database(schema, db_path)
    
    print(f"Excel表数量: {comparison['excel_tables']}")
    print(f"数据库表数量: {comparison['db_tables']}")
    print(f"匹配的表: {comparison['matched_tables']}")
    
    if comparison['mismatched_tables']:
        print(f"\n不匹配的表 ({len(comparison['mismatched_tables'])}个):")
        for item in comparison['mismatched_tables']:
            print(f"  - {item['table']}: {item.get('reason', 'Field mismatch')}")
    
    # 保存对比结果
    comparison_file = output_dir / "schema_comparison.json"
    with open(comparison_file, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"\n对比结果已保存: {comparison_file}")
    
    # 打印前3张表的详细信息
    print("\n" + "=" * 80)
    print("前3张表详细信息")
    print("=" * 80)
    for table in schema["tables"][:3]:
        print(f"\n表: {table['name']}")
        print(f"  描述: {table.get('comment', 'N/A')}")
        print(f"  字段数: {len(table['fields'])}")
        for field in table["fields"][:5]:
            print(f"    - {field['name']} ({field['type']}): {field.get('comment', '')}")
        if len(table["fields"]) > 5:
            print(f"    ... 还有 {len(table['fields']) - 5} 个字段")


if __name__ == "__main__":
    main()
