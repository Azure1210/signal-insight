#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : db.py
# @Path       : signal-insight/src/signal_insight/db.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-15 10:59:08
# @Version    : v1.0.0
# @Description: 数据库读写：连接、按日期分区写入、整表替换、追加。
# @ChangeLog:
#   2026-10-15 10:59:08 | Matri | v1.0.0 | 初始化创建

"""
只会因为"换了数据库"而改（AGENTS.md 第 2 条）。换成 MySQL、Hive 时，计算模块一行不动，只改这里。
D05 起只有 db.py 和 pipeline.py 碰数据库（AGENTS.md 第 4 条；quality.dq_record 是唯一的例外，见规范）。
"""
import sqlite3

import pandas as pd

from . import config

TS_FORMAT = "%Y-%m-%d %H:%M:%S.%f"     # 写库时统一的时间格式（毫秒精度，见 _for_storage）


def connect(path=None) -> sqlite3.Connection:
    """连接数据库；不给路径就连 config.DB_PATH（探索库 signal.db）。"""
    return sqlite3.connect(config.DB_PATH if path is None else path)


def table_exists(con, table: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def _for_storage(df: pd.DataFrame) -> pd.DataFrame:
    """把时间列统一成固定宽度的文本再写库。

    SQLite 没有日期类型，时间会被存成文本。不统一格式的话，毫秒为 0 的行会少写小数部分，
    读回来时 parse_dates 按第一行推断格式，格式不同的行会悄悄变成空值（D02 需求卡 2.6 的坑）。
    这件事放在 db.py 而不放在 dwd.py，是因为它是"存储"的事：换成有 DATETIME 类型的库就不需要了。
    """
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime(TS_FORMAT).str[:-3]
    return out


def write_partition(con, df: pd.DataFrame, table: str, dt: str, dt_col: str = "dt") -> int:
    """按日期分区写入：先删掉这一天的旧数据，再追加。同一天重跑多少次，结果都一样（幂等）。

    ⚠️ 已知不足（D11 会遇到）："删"和"写"是两次提交。删完、还没写完时程序崩了，这一天就没了。
    返回写入的行数。
    """
    if table_exists(con, table):
        con.execute(f'DELETE FROM "{table}" WHERE "{dt_col}" = ?', (dt,))
        con.commit()
    _for_storage(df).to_sql(table, con, if_exists="append", index=False)
    return len(df)


def replace_table(con, df: pd.DataFrame, table: str) -> int:
    """整表替换：维度表这类"永远只有一份"的表用它。返回写入的行数。"""
    _for_storage(df).to_sql(table, con, if_exists="replace", index=False)
    return len(df)


def append_table(con, df: pd.DataFrame, table: str) -> int:
    """追加：日志这类"只增不改"的表用它。返回写入的行数。"""
    _for_storage(df).to_sql(table, con, if_exists="append", index=False)
    return len(df)

if __name__ == '__main__':
    pass
