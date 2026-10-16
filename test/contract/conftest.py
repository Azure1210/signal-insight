#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : conftest.py
# @Path       : signal-insight/test/contract/conftest.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: 契约测试的公共 fixture：按真实 schema 造一个"迷你 ODS 库"。
"""契约测试的公共 fixture：按真实 schema 造一个"迷你 ODS 库"。

数据全是合成的（一个正方形区县、一个商圈、两个站点坐标、33 行信令），
不读 data/ 下的任何东西；表结构按 ods_schema.py 的契约常量建。
"""
import sqlite3

import pandas as pd
import pytest

# 北京时间的 UTC 毫秒：2018-10-03 08:00 / 2018-10-02 08:00（dwd.to_local 加 8 小时）
TS_1003 = 1538524800000
TS_1002 = TS_1003 - 86_400_000

IMSI_A = "123456789012345678"   # 18 位才是一个完整 IMSI（D02 需求卡 2.5）
IMSI_B = "234567890123456789"

# 三个扇区：前两个同坐标（→ 同一站点，落在区县和商圈内），第三个独立坐标（→ 区县外、商圈外）
LAC_CELLS = ["16789-4708", "16789-4709", "16888-4701"]


def make_ods(con: sqlite3.Connection) -> None:
    """往 con 里建 4 张 ODS 表并写入合成数据。clean 之后 dwd_signal 应为 24 行。"""
    rows = []
    for i in range(24):                      # 24 行 10-03：三组扇区轮流，前 20 行是 A、后 4 行是 B
        lac, cell = map(int, LAC_CELLS[i % 3].split("-"))
        rows.append([TS_1003 + i * 60_000, IMSI_A if i < 20 else IMSI_B,
                     float(lac), float(cell), "13800006666", TS_1003 + i * 60_000 + 23,
                     None, "", 8, "#*#0000"])
    rows.append(rows[0])                     # 两行与第 0 行完全重复 → 去重剔除 2
    rows.append(rows[0])
    for i in range(4):                       # 4 行 10-02 → 被日期过滤
        lac, cell = map(int, LAC_CELLS[i % 3].split("-"))
        rows.append([TS_1002 + i * 60_000, IMSI_A, float(lac), float(cell),
                     "13800006666", TS_1002 + i * 60_000 + 23, None, "", 8, "#*#0000"])
    rows.append([TS_1003, None, 16789.0, 4708.0, "13800006666", TS_1003, None, "", 8, "#*#0000"])   # 缺 imsi
    rows.append([TS_1003, IMSI_A, None, 4708.0, "13800006666", TS_1003, None, "", 8, "#*#0000"])   # 缺 lac_id
    rows.append([TS_1003, "123456789012345", 16789.0, 4708.0, "13800006666", TS_1003, None, "", 8, "#*#0000"])  # 15 位
    pd.DataFrame(rows, columns=["timestamp", "imsi", "lac_id", "cell_id", "phone",
                                "timestamp1", "tmp0", "tmp1", "nid", "npid"]).to_sql(
        "ods_signal", con, index=False)

    pd.DataFrame({                          # 3 个扇区；前两个同坐标 → 同一站点
        "lng": [123.5, 123.5, 125.0],
        "lat": [41.5, 41.5, 41.5],
        "lac_cell": LAC_CELLS,
    }).to_sql("ods_cell", con, index=False)

    pd.DataFrame({                          # 正方形区县，ring=0 单环，覆盖站点 1、不覆盖站点 2
        "adcode": ["210102"] * 4,
        "district": ["和平区"] * 4,
        "ring": [0] * 4,
        "seq": [0, 1, 2, 3],
        "lng": [123.0, 124.0, 124.0, 123.0],
        "lat": [41.0, 41.0, 42.0, 42.0],
    }).to_sql("ods_district_boundary", con, index=False)

    pd.DataFrame({                          # 正方形商圈，无 ring 列（默认单环），只覆盖站点 1
        "name": ["西塔"] * 4,
        "seq": [0, 1, 2, 3],
        "lng": [123.4, 123.6, 123.6, 123.4],
        "lat": [41.4, 41.4, 41.6, 41.6],
    }).to_sql("ods_aoi_v2", con, index=False)


@pytest.fixture
def ods_db_path(tmp_path) -> str:
    """建好 4 张 ODS 表的临时库路径（连接已关，pipeline.run_day 可以自己连）。"""
    path = tmp_path / "ods.db"
    con = sqlite3.connect(path)
    make_ods(con)
    con.close()
    return str(path)


@pytest.fixture
def ods_con(ods_db_path) -> sqlite3.Connection:
    """同一个库的打开连接，给直接读表的测试用。"""
    con = sqlite3.connect(ods_db_path)
    yield con
    con.close()
