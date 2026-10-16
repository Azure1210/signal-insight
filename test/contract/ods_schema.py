#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : ods_schema.py
# @Path       : signal-insight/test/contract/ods_schema.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15
# @Description: ODS 表与产物表的期望结构（契约常量）。
"""ODS 表与产物表的期望结构（契约常量）。

契约测试和真实库对账测试（test_real_db_smoke.py）共用这一份常量：
它只抄表结构、不抄数据行（AGENTS.md 1.4、15.3）。
来源：data/signal.db 的 PRAGMA table_info，2026-10-15。
"""
from signal_insight import dims, dwd, quality

# pipeline.extract_ods 读 ods_signal；dwd.clean_signal 依赖这些列齐全（含全空的 tmp0/tmp1）
ODS_SIGNAL_COLS = ["timestamp", "imsi", "lac_id", "cell_id", "phone",
                   "timestamp1", "tmp0", "tmp1", "nid", "npid"]

# pipeline.build_dim_cell 读 ods_cell：坐标 + 扇区键
ODS_CELL_COLS = ["lng", "lat", "lac_cell"]

# pipeline.build_dim_cell 读 ods_district_boundary：区县多边形顶点（有飞地/洞，靠 ring 区分）
ODS_DISTRICT_COLS = ["adcode", "district", "ring", "seq", "lng", "lat"]

# pipeline.build_dim_cell 读 ods_aoi_v2：商圈多边形顶点（无 ring，默认单环）
ODS_AOI_V2_COLS = ["name", "seq", "lng", "lat"]

# 产物表：src 里的列常量（DWD_COLS / DIM_CELL_COLS / quality.COLUMNS）就是它们的契约来源
DWD_SIGNAL_COLS = dwd.DWD_COLS
DIM_CELL_COLS = dims.DIM_CELL_COLS
DIM_HOTSPOT_COLS = ["name", "lng", "lat", "radius_m", "依据"]
ETL_LOG_COLS = ["步骤", "输入行数", "输出行数", "耗时(秒)", "运行时间", "日期分区", "批次"]
DQ_CHECK_RESULT_COLS = quality.COLUMNS
