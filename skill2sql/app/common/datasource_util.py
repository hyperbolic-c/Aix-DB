"""数据源工具：解析配置、建立连接、执行查询、获取 schema。"""

import logging
import urllib.parse
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ConnectType(str, Enum):
    sqlalchemy = "sqlalchemy"
    native = "native"


SQLALCHEMY_TYPES = {
    "mysql",
    "pg",
    "postgres",
    "postgresql",
    "oracle",
    "sqlserver",
    "mssql",
    "ck",
    "clickhouse",
    "sqlite",
    "doris",
    "starrocks",
}


@dataclass(frozen=True)
class DatasourceInfo:
    type: str
    uri: str
    db_schema: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)


class DatasourceError(ValueError):
    pass


def parse_datasource(payload: Dict[str, Any]) -> DatasourceInfo:
    if not isinstance(payload, dict):
        raise DatasourceError("datasource 必须是对象")

    ds_type = (payload.get("type") or "").strip()
    uri = (payload.get("uri") or "").strip()
    db_schema = (payload.get("db_schema") or payload.get("schema") or "").strip()
    config = payload.get("config") or {}

    if not uri:
        if not ds_type:
            raise DatasourceError("datasource.type 不能为空")
        uri = build_connection_uri(ds_type, config)

    if not uri:
        raise DatasourceError("无法解析 datasource.uri")

    return DatasourceInfo(type=ds_type or "unknown", uri=uri, db_schema=db_schema or None, config=config)


def get_connect_type(ds: DatasourceInfo) -> ConnectType:
    if ds.uri:
        return ConnectType.sqlalchemy
    if ds.type.lower() in SQLALCHEMY_TYPES:
        return ConnectType.sqlalchemy
    return ConnectType.native


def build_connection_uri(ds_type: str, config: Dict[str, Any]) -> str:
    ds_type = (ds_type or "").lower()
    host = config.get("host", "")
    port = config.get("port")
    username = config.get("username", "")
    password = config.get("password", "")
    database = config.get("database", "")
    extra_jdbc = config.get("extraJdbc", "")
    mode = config.get("mode", "service_name")

    if not host and ds_type not in ("sqlite",):
        return ""

    username_encoded = urllib.parse.quote(str(username))
    password_encoded = urllib.parse.quote(str(password))

    def _append_extra(base_uri: str) -> str:
        if extra_jdbc:
            return f"{base_uri}?{extra_jdbc}"
        return base_uri

    if ds_type in ("mysql", "doris", "starrocks"):
        port = port or 3306
        return _append_extra(
            f"mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database}"
        )

    if ds_type in ("pg", "postgres", "postgresql"):
        port = port or 5432
        return _append_extra(
            f"postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database}"
        )

    if ds_type == "oracle":
        port = port or 1521
        if mode == "service_name":
            base = f"oracle+oracledb://{username_encoded}:{password_encoded}@{host}:{port}?service_name={database}"
        else:
            base = f"oracle+oracledb://{username_encoded}:{password_encoded}@{host}:{port}/{database}"
        return _append_extra(base)

    if ds_type in ("sqlserver", "mssql"):
        port = port or 1433
        return _append_extra(
            f"mssql+pymssql://{username_encoded}:{password_encoded}@{host}:{port}/{database}"
        )

    if ds_type in ("ck", "clickhouse"):
        port = port or 8123
        return _append_extra(
            f"clickhouse+http://{username_encoded}:{password_encoded}@{host}:{port}/{database}"
        )

    if ds_type == "sqlite":
        return f"sqlite:///{database}" if database else "sqlite:///"

    return ""


def _create_engine(ds: DatasourceInfo) -> Engine:
    connect_args = {}
    timeout = ds.config.get("timeout")
    if timeout is not None:
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = None
    if timeout:
        if ds.type.lower() in ("mysql", "doris", "starrocks", "pg", "postgres", "postgresql"):
            connect_args["connect_timeout"] = timeout
        elif ds.type.lower() in ("sqlserver", "mssql"):
            connect_args["timeout"] = timeout

    if connect_args:
        return create_engine(ds.uri, pool_pre_ping=True, connect_args=connect_args)

    return create_engine(ds.uri, pool_pre_ping=True)


def list_tables(ds: DatasourceInfo) -> List[str]:
    engine = _create_engine(ds)
    inspector = inspect(engine)
    return inspector.get_table_names(schema=ds.db_schema)


def get_table_info(
    ds: DatasourceInfo, table_names: Optional[Iterable[str]] = None
) -> Dict[str, Dict[str, Any]]:
    engine = _create_engine(ds)
    inspector = inspect(engine)

    if table_names is None:
        table_names = inspector.get_table_names(schema=ds.db_schema)

    info: Dict[str, Dict[str, Any]] = {}

    for table in table_names:
        columns = {}
        for col in inspector.get_columns(table, schema=ds.db_schema):
            columns[col.get("name")] = {
                "type": str(col.get("type")),
                "comment": col.get("comment") or "",
            }

        table_comment = ""
        try:
            comment_obj = inspector.get_table_comment(table, schema=ds.db_schema)
            table_comment = (comment_obj or {}).get("text") or ""
        except Exception:
            table_comment = ""

        foreign_keys = []
        try:
            fk_list = inspector.get_foreign_keys(table, schema=ds.db_schema)
            for fk in fk_list:
                referred_table = fk.get("referred_table")
                referred_columns = fk.get("referred_columns") or []
                constrained_columns = fk.get("constrained_columns") or []
                for idx, col in enumerate(constrained_columns):
                    if idx < len(referred_columns):
                        foreign_keys.append(
                            f"{table}.{col} = {referred_table}.{referred_columns[idx]}"
                        )
        except Exception:
            foreign_keys = []

        info[table] = {
            "columns": columns,
            "foreign_keys": foreign_keys,
            "table_comment": table_comment,
        }

    return info


def get_table_relationships(
    ds: DatasourceInfo, table_names: Optional[Iterable[str]] = None
) -> List[str]:
    info = get_table_info(ds, table_names)
    relationships: List[str] = []
    for table_info in info.values():
        for fk in table_info.get("foreign_keys", []):
            if fk not in relationships:
                relationships.append(fk)
    return relationships


def execute_query(ds: DatasourceInfo, query: str) -> List[Dict[str, Any]]:
    engine = _create_engine(ds)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.mappings().all()
    except SQLAlchemyError as exc:
        raise RuntimeError(str(exc)) from exc

    output: List[Dict[str, Any]] = []
    for row in rows:
        row_dict: Dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                row_dict[key] = float(value)
            elif hasattr(value, "isoformat"):
                try:
                    row_dict[key] = value.isoformat()
                except Exception:
                    row_dict[key] = value
            else:
                row_dict[key] = value
        output.append(row_dict)
    return output
