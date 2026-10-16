#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_dwd_contract.py
# @Path       : signal-insight/test/contract/test_dwd_contract.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: dwd.clean_signal 对下游的契约测试。
"""dwd.clean_signal 对下游的契约测试。

下游（db.write_partition、dims.build_dim_hotspot、notebook）依赖这些承诺：
列与顺序、dtype、ts 与 dt 一致、按 (imsi, ts) 排序、剔除记录的键结构。
改 clean_signal 的实现可以，但这些承诺变了就是破坏下游的契约。
"""
import pandas as pd
import pytest

from signal_insight import dwd

from ods_schema import DWD_SIGNAL_COLS

IMSI_A = "123456789012345678"
IMSI_B = "234567890123456789"
TS_1003 = 1538524800000                      # 2018-10-03 08:00 北京时间


def make_raw(n=6):
    """干净/脏混合的信令，构造时故意乱序：输出必须自己排回来。"""
    rows = []
    for i in range(n):
        rows.append([TS_1003 + i * 60_000, IMSI_A if i % 2 == 0 else IMSI_B,
                     16789.0, 4708.0, "13800006666", TS_1003 + i * 60_000 + 23,
                     None, "", 8, "#*#0000"])
    raw = pd.DataFrame(rows, columns=["timestamp", "imsi", "lac_id", "cell_id",
                                      "phone", "timestamp1", "tmp0", "tmp1", "nid", "npid"])
    return raw.sample(frac=1, random_state=42).reset_index(drop=True)


@pytest.fixture
def clean():
    return dwd.clean_signal(make_raw(), "2018-10-03")


def test_columns_exact(clean):
    out, _ = clean
    assert list(out.columns) == DWD_SIGNAL_COLS


def test_dtypes(clean):
    out, _ = clean
    # pandas 3 里字符串列推断为 str dtype（StringDtype），断言"是字符串"而不是具体 dtype
    assert pd.api.types.is_string_dtype(out["imsi"])
    assert pd.api.types.is_datetime64_any_dtype(out["ts"])
    assert pd.api.types.is_string_dtype(out["dt"])
    assert out["lac_id"].dtype == "int64" and out["cell_id"].dtype == "int64"
    assert pd.api.types.is_integer_dtype(out["nid"])
    assert pd.api.types.is_string_dtype(out["lac_cell"])


def test_ts_date_matches_dt(clean):
    out, _ = clean
    assert (out["ts"].dt.strftime("%Y-%m-%d") == out["dt"]).all()


def test_sorted_by_imsi_then_ts(clean):
    """同一个人的记录按时间相邻：D06 停留识别依赖这个顺序。"""
    out, _ = clean
    expected = out.sort_values(["imsi", "ts"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(out, expected)


def test_no_missing_key_values(clean):
    out, _ = clean
    assert out[["imsi", "ts", "dt", "lac_id", "cell_id", "lac_cell"]].notna().all().all()


def test_steps_record_contract(clean):
    """剔除记录与 ads_clean_steps 同一个结构：{"步骤", "剔除行数", "剩余行数"}。"""
    out, steps = clean
    assert isinstance(steps, list) and steps
    for s in steps:
        assert set(s) == {"步骤", "剔除行数", "剩余行数"}
        assert isinstance(s["步骤"], str)
        assert isinstance(s["剔除行数"], int) and s["剔除行数"] >= 0
        assert isinstance(s["剩余行数"], int)
    remain = [s["剩余行数"] for s in steps]
    assert remain == sorted(remain, reverse=True)      # 每步剩余行数只减不增
    assert remain[-1] == len(out)                      # 最后一步的剩余 = 输出行数
