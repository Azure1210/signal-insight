#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_geo.py
# @Path       : signal-insight/test/unit/test_geo.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: geo 的单元测试：球面距离、多边形还原、点落面。
"""geo 的单元测试：球面距离、多边形还原、点落面（纯计算，手写几个点就能测）。"""
import numpy as np
import pandas as pd
import pytest

from signal_insight import geo

# ── haversine ──

def test_haversine_same_point_is_zero():
    assert geo.haversine(41.5, 123.5, 41.5, 123.5) == pytest.approx(0.0)


def test_haversine_one_degree_longitude_at_equator():
    # 赤道上 1 度经度 ≈ 2πR/360 ≈ 111.19 km
    assert geo.haversine(0, 0, 0, 1) == pytest.approx(2 * np.pi * geo.EARTH_R / 360, rel=1e-9)


def test_haversine_is_symmetric():
    assert geo.haversine(0, 0, 1, 1) == pytest.approx(geo.haversine(1, 1, 0, 0))


def test_haversine_accepts_arrays():
    out = geo.haversine([0, 0], [0, 1], [1, 0], [1, 1])
    assert isinstance(out, np.ndarray) and len(out) == 2
    assert out[0] == pytest.approx(geo.haversine(0, 0, 1, 1))   # 逐元素对应：lat1/lng1/lat2/lng2 的第 0 个


def test_haversine_lat_lng_order_matters():
    # 参数顺序是先纬度后经度；每个点的经纬度对调后距离会差出几百公里（docstring 的警告）
    correct = geo.haversine(60, 0, 60, 10)      # (60°N, 0°) → (60°N, 10°E)：同纬度 10 个经度
    swapped = geo.haversine(0, 60, 10, 60)      # 经纬度传反后变成 10 个纬度
    assert abs(correct - swapped) > 10_000


def test_haversine_scalar_returns_number():
    assert isinstance(geo.haversine(0, 0, 0, 1), (float, np.floating))


# ── rings_from_points ──

def test_rings_without_ring_column_is_single_ring():
    points = pd.DataFrame({
        "name": ["a"] * 4,
        "seq": [2, 0, 3, 1],            # 故意乱序：还原时按 seq 排序
        "lng": [1.0, 0.0, 1.0, 0.0],
        "lat": [1.0, 0.0, 0.0, 1.0],
    })
    rings = geo.rings_from_points(points, "name")
    assert list(rings) == ["a"]
    ring = rings["a"][0]
    assert ring.shape == (4, 2)
    assert ring.tolist() == [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0]]


def test_rings_with_ring_column_splits_rings():
    points = pd.DataFrame({
        "name": ["a"] * 8,
        "ring": [0, 0, 0, 0, 1, 1, 1, 1],
        "seq": [0, 1, 2, 3] * 2,
        "lng": [0.0, 2.0, 2.0, 0.0, 5.0, 7.0, 7.0, 5.0],
        "lat": [0.0, 0.0, 2.0, 2.0, 5.0, 5.0, 7.0, 7.0],
    })
    rings = geo.rings_from_points(points, "name")
    assert len(rings["a"]) == 2                 # 两个环：飞地或洞
    assert rings["a"][0][0].tolist() == [0.0, 0.0]
    assert rings["a"][1][0].tolist() == [5.0, 5.0]


def test_rings_keep_first_appearance_order():
    points = pd.DataFrame({
        "name": ["b", "b", "a", "a"],
        "seq": [0, 1, 0, 1],
        "lng": [0.0, 1.0, 0.0, 1.0],
        "lat": [0.0, 0.0, 0.0, 0.0],
    })
    assert list(geo.rings_from_points(points, "name")) == ["b", "a"]


# ── point_in_polygons ──

SQUARE = {"sq": [np.array([[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0]])]}


def test_point_inside_and_outside():
    out = geo.point_in_polygons([1.0, 9.0], [1.0, 9.0], SQUARE)
    assert out.tolist() == ["sq", None]


def test_hole_parity_even_rings_is_outside():
    # 外环 + 内环（洞）：洞里的点落在 2 个环里（偶数）→ 不算在内
    outer = np.array([[0.0, 0.0], [0.0, 4.0], [4.0, 4.0], [4.0, 0.0]])
    inner = np.array([[1.0, 1.0], [1.0, 3.0], [3.0, 3.0], [3.0, 1.0]])
    polys = {"x": [outer, inner]}
    assert geo.point_in_polygons(2.0, 2.0, polys).tolist() == [None]    # 在洞里
    assert geo.point_in_polygons(0.5, 0.5, polys).tolist() == ["x"]     # 在环里、洞外


def test_enclave_odd_rings_is_inside():
    # 飞地：两个不相交的外环，点在第二个环里（1 个环，奇数）→ 算在内
    ring0 = np.array([[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0]])
    ring1 = np.array([[10.0, 10.0], [10.0, 12.0], [12.0, 12.0], [12.0, 10.0]])
    polys = {"x": [ring0, ring1]}
    assert geo.point_in_polygons([1.0, 11.0], [1.0, 11.0], polys).tolist() == ["x", "x"]


def test_overlapping_polys_first_name_wins():
    a = np.array([[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0]])
    b = np.array([[1.0, 0.0], [1.0, 3.0], [3.0, 3.0], [3.0, 0.0]])
    assert geo.point_in_polygons(1.5, 1.5, {"a": [a], "b": [b]}).tolist() == ["a"]


def test_no_match_returns_none_array():
    out = geo.point_in_polygons([5.0, 6.0], [5.0, 6.0], SQUARE)
    assert out.tolist() == [None, None]
    assert out.dtype == object
