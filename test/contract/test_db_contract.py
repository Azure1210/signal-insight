#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_db_contract.py
# @Path       : signal-insight/test/contract/test_db_contract.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: db 的存储契约测试。
"""db 的存储契约测试。

对读回方的承诺：ts 写库后是固定宽度的文本（毫秒为 0 的行也必须带 .000，
否则 parse_dates 按第一行推断格式、格式不同的行会悄悄变空值 —— D02 需求卡 2.6 的坑）；
write_partition 同一天重跑幂等、不同天互不影响；replace 全量替换、append 只增。
"""
import sqlite3

import pandas as pd

from signal_insight import db, dwd

from ods_schema import DWD_SIGNAL_COLS


def make_dwd(day="2018-10-03"):
    """两条记录：一条毫秒非 0、一条毫秒为 0 —— 2.6 的坑就是这两行格式不一致。"""
    return pd.DataFrame({
        "imsi": ["123456789012345678", "234567890123456789"],
        # format="mixed"：pandas 3 对混合格式（一行带微秒、一行不带）不再自动推断
        "ts": pd.to_datetime(["2018-10-03 08:00:00.123456", "2018-10-03 08:01:00"], format="mixed"),
        "dt": [day, day],
        "lac_id": [16789, 16789],
        "cell_id": [4708, 4709],
        "nid": [8, 8],
        "lac_cell": ["16789-4708", "16789-4709"],
    })


def test_ts_roundtrip_fixed_width_text(tmp_path):
    """写库后读回：parse_dates 不丢行、不悄悄变空（D02 2.6 回归）。"""
    con = sqlite3.connect(tmp_path / "dwd.db")
    db.write_partition(con, make_dwd(), "dwd_signal", "2018-10-03")
    read = pd.read_sql("SELECT * FROM dwd_signal", con, parse_dates=["ts"])
    con.close()
    assert read["ts"].notna().all()
    assert read["ts"].iloc[0] == pd.Timestamp("2018-10-03 08:00:00.123000")
    assert read["ts"].iloc[1] == pd.Timestamp("2018-10-03 08:01:00")


def test_table_schema_matches_dwd_contract(tmp_path):
    con = sqlite3.connect(tmp_path / "dwd.db")
    db.write_partition(con, make_dwd(), "dwd_signal", "2018-10-03")
    cols = [r[1] for r in con.execute('PRAGMA table_info("dwd_signal")')]
    con.close()
    assert cols == DWD_SIGNAL_COLS == dwd.DWD_COLS


def test_write_partition_idempotent_same_day(tmp_path):
    con = sqlite3.connect(tmp_path / "dwd.db")
    db.write_partition(con, make_dwd(), "dwd_signal", "2018-10-03")
    db.write_partition(con, make_dwd(), "dwd_signal", "2018-10-03")
    assert pd.read_sql("SELECT COUNT(*) n FROM dwd_signal", con)["n"].item() == 2
    con.close()


def test_write_partition_days_independent(tmp_path):
    con = sqlite3.connect(tmp_path / "dwd.db")
    db.write_partition(con, make_dwd("2018-10-02"), "dwd_signal", "2018-10-02")
    db.write_partition(con, make_dwd("2018-10-03"), "dwd_signal", "2018-10-03")
    db.write_partition(con, make_dwd("2018-10-02"), "dwd_signal", "2018-10-02")   # 重跑 10-02
    counts = pd.read_sql("SELECT dt, COUNT(*) n FROM dwd_signal GROUP BY dt", con)
    con.close()
    assert counts.set_index("dt")["n"].to_dict() == {"2018-10-02": 2, "2018-10-03": 2}


def test_replace_table_keeps_only_latest(tmp_path):
    con = sqlite3.connect(tmp_path / "dwd.db")
    db.replace_table(con, make_dwd().iloc[:1], "dim_cell")
    db.replace_table(con, make_dwd().iloc[:2], "dim_cell")
    assert pd.read_sql("SELECT COUNT(*) n FROM dim_cell", con)["n"].item() == 2
    con.close()


def test_append_table_only_grows(tmp_path):
    con = sqlite3.connect(tmp_path / "dwd.db")
    db.append_table(con, make_dwd().iloc[:1], "etl_log")
    db.append_table(con, make_dwd().iloc[:2], "etl_log")
    assert pd.read_sql("SELECT COUNT(*) n FROM etl_log", con)["n"].item() == 3
    con.close()
