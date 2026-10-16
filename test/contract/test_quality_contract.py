#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_quality_contract.py
# @Path       : signal-insight/test/contract/test_quality_contract.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: dq_record 与 dq_check_result 表的契约测试。
"""dq_record 与 dq_check_result 表的契约测试。

对读表的调用方（notebook 里的稽核结果展示）的承诺：
表结构 = quality.COLUMNS；同一个 check_id 重跑覆盖旧记录；不同 check_id 共存。
"""
import pandas as pd

from signal_insight import quality

from ods_schema import DQ_CHECK_RESULT_COLS


def test_table_schema_contract(con):
    quality.dq_record(con, "c1", "完整性", "缺 imsi", "imsi", "缺失 0 行", "通过")
    actual = [r[1] for r in con.execute('PRAGMA table_info("dq_check_result")')]
    assert actual == DQ_CHECK_RESULT_COLS
    assert actual == quality.COLUMNS            # 契约常量与代码常量一致


def test_first_write_creates_table(con):
    # 表不存在时 dq_record 也能写（内部先读、读不到就建）
    quality.dq_record(con, "c1", "完整性", "项", "imsi", "r", "通过")
    assert len(pd.read_sql("SELECT * FROM dq_check_result", con)) == 1


def test_same_check_id_overwrites(con):
    quality.dq_record(con, "c1", "完整性", "项", "imsi", "结果1", "通过")
    quality.dq_record(con, "c1", "完整性", "项", "imsi", "结果2", "警告")
    out = pd.read_sql("SELECT * FROM dq_check_result", con)
    assert len(out) == 1
    assert out["结果"].iloc[0] == "结果2"
    assert out["状态"].iloc[0] == "警告"


def test_different_check_ids_coexist(con):
    quality.dq_record(con, "c1", "完整性", "项", "imsi", "r", "通过")
    quality.dq_record(con, "c2", "一致性", "项", "cell_id", "r", "通过")
    assert sorted(pd.read_sql("SELECT * FROM dq_check_result", con)["check_id"]) == ["c1", "c2"]
