#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_pipeline.py
# @Path       : signal-insight/test/unit/test_pipeline.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: pipeline 的单元测试：_rows 的行数口径与 step 装饰器。
"""pipeline 的单元测试：_rows 的行数口径与 step 装饰器的记录行为。

run_day 的端到端行为见 contract/test_pipeline_contract.py。
"""
import pandas as pd
import pytest

from signal_insight import pipeline


@pytest.fixture(autouse=True)
def clear_log():
    """_LOG 是进程级全局，测试之间要清干净。"""
    pipeline._LOG.clear()


# ── _rows ──

def test_rows_for_dataframe_tuple_int_and_other():
    df = pd.DataFrame({"a": [1, 2]})
    assert pipeline._rows(df) == 2
    assert pipeline._rows((df, ["x"])) == 2      # (DataFrame, 其他) 取第一个的行数
    assert pipeline._rows(5) == 5
    assert pipeline._rows(None) is None
    assert pipeline._rows("text") is None


# ── step 装饰器 ──

def test_step_records_and_preserves_behavior():
    calls = []

    @pipeline.step
    def double(df, k):
        calls.append(k)
        return pd.DataFrame({"v": df["v"] * 2})

    out = double(pd.DataFrame({"v": [1, 2, 3]}), k=7)
    assert calls == [7]                          # 函数行为不变：参数原样传入
    assert out["v"].tolist() == [2, 4, 6]
    rec = pipeline._LOG[-1]
    assert rec["步骤"] == "double"
    assert rec["输入行数"] == 3 and rec["输出行数"] == 3
    assert isinstance(rec["耗时(秒)"], float) and rec["耗时(秒)"] >= 0
    assert "运行时间" in rec


def test_step_keeps_function_metadata():
    @pipeline.step
    def my_func():
        """docstring 保留。"""
    assert my_func.__name__ == "my_func"
    assert my_func.__doc__ == "docstring 保留。"


def test_step_input_rows_only_from_dataframe_args():
    @pipeline.step
    def f(con, df):
        return df

    f(object(), pd.DataFrame({"a": [1, 2, 3]}))
    assert pipeline._LOG[-1]["输入行数"] == 3


def test_step_rows_out_none_when_not_countable():
    @pipeline.step
    def f():
        return "text"

    f()
    assert pipeline._LOG[-1]["输出行数"] is None
