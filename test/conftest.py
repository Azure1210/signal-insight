#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : conftest.py
# @Path       : signal-insight/test/conftest.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: pytest 根配置：共享 fixture 与命令行参数。
"""pytest 根配置：共享 fixture 与命令行参数。

运行方式（项目根目录）：
    python -m pytest                 # 全部测试（不含真实库对账）
    python -m pytest --run-smoke     # 加跑 data/signal.db 的对账测试

signal_insight 包的导入路径由 pyproject.toml 的 [tool.pytest.ini_options] pythonpath 提供，
这里不再 hack sys.path，也不依赖 pip install -e。
"""
import sqlite3

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: 依赖真实数据库 data/signal.db 的对账测试")


def pytest_addoption(parser):
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="运行依赖真实数据库 data/signal.db 的对账测试（默认跳过）",
    )


def pytest_collection_modifyitems(config, items):
    """不给 --run-smoke 时，跳过所有标了 smoke 的测试：CI 和没有 data/ 的机器照常跑。"""
    if config.getoption("--run-smoke"):
        return
    skip = pytest.mark.skip(reason="需要 --run-smoke 才运行（依赖真实 data/signal.db）")
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def con():
    """内存 SQLite 连接：每个测试一个独立的库，测试结束自动关闭。"""
    c = sqlite3.connect(":memory:")
    yield c
    c.close()
