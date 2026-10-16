#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_db.py
# @Path       : signal-insight/test/unit/test_db.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: db 的单元测试：时间格式化与三种写入函数。
"""db 的单元测试：时间格式化（_for_storage）与三种写入函数的行数语义。"""
import pandas as pd
import pytest

from signal_insight import db


# ── _for_storage ──

def test_for_storage_formats_ts_with_and_without_ms():
    df = pd.DataFrame({
        # format="mixed"：pandas 3 对混合格式（一行带微秒、一行不带）不再自动推断
        "ts": pd.to_datetime(["2026-10-15 10:00:00.123456", "2026-10-15 10:00:00"], format="mixed"),
        "x": [1, 2],
    })
    out = db._for_storage(df)
    # 毫秒非 0 保留 3 位；毫秒为 0 也补 .000 —— 格式统一才不会读回时丢行
    assert out["ts"].tolist() == ["2026-10-15 10:00:00.123", "2026-10-15 10:00:00.000"]
    assert (out["x"] == df["x"]).all()               # 非时间列不动


def test_for_storage_does_not_mutate_input():
    df = pd.DataFrame({"ts": pd.to_datetime(["2026-10-15 10:00:00.123"])})
    db._for_storage(df)
    assert pd.api.types.is_datetime64_any_dtype(df["ts"])   # 原 df 仍是时间类型


def test_for_storage_ignores_tz_aware_nothing():
    df = pd.DataFrame({"v": [1, 2]})
    out = db._for_storage(df)
    pd.testing.assert_frame_equal(out, df)


# ── table_exists ──

def test_table_exists(con):
    con.execute("CREATE TABLE t (a INTEGER)")
    assert db.table_exists(con, "t") is True
    assert db.table_exists(con, "nope") is False


# ── 三种写入 ──

def test_write_partition_returns_rows_and_replaces_same_day(con):
    df = pd.DataFrame({"dt": ["2026-10-15"] * 2, "v": [1, 2]})
    assert db.write_partition(con, df, "t", "2026-10-15") == 2
    assert db.write_partition(con, df, "t", "2026-10-15") == 2   # 先删当天再写：表里仍是 2 行
    assert pd.read_sql("SELECT COUNT(*) n FROM t", con)["n"].item() == 2


def test_replace_table_returns_rows_and_replaces(con):
    assert db.replace_table(con, pd.DataFrame({"v": [1, 2]}), "t") == 2
    assert db.replace_table(con, pd.DataFrame({"v": [3, 4, 5]}), "t") == 3
    assert pd.read_sql("SELECT * FROM t", con)["v"].tolist() == [3, 4, 5]


def test_append_table_returns_rows_and_appends(con):
    assert db.append_table(con, pd.DataFrame({"v": [1]}), "t") == 1
    assert db.append_table(con, pd.DataFrame({"v": [2]}), "t") == 1
    assert pd.read_sql("SELECT * FROM t", con)["v"].tolist() == [1, 2]
