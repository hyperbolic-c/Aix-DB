"""SQL 工具（基于请求注入的数据源配置）。"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from langchain_core.tools import tool

from ...common.datasource_util import (
    DatasourceInfo,
    execute_query,
    get_table_info,
    get_table_relationships,
    list_tables,
)
from .tool_call_manager import get_current_session, get_tool_call_manager

logger = logging.getLogger(__name__)


@dataclass
class DatasourceContext:
    datasource: DatasourceInfo
    session_id: Optional[str] = None


from contextvars import ContextVar

_current_datasource: ContextVar[Optional[DatasourceContext]] = ContextVar(
    "native_datasource", default=None
)


def set_native_datasource_info(
    datasource: DatasourceInfo, session_id: Optional[str] = None
) -> None:
    """设置当前请求的数据源信息。"""
    _current_datasource.set(DatasourceContext(datasource=datasource, session_id=session_id))
    logger.info("设置数据源信息: type=%s, session=%s", datasource.type, session_id)


def _get_datasource() -> Optional[DatasourceContext]:
    return _current_datasource.get()


def _get_session_id() -> str:
    session_id = get_current_session()
    if session_id:
        return session_id
    ctx = _get_datasource()
    if ctx and ctx.session_id:
        return ctx.session_id
    return "default"


def _check_tool_call(tool_name: str, query: Optional[str] = None) -> tuple[bool, str]:
    session_id = _get_session_id()
    manager = get_tool_call_manager()
    return manager.check_before_call(session_id, tool_name, query)


def _record_tool_call(tool_name: str, success: bool, query: Optional[str] = None) -> None:
    session_id = _get_session_id()
    manager = get_tool_call_manager()
    manager.record_call(session_id, tool_name, success, query)


@tool
def sql_db_list_tables() -> str:
    """列出数据库中的所有表名。"""
    ctx = _get_datasource()
    if not ctx:
        return "错误: 未设置数据源信息"

    allowed, reason = _check_tool_call("sql_db_list_tables")
    if not allowed:
        return reason

    try:
        table_names = list_tables(ctx.datasource)
        if not table_names:
            _record_tool_call("sql_db_list_tables", True)
            return "数据库中没有表"

        table_info = get_table_info(ctx.datasource, table_names)
        result_lines = ["数据库中有以下表：\n"]
        for table_name in table_names:
            comment = table_info.get(table_name, {}).get("table_comment", "")
            if comment:
                result_lines.append(f"- {table_name}: {comment}")
            else:
                result_lines.append(f"- {table_name}")

        result_lines.append("\n✅ 表列表已获取完成。如需查看表结构，请使用 sql_db_schema 工具。")
        _record_tool_call("sql_db_list_tables", True)
        return "\n".join(result_lines)
    except Exception as exc:
        _record_tool_call("sql_db_list_tables", False)
        logger.error("列出表失败: %s", exc, exc_info=True)
        return f"列出表失败: {str(exc)[:100]}"


@tool
def sql_db_schema(table_names) -> str:
    """
    获取指定表的架构信息。

    Args:
        table_names: 表名，可以是单个表名或多个表名（用逗号分隔）
    """
    ctx = _get_datasource()
    if not ctx:
        return "错误: 未设置数据源信息"

    allowed, reason = _check_tool_call("sql_db_schema")
    if not allowed:
        return reason

    try:
        if isinstance(table_names, str):
            table_list = [t.strip() for t in table_names.split(",") if t.strip()]
        elif isinstance(table_names, list):
            table_list = [str(t).strip() for t in table_names if str(t).strip()]
        else:
            table_list = [str(table_names).strip()] if table_names else []

        table_info = get_table_info(ctx.datasource, table_list or None)
        if not table_list:
            table_list = list(table_info.keys())
        schema_parts = []
        for table_name in table_list:
            if table_name not in table_info:
                schema_parts.append(f"表 '{table_name}' 不存在")
                continue

            info = table_info[table_name]
            columns = info.get("columns", {})
            table_comment = info.get("table_comment", "")

            schema_text = f"\n表 '{table_name}':"
            if table_comment:
                schema_text += f"\n注释: {table_comment}"

            schema_text += "\n列:"
            for col_name, col_info in columns.items():
                col_type = col_info.get("type", "")
                col_comment = col_info.get("comment", "")
                schema_text += f"\n  - {col_name} ({col_type})"
                if col_comment:
                    schema_text += f" - {col_comment}"

            schema_parts.append(schema_text)

        _record_tool_call("sql_db_schema", True)
        result = "\n".join(schema_parts) if schema_parts else "未找到表信息"
        result += "\n\n✅ 表架构已获取完成。请基于此信息编写 SQL 查询，无需重复获取架构。"
        return result
    except Exception as exc:
        _record_tool_call("sql_db_schema", False)
        logger.error("获取表架构失败: %s", exc, exc_info=True)
        return f"获取表架构失败: {str(exc)[:100]}"


@tool
def sql_db_query(query: str) -> str:
    """
    执行 SQL SELECT 查询并返回结果。
    只允许执行 SELECT 查询，不允许执行 INSERT、UPDATE、DELETE、DROP 等操作。
    """
    ctx = _get_datasource()
    if not ctx:
        return "错误: 未设置数据源信息"

    query_upper = query.strip().upper()
    forbidden_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE",
    ]
    for keyword in forbidden_keywords:
        if keyword in query_upper:
            return f"错误: 不允许执行 {keyword} 操作，只允许 SELECT 查询"

    if not query_upper.startswith("SELECT"):
        return "错误: 只允许执行 SELECT 查询"

    allowed, reason = _check_tool_call("sql_db_query", query)
    if not allowed:
        return reason

    logger.info("执行 SQL 查询: %s", query[:500])

    try:
        result_data = execute_query(ctx.datasource, query)
        _record_tool_call("sql_db_query", True, query)

        if not result_data:
            return "✅ 查询成功执行，但没有返回数据。"

        max_rows = 50
        result_rows = result_data[:max_rows]

        if len(result_data) > max_rows:
            result_str = f"✅ 查询成功，返回 {len(result_data)} 行数据（显示前 {max_rows} 行）:\n\n"
        else:
            result_str = f"✅ 查询成功，返回 {len(result_data)} 行数据:\n\n"

        if result_rows:
            columns = list(result_rows[0].keys())
            col_widths = {}
            for col in columns:
                col_widths[col] = min(
                    max(
                        len(str(col)),
                        max(len(str(row.get(col, ""))[:50]) for row in result_rows),
                    ),
                    50,
                )

            header = " | ".join(str(col).ljust(col_widths[col]) for col in columns)
            separator = "-" * min(len(header), 200)
            result_str += header + "\n" + separator + "\n"

            for row in result_rows:
                row_str = " | ".join(
                    str(row.get(col, ""))[:50].ljust(col_widths[col])
                    for col in columns
                )
                result_str += row_str + "\n"

        result_str += "\n✅ 查询已完成。请基于以上结果进行分析，无需重复执行相同查询。"
        return result_str

    except Exception as exc:
        _record_tool_call("sql_db_query", False, query)
        error_msg = str(exc)

        concise_error = _handle_starrocks_error(error_msg, query)
        if concise_error:
            logger.error("SQL 查询失败: %s", error_msg[:200])
            return concise_error

        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."

        logger.error("SQL 查询失败: %s", error_msg)
        return (
            f"SQL 执行失败: {error_msg}\n\n"
            "请检查 SQL 语法和表结构是否正确。"
            "如果之前已获取表架构，请直接使用已有信息，无需重复查询。"
        )


@tool
def sql_db_query_checker(query: str) -> str:
    """
    检查 SQL 查询的语法是否正确。
    注意：这只是一个基本的检查，不会实际执行查询。
    """
    allowed, reason = _check_tool_call("sql_db_query_checker")
    if not allowed:
        return reason

    query_upper = query.strip().upper()

    if not query_upper:
        _record_tool_call("sql_db_query_checker", False)
        return "错误: SQL 查询为空"

    forbidden_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "CREATE",
    ]
    for keyword in forbidden_keywords:
        if keyword in query_upper:
            _record_tool_call("sql_db_query_checker", False)
            return f"错误: 不允许执行 {keyword} 操作，只允许 SELECT 查询"

    if not query_upper.startswith("SELECT"):
        _record_tool_call("sql_db_query_checker", False)
        return "错误: 只允许执行 SELECT 查询"

    issues = []
    if "FROM" not in query_upper:
        issues.append("缺少 FROM 子句")

    if query.count("(") != query.count(")"):
        issues.append("括号不匹配")

    if query.count("'") % 2 != 0:
        issues.append("单引号不匹配")

    _record_tool_call("sql_db_query_checker", True)

    if issues:
        return f"SQL 语法警告: {', '.join(issues)}"

    return "✅ SQL 查询语法检查通过，可以执行。"


@tool
def sql_db_table_relationship(table_names: str = "") -> str:
    """
    获取指定表之间的关系信息（外键/关联关系）。
    """
    ctx = _get_datasource()
    if not ctx:
        return "错误: 未设置数据源信息"

    allowed, reason = _check_tool_call("sql_db_table_relationship")
    if not allowed:
        return reason

    try:
        table_list = None
        if table_names and table_names.strip():
            table_list = [t.strip() for t in table_names.split(",") if t.strip()]

        relationships = get_table_relationships(ctx.datasource, table_list)

        _record_tool_call("sql_db_table_relationship", True)

        if not relationships:
            if table_list:
                return (
                    f"未找到表 {', '.join(table_list)} 之间的关系配置。\n\n"
                    "可能的原因：\n"
                    "1. 这些表之间没有配置外键/关联关系\n"
                    "2. 可以尝试通过列名推断关系（如 customer_id 可能关联 customers.id）\n\n"
                    "提示：可以查看表架构中的列名来推断可能的关联关系。"
                )
            return (
                "当前数据源未配置任何表关系。\n\n"
                "提示：可以通过表架构中的外键列（如 xxx_id）推断可能的关联关系。"
            )

        result_lines = ["表之间的关系如下：\n"]
        for rel in relationships:
            result_lines.append(f"  • {rel}")

        result_lines.append("\n✅ 表关系已获取完成。")
        result_lines.append("请使用以上关系信息编写正确的 JOIN 语句。")

        return "\n".join(result_lines)

    except Exception as exc:
        _record_tool_call("sql_db_table_relationship", False)
        logger.error("获取表关系失败: %s", exc, exc_info=True)
        return f"获取表关系失败: {str(exc)[:100]}"


def _handle_starrocks_error(error_msg: str, query: str) -> Optional[str]:
    error_lower = error_msg.lower()

    if "cannot be resolved" in error_lower:
        column_match = re.search(r"Column\s+['`]([^'`]+)['`]", error_msg, re.IGNORECASE)
        column_name = column_match.group(1) if column_match else "未知列"

        table_aliases = set()
        alias_pattern = r"FROM\s+[`]?(\w+)[`]?\s+(\w+)|JOIN\s+[`]?(\w+)[`]?\s+(\w+)"
        matches = re.findall(alias_pattern, query, re.IGNORECASE)
        for match in matches:
            if match[1]:
                table_aliases.add(match[1])
            if match[3]:
                table_aliases.add(match[3])

        return (
            f"SQL 执行失败: 列 '{column_name}' 无法解析。\n"
            f"已定义的表别名: {', '.join(sorted(table_aliases)) if table_aliases else '无'}\n\n"
            "请检查：\n"
            "1. 表别名是否正确定义\n"
            "2. 列名是否存在于对应的表中\n"
            "3. JOIN 语句是否正确\n\n"
            "请使用已获取的表架构信息修正 SQL，无需重复查询架构。"
        )

    if "table" in error_lower and ("doesn't exist" in error_lower or "not exist" in error_lower):
        return (
            "SQL 执行失败: 表不存在。\n\n"
            "请检查表名是否正确，可使用 sql_db_list_tables 查看可用表列表。"
        )

    return None
