#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : dws.py
# @Path       : signal-insight/src/signal_insight/dws.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-16 11:01:15
# @Version    : v1.0.0
# @Description: 
# @ChangeLog:
#   2026-10-16 11:01:15 | Matri | v1.0.0 | 初始化创建
"""停留识别：把每个人按时间排好的信令切成段，时长够的段叫停留。"""

import numpy as np
import pandas as pd
from .geo import _dist_m
__all__ = ["find_segments"]
EARTH_R = 6_371_000


def _label_segments(new_user, lat, lng, w, radius_m):
    """顺序扫描，给每个点打段号。算法里唯一必须逐点做的部分。
    new_user[i]: 第 i 个点是不是某人的第一个点（第 0 个必须是 True）
    w[i]:        第 i 个点代表几条原始记录（用于加权算质心）
    """
    labels = np.empty(len(lat), dtype=np.int64)
    seg, s_lat, s_lng, s_w = -1, 0.0, 0.0, 0.0
    for i in range(len(lat)):
        if new_user[i] or _dist_m(s_lat / s_w, s_lng / s_w, lat[i], lng[i]) > radius_m:
            seg, s_lat, s_lng, s_w = seg + 1, 0.0, 0.0, 0.0      # 换人或走远了：开新段
        s_lat += lat[i] * w[i]
        s_lng += lng[i] * w[i]
        s_w += w[i]
        labels[i] = seg
    return labels


def find_segments(df: pd.DataFrame, radius_m: float = 500, min_stay_min: float = 30) -> pd.DataFrame:
    """信令 → 段表。离当前段质心不超过 radius_m 就并入，否则开新段；
    时长不少于 min_stay_min 分钟的段 is_stay=True，其余是经过。
    df 至少要有 imsi、ts、lat、lng。
    """
    df = df.sort_values(["imsi", "ts"], ignore_index=True)
    imsi, lat, lng = (df[c].to_numpy() for c in ("imsi", "lat", "lng"))

    # 1. 连续落在同一坐标的记录必然同段，先压成一行，循环次数大幅减少
    new_user = np.r_[True, imsi[1:] != imsi[:-1]]
    moved = new_user | np.r_[True, (lat[1:] != lat[:-1]) | (lng[1:] != lng[:-1])]
    starts = np.flatnonzero(moved)
    counts = np.diff(np.r_[starts, len(df)])

    # 2. 在压缩后的点上顺序扫描打段号，再展开回原始记录
    run_seg = _label_segments(new_user[starts],
            lat[starts], lng[starts], counts.astype(float), radius_m)
    df["seg"] = np.repeat(run_seg, counts)

    # 3. 按段汇总：质心就是段内原始记录的平均位置
    seg = df.groupby("seg").agg(
        imsi=("imsi", "first"),
        t_start=("ts", "first"),
        t_end=("ts", "last"),
        lat=("lat", "mean"),
        lng=("lng", "mean"),
        n_records=("ts", "size"),
    ).reset_index(drop=True)
    seg["duration_min"] = (seg["t_end"] - seg["t_start"]).dt.total_seconds() / 60
    seg["is_stay"] = seg["duration_min"] >= min_stay_min
    return seg




if __name__ == '__main__':
    pass
