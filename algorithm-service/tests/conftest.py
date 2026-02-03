"""
Pytest配置和共享fixture

提供测试用的共享fixture和配置
"""

import pytest
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def competition_builder():
    """提供CompetitionRequestBuilder实例"""
    from framework.request_builder import CompetitionRequestBuilder
    return CompetitionRequestBuilder("target_db/competition")


@pytest.fixture
def schema_loader():
    """提供ExcelSchemaLoader实例"""
    from framework.request_builder import ExcelSchemaLoader
    return ExcelSchemaLoader("target_db/competition/finalTableSchema.xlsx")


@pytest.fixture
def syntax_checker():
    """提供SQLSyntaxChecker实例"""
    from framework.validators import SQLSyntaxChecker
    return SQLSyntaxChecker()


@pytest.fixture
def execution_validator():
    """提供ExecutionValidator实例"""
    from framework.validators import ExecutionValidator
    return ExecutionValidator("target_db/competition/final.db")


@pytest.fixture
def sample_request():
    """提供示例请求数据"""
    return {
        "query": "查询最近7天的订单量",
        "datasource_config": {
            "db_type": "sqlite",
            "db_path": "target_db/competition/final.db"
        },
        "schema_info": {
            "tables": [
                {
                    "name": "orders",
                    "comment": "订单表",
                    "fields": [
                        {"name": "id", "type": "INTEGER", "comment": "订单ID"},
                        {"name": "order_date", "type": "DATETIME", "comment": "订单日期"},
                        {"name": "amount", "type": "DECIMAL", "comment": "订单金额"}
                    ]
                }
            ]
        },
        "terminologies": [],
        "training_examples": [],
        "chat_history": [],
        "user_id": 1,
        "datasource_id": 1
    }


# 配置pytest
def pytest_configure(config):
    """配置pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "gold: marks tests as gold case tests"
    )


# 命令行选项
def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="运行慢速测试"
    )
    parser.addoption(
        "--run-integration", action="store_true", default=False, help="运行集成测试"
    )


# 根据选项跳过测试
def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="需要 --run-slow 选项")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(reason="需要 --run-integration 选项")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
