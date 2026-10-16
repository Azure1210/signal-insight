#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_dims_contract.py
# @Path       : signal-insight/test/contract/test_dims_contract.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: dims 维表对下游的契约测试。
"""dims 维表对下游的契约测试。

下游（write_dim_cell、build_dim_hotspot、地图/分析）依赖这些承诺：
列与顺序、lac_cell 主键唯一、district 永不缺失（"市外"兜底）、site_id 编号格式。
"""
import pandas as pd
import pytest

from signal_insight import dims, geo

from ods_schema import DIM_CELL_COLS, DIM_HOTSPOT_COLS


def read_polys(con, table, key):
    return geo.rings_from_points(pd.read_sql(f"SELECT * FROM {table}", con), key)


def test_dim_cell_contract(ods_con):
    districts = read_polys(ods_con, "ods_district_boundary", "district")
    aois = read_polys(ods_con, "ods_aoi_v2", "name")
    dim = dims.build_dim_cell(pd.read_sql("SELECT * FROM ods_cell", ods_con), districts, aois)
    assert list(dim.columns) == DIM_CELL_COLS
    assert dim["lac_cell"].is_unique                    # 主键承诺：join 信令不放大行数
    assert dim["site_id"].str.fullmatch(r"S\d{5}").all()
    assert dim["district"].notna().all()                # 落不进区县也标"市外"，不丢
    assert dim.loc[dim["lac_cell"] == "16789-4708", "district"].item() == "和平区"
    assert dim.loc[dim["lac_cell"] == "16888-4701", "district"].item() == "市外"
    assert dim.loc[dim["lac_cell"] == "16789-4708", "aoi"].item() == "西塔"
    assert dim["aoi"].isna().sum() == 1                 # 只有区县外的那个扇区没有商圈


def test_dim_hotspot_contract(ods_con):
    dim = dims.build_dim_cell(pd.read_sql("SELECT * FROM ods_cell", ods_con), {}, {})
    dwd_df = pd.DataFrame({
        "imsi": [f"u{i}" for i in range(4)],
        "lac_cell": ["16789-4708"] + ["16888-4701"] * 3,   # 站点 1 有 1 个用户、站点 2 有 3 个
    })
    hp = dims.build_dim_hotspot(dwd_df, dim)
    assert list(hp.columns) == DIM_HOTSPOT_COLS
    assert len(hp) == 1
    assert isinstance(hp["lng"].iloc[0], float) and isinstance(hp["lat"].iloc[0], float)
    assert hp["lng"].iloc[0] == pytest.approx((123.5 * 1 + 125.0 * 3) / 4)
    assert hp["radius_m"].iloc[0] == 500
    assert "前 5" in hp["依据"].iloc[0] and "加权" in hp["依据"].iloc[0]
