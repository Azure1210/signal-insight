# 西塔访客洞察看板（对外展示）

把 `data/signal.db` 里的聚合结果做成可点击的展示页：8 个页面、18 张图、1 张暗色六边形地图（24 个时刻）、
2 张明细表。配色沿用 `src/signal_insight/viz/theme.py` 与报告 docx（主色 `#1D6FA5`，深 `#174E73`），
版式参考 `项目介绍_讲师版.html`：纸色底（`#F3F4F1`）、衬线大标题、暗色首屏、圆角拟态侧栏。

## 启动

```powershell
cd dashboard
E:\Anaconda3\python.exe -m streamlit run visitor_dashboard.py --server.port 8501
```

打开 http://localhost:8501 。`streamlit`、`altair`、`pandas` 装在 base 环境；`signal` 环境用于跑流水线与测试。

## 首屏地图数据（可重新生成）

首屏的六边形地图由前端 canvas 现画，数据在 `dashboard/static/hero.json`（一份，约 26 KB）：
每个格子 24 个小时的人数、区县边界、商圈轮廓、逐小时合计。由 `build_hexdata.py` 从 `dws_user_hour` 现算：

```powershell
E:\Anaconda3\python.exe dashboard\build_hexdata.py
```

画面跟着时间走：白天（6—17 点）底色转浅、格子转蓝，夜里底色转深、格子转琥珀；
时间连续推进（常速每小时 1150 毫秒，整天约 28 秒）。缺失 hero.json 时看板会提示先跑上面那条命令。

## 页面

| 页面 | 回答的问题 | 主要证据 |
| --- | --- | --- |
| 概览 | 这一天西塔是什么形状 | `ads_zone_hourly`、`dws_user_hour`、`ads_xita_hourly` |
| 到访口径 | “来了多少人”为什么会有 12 个答案 | `ads_caliber_visitors`、`ads_hotspot_radius` |
| 空间口径 | 西塔这个点是怎么定出来的 | `dim_hotspot`、`ads_hotspot_radius`、`ads_night_distance` |
| 时间节奏 | 几点来、几点走 | `ads_xita_hourly`、`ads_xita_censoring` |
| 停留识别 | 怎样把信令压成“停留” | `dws_stay`、`dws_visitor`、`ads_stay_sensitivity` |
| 客群构成 | 来的是谁 | `ads_visitor_segment`、`dws_visitor_tag` |
| 商圈联动 | 来之前、走之后还去了哪 | `ads_xita_linkage`、`ads_zone_hourly` |
| 工程与边界 | 这些数字能不能重跑、能说多大话 | `etl_log`、`ads_dq_summary`、`dq_check_result` |

## 口径（每一页都带）

- 西塔 = `dim_hotspot` 的 500 米圆，中心 `123.410582, 41.806944`（前 5 站点按连接用户数加权的重心）。
- 到访 = 半径内停留 ≥ 30 分钟；停留 = 质心 ≤ 500 米且持续 ≥ 30 分钟。
- 傍晚访客 = 西塔停留结束时刻 ≥ 17:00，共 3,310 人。
- 数据在 23:59 截止，所有时长都是**下限**。

## 合规

页面只读 `signal.db` 的 `ads_*` / `dws_*` 聚合表，不输出 IMSI、手机号或轨迹；侧栏固定声明
“样本为中国移动用户样本内口径，不等于西塔客流，也不等于全市人流”。

## 文件

- `visitor_dashboard.py`：全部页面与样式（单文件）。
- `build_hexdata.py`：首屏六边形地图的数据生成器（输出 `static/hero.json`）。
- `.streamlit/config.toml`：主题色（纸色底）与 headless 设置。
- `static/hero.json`：首屏地图数据（生成物，约 26 KB）。
- 其余图表引用 `../image/` 下的 png（与报告同一批图）。
