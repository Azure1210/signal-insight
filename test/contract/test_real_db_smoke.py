#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_real_db_smoke.py
# @Path       : signal-insight/test/contract/test_real_db_smoke.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: 真实库对账（smoke）：只比表结构，不读数据行。
"""真实库对账（smoke）：只比表结构，不读数据行（AGENTS.md 1.4、15.3）。

data/ 不进 Git，所以这组测试默认跳过；本地想对账时显式打开：
    python -m pytest test/contract/test_real_db_smoke.py --run-smoke

如果真实库的 ODS 表被平台方改了结构，这里会最先报出来。
"""
import sqlite3
from pathlib import Path

import pytest

from ods_schema import (DIM_CELL_COLS, DIM_HOTSPOT_COLS, DWD_SIGNAL_COLS,
                        ETL_LOG_COLS, ODS_AOI_V2_COLS, ODS_CELL_COLS,
                        ODS_DISTRICT_COLS, ODS_SIGNAL_COLS)

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "signal.db"

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def real_db():
    if not DB_PATH.exists():
        pytest.skip(f"真实库不存在：{DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


def _cols(con, table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]


def test_ods_tables_match_contract(real_db):
    for table, expected in [("ods_signal", ODS_SIGNAL_COLS), ("ods_cell", ODS_CELL_COLS),
                            ("ods_district_boundary", ODS_DISTRICT_COLS), ("ods_aoi_v2", ODS_AOI_V2_COLS)]:
        assert _cols(real_db, table) == expected, f"真实库 {table} 的结构与契约不符，流水线会读错列"


def test_product_tables_match_contract(real_db):
    for table, expected in [("dwd_signal", DWD_SIGNAL_COLS), ("dim_cell", DIM_CELL_COLS),
                            ("dim_hotspot", DIM_HOTSPOT_COLS), ("etl_log", ETL_LOG_COLS)]:
        assert _cols(real_db, table) == expected, f"真实库 {table} 的结构与契约不符，下游会读错列"
