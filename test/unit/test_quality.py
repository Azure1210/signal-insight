#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_quality.py
# @Path       : signal-insight/test/unit/test_quality.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: quality 的单元测试：数据画像的统计口径与 dq_record 的参数校验。
"""quality 的单元测试：数据画像的统计口径与 dq_record 的参数校验。

dq_record 与 dq_check_result 表的契约（结构、覆盖语义）见 contract/test_quality_contract.py。
"""
import pandas as pd
import pytest

from signal_insight import quality


# ── profile ──

def test_profile_basic_stats():
    df = pd.DataFrame({
        "数值": [1.0, 2.0, None, 4.0],
        "文本": ["a", "  ", "b", None],
    })
    out = quality.profile(df)
    assert list(out.columns) == ["字段", "类型", "缺失数", "缺失率", "唯一值个数", "示例值"]
    num = out.loc[out["字段"] == "数值"].iloc[0]
    assert num["缺失数"] == 1 and num["缺失率"] == 0.25
    assert num["唯一值个数"] == 3 and num["示例值"] == 1.0
    txt = out.loc[out["字段"] == "文本"].iloc[0]
    assert txt["缺失数"] == 2                    # "  " 去掉首尾空白后为空 → 也算缺失
    assert txt["唯一值个数"] == 2


def test_profile_empty_df():
    out = quality.profile(pd.DataFrame({"a": pd.Series(dtype="float64")}))
    assert out["缺失率"].iloc[0] == 0.0          # 0 行时缺失率为 0，不除零
    assert out["示例值"].iloc[0] is None


def test_profile_duplicate_column_names():
    out = quality.profile(pd.DataFrame([[1, 2], [3, 4]], columns=["x", "x"]))
    assert len(out) == 2                         # 按位置取列，重复列名不会少统计


def test_profile_unhashable_values():
    df = pd.DataFrame({"v": [[1, 2], [3], [1, 2]]})
    out = quality.profile(df)
    assert out["唯一值个数"].iloc[0] == 2        # list 不可哈希，按其字符串形式去重


def test_profile_all_missing_example_is_none():
    out = quality.profile(pd.DataFrame({"v": [None, None]}))
    assert out["示例值"].iloc[0] is None
    assert out["缺失数"].iloc[0] == 2


def test_profile_categorical_counts_blank():
    df = pd.DataFrame({"v": pd.Categorical(["a", "  ", "a", None])})
    out = quality.profile(df)
    assert out["缺失数"].iloc[0] == 2            # "  " 和 None 都算缺失


# ── dq_record 参数校验 ──

def test_dq_record_rejects_bad_status(con):
    with pytest.raises(ValueError, match="状态只能"):
        quality.dq_record(con, "c1", "完整性", "项", "imsi", "r", "随便")
