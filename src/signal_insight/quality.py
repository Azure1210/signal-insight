#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : quality.py
# @Path       : signal-insight/src/signal_insight/quality.py
# @Project    : signal-insight
# @Author     : Matri
# @Date       : 2026-10-10 16:34:08
# @Version    : v1.0.0
# @Description: 
# @ChangeLog:
#   2026-10-10 16:34:08 | Matri | v1.0.0 | 初始化创建
import pandas as pd
STATUSES = ("通过","警告","不通过")
COLUMNS = ["check_id", "维度", "检查项","表字段", "结果", "状态", "证据","处理决定"]

def dq_record(con, check_id:str, dimension:str, item:str,
            field:str, result:str, status:str, evidence="",decision="") ->None:
    """把一条数据质量检查结果记录到dq_check_result表里，同一个check_id再运行会覆盖旧的记录"""
    if status not in STATUSES:
        raise ValueError(f"状态只能是: {' /'.join(STATUSES)},收到了: {status}")

    row = pd.DataFrame([dict(zip(COLUMNS, [check_id, dimension,item,field,
                        result,status, evidence,decision]))])

    try:
        old = pd.read_sql("SELECT * FROM dq_check_result", con)
    except Exception:
        old = row.iloc[0:0]
    new = pd.concat([old[old['check_id'] != check_id], row],ignore_index=True)
    new.to_sql("dq_check_result",con, if_exists='replace', index = False)
    n_old = len(old[old['check_id'] == check_id])
    overwrite = f"（覆盖 {n_old} 条旧记录）" if n_old else ""
    print(f"【{status}】{check_id} {dimension} | {item}: {result}{overwrite}")


def profile(df: pd.DataFrame) -> pd.DataFrame:
    """生成数据画像，每个字段输出一行统计信息。

    缺失值包括 NaN/None/NA，以及文本类字段（str、object、category）中
    去除首尾空白后为空的字符串。唯一值个数和示例值均基于非缺失值计算，
    保证各统计项的缺失口径一致。

    Args:
        df: 待分析的 DataFrame。允许 0 行、重复列名，以及包含 list、dict
            等不可哈希值的列。

    Returns:
        每个字段一行的 DataFrame，包含以下列：

        - 字段：列名。
        - 类型：pandas dtype 的字符串表示，如 "int64"、"str"。
        - 缺失数：缺失值个数（int）。
        - 缺失率：缺失数 / 总行数（float），0 行时为 0.0。
        - 唯一值个数：非缺失值的去重个数（int）。不可哈希的值按其字符串
        形式去重。
        - 示例值：第一个非缺失值；全部缺失时为 None。
    """
    n = len(df)
    rows = []
    for col, s in df.items():  # 按位置取列，列名重复也不会出错
        missing = s.isna()
        if (pd.api.types.is_string_dtype(s) or s.dtype == object
                or isinstance(s.dtype, pd.CategoricalDtype)):
            blank = s.astype("string").str.strip().eq("").fillna(False).astype(bool)
            missing = missing | blank
        valid = s[~missing]
        try:
            n_unique = int(valid.nunique())
        except TypeError:  # 列里有 list/dict 等不可哈希的值
            n_unique = int(valid.astype(str).nunique())
        n_missing = int(missing.sum())
        rows.append({
            "字段": col,
            "类型": str(s.dtype),
            "缺失数": n_missing,
            "缺失率": n_missing / n if n else 0.0,
            "唯一值个数": n_unique,
            "示例值": valid.iloc[0] if len(valid) else None,
        })
    return pd.DataFrame(rows)


if __name__ == '__main__':
    pass
