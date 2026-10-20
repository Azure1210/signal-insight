"""生成首屏六边形地图的数据（24 小时 × 每格人数），输出 dashboard/static/hero.json。

口径：dws_user_hour 每人每小时一个位置点（102,859 个用户—小时），
按 0.55 公里边长切成尖顶六边形，同一小时少于 5 人的格子不显示（隐私与视觉噪声）。
前端拿到网格后自己按“昼夜系数”上色：白天蓝、夜里琥珀，时间连续推进。

用法：python dashboard/build_hexdata.py
"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "signal.db"
OUT = ROOT / "dashboard" / "static" / "hero.json"

XITA = (123.410582, 41.806944)
R_KM = 0.55                 # 六边形边长
MIN_USERS = 5               # 低于 5 人不画
WIN = (-13.5, 13.5, -12.0, 12.0)   # xmin, xmax, ymin, ymax（公里，以西塔为原点）
KM_PER_LAT = 110.57
KM_PER_LNG = 111.32 * math.cos(math.radians(XITA[1]))

LABELS = [
    ["和平区", -1.7, -6.4], ["沈河区", 8.7, -1.6], ["大东区", 8.3, 4.8],
    ["皇姑区", 1.1, 6.0], ["铁西区", -7.7, -3.6], ["苏家屯区", -8.1, -11.2],
    ["浑南区", 8.3, -7.2], ["沈北新区", 6.3, 11.2], ["于洪区", -7.3, 3.6],
]


def to_km(lng: float, lat: float) -> tuple[float, float]:
    return (lng - XITA[0]) * KM_PER_LNG, (lat - XITA[1]) * KM_PER_LAT


def hex_round(q: float, r: float) -> tuple[int, int]:
    x, z = q, r
    y = -x - z
    rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz:
        rx = -ry - rz
    elif dy > dz:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def hex_cells() -> tuple[list[list[int]], int]:
    con = sqlite3.connect(DB)
    try:
        rows = con.execute("SELECT hour, lng, lat FROM dws_user_hour").fetchall()
    finally:
        con.close()

    grid: dict[tuple[int, int], list[int]] = {}
    for hour, lng, lat in rows:
        x, y = to_km(lng, lat)
        if not (WIN[0] <= x <= WIN[1] and WIN[2] <= y <= WIN[3]):
            continue
        r0 = y / (1.5 * R_KM)
        q1 = x / (R_KM * math.sqrt(3)) - r0 / 2
        q, r = hex_round(q1, r0)
        cell = grid.get((q, r))
        if cell is None:
            cell = grid[(q, r)] = [0] * 24
        cell[int(hour)] += 1

    keep = {k: v for k, v in grid.items() if max(v) >= MIN_USERS}
    vmax = max(max(v) for v in keep.values()) if keep else MIN_USERS
    hexes = [[q, r] + v for (q, r), v in sorted(keep.items(), key=lambda kv: kv[0][1])]
    return hexes, vmax


def rings() -> list[list[float]]:
    con = sqlite3.connect(DB)
    try:
        rows = con.execute(
            "SELECT district, ring, seq, lng, lat FROM ods_district_boundary ORDER BY district, ring, seq"
        ).fetchall()
    finally:
        con.close()
    groups: dict[tuple[str, int], list[float]] = {}
    for _d, ring, _seq, lng, lat in rows:
        x, y = to_km(lng, lat)
        if not (WIN[0] - 6 <= x <= WIN[1] + 6 and WIN[2] - 6 <= y <= WIN[3] + 6):
            continue
        groups.setdefault((_d, ring), []).extend([round(x, 2), round(y, 2)])
    return list(groups.values())


def aoi() -> list[dict]:
    con = sqlite3.connect(DB)
    try:
        rows = con.execute(
            "SELECT name, seq, lng, lat FROM ods_aoi_v2 "
            "WHERE name IN ('太原街商圈', '中街商圈') ORDER BY name, seq"
        ).fetchall()
    finally:
        con.close()
    groups: dict[str, list[float]] = {}
    for name, _seq, lng, lat in rows:
        x, y = to_km(lng, lat)
        groups.setdefault(name, []).extend([round(x, 2), round(y, 2)])
    return [{"name": k.replace("商圈", ""), "ring": v} for k, v in groups.items()]


def hourly() -> dict[str, list[int]]:
    con = sqlite3.connect(DB)
    try:
        zh = con.execute(
            "SELECT 小时, 太原街商圈, 中街商圈, 可定位人数 FROM ads_zone_hourly ORDER BY 小时"
        ).fetchall()
        xh = con.execute("SELECT 小时, 在场人数 FROM ads_xita_hourly ORDER BY 小时").fetchall()
        hp = con.execute(
            "SELECT hour, COUNT(DISTINCT imsi) FROM dws_user_hour "
            "WHERE district = '和平区' GROUP BY hour ORDER BY hour"
        ).fetchall()
    finally:
        con.close()
    heping = {int(h): int(c) for h, c in hp}
    xita = {int(h): int(c) for h, c in xh}
    obs = [int(r[3]) for r in zh]
    return {
        "obs": obs,
        "xita": [xita.get(h, 0) for h in range(24)],
        "ty": [int(r[1]) for r in zh],
        "zj": [int(r[2]) for r in zh],
        "out": [obs[h] - heping.get(h, 0) for h in range(24)],
    }


def main() -> None:
    hexes, vmax = hex_cells()
    payload = {
        "ext": list(WIN),
        "s": R_KM,
        "k_min": MIN_USERS,
        "vmax": vmax,
        "hex": hexes,
        "rings": rings(),
        "labels": LABELS,
        "aoi": aoi(),
        "hourly": hourly(),
        "n_users": 5644,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"cells={len(hexes)} vmax={vmax} rings={len(payload['rings'])} "
          f"aoi={len(payload['aoi'])} bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
