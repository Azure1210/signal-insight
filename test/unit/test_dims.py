#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_dims.py
# @Path       : signal-insight/test/unit/test_dims.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: dims 的单元测试：站点归并、市外兜底、热点加权中心。
"""dims 的单元测试：站点归并、市外兜底、热点加权中心。"""
import numpy as np
import pandas as pd
import pytest

from signal_insight import dims

# 覆盖 (100, 30) 的正方形区县
SQUARE = [np.array([[99.0, 29.0], [101.0, 29.0], [101.0, 31.0], [99.0, 31.0]])]


def make_cells():
    """c1/c2 同坐标（→ 同一站点），c3 独立坐标（→ 区县外），c4 坐标为空（→ 剔除）。"""
    return pd.DataFrame({
        "lac_cell": ["c1", "c2", "c3", "c4"],
        "lng": [100.0, 100.0, 200.0, np.nan],
        "lat": [30.0, 30.0, 40.0, np.nan],
    })


# ── build_dim_cell ──

def test_same_coordinates_share_site_id():
    dim = dims.build_dim_cell(make_cells(), {"D区": SQUARE}, {})
    assert len(dim) == 3                                   # c4 坐标为空被剔除
    id1 = dim.loc[dim["lac_cell"] == "c1", "site_id"].item()
    id2 = dim.loc[dim["lac_cell"] == "c2", "site_id"].item()
    assert id1 == id2


def test_site_id_numbered_by_first_appearance():
    dim = dims.build_dim_cell(make_cells(), {"D区": SQUARE}, {})
    assert dim.loc[dim["lac_cell"] == "c1", "site_id"].item() == "S00001"
    assert dim.loc[dim["lac_cell"] == "c3", "site_id"].item() == "S00002"
    assert dim["site_id"].str.fullmatch(r"S\d{5}").all()


def test_district_fallback_to_city_outside():
    dim = dims.build_dim_cell(make_cells(), {"D区": SQUARE}, {})
    assert dim.loc[dim["lac_cell"] == "c1", "district"].item() == "D区"
    assert dim.loc[dim["lac_cell"] == "c3", "district"].item() == "市外"
    assert dim["district"].notna().all()                   # 落不进任何区县也不丢


def test_aoi_none_when_no_polygon():
    dim = dims.build_dim_cell(make_cells(), {"D区": SQUARE}, {})
    assert dim["aoi"].isna().all()


def test_aoi_matches_containing_polygon():
    dim = dims.build_dim_cell(make_cells(), {}, {"西塔": SQUARE})
    assert dim.loc[dim["lac_cell"] == "c1", "aoi"].item() == "西塔"
    assert pd.isna(dim.loc[dim["lac_cell"] == "c3", "aoi"].iloc[0])


def test_duplicate_lac_cell_raises():
    dup = pd.concat([make_cells(), make_cells().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="lac_cell"):
        dims.build_dim_cell(dup, {"D区": SQUARE}, {})


# ── build_dim_hotspot ──

def make_dwd_and_cell():
    """站点 1 有 1 个用户，站点 2 有 3 个用户。"""
    dwd = pd.DataFrame({
        "imsi": ["u1", "u2", "u3", "u4"],
        "lac_cell": ["c1", "c2", "c2", "c2"],
    })
    cell = pd.DataFrame({
        "lac_cell": ["c1", "c2"],
        "site_id": ["S00001", "S00002"],
        "lng": [100.0, 110.0],
        "lat": [30.0, 31.0],
    })
    return dwd, cell


def test_hotspot_is_weighted_average():
    hp = dims.build_dim_hotspot(*make_dwd_and_cell(), top_n=2)
    assert len(hp) == 1
    assert hp["lng"].iloc[0] == pytest.approx((100.0 * 1 + 110.0 * 3) / 4)
    assert hp["lat"].iloc[0] == pytest.approx((30.0 * 1 + 31.0 * 3) / 4)


def test_hotspot_top_n_truncates():
    dwd = pd.DataFrame({
        "imsi": ["a1", "a2", "a3", "b1", "b2", "c1"],
        "lac_cell": ["ca"] * 3 + ["cb"] * 2 + ["cc"],
    })
    cell = pd.DataFrame({
        "lac_cell": ["ca", "cb", "cc"],
        "site_id": ["S00001", "S00002", "S00003"],
        "lng": [100.0, 200.0, 300.0],
        "lat": [0.0, 0.0, 0.0],
    })
    hp = dims.build_dim_hotspot(dwd, cell, top_n=2)
    # 用户数 3、2 的两个站点进 top，用户数 1 的被截掉
    assert hp["lng"].iloc[0] == pytest.approx((100.0 * 3 + 200.0 * 2) / 5)
    assert "前 2" in hp["依据"].iloc[0]


def test_hotspot_defaults():
    hp = dims.build_dim_hotspot(*make_dwd_and_cell())
    assert hp["name"].iloc[0] == "西塔"
    assert hp["radius_m"].iloc[0] == 500
