#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_dwd.py
# @Path       : signal-insight/test/unit/test_dwd.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: dwd 的单元测试：时区转换与五步清洗。
"""dwd 的单元测试：时区转换（to_local）与五步清洗（clean_signal）。"""
import pandas as pd
import pytest

from signal_insight import dwd

TS_1003 = 1538524800000                     # 2018-10-03 08:00 北京时间
TS_1002 = TS_1003 - 86_400_000              # 2018-10-02 08:00 北京时间
IMSI_A = "123456789012345678"
IMSI_B = "234567890123456789"


# ── to_local ──

def test_to_local_adds_utc_offset():
    out = dwd.to_local(pd.Series([0, TS_1003]))
    assert isinstance(out, pd.Series)
    assert out.iloc[0] == pd.Timestamp("1970-01-01 08:00:00")
    assert out.iloc[1] == pd.Timestamp("2018-10-03 08:00:00")


# ── clean_signal ──

def make_raw():
    """10 行脏数据。

    行 0：正常 10-03（A）            行 5：与行 0 完全重复 → 去重剔除
    行 1：正常 10-03（B）            行 6：10-02 → 日期过滤剔除
    行 2：缺 imsi → 剔除             行 7：正常 10-03（A，另一个扇区）
    行 3：缺 lac_id → 剔除           行 8：缺 cell_id → 剔除
    行 4：15 位 IMSI → 剔除          行 9：与行 7 完全重复 → 去重剔除
    """
    df = pd.DataFrame({
        "timestamp": [TS_1003, TS_1003 + 60_000, TS_1003, TS_1003, TS_1003,
                      TS_1003, TS_1002, TS_1003 + 120_000, TS_1003, TS_1003 + 120_000],
        "imsi": [IMSI_A, IMSI_B, None, IMSI_A, "123456789012345",
                 IMSI_A, IMSI_A, IMSI_A, IMSI_A, IMSI_A],
        "lac_id": [16789.0, 16789.0, 16789.0, None, 16789.0,
                   16789.0, 16789.0, 16888.0, 16789.0, 16888.0],
        "cell_id": [4708.0, 4709.0, 4708.0, 4708.0, 4708.0,
                    4708.0, 4708.0, 4701.0, None, 4701.0],
    })
    df["timestamp1"] = df["timestamp"] + 23   # 与 timestamp 错开 23 毫秒（数据字典的中位差）
    df["phone"] = "13800006666"
    df["nid"] = 8
    df["npid"] = "#*#0000"
    df["tmp0"] = None
    df["tmp1"] = ""
    return df


def test_clean_signal_steps_and_counts():
    out, steps = dwd.clean_signal(make_raw(), "2018-10-03")
    assert len(out) == 3
    assert [s["步骤"] for s in steps] == ["缺 imsi / lac / cell", "IMSI 格式异常", "完全重复", "不是 2018-10-03"]
    assert [s["剔除行数"] for s in steps] == [3, 1, 2, 1]
    assert [s["剩余行数"] for s in steps] == [7, 6, 4, 3]


def test_clean_signal_output_shape():
    out, _ = dwd.clean_signal(make_raw(), "2018-10-03")
    assert list(out.columns) == dwd.DWD_COLS
    assert out["lac_id"].dtype == "int64" and out["cell_id"].dtype == "int64"
    # 拼接前先转整数：lac_cell 不会出现 "16789.0-4708.0"
    assert out["lac_cell"].tolist() == ["16789-4708", "16888-4701", "16789-4709"]
    assert pd.api.types.is_datetime64_any_dtype(out["ts"])


def test_clean_signal_sorts_by_imsi_then_ts():
    out, _ = dwd.clean_signal(make_raw(), "2018-10-03")
    assert out["imsi"].tolist() == [IMSI_A, IMSI_A, IMSI_B]
    expected = out.sort_values(["imsi", "ts"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(out, expected)


def test_clean_signal_keeps_only_given_day():
    out, _ = dwd.clean_signal(make_raw(), "2018-10-02")
    assert len(out) == 1
    assert out["dt"].iloc[0] == "2018-10-02"
    assert out["ts"].dt.strftime("%Y-%m-%d").iloc[0] == "2018-10-02"


def test_duplicate_needs_all_orig_cols():
    # 只有 ORIG_COLS 全部相同才算完全重复；差一个 phone 就保留
    raw = make_raw()
    raw.loc[5, "phone"] = "13800007777"
    out, steps = dwd.clean_signal(raw, "2018-10-03")
    by_name = {s["步骤"]: s for s in steps}
    assert by_name["完全重复"]["剔除行数"] == 1      # 只剩行 9 与行 7 那一对
    assert len(out) == 4


def test_clean_signal_drops_tmp_columns():
    out, _ = dwd.clean_signal(make_raw(), "2018-10-03")
    assert "tmp0" not in out.columns and "tmp1" not in out.columns


def test_clean_signal_requires_tmp_columns():
    raw = make_raw().drop(columns=["tmp0", "tmp1"])
    with pytest.raises(KeyError):
        dwd.clean_signal(raw, "2018-10-03")
