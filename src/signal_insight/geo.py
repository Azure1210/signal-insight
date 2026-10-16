#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : geo.py
# @Path       : signal-insight/src/signal_insight/geo.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-14 10:03:29
# @Version    : v1.0.0
# @Description: 
# @ChangeLog:
#   2026-10-14 10:03:29 | Matri | v1.0.0 | 初始化创建
"""空间计算：球面距离、从顶点表还原多边形、点落面。

纯计算（AGENTS.md 第 4 条）：只接收数字、数组、DataFrame，不连数据库、不读文件、不 import viz。
所以测试时手写几个点就能测；notebook、流水线（D05）、地图（viz.maps）都能直接用。
"""
from typing import Any, Hashable
import math

import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath

__all__ = ["haversine", "rings_from_points", "point_in_polygons"]

EARTH_R = 6_371_000          # 地球平均半径（米）


def haversine(lat1, lng1, lat2, lng2):
    """两点间的球面距离（米）。参数可以是数字，也可以是等长的数组 / Series。
    注意参数顺序：先纬度、后经度——传反了不会报错，距离会差出几十公里。
    """
    lat1, lng1, lat2, lng2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(a))


def rings_from_points(points: pd.DataFrame, key: str) -> dict[Hashable, list[Any]]:
    """从"一行一个顶点"的表还原多边形：{名称: [环1, 环2, ...]}，每个环是 N×2 的 (lng, lat) 数组。
    points 至少要有 key、seq、lng、lat；有 ring 列时按环分开（区县有飞地和洞），没有就当只有一个环（商圈）。
    读表是调用方的事：这里只接收读好的 DataFrame。
    """
    pts = points if "ring" in points.columns else points.assign(ring=0)
    return {name: [r.sort_values("seq")[["lng",
                "lat"]].to_numpy(dtype=float) for _, r in g.groupby("ring")]
            for name, g in pts.groupby(key, sort=False)}


def point_in_polygons(lng, lat, polys: dict[str, list[np.ndarray]]) -> np.ndarray:
    """点落面：返回每个点所在多边形的名称，不在任何多边形里的返回 None。
    奇偶规则：落在奇数个环里算"在里面"，飞地（多个外环）和洞（内环）不用分情况写。
    多边形有重叠时，先出现的名称优先。
    """
    xy = np.column_stack([np.asarray(lng, dtype=float), np.asarray(lat, dtype=float)])
    out = np.full(len(xy), None, dtype=object)
    for name, rings in polys.items():
        inside = np.zeros(len(xy), dtype=bool)
        for ring in rings:
            inside ^= MplPath(ring).contains_points(xy)        # ^= 异或：奇数个环 = 在里面
        out[inside & pd.isna(out)] = name
    return out

def dist_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """两点间的球面距离（米），标量版（D06）：在 Python 循环里一次只算一对点时用它。

    为什么要两个版本：numpy 的优势是“一次算一百万对”；单独算一对点时，构造数组的开销比计算本身还大，
    比这个 math 版慢几十倍。停留识别的内层循环一次只比一对点，所以用这个。
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))

if __name__ == '__main__':
    pass
