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

if __name__ == '__main__':
    pass
