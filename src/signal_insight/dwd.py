#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : dwd.py
# @Path       : signal-insight/src/signal_insight/dwd.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15 10:39:24
# @Version    : v1.0.0
# @Description: 明细层 dwd_signal: 原始信令的清洗
# @ChangeLog:
#   2026-10-15 10:39:24 | Matri | v1.0.0 | 初始化创建
import pandas as pd

from . import config

ORIG_COLS = ["timestamp", "imsi", "lac_id", "cell_id", "phone", "timestamp1", "nid", "npid"]   # 判重复用的原始字段
DWD_COLS = ["imsi", "ts", "dt", "lac_id", "cell_id", "nid", "lac_cell"]


def to_local(ts_ms: pd.Series) -> pd.Series:
    """UTC 毫秒时间戳 → 北京时间。偏移量取 config.UTC_OFFSET_HOURS（口径只有一个来源）。"""
    return pd.to_datetime(ts_ms, unit="ms") + pd.Timedelta(hours=config.UTC_OFFSET_HOURS)


def clean_signal(raw: pd.DataFrame, day: str) -> tuple[pd.DataFrame, list[dict]]:
    """按 D02 的顺序清洗，只留 day 这一天。返回 (dwd_signal, 每一步的剔除记录)。

    顺序：删整列为空的 tmp0/tmp1 → 删缺 imsi/lac/cell → 删 IMSI 格式异常 → 去完全重复 → 只留 day。
    剔除记录的每一项是 {"步骤", "剔除行数", "剩余行数"}，和 D02 写的 ads_clean_steps 同一个结构。
    ts 返回的是时间类型；写库时由 db.py 统一成文本。
    """
    steps = []

    def log(name, before, after):
        steps.append({"步骤": name, "剔除行数": before - after, "剩余行数": after})

    df = raw.drop(columns=["tmp0", "tmp1"])
    n = len(df); df = df.dropna(subset=["imsi", "lac_id", "cell_id"]);   log("缺 imsi / lac / cell", n, len(df))
    n = len(df); df = df[df["imsi"].str.fullmatch(r"\d{18}")];           log("IMSI 格式异常", n, len(df))
    n = len(df); df = df.drop_duplicates(subset=ORIG_COLS);               log("完全重复", n, len(df))
    ts = to_local(df["timestamp"])
    n = len(df); keep = ts.dt.strftime("%Y-%m-%d") == day
    df, ts = df[keep], ts[keep];                                          log(f"不是 {day}", n, len(df))

    out = pd.DataFrame({
        "imsi": df["imsi"],
        "ts": ts,
        "dt": day,
        "lac_id": df["lac_id"].astype("int64"),     # 原始是浮点（列里有空值）；先转整数再拼，否则会拼出 "16789.0-…"
        "cell_id": df["cell_id"].astype("int64"),
        "nid": df["nid"],
    })
    out["lac_cell"] = out["lac_id"].astype(str) + "-" + out["cell_id"].astype(str)
    out = out.sort_values(["imsi", "ts"]).reset_index(drop=True)   # 同一个人的记录按时间相邻：D06 停留识别要用
    return out[DWD_COLS], steps


if __name__ == '__main__':
    pass
