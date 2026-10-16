#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_pipeline_contract.py
# @Path       : signal-insight/test/contract/test_pipeline_contract.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: pipeline.run_day 的端到端契约测试。
"""pipeline.run_day 的端到端契约测试。

对调用方的承诺：给定符合契约的 ODS 表，产出的四张表
（dwd_signal / dim_cell / dim_hotspot / etl_log）结构与内容正确；
同一天重跑幂等；返回的日志 DataFrame 就是写进 etl_log 的那份。
"""
import sqlite3

import pandas as pd

from signal_insight import pipeline

from ods_schema import (DIM_CELL_COLS, DIM_HOTSPOT_COLS, DWD_SIGNAL_COLS,
                        ETL_LOG_COLS, ODS_AOI_V2_COLS, ODS_CELL_COLS,
                        ODS_DISTRICT_COLS, ODS_SIGNAL_COLS)

DAY = "2018-10-03"
# run_day 的实际执行顺序：write_dim_cell 在 build_dim_hotspot 之前
# （write_dim_hotspot 的参数 build_dim_hotspot(...) 要到调用那一刻才求值）
EXPECTED_STEPS = ["extract_ods", "clean_signal", "write_dwd", "build_dim_cell",
                  "write_dim_cell", "build_dim_hotspot", "write_dim_hotspot"]


def test_ods_schema_contract(ods_con):
    """pipeline 依赖的 ODS 表结构必须与契约常量一致（常量抄自真实库，见 ods_schema.py）。

    pipeline 里写死的是 SELECT *，列的顺序变了 clean/维表就会读错位。
    """
    for table, cols in [("ods_signal", ODS_SIGNAL_COLS), ("ods_cell", ODS_CELL_COLS),
                        ("ods_district_boundary", ODS_DISTRICT_COLS), ("ods_aoi_v2", ODS_AOI_V2_COLS)]:
        actual = [r[1] for r in ods_con.execute(f'PRAGMA table_info("{table}")')]
        assert actual == cols, f"{table} 的结构与契约不符"


def test_run_day_produces_four_tables(ods_db_path):
    log = pipeline.run_day(DAY, ods_db_path)
    con = sqlite3.connect(ods_db_path)
    dwd_s = pd.read_sql("SELECT * FROM dwd_signal", con)
    dim_c = pd.read_sql("SELECT * FROM dim_cell", con)
    dim_h = pd.read_sql("SELECT * FROM dim_hotspot", con)
    etl = pd.read_sql("SELECT * FROM etl_log", con)
    con.close()
    # 产物表：结构与行数（33 行 ODS → 清洗后 24 行 dwd）
    assert len(dwd_s) == 24 and (dwd_s["dt"] == DAY).all()
    assert list(dwd_s.columns) == DWD_SIGNAL_COLS
    assert len(dim_c) == 3 and list(dim_c.columns) == DIM_CELL_COLS
    assert len(dim_h) == 1 and list(dim_h.columns) == DIM_HOTSPOT_COLS
    # 运行记录：7 步、同一批次、日期分区
    assert list(etl.columns) == ETL_LOG_COLS
    assert etl["步骤"].tolist() == EXPECTED_STEPS
    assert etl["批次"].nunique() == 1
    assert (etl["日期分区"] == DAY).all()
    # 步骤行数：读 33 行 → 清洗出 24 行 → dwd 写 24 行
    ex = etl.loc[etl["步骤"] == "extract_ods"].iloc[0]
    assert pd.isna(ex["输入行数"]) and ex["输出行数"] == 33   # con 不是 DataFrame，输入行数留空
    cl = etl.loc[etl["步骤"] == "clean_signal"].iloc[0]
    assert cl["输入行数"] == 33 and cl["输出行数"] == 24
    # 返回的日志就是写进表的那份
    pd.testing.assert_frame_equal(log, etl, check_dtype=False)


def test_run_day_idempotent(ods_db_path):
    pipeline.run_day(DAY, ods_db_path)
    pipeline.run_day(DAY, ods_db_path)
    con = sqlite3.connect(ods_db_path)
    assert pd.read_sql("SELECT COUNT(*) n FROM dwd_signal", con)["n"].item() == 24   # 分区重写，不翻倍
    etl = pd.read_sql("SELECT * FROM etl_log", con)
    con.close()
    assert len(etl) == len(EXPECTED_STEPS) * 2      # 日志追加：两次运行的批次号不同
    assert etl["批次"].nunique() == 2


def test_run_day_another_day_partition(ods_db_path):
    pipeline.run_day("2018-10-02", ods_db_path)     # 库里只有 4 行 10-02 的信令
    con = sqlite3.connect(ods_db_path)
    dwd_s = pd.read_sql("SELECT * FROM dwd_signal", con)
    con.close()
    assert len(dwd_s) == 4
    assert (dwd_s["dt"] == "2018-10-02").all()
