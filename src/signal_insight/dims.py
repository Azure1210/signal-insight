#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : dims.py
# @Path       : signal-insight/src/signal_insight/dims.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15 14:37:08
# @Version    : v1.0.0
# @Description: 维度表：dim_cell（扇区 → 站点 → 区县 → 商圈）、dim_hotspot（热点）。
# @ChangeLog:
#   2026-10-15 14:37:08 | Matri | v1.0.0 | 初始化创建
"""
纯计算（AGENTS.md 第 4 条）：多边形由调用方用 geo.rings_from_points 还原好传进来，这里不读库。
"""
import numpy as np
import pandas as pd

from . import geo

DIM_CELL_COLS = ["lac_cell", "site_id", "lng", "lat", "district", "aoi"]


def build_dim_cell(ods_cell: pd.DataFrame, districts: dict, aois: dict) -> pd.DataFrame:
    """按 D03 的做法生成 dim_cell：一个扇区一行，主键 lac_cell 唯一。

    站点 = 坐标相同的扇区，编号按坐标第一次出现的顺序给 S00001、S00002……
    落不进任何区县的标"市外"（不丢）；商圈用 D03 甄别后选定的 v2 边界，落不进商圈的为空。
    """
    cell = ods_cell.dropna(subset=["lng", "lat"])
    sites = cell[["lng", "lat"]].drop_duplicates().reset_index(drop=True)
    sites["site_id"] = "S" + (sites.index + 1).astype(str).str.zfill(5)
    sites["district"] = pd.Series(geo.point_in_polygons(sites["lng"], sites["lat"], districts)).fillna("市外")
    sites["aoi"] = geo.point_in_polygons(sites["lng"], sites["lat"], aois)
    dim = cell.merge(sites, on=["lng", "lat"], how="left")[DIM_CELL_COLS].reset_index(drop=True)
    if not dim["lac_cell"].is_unique:
        raise ValueError("dim_cell 的主键 lac_cell 不唯一：每 join 一次信令行数就会被放大")
    return dim


def build_dim_hotspot(dwd: pd.DataFrame, dim_cell: pd.DataFrame, top_n: int = 5,
                    name: str = "西塔", radius_m: int = 500) -> pd.DataFrame:
    """按 D04 的做法定热点中心：连接用户数前 top_n 的站点，按用户数加权平均。

    为什么不用第一名站点的坐标：一座基站覆盖几百米，第一名只是那座铁塔的位置，不是人群的重心。
    name、radius_m 现在是参数默认值，D06 起由 settings.yaml 给（AGENTS.md 第 8 条）。
    """
    sig = dwd[["imsi", "lac_cell"]].merge(dim_cell[["lac_cell", "site_id", "lng", "lat"]], on="lac_cell")
    users = (sig.groupby(["site_id", "lng", "lat"])["imsi"].nunique()
                .sort_values(ascending=False).reset_index(name="用户数"))
    top = users.head(top_n)
    return pd.DataFrame([{
        "name": name,
        "lng": float(np.average(top["lng"], weights=top["用户数"])),
        "lat": float(np.average(top["lat"], weights=top["用户数"])),
        "radius_m": radius_m,
        "依据": f"连接用户数前 {top_n} 的站点按用户数加权的中心",
    }])


if __name__ == '__main__':
    pass
