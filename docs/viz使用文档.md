# viz 使用文档

版本：maps v2.7.0 · layers v1.0.0 · heatmatrix v1.0.0（新）· callouts v1.3.0 · mapcolors v1.3.0 · theme 保持你现有的 v1.3.0 不动
日期：2026-10-16

---

## 1. 交付内容与安装

地图分两层画：先画**底图**（`geo.base()`，只由边界决定，不需要任何数据），再往上叠**数据层**（填色、散点、区内标注、外部引线），每层只画自己有数据的区，缺哪个区就不画哪个。地图颜色和 `theme.py` 无关，由 `mapcolors.py` 管。你项目里现有的 `theme.py`、`__init__.py`、`styles/` 一个字节都没改。

### 压缩包里有什么

| 路径 | 放到项目哪里 | 说明 |
| --- | --- | --- |
| `viz/` | `src/signal_insight/viz/` 整个替换 | theme.py、styles/、callouts.py 是原来的；maps.py、mapcolors.py、layers.py 更新；__init__.py 加了一行导出 `viz.matrix`；heatmatrix.py 新增 |
| `tests/test_viz_maps.py` | `tests/` | 地图测试，45 项（未改） |
| `tests/test_viz_layers.py` | `tests/` | 新数据层测试，29 项 |
| `tests/test_viz_matrix.py` | `tests/` | 热力矩阵测试，27 项 |
| `tests/test_viz_privacy.py` | `tests/` | 区域填色小样本抑制测试，9 项 |
| `tests/demo_matrix_privacy.py` | 随便放 | 热力矩阵两张、小样本抑制一张，生成第 11、12 节的图 |
| `tests/demo_layers.py` | 随便放 | 流向图、小多图、六边形热力口径对比，生成第 10 节的图 |
| `notebook/D3_05_西塔热点基站_cell.py` | 替换 notebook 里 D3_05 那个 cell | 改用 hexbin / zoom / bubbles 的写法 |
| `tests/fake_geo.py` | `tests/` | 模拟边界：区县版 `make()`、商圈版 `make_areas()` |
| `tests/demo_base_data.py` | 随便放 | 底图与数据层示例，生成第 2 节第一张图 |
| `tests/demo_center_alias.py` | 随便放 | 居中与别名示例，生成第 2 节第二张图 |
| `tests/demo_style_recipe.py` | 随便放 | 配色配方示例，生成第 4.4 节的图 |
| `tests/demo_areas.py` | 随便放 | 商圈示例，生成第 2 节第二张图 |
| `docs/` | 随便放 | 本文档和配图 |

### viz 包的结构

| 文件 | 管什么 | 常用入口 |
| --- | --- | --- |
| `theme.py`（未改） | 主题切换、通用图表的语义色常量、标题区和来源行 | `apply_theme`、`use_theme`、`finish`、`MAIN` 等常量 |
| `mapcolors.py`（新） | 地图自己的默认颜色 | `viz.maps.colors` |
| `maps.py` | 地图几何与分层绘制 | `Regions`、`scale_bar`、`north_arrow` |
| `callouts.py` | 外部引线标注、区内标注、参数包 | `Callouts`、`RegionTexts`、`LabelLayout` |
| `heatmatrix.py`（新） | 热力矩阵：A 与 B 的关系（OD、交叉表），格子里写数，小样本自动抑制 | `viz.matrix(...)` |
| `layers.py` | 数据层的实现：六边形热力、气泡、流向、小多图、定位小图、放大框、按米画圆、色条 | 通过 `geo.hexbin` 等方法和 `viz.maps.zoom` 等函数调用，一般不直接 import |
| `styles/*.mplstyle`（未改） | 主题外观文件 | `default`、`business`、`lively`、`academic` |
| `layouts/*.json` | 存好的引线参数包（第一次保存时自动建） | `geo.label(..., layout="名字")` |

依赖关系：`maps → layers → callouts → mapcolors`（layers 不 import maps）；`heatmatrix` 只用 `theme` 的语义色（它是通用图表，不是地图）；`maps` 只从 `theme` 取 `margins_in` 一个函数（给旧接口 `DistrictMap` 算留白），不取任何颜色。

### 运行前提

- Python 3.9+，matplotlib 3.6+，numpy、pandas；geopandas 可选，只有 `Regions.from_geodataframe` 用到。
- `viz` 依赖 `signal_insight/config.py` 的 `THEME`（默认主题名）和 `IMAGE_DIR`（`finish` 存图根目录），和以前一样。
- 字体沿用 `base.mplstyle`：TeX Gyre Termes、Noto Serif CJK SC。没装中文字体时汉字是方框。
- `styles/`、`layouts/` 是数据文件，打包时要声明为 package data。

---

## 2. 快速上手：先底图，再数据

底图只由边界决定，任何数据都不需要；数据层往上叠，有几个区的数据就画几个区。

```python
import matplotlib.pyplot as plt
from signal_insight import viz

viz.apply_theme("default")                       # 主题只管外观
geo = viz.maps.Regions(districts)                # {'和平区': [array([[123.429, 41.817], ...])], ...}

# 1) 底图：浅灰底色 + 白色内边界 + 深色外边界 + 比例尺 + 指北针
fig, ax = plt.subplots(figsize=(9, 6.4), layout="constrained")
geo.base(ax)

# 2) 数据层：缺和平区也没关系，和平区不填色、露出底色
visits = {"沈河区": 5489, "皇姑区": 765, "大东区": 1599}
geo.fill(ax, visits)                             # 填色
geo.label(ax, visits, inside="auto", hot=["沈河区"])   # 放得下写区内，放不下引到外面

viz.finish(fig, "各区到访人数", "2026 年 9 月", "来源：信令数据", "D3_到访.png")
```

![A 只有底图；B 底图 + 部分数据；C 自定义底图配色 + 只写区内](img/示例_底图与数据层.png)

A：不给任何数据，只写区名。B：只有 8 个区有数据，其余露出灰色底色，和"数值低"的白色分得开。C：底色、内边界、外边界都换了颜色，标注只写在区内，放不下的小区不写。完整代码见 `tests/demo_base_data.py`。

一步画完也可以：`geo.plot(values, texts=True, ...)` 就是 `base` + `fill` + `label`。`geo.plot(texts=True)` 不给数据时，只写全部区名。

### 地图默认居中；名字太长用别名

自己建的图比地图宽时（比如 `plt.subplots(figsize=(9, 6.4))`），地图完整、居中，两侧留白；之后加标注就排在留白里，地图不用挪。notebook 显示和 `finish` 存图都会裁白边，地图仍在正中。

```python
geo = viz.maps.Regions(districts, alias={"棋盘山风景区": "棋盘山", "沈阳世博园": "世博园"})
fig, ax = plt.subplots(figsize=(9, 6.4))
geo.plot(ax=ax)                                          # A 只有底图：居中
geo.plot(visits, texts=True, ax=ax, hot=["和平区"])       # B 加标注：排在两侧留白里
```

![A 只有底图；B 加标注；C 别名；D 窄图 + inside="auto"](img/示例_居中与别名.png)

别名只改标注里显示的名字；数据、`hot`、`each`、参数包仍用原名（图 C 里 `hot=["沈北新区"]` 照样生效）。详见第 3 节。

### 商圈这类零散区域

商圈彼此不相邻，常贴着外框四角，比例尺和指北针容易压上去：调大留白、挪开比例尺。

```python
ax = geo.base(ax, margin=0.08, scale=dict(x=0.55))
geo.fill(ax, colors=viz.AREA_COLOR, alpha=0.85)          # 每个商圈一个固定颜色
geo.points(ax, geo.clip(sites), by="district", colors={"铁西区": "#D64545"}, color="#C4CAD3", s=4, zorder=0.5)
geo.label(ax, visits, fmt="{:,.0f} 人")
```

![左：按数值填色；右：商圈固定颜色、站点按区着色](img/示例_商圈地图.png)

---

## 3. 数据格式

### 边界

| 写法 | 说明 |
| --- | --- |
| `{名字: 数组}` | 一个区一个环 |
| `{名字: [数组, 数组, ...]}` | 一个区多个环：多块飞地，或外环 + 洞 |
| `Regions.from_geodataframe(gdf, name="列名")` | GeoDataFrame，Polygon / MultiPolygon，内环自动带上 |

- 环首尾点相同或不同都可以，连续重复点自动去掉，少于 3 个点的环丢掉。
- 洞不用标：被奇数个环包住的环自动当作洞。被包住的飞地（如铁西区在于洪区里）要作为外面那个区的内环一起给，这样外面的区才会挖空。
- 商圈这类彼此不相邻的区域没问题：每个商圈整圈都算外边界，`borders`（内边界）什么也不画。
- 坐标是经纬度。长宽比按边界中心纬度自动校正，街道、城市、省都能用。

### 别名：名字太长时

```python
geo = viz.maps.Regions(districts, alias={"棋盘山风景区": "棋盘山"})   # 底图级：所有图都用
geo.alias["沈阳世博园"] = "世博园"                                  # 事后加、改
geo.label(ax, values, alias={"铁西区": "铁西(飞地)"})               # 只这一次，盖过 geo.alias
geo.text(ax, values, alias={...})                                   # 区内标注同样可以
```

- 只在数据给的是数（或 NaN、或 `plot(texts=True)` 只写名字）时生效。数据里自己写了字符串或 `(文字, 数)`，按你写的显示。
- 数据、`hot`、`each`、参数包、`at`、`side` 里一律用原名；别名写了底图没有的名字会警告。

### 站点（散点）

`geo.points(ax, df)` 默认读 `lng`、`lat` 两列，列名不同用 `lng=`、`lat=` 指定，也可以直接给 N×2 数组。

```python
geo.points(ax, sites)                                       # 一个颜色，默认 colors.ink
geo.points(ax, sites, color="#9CA3AF", s=3)                 # 自己定颜色、大小
geo.points(ax, sites, by="district",                        # 按某一列分组着色
           colors={"铁西区": "#D64545", "沈河区": "#1D6FA5"},
           color="#C4CAD3")                                 # colors 里没有的组用 color
geo.points(ax, sites, s=sites["nn_m"] / 40)                 # 点大小也可以给一列
geo.clip(sites, margin=0.1)                                 # 只留外框四周外扩 10% 内的点
```

`colors` 里写了、数据里没有的组会警告，方便发现区名写错。其余关键字（`alpha`、`zorder`、`marker`…）原样交给 `ax.scatter`。

---

## 4. 颜色

### 4.1 地图颜色：独立于主题

地图的每个默认颜色都只是"没传参数时用什么"。任何一次调用传了 `color=`、`lineprops=` 之类，以调用为准。

| 名字 | 用在哪 | 默认 |
| --- | --- | --- |
| `ink` | 标注名字和数值、外边界、落点、散点、比例尺、指北针 | `#1F2937` |
| `line` | 引线 | `#6B7280` |
| `hot` | `hot=` 强调的名字和数值、`edges` 整圈边界 | `#1D6FA5` |
| `land` | 底图底色；没数据的区就是这个颜色 | `#EEF0F3` |
| `low` | 填色色阶浅端（最小值） | `#FFFFFF` |
| `high` | 填色色阶深端（最大值） | `#8E99A6` |
| `border` | 内边界（区与区之间） | `#FFFFFF` |
| `nan` | 数据层里没数值、没给颜色的区 | `none`（不填，露出底图的 land） |
| `debug` | `debug=True` 时写的坐标 | `#B7791F` |
| `small_hatch` | `fill(min_value=5)` 里不足 5 人的区：白底上斜线的颜色 | `#9CA3AF` |
| `heat_low` / `heat_mid` / `heat_high` | 热力色阶（`hexbin`、`heat_cmap()`）浅 → 深；`locator` 的高亮区用 `heat_mid` | `#DCEAF5` / `#7FB3D9` / `#174E73` |
| `small` | `hexbin(small="gray")` 里不足门槛的格子，比 `land` 深一档 | `#D5DAE1` |

```python
viz.maps.colors                                    # 查看当前设置；notebook 里显示色块
viz.maps.colors.set(hot="#D64545", high="#1D6FA5") # 整体改，之后画的地图都用它
with viz.maps.colors.use(ink="#000000"):           # 临时改，出了 with 恢复
    geo.plot(values, texts=True)
viz.maps.colors.reset()                            # 全部恢复默认
```

- 颜色在画的那一刻取定：先 `set`，再画。
- 名字写错报 `TypeError` 并列出可用名字；值不是颜色报 `ValueError`。
- `viz.maps.colors.ink = ...` 这种直接赋值会报错，统一用 `set`。
- 想和某个主题保持一致，自己填进来即可：`viz.maps.colors.set(hot=viz.MAIN, ink=viz.INK)`。

### 4.2 主题：只管通用图表外观（未改动）

```python
viz.apply_theme("business")            # 全局切换，返回生效字体列表；不给参数用 config.THEME
viz.available_themes()                 # ['academic', 'business', 'default', 'lively']
with viz.use_theme("academic"):        # 临时切换
    ...
```

`theme.py` 里的 `MAIN`、`GRAY`、`RED`、`INK`、`AREA_COLOR`、`SEG_COLOR` 等是固定常量，不随主题变，可以 `from signal_insight.viz import MAIN, RED` 直接用，也可以拿来给地图上色（如 `colors=viz.AREA_COLOR`）。换主题不会改变地图颜色，换地图颜色也不会影响其他图表。

### 4.3 finish：标题区、来源行、存图

```python
viz.finish(fig, title, subtitle, source, path=None, *, accent=True)
```

左上角写标题和副标题（副标题可多行，用 `\n`），左下角写来源。给了 `path` 就以 300 dpi 存图，相对路径存进 `config.IMAGE_DIR`，返回完整路径。`accent=False` 去掉标题上方的主色短条。

### 4.4 配色配方：D3_02 / D3_03 的样子

三条规则：**灰阶打底，一种颜色强调一件事，点比区小。** 区县填色只用白到灰，强调色（蓝）只留给要读者注意的那一类；散点要比区界和填色"轻"，不然盖住底图。

![左：常见的坑；右：D3_02 的配方](img/示例_配色配方.png)

左图的三个坑都来自同一段常见写法：

| 坑 | 原因 | 改法 |
| --- | --- | --- |
| 比例尺两个、自定的红色内边界被盖住 | `geo.base(ax, ...)` 之后又 `geo.plot(..., ax=ax)`，plot 里又画了一遍底图 | 二选一：`base` + 数据层，或者只用 `plot`。现在重复画会警告 |
| 整张图一片深灰 | 填色的值全是 1，色阶两端相同，全部落在最深 | 填真实数值；不需要填色就别给 values |
| 城区一团蓝、看不清区界 | 点 `s=3` 太大，市内点用了强调色、`zorder` 压在区界上 | 市内点用墨色、`s≈0.3`；强调色给要强调的那类（市外） |

**D3_02（站点与区县）的配方：**

```python
from signal_insight.viz import MAIN, INK

inside  = sites[sites["district"] != "市外"]          # 按你表里"市外"的写法改
outside = sites[sites["district"] == "市外"]
counts  = inside.groupby("district").size()

fig, ax = plt.subplots(figsize=(9, 6.4), layout="constrained")
geo.base(ax)                                          # 默认就是：浅灰底、白内边界、深色外边界
geo.fill(ax, counts)                                  # 白 → 灰，越多越深（数值差很多倍时加 norm="log"）
geo.points(ax, geo.clip(outside), color=MAIN, s=0.5)  # 市外：强调色，小点
geo.points(ax, inside, color=INK, s=0.3)              # 市内：墨色，更小
geo.label(ax, counts)                                 # 名字 + 数值，同一种墨色
```

**D3_03（站点间距）的配方：**

```python
med = inside.groupby("district")["nn_m"].median()
far = med[med >= 900].index.tolist()                  # 要强调的那几个

fig, ax = plt.subplots(figsize=(9, 6.4), layout="constrained")
geo.base(ax)
geo.fill(ax, med, norm="log")                         # 间距差 16 倍：对数色阶
geo.label(ax, med, fmt="{:,.0f} 米", hot=far)         # hot：名字和数值换成强调色加粗
```

想整体换色调，改地图默认色即可，配方本身不用动：`viz.maps.colors.set(high="#1D6FA5", hot="#D64545")`。

---

## 5. 底图与数据层

地图从下到上分层，顺序由 zorder 固定，和调用先后无关：先画底图、后加数据，填色也会自动落在区界下面。

| 层 | 调用 | 属于 | zorder |
| --- | --- | --- | --- |
| 底色 | `base(land=...)` | 底图 | 0.8 |
| 填色 | `fill(...)` | 数据层 | 1.0 |
| 内边界 / 外边界 / 强调边界 | `borders` / `outline` / `edges` | 底图（edges 常用于强调） | 1.5 / 1.6 / 1.7 |
| 散点 | `points(...)` | 数据层 | 3 |
| 外部引线标注 | `label(...)` | 数据层 | 5 |
| 区内标注 | `text(...)` | 数据层 | 6（白边压住穿过的引线） |

### base：底图

```python
ax = geo.base(ax=None, *, land=True, borders=True, outline=True,
              scale=True, north=True, km=None, margin=0.02, height=6.0, room=True)
```

不需要任何数据，返回 ax。`ax` 不给就新建一张图，宽度按地图长宽比算（`room=True` 时两侧多留引线标注的位置）。给了 ax，地图在 ax 里居中（见下面 `frame` 的 `fill`）。每一层都可以 `True`（默认样式）、`dict`（自定样式）、`False`（不画）。

**区界配色怎么调**，三种方式，按需要选：

```python
# 1) 画底图时直接给：只影响这一张
geo.base(ax, land="#FBF6EE",
         borders=dict(color="#C9B79C", lw=0.6, ls=(0, (3, 2))),   # 内边界
         outline=dict(color="#7A5C3E", lw=1.6))                  # 外边界

# 2) 改地图默认色：之后所有地图都用它
viz.maps.colors.set(land="#F5F5F5", border="#FFFFFF", ink="#333333")   # ink 也是外边界色

# 3) 画完再改：返回值和 ax.collections 都是 matplotlib 对象
lc = geo.borders(ax); lc.set_color("#999999")
```

**为什么以前没数据时看不到内边界**：内边界默认是白线，以前底下没有底色，白线画在白底上等于没画；有数据时填了灰色，白线才显出来。现在底图自带浅灰底色，白线一直看得见。不想要底色，用 `base(land=False, borders=dict(color="#C4CAD3"))` 换成灰线即可。

### frame：把 ax 变成地图

```python
geo.frame(ax, margin=0.02, bare=True, fill=True)
```

地图框 = 外框四周留 `margin`（按长边比例），长宽比按纬度校正，`bare=True` 去刻度和边框。

- `fill=True`（默认）：ax 占满给它的位置，地图完整、居中，多出的宽度（或高度）两侧留白，引线标注排在留白里。每次排版按当时 ax 的大小重算，缩放、换版面都对。裁白边存图时地图也在正中。
- `fill=False`：ax 缩到地图本身大小（旧行为）。裁白边时，左边有标题、右边没有东西，地图会被挤到右边。
- 想放大某一块：`frame` 之后自己 `ax.set_xlim / set_ylim`，以你设的为新的地图框。

### fill（数据层）：按数值，或按区给颜色

```python
pc = geo.fill(ax, values, norm="log")                       # 按数值，走色阶
pc = geo.fill(ax, colors={"西塔": "#1D6FA5", "中街商圈": "#3B8C66"})   # 按区给颜色
pc = geo.fill(ax, colors="#EEEEEE")                         # 全部一个颜色
```

| 参数 | 作用 | 默认 |
| --- | --- | --- |
| `values` | `{名字: 数}` 或 Series；名字不在边界里会警告 | 无 |
| `colors` | `{名字: 颜色}` 或单个颜色；和 `values` 二选一 | 无 |
| `cmap` | 色阶（仅 values） | `colors.low → colors.high` |
| `norm` | `"linear"`、`"log"` 或 Normalize（仅 values） | `"linear"` |
| `nan_color` | 没数值 / 没给颜色的区 | `colors.nan`（露出底色） |
| `edgecolor`、`lw` | 填色块自带的边；默认与填色同色，防白缝 | `"face"`、0.3 |
| 其余 | 交给 PatchCollection，如 `alpha=0.85` | — |

数据为空也不报错，什么都不填。按数值填色时返回的 PatchCollection 本身就能出色条：`fig.colorbar(pc)`；`pc.cmap`、`pc.norm` 可以给旁边的图共用。

### borders / outline / edges（底图里已经画了，单独调用用于自定义或强调）

```python
geo.borders(ax)                                         # 内边界，默认 colors.border（白线）、0.9 磅
geo.borders(ax, color="#C4CAD3", lw=0.5, ls=(0, (2, 2)))  # 灰色虚线
geo.outline(ax, color="#1F2937", lw=1.4)                # 外边界，默认 colors.ink、1.0 磅
geo.edges(ax, ["和平区", "沈河区"], color="#D64545", lw=1.2)   # 强调几个区，默认 colors.hot
```

- `borders`：相邻两区的公共边（含飞地和包住它的区之间那圈），每条只画一次，虚线不会叠花。
- `outline`：所有区拼起来的最外圈；商圈这类零散区域就是每个商圈各一圈。
- `edges`：指定区的整圈边界（连洞边一起），压在内外边界上面。

### 比例尺和指北针

`base()` 已经画好了，调位置、长度直接在 `base` 里给：

```python
geo.base(ax, scale=dict(x=0.6, y=0.05, km=10),   # 比例尺：左端位置 + 长度（公里）
             north=dict(x=0.05, y=0.95))          # 指北针：位置
geo.base(ax, scale=False, north=False)            # 不要
```

画完想再挪，单独调用即可，**会替换旧的，不会叠出第二个**：

```python
viz.maps.scale_bar(ax, km=5, x=0.7, y=0.04)       # km 不给自动取约 1/4 地图框宽的整数（1、2、5、10、20…）
viz.maps.north_arrow(ax, x=0.95, y=0.95)
```

`x`、`y` 是在**地图框**里的比例位置（0~1）：(0, 0) 左下、(1, 1) 右上；比例尺的 `x, y` 是它左端的位置。地图居中、两侧留白时，它们仍贴着地图。区域贴着地图框四角时（商圈常见），挪到空的地方。引线标注会自动避开这两个附件；你自己加的图例想让标注避开，`artist.set_gid(viz.maps.FURNITURE)`。

### plot：一步画完

```python
ax = geo.plot(values=None, texts=None, *, ax=None, colors=None, norm="linear", cmap=None,
              dots=(), land=True, borders=True, outline=True, scale=True, north=True, km=None,
              margin=0.02, height=6.0, **label_kw)
```

等于 `base()` + `fill` + `points` + `label`。`values`、`colors` 都不给就只有底图；`texts=True` 用 values 写"名字 数值"，没有 values 就只写全部区名。其余关键字（`hot`、`inside`、`layout`、`angle`、`nameprops`、`each`…）交给 `label`。

---

## 6. 标注位置：label 怎么排

`geo.label(ax, values)` 在地图左右两侧各排一列文字。每条引线从文字出发，横走到拐点，再斜线扎进区内落点（区内离边界最远的点，`geo.anchor(名字)`）。

### 数据怎么给

```python
geo.label(ax, {"西塔": 3120})                   # 数 → "名字 数值"，两段可分开设样式
geo.label(ax, {"西塔": "西塔 3,120 人"})        # 字符串 → 整段照写
geo.label(ax, {"西塔": ("西塔商圈", 3120)})      # (文字, 数) → 自定名字那段，再跟数值
geo.label(ax, values, fmt="{:.1%}")            # 数值格式：格式串或函数，默认千分位取整
```

NaN 只写名字；名字不在边界里会警告，不画；数据为空就什么都不画，不报错。

### inside：放得下写区内，放不下引到外面

```python
co = geo.label(ax, values, inside="auto")
```

每次绘制时量一下文字能不能整块放进自己的区：放得下的写在区内（同第 7 节的 `text`），放不下的才排进左右两列。郊县这类大区写在区内，城区小区引到外面，两列短很多。区内那部分在 `co.inside`，改样式用 `co.inside.texts[名字]`；`co.freeze()` 的参数包里只有引到外面的那些。默认 `inside=False`，全部引到外面。

### 自动排版的六步

1. 分侧：按 `split` 定一条经度线，落点在线西进左列、线东进右列。只看底图，不看这次标了哪几个区，同一个区每张图都在同一侧。
2. 排序：每列按落点纬度从北到南。
3. 行位：`spread="span"`（默认）两列都铺满落点的上下范围再等距；`"fit"` 行位贴着落点高度，引线更平。
4. 拐点：`angle=None`（默认）同一列拐点对齐在一条竖线上；给度数则所有斜线同一角度、互相平行。
5. 去交叉：`uncross=True`（默认）出现交叉就对调这两条。
6. 避让：让开指北针、比例尺等地图附件。

每次绘制都按当时像素重排，缩放、`finish` 调整版面、存 300 dpi 都不会错位。

### split：分左右的那条线

| 取值 | 分界线 | 适用 |
| --- | --- | --- |
| `"center"`（默认） | 外框左右两沿的正中 | 区分布比较均匀 |
| `"balance"` | 所有区落点经度的中位数 | 区域偏在一边，想两列条数接近 |
| 数值，如 `123.3` | 直接给经度 | 精确控制 |

```python
geo.split_lng("center")                         # 查看分界线经度
geo.label(ax, values, side={"沈阳北站": "right"}) # 个别区单独指定；side="left" 全放左列
```

![左 split="center"、右 split="balance"（城区偏东的模拟底图）](img/分侧_center_vs_balance.png)

按模拟的商圈位置：城区四个商圈在西侧，世博园和棋盘山在东侧，`center` 分成左 4 右 2（见第 2 节的图）。真实沈阳区县很可能是左 2 右 11，这时 `balance` 更均衡。建议用真实边界各出一张再定。

### angle：拐点样式

| 取值 | 效果 |
| --- | --- |
| `None`（默认） | 同一列拐点对齐在竖线上，再斜线进区；最干净 |
| (0, 90) 内的度数，如 `60` | 所有斜线同一角度、互相平行，拐点沿横线往地图内收；更规整，横线会伸进地图 |
| `90` | 先竖后横的直角引线 |

![A 默认、B angle=60、C angle=90](img/引线角度对比.png)

### 其他位置参数

| 参数 | 含义 | 默认 |
| --- | --- | --- |
| `at` | `{名字: (lng, lat)}` 手动指定终点 | 无 |
| `elbow` | 拐点离地图外缘（磅） | 14 |
| `stub` | 起点到拐点的横线（磅） | 28 |
| `gap` | 文字离起点（磅） | 4 |
| `pad` | 上下两行文字的空隙（磅） | 3 |
| `sep` | 名字和数值之间（磅） | 3 |
| `fs` | 字号 | 9 |
| `debug` | 图上写出拐点、终点经纬度 | False |

---

## 7. 区内标注：text

名字和数值直接写在每个区的落点上（区内离边界最远的点，不贴边、不落进洞）。数据写法和样式参数与 `label` 完全一样。

```python
rt = geo.text(ax, values, hot=["沈河区"], fmt="{:,.0f}",
              nameprops=dict(size=8), valueprops=dict(weight="bold"),
              each={"康平县": dict(value=False)},
              stack=True,          # True 名字在上、数值在下；False 一行"名字 数值"
              halo=True,           # 文字白边，压在深色填色上也看得清；也可以给颜色或 False
              overflow="show")     # 放不下时："show" 照画并警告一次；"hide" 不画
rt.overflow                        # 最近一次绘制时放不下的区名
rt.texts["沈河区"], rt.nums["沈河区"]   # matplotlib Text，可以接着改
```

| 参数 | 含义 | 默认 |
| --- | --- | --- |
| `stack` | 名字、数值上下两行；False 写成一行 | True |
| `sep` | 上下两行的间距（磅） | 1 |
| `halo` | 文字白边：True / 颜色 / False | True |
| `overflow` | 放不下时 `"show"` 照画并警告、`"hide"` 不画 | `"show"` |
| `at` | `{名字: (lng, lat)}` 手动指定位置 | 无 |

"放得下"按当前版面判断，图变小了原本放得下的可能放不下。想自动处理，用 `geo.label(ax, values, inside="auto")`。

---

## 8. 标注样式：四个部分逐个设置

每条标注有四个部分：名字 `name`、数值 `value`、引线 `line`、落点 `dot`。每部分可整体设样式、用 `False` 隐藏、用 `each` 对单个区覆盖。优先级：默认 < 整体 props < `hot` < `each`。

![左：默认；右：名字与数值分色、虚线引线、去掉落点、两区红色强调、内外边界分开设计](img/样式对比.png)

| 部分 | 参数 | 接受的样式 | 默认 |
| --- | --- | --- | --- |
| 名字 | `nameprops` | Text：`color`、`size`、`weight`、`family`、`alpha`… | 9 号，`colors.ink` |
| 数值 | `valueprops` | 同上 | 9 号，`colors.ink` |
| 引线 | `lineprops` | Line2D：`color`、`lw`、`ls`、`alpha`… | `colors.line`，0.45 磅实线 |
| 落点 | `dotprops` | Line2D 标记：`marker`、`ms`、`color`、`mec`、`mew` | 圆点 2.2，`colors.ink`，白边 |

```python
geo.label(ax, values, fmt="{:,.0f}",
    nameprops=dict(color="#6B7280", size=8.5),
    valueprops=dict(weight="bold"),
    lineprops=dict(lw=0.6, ls=(0, (3, 2))),
    dotprops=False,                                 # False = 这部分全部不画
    hot=["中街商圈"],                                # 名字和数值换成 colors.hot 加粗
    each={
        "太原街商圈": dict(value=dict(color="#D64545"), line=dict(color="#D64545", lw=1)),
        "沈阳北站": dict(value=False),               # 只写名字
        "西塔": dict(line=False, dot=False),         # 只留文字
        "棋盘山风景区": False,                       # 整条不画
    })
```

- 部分名写错直接报错并指出哪个区；区名写错会警告。
- 画完还能改：`co = geo.label(...)`，然后 `co.texts[名字]`、`co.nums[名字]`、`co.lines[名字]`、`co.dots[名字]` 都是 matplotlib 对象。位置相关属性由排版控制，改了会被覆盖。
- 一个区整体突出，通常三处一起改：`geo.edges(ax, [名字], color=...)`、`each` 里的 name/value/line、必要时 `fill(colors=...)`。

样式不存进参数包：位置是底图的属性，样式是这张图的属性。

---

## 9. 参数包与手动微调

自动排版满意后，用 `co.freeze()` 把位置定成参数包（`LabelLayout`），手动改几条，存成 JSON；以后同一张底图的所有图都套这个包，只换数值和样式。

### 流程

1. 自动排一版并打开 debug：`co = geo.label(ax, values, debug=True)`。
2. 先把图画完：`viz.finish(...)` 存图，或在 notebook 里显示一次。版面定了坐标才是最终的。
3. 定下来：`lay = co.freeze()`。
4. 微调：`swap` / `move` / `edit`，可以连着写。
5. 保存：`lay.save("src/signal_insight/viz/layouts/shenyang_areas.json")`。
6. 以后每张图：`geo.label(ax, values, layout="shenyang_areas")`。

```python
co = geo.label(ax, visits, debug=True)
viz.finish(fig, title, sub, src, "draft.png")
lay = co.freeze()
print(lay)                                    # 每条一行：侧、拐点、终点
lay.swap("西塔", "中街商圈").move("沈阳北站", dy=-0.005).edit("棋盘山风景区", stub=40)
lay.save("src/signal_insight/viz/layouts/shenyang_areas.json")
```

### 修改方法

| 方法 | 作用 | 单位 |
| --- | --- | --- |
| `swap(a, b)` | 两条对调位置（侧、拐点、起点、横线长），终点不变 | — |
| `move(name, dx=0, dy=0)` | 拐点（及单给的起点）平移，文字跟着走 | 度 |
| `edit(name, **字段)` | 改 `side`、`elbow`、`end`、`start`、`stub`；名字不在包里时新加一条（side、elbow、end 必填） | 坐标 (lng, lat)，stub 磅 |

`edit(name, start=None)` 让起点回到"从拐点水平向外 stub 磅"。商圈这类小范围底图，`move` 的 `dy` 要按实际纬度跨度给，比如 0.005 度约 550 米。

### JSON 格式

一个名字一行，方便手改和看 diff（坐标是示意）：

```json
{
  "stub": 28.0,
  "gap": 4.0,
  "labels": {
    "西塔": {"side": "left", "elbow": [123.36512, 41.80123], "end": [123.41201, 41.80598]},
    "棋盘山风景区": {"side": "right", "elbow": [123.71234, 41.93012], "end": [123.66, 41.93], "stub": 40}
  }
}
```

### 套参数包时的规则

- `layout` 可以是 `LabelLayout`、JSON 路径，或 `viz/layouts/` 下的文件名（不带 `.json`）。
- 位置、`stub`、`gap` 全按参数包；`split`、`spread`、`angle`、`at` 不起作用。
- 数据里有、包里没有的区会警告并跳过；终点不在对应区内也会警告（多半拿错了底图的包）。
- 自检：文字重叠、文字压到附件、同列引线交叉时各警告一次。

---

## 10. 更多数据层：六边形热力、气泡、流向、小多图、放大图

和 `fill` / `points` 一样，都是"往给定的 ax 上加一层，返回 matplotlib 对象"。实现在 `layers.py`，入口挂在 `Regions` 上；不依赖区界的几样是 `viz.maps` 的函数。颜色都从 `viz.maps.colors` 取，新增 `heat_low / heat_mid / heat_high`（热力色阶，主色浅 → 深）和 `small`（不足门槛的格子）。

距离一律给米：格宽、圆半径、放大框半宽。经纬两个方向分别折算，配上长宽比校正画出来是正六边形、正圆、正方形。

### hexbin：六边形热力

```python
hb = core.hexbin(ax, sig, 500, value="imsi", how="nunique")      # 每格 = 连过格内任一基站的人，去重
viz.maps.colorbar(hb, ax, label="格内连接用户数（人，去重；每格 500 米）")
hb.cells.head()       # 每格一行：q, r, lng, lat, value, n_rows, suppressed —— 标题里的数从这里算
hb.size_m             # 格宽（米），写进副标题
```

| 口径 `how` | `value` | 含义 | 什么时候用 |
| --- | --- | --- | --- |
| `"nunique"` | `"imsi"`，传 `sig` | 连过格内任一基站的人数，一人只算一次 | 人数推荐用它 |
| `"max"` | `"用户数"`，传 `site_users` | 格内最热基站的人数 | D3_05 原来的口径 |
| `"sum"` | `"用户数"` | 格内各站相加 | 人数别用：一人连多站会重复计数 |
| `"count"` | — | 行数 | 信令条数，不是人数 |
| `"mean"` | 任意数值列 | 平均 | 不是人数，记得 `min_value=None` |

- **格宽 `size_m`**：相邻两格中心的距离。不给时取外框宽约 40 格，取整到 500 米、2.5 公里这类数。几张图用同一个 `size_m`，格子才一样大、颜色才能比。
- **门槛 `min_value=5`**：按格子判断（规范第 7 节）。默认不画；`small="gray"` 画成 `colors.small`，副标题写明"灰格 = 不足 5 人"。旧做法先按基站滤掉不足 5 人的站，郊区的站会整批消失；按格去重时一格里几个站的人合起来就能过线，见下图。
- **裁剪 `clip=True`**：只统计区内的点（区外、洞里的都不算），六边形裁到区界。
- **色阶**：默认对数，下限 = 门槛，色条刻度标 5、10、30、100…。几张图要同一色阶时给同一个 `vmax`，或直接传同一个 `Normalize`。
- 只要统计、不画：`viz.maps.hexgrid(df, 500, value="imsi", how="nunique")`。几十万行信令也只按几千个不同坐标算格号，200 万行约 1 秒。

![六边形热力两种口径](img/示例_六边形热力口径.png)

### bubbles：气泡

```python
sc = core.bubbles(ax, sites, "用户数", hot=sites["site_id"].isin(top["site_id"]), color=GRAY)
r_pt = np.sqrt(sc.size_of(2300) / np.pi)        # 气泡半径（磅），自己在旁边写数字时用
```

面积 ∝ 数值（不是直径）；大的先画，小气泡压在上面。`hot` 是和 `df` 等长的布尔数组，强调的用 `colors.hot`，其余用 `color`（默认 `colors.high`）。不足 `min_value` 的不画。图例是三个参考圈（1 / 2 / 5 × 10ⁿ 自动选），默认横排在 ax 正下方；`legend=dict(...)` 改位置，`ref=[...]` 自己定参考值，`legend=False` 不要。`vmax` 给折算面积用的最大值，几张图要可比时给同一个数。

### flows：流向（OD）

```python
fl = geo.flows(ax, od_df, origin="居住区", dest="工作区", value="人数", top=15, hot=3,
               at={"外地": (123.9, 42.1)})
fl.dropped     # {'self_loops': 区内流动条数, 'small': 不足 5 人条数, 'unknown': [不认识的名字], 'beyond_top': 没画的条数}
```

线宽 ∝ 人数；最大的 `hot` 条用 `colors.hot`，数值写在弧线外凸一侧，其余灰色。弧线往前进方向的右手边弯，A→B 和 B→A 自然分开。区内流动（起点 = 终点）不画；边界里没有的起讫点（"外地"、某个商圈）用 `at` 给坐标。左上角是线宽图例。

注意：只画最大的 `top` 条（默认 15）。条数一多就成了一团线，完整的 A 与 B 关系按规范第 4 节用热力矩阵；`fl.dropped` 里的数写进副标题。城区几个小区挤在一起时箭头会汇成一团，这时先放大到城区再画。

![流向图](img/示例_流向图.png)

### facets：小多图

```python
hourly = presence.pivot(index="区", columns="时段", values="人数")     # 行 = 区，列 = 面板
fig, axes, cb = geo.facets(hourly[["8 点", "12 点", "19 点", "23 点"]], norm="log",
                           label="在场人数（人）", cmap=viz.maps.heat_cmap())
viz.finish(fig, title, subtitle, SOURCE, "D3_xx.png")
```

同一张底图画几遍，所有面板共用一个色阶和一根色条；每张面板人数最多的区整圈描边（`hot_max=False` 关掉）。比例尺、指北针只画在第一张。`text=True` 在区内写数值，面板小时多半写不下（放不下的不写），可以把 `height` 调大。返回的 `axes` 照常往上加东西。

![小多图](img/示例_小多图.png)

### 放大图：zoom、circle、locator

```python
core.base(ax_map)
core.base(ax_z, fill=False, outline=False, north=False)            # 右图先画底色和区界
viz.maps.zoom(ax_map, ax_z, lng, lat, 1000, label="西塔")          # 2 × 2 公里；右图比例尺跟着挪进新视窗
viz.maps.circle(ax_z, lng, lat, 500)                               # 500 米圈，画出来是正圆
city.locator(ax_map, highlight=CORE)                               # 角落里的全市定位小图
```

- `zoom` 在左图画放大框（主色 + 白边，压在深色热力上也看得见），把右图设成框里的范围、校正长宽比、画同色边框，框左上方写 `label`。`half_m` 给 `(半宽, 半高)` 可以做成长方形。右图先 `base()` 过也行：`zoom` 会关掉"撑满 ax"，并把已有的比例尺、指北针按新视窗重放。
- **连接线默认不画**：框和右图边框同色、框旁写同一个名字，读者就能对上。原来 `fig.add_artist(ConnectionPatch(..., zorder=0))` 的写法，线排在 axes 前面画，被两张图的白底盖住，只在两图之间的空隙露出一小段。确实要连线（框很小、离右图远）用 `connect=True`：线在最上层、带白描边，代价是横穿左图。
- `circle` 默认主色虚线、不填充；`fc=...` 加底色。
- `locator` 用调用它的那个 `Regions`（通常是全市）画缩略图，`highlight` 的区用 `colors.heat_mid`，`box=(lng0, lat0, lng1, lat1)` 画框；`loc` 选角落。

### colorbar：色条

`viz.maps.colorbar(mappable, ax, label=...)`，`hexbin` 和 `fill` 的返回值都能用。对数色阶标 5、10、30、100… 这样的实际数值（千分位），下限是 5、20 这类整数时也标上；无边框、无短刻度线。`ax` 可以给一组 ax（小多图共用一根）。

---

## 11. 小样本抑制：少于 5 人的不公布

### 为什么要做

规范第 7 节：少于 5 人的格子不能公布。人数太少时，配合别的信息（住哪个区、几点出现在哪）就可能认出具体的人。所以凡是**人数**，图上都不能出现 1、2、3、4 这样的数，也不能让读者把它**算出来**。

后半句容易漏。看这个例子：

| 区 | 人数 |
| --- | --- |
| 甲区 | 120 |
| 乙区 | <5 |
| 丙区 | 300 |
| **合计** | **423** |

乙区写了 `<5`，看起来藏住了。可是 423 − 120 − 300 = 3，一减就出来了。所以只要图上（或者标题、正文里）出现了合计，被藏的就不能只有一个；要再藏一个，让读者面对"两个未知数、一个等式"，算不出来。这叫**互补抑制**。

viz 里有两处会自动处理这些事：区域填色（本节）和热力矩阵（第 12 节）。六边形热力 `hexbin` 本来就按格子抑制（第 10 节）。

### 最小例子：一行搞定

```python
geo.plot(visits, texts=True, min_value=5)
```

这一行做了四件事：

1. 不足 5 人的区不按数值上色，画成白底斜线；
2. 这些区也不参与色阶计算，色阶的浅端不会被一个 3 人的区拉低；
3. 标注里这些区的数写成 `<5`；
4. 地图正下方加一个图例色块"不足 5 人（不公布）"。

![小样本抑制的三种样式](img/示例_小样本抑制.png)

### 分层画时：fill、text、label 给同一个 min_value

不用 `plot`、自己一层一层叠时，每一层都要传 `min_value`。只给 `fill` 不给 `label`，颜色藏住了，数字却还写在图上。

```python
ax = geo.base()
pc = geo.fill(ax, visits, norm="log", min_value=5)          # 1) 填色：不足 5 的画斜线
geo.label(ax, visits, inside="auto", min_value=5)          # 2) 标注：不足 5 的写 "<5"
if pc.suppressed:                                          # 3) 有被藏的区才加图例
    ax.legend(handles=[pc.small_patch], loc="upper center", bbox_to_anchor=(0.5, 0), frameon=False)
print(pc.suppressed)                                       # ['康平县', '法库县']：哪些区被藏了
```

### 参数

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `min_value` | `None`（默认）或数 | 小于它的区被藏。默认不抑制，是为了不影响原来的图；**值是人数时请总是写 `min_value=5`**。占比、密度这类不是人数的值别开 |
| `small` | `"hatch"`（默认） | 白底灰斜线。一眼看出"有数据，但不公布"，推荐 |
| | `"gray"` | 填浅灰（`colors.small`）。配默认的灰色色阶时容易和"数值低"混淆（见上图中间），配蓝色色阶时再用 |
| | `"blank"` | 不画，露出底色。看起来和"没有数据"一样，用它时副标题必须写清楚 |

`fill` 的返回值多了三样：`pc.suppressed`（被藏的区名列表）、`pc.small_patch`（放进图例的色块）、`pc.small_layer`（画斜线的那一层，没有被藏的区时是 `None`）。

`facets` 也有 `min_value` / `small`，每张面板都按它藏，数字也写 `<5`。

### "只剩一个区被藏"的警告

```
UserWarning: 只有 康平县 一个区不足 5：如果标题、副标题或别的图里写了这些区的合计，用合计减去其他区就能算出它……
```

这就是上面那个"一减就出来"的情况。地图本身不写合计，所以只是提醒，不会自动多藏。看到它时检查三处：标题、副标题、同一份报告的其他图表里有没有写这些区的精确合计（比如"全市 12,345 人"）。有的话，把合计改成粗略的写法（"约 1.2 万人"），或者删掉。

热力矩阵会在图上画合计，所以那里的互补抑制是自动做的，见下一节。

---

## 12. 热力矩阵：viz.matrix

### 什么时候用

规范第 4 节：要看"A 与 B 的关系"（住在哪个区的人去哪个区上班、哪两个商圈的客人重叠、哪类人在哪个时段出现），用热力矩阵，格子里写数字；不用和弦图。地图上的流向图（第 10 节 `flows`）只能画最大的十几条，矩阵能把所有组合都摆出来，两者互补。

![热力矩阵：人数](img/示例_热力矩阵_人数.png)

### 五分钟上手

**第 1 步：准备长表。** 一行一条记录，三列：行是什么、列是什么、数值。从 ADS 层查出来通常就是这样：

```python
od.head()
#   居住区  工作区   人数
# 0 铁西区  铁西区  2,112
# 1 铁西区  和平区    740
# 2 铁西区  沈河区    123
```

**第 2 步：画。** 告诉函数哪一列是行、哪一列是列、哪一列是数：

```python
m = viz.matrix(od, row="居住区", col="工作区", value="人数", order="total", totals=True, hot=3)
```

**第 3 步：标题、副标题、存图。** 标题里的数从 `m.counts` 算（规范第 1 节：标题里的数必须代码算）；`m.note` 是图上符号的说明，接在副标题后面：

```python
off = m.counts.where(~np.eye(len(m.counts), dtype=bool))          # 去掉对角线（区内），只看跨区
r, c = np.unravel_index(np.nanargmax(off.to_numpy()), off.shape)
viz.finish(m.ax.figure,
           f"跨区通勤最多的是 {m.counts.index[r]}→{m.counts.columns[c]}，{off.iat[r, c]:,.0f} 人",
           f"行 = 居住区，列 = 工作区，按合计从大到小排；深色框 = 跨区前 3 名\n{m.note}",
           SOURCE, "D14_03_通勤矩阵.png")
```

就这些。下面是细节。

### 数据：长表还是宽表

| 你手里的数据 | 怎么调 |
| --- | --- |
| 长表（一行一条：行名、列名、数值） | `viz.matrix(df, row="居住区", col="工作区", value="人数")`。同一格出现多次会自动相加 |
| 宽表（行 = A、列 = B，`df.pivot` 出来的） | `viz.matrix(wide)`，三个列名都不给 |

长表里缺的组合（比如没有"苏家屯区→康平县"这一行）在矩阵里是空白格，不写字。如果"缺"的意思是 0 人，先补上 0 再画（0 也小于 5，会显示成 `<5`）。

### 读懂格子里的符号

| 格子 | 意思 |
| --- | --- |
| 蓝色 + 数字 | 正常数据，颜色越深越大；深色格子自动用白字 |
| 深色边框 + 粗体 | `hot` 强调的格子 |
| 浅灰底 + `<5` | 不足 5 人，不公布 |
| 浅灰底 + `*` | 互补抑制：这格本身不少，但为了让 `<5` 算不出来一并藏起来 |
| 很浅的灰底 + 灰字 | 对角线（区内），不参与配色（见下面 `diagonal`） |
| 白底、没字 | 没有这个组合的数据，或者 `diagonal="hide"` |

`m.note` 会根据图上实际出现了哪些符号生成说明，比如"<5 = 不足 5 人，不公布；* = 为防止由合计反推而一并隐去；对角线（灰字）= 区内，不参与配色"。

### 互补抑制：什么时候会出现 `*`

只在读者**能做减法**的时候：

- `totals=True`：画了每行、每列的合计；
- `percent="row"` / `"col"` / `"all"`：每行（列、全表）加起来是 100%，等于也给了合计。

这时如果某一行里看不见的格子只有一个、而且它是 `<5`，就在这一行再藏一格；列也一样，反复检查到每一行、每一列都安全为止。挑哪一格的规则：优先挑"能同时补好一行一列"的格子，其次挑数最小的（藏小数对读者损失最小）。例子里 3 个 `<5` 分在不同行、不同列，一共只多藏了 3 格，这已经是最少的。

两种不需要 `*` 的情况：

- 不画合计、不算占比：读者没法做减法；
- 对角线设成 `diagonal="hide"`：有 `<5` 的那一行本来就有两个看不见的格子（`<5` 和对角线），算不出来。见下面的占比图，一个 `*` 都没有。

合计本身不足 5 时也写 `<5`。

想在 Excel、Word 表格里用同样的规则：`from signal_insight.viz.heatmatrix import suppress_cells`，`primary, secondary = suppress_cells(counts, 5, rows=True, cols=True)`，拿到两张布尔表再自己填。

### 看占比：percent

```python
m = viz.matrix(od, row="居住区", col="工作区", value="人数", order="total", percent="row", diagonal="hide")
```

| percent | 每格是 | 回答的问题 |
| --- | --- | --- |
| `None`（默认） | 人数 | 哪两个区之间人最多 |
| `"row"` | 占这一行的比例，每行加起来 100% | 住在 A 区的人，分别去了哪些区 |
| `"col"` | 占这一列的比例，每列加起来 100% | 在 B 区上班的人，分别从哪来 |
| `"all"` | 占全表的比例 | 这个组合占全部的多少 |

占比的分母是**真实的合计**，包括被藏的格子和对角线，所以显示的百分比是真实比例；被藏的那几格加起来就是这一行没写出来的那部分。百分比按规范第 6 节写：一般取整（40%），不到 1% 保留一位（0.4%），不到 0.1% 保留两位。

![热力矩阵：按行占比](img/示例_热力矩阵_行占比.png)

### 对角线：diagonal

行和列是同一组名字时（OD 矩阵），左上到右下那条斜线是"区内"：住在铁西、也在铁西上班。它通常比跨区的数大得多，一起配色会把其他格子全压成浅色，看不出差别。

| diagonal | 效果 | 什么时候用 |
| --- | --- | --- |
| `"auto"`（默认） | 方阵用 `"gray"`，不是方阵用 `"show"` | 一般不用改 |
| `"gray"` | 浅灰底灰字，写数但不参与配色 | 想保留区内人数作参考 |
| `"hide"` | 不显示 | 只关心跨区（常配 `percent="row"`） |
| `"show"` | 和别的格子一样上色 | 对角线不特殊时（比如两个商圈的客人重叠） |

### 全部参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `data` | — | 长表或宽表，见上 |
| `ax` | `None` | 不给就新建一张图，大小按格子数算；给了就画进去 |
| `row` / `col` / `value` | `None` | 长表的三个列名 |
| `order` | `None` | `None` 按数据原样；`"total"` 按合计从大到小；列表 = 指定顺序（方阵行列同序）；`(行列表, 列列表)` 分别指定，也可以只挑一部分 |
| `percent` | `None` | `"row"` / `"col"` / `"all"`，见上 |
| `min_value` | `5` | 小于它写 `<5`。数不是人数时给 `None` |
| `totals` | `False` | 右边加合计列、下边加合计行 |
| `diagonal` | `"auto"` | 见上 |
| `hot` | `0` | 整数 = 强调前几名（不含对角线和被藏的）；`[(行, 列), ...]` = 指定格子 |
| `fmt` | 自动 | 数字写法：人数 `"{:,.0f}"`，占比按规范；可以给格式串或函数 |
| `norm` | `"linear"` | `"log"`：数差好几个数量级时用 |
| `cmap` | 主色浅 → 深 | 色阶 |
| `cbar` / `cbar_label` | `False` / `""` | 要不要色条。格子里已经写了数，一般不要 |
| `row_title` / `col_title` | 长表列名 | 行、列分别是什么 |
| `fontsize` | `9` | 格子里的字号，小于 8 会警告（规范第 3 节） |
| `cell` | `(0.62, 0.40)` | 自动建图时每格的宽、高（英寸）。名字长就加宽 |
| `rotate` | `"auto"` | 列名放不下自动斜 45° |

### 返回值 MatrixPlot

| 属性 | 是什么 | 常见用法 |
| --- | --- | --- |
| `m.ax` | 画在哪个 ax | `m.ax.figure` 交给 `viz.finish` |
| `m.counts` | 排好序的人数矩阵（DataFrame） | 标题里的数从这里算 |
| `m.values` | 上色用的值（`percent` 时是 0~1 的占比） | 算"最高占比" |
| `m.shown` | 每格实际写的字 | 交付前核对：`m.shown` 里不该有小于 5 的数 |
| `m.suppressed` / `m.secondary` | 布尔表：`<5` 的格子 / `*` 的格子 | `m.n_hidden` 是两者合计 |
| `m.texts` | `{(行, 列): Text}` | 单独改某一格：`m.texts[("铁西区", "和平区")].set_color(viz.RED)` |
| `m.totals` | `{"row", "col", "all"}` 合计（`totals=True` 时） | |
| `m.mesh` | 上色的 QuadMesh | 自己加色条：`fig.colorbar(m.mesh, ax=m.ax)` |
| `m.note` | 符号说明 | 接在副标题后面 |

### 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `ValueError: 长表要同时给 row=、col=、value=` | 只给了一两个列名 | 三个都给，或者三个都不给（宽表） |
| `KeyError: data 里没有这些列` | 列名打错 | 报错信息里列出了现有的列 |
| 除了对角线全是浅色 | 对角线参与了配色 | 默认已经不参与；如果设了 `diagonal="show"`，改回 `"auto"` |
| 出现了很多 `*` | 开了 `totals` 或 `percent`，`<5` 又分散 | 正常；只看跨区时用 `diagonal="hide"` 往往一个 `*` 都不用 |
| 不想要 `*` | — | 不画合计、不算占比；**不要**为了去掉 `*` 把 `min_value` 设成 `None` |
| 列名斜着、挤 | 名字长、格子窄 | `cell=(0.9, 0.4)` 加宽，或用简称 |
| 色条刻度是 0.2、0.4 | 开了 `percent` 又开了 `cbar` | 色条已按百分比显示；一般不需要色条 |

---

## 13. API 速查

### viz.maps.Regions

| 调用 | 返回 | 说明 |
| --- | --- | --- |
| `Regions(regions, *, lat0=None, alias=None)` | Regions | `{名字: 环或[环...]}`；alias 别名 |
| `Regions.from_geodataframe(gdf, name)` | Regions | 从 GeoDataFrame 建 |
| `.names` / `.bounds` / `.aspect` / `.lat0` / `.alias` | — | 区名、外框、宽高比、折算纬度、别名 |
| `.anchor(name)` | (lng, lat) | 区内落点 |
| `.split_lng(split="center")` | 经度 | 分左右列的线 |
| `.clip(df, margin=0.1)` | DataFrame | 只留外框附近的点 |
| `.base(ax=None, *, land, borders, outline, scale, north, km, margin)` | ax | 底图，不需要数据 |
| `.frame(ax, margin=0.02, bare=True, fill=True)` | ax | 地图框、长宽比；fill 居中留白 |
| `.fill(ax, values=None, *, colors=None, cmap, norm, nan_color, ...)` | PatchCollection | 填色 |
| `.borders(ax, color=None, lw=0.9, ls="-")` | LineCollection | 内边界 |
| `.outline(ax, color=None, lw=1.0, ls="-")` | LineCollection | 外边界 |
| `.edges(ax, names, color=None, lw=1.2)` | PatchCollection | 指定区整圈边界 |
| `.points(ax, data, *, color=None, by=None, colors=None, s=1)` | PathCollection | 叠点 |
| `.text(ax, texts, ..., alias=None)` | RegionTexts | 区内标注 |
| `.label(ax, texts, ..., inside=False, alias=None)` | Callouts | 外部引线；`inside="auto"` 放得下写区内 |
| `.plot(values, texts, *, ax, colors, land, ..., margin, **label_kw)` | ax | base + 数据层，一步出图 |
| `.hexbin(ax, df, size_m=None, *, value, how, min_value=5, small, norm, vmax, clip)` | PolyCollection（`.cells`、`.size_m`） | 六边形热力 |
| `.bubbles(ax, df, value, *, hot, color, smax, vmax, min_value=5, legend, ref)` | PathCollection（`.size_of`、`.data`） | 气泡，面积 ∝ 数值 |
| `.flows(ax, od, *, origin, dest, value, top=15, hot=3, at, bend, min_value=5)` | 命名空间（`arrows`、`texts`、`data`、`dropped`） | 流向弧线 |
| `.facets(data, *, ncols, norm, vmax, cmap, height, label, text, hot_max)` | (fig, axes, colorbar) | 小多图，同一色阶 |
| `.locator(ax, highlight=(), *, box, loc, width)` | 小图的 ax | 角落定位小图 |
| `.fill(..., min_value=None, small="hatch")` / `.text(..., min_value=None)` / `.label(..., min_value=None)` / `.plot(..., min_value=None, small="hatch")` / `.facets(..., min_value=None)` | — | 小样本抑制（第 11 节） |

### 其他

| 调用 | 说明 |
| --- | --- |
| `viz.maps.colors.set(**kw)` / `.use(**kw)` / `.reset()` | 地图默认颜色 |
| `viz.maps.scale_bar(ax, km=None, lat0=None, x=0.04, y=0.04)` | 比例尺；再调用是替换 |
| `viz.maps.north_arrow(ax, x=0.95, y=0.95)` | 指北针；再调用是替换 |
| `viz.maps.set_map_aspect(ax, lat0=None, bare=True)` | 只做长宽比校正 |
| `viz.maps.zoom(src, dst, lng, lat, half_m, *, label, color, connect=False)` | 放大框 + 右图视窗 |
| `viz.maps.circle(ax, lng, lat, radius_m, **kw)` | 按米画圆 |
| `viz.maps.colorbar(mappable, ax, *, label, ticks=None)` | 规范色条 |
| `viz.maps.hexgrid(df, size_m, *, value, how, min_value=5)` | 只统计六边形格子 |
| `viz.maps.nice_size(span_m, n=40)` / `m2deg(m, lat0)` / `heat_cmap()` / `HALO` / `M_PER_DEG` | 格宽取整、米换度、热力色阶、文字白边、每度米数 |
| `viz.maps.FURNITURE` | 让标注避开的 gid |
| `viz.maps.LAND` | 底色层的 gid，`ax.collections` 里按它找 |
| `Callouts.texts / nums / lines / dots` | 按区名取四个部分 |
| `Callouts.freeze()` / `.layout` | 定成参数包 / 当前参数包 |
| `LabelLayout.load(path)` / `.save(path)` / `.swap` / `.move` / `.edit` | 参数包读写与微调 |
| `viz.apply_theme` / `use_theme` / `available_themes` / `finish` | 主题与出图（theme.py，未改） |
| `viz.matrix(data, ax=None, *, row, col, value, order, percent, min_value=5, totals, diagonal, hot, ...)` | 热力矩阵，返回 `MatrixPlot`（第 12 节） |
| `viz.heatmatrix.suppress_cells(counts, 5, rows=, cols=)` | 只算哪些格子要藏（含互补抑制），自己做表格时用 |
| `viz.heatmatrix.fmt_pct(v)` | 按规范写百分比：40%、0.4%、0.04% |

---

## 14. 常见问题、升级说明、测试

### 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `ImportError: cannot import name 'C'` | 用了上一轮那个 `viz.zip`（maps 依赖新版 theme） | 换成本次交付的 `viz/` |
| `base()` 之后调 `scale_bar` 出现两个比例尺 | 旧版每调一次画一个 | 现在再调用是替换；或直接 `base(scale=dict(x=..., km=...))` |
| 比例尺出现两个、自定的区界样式没生效 | `base()` 之后又 `plot(ax=ax)`，底图画了两遍 | 二选一，见 4.4 节；现在会警告 |
| 地图一片深灰 | 填色的值全一样 | 填真实数值，或不给 values |
| 地图偏在图的一边（左边一大块空白） | 旧版 ax 缩到地图大小，裁白边时左边被标题撑住、右边没有 | 现在默认居中；仍偏的话检查是不是 `frame(fill=False)` |
| 名字太长，标注挤 | — | 用别名：`Regions(..., alias={...})` 或 `label(..., alias={...})` |
| 没数据时内边界看不见 | 内边界默认白线，旧版底下没有底色 | 现在 `base()` 自带浅灰底色；或 `borders=dict(color="#C4CAD3")` |
| `geo.plot(texts=True)` 没出标注 | 旧版 texts=True 只从 values 取 | 现在没有 values 会写全部区名 |
| 比例尺或指北针压在区域上 | 区域贴着外框四角（商圈常见） | `plot(..., margin=0.08, scale=dict(x=0.55))`，或 `scale_bar(ax, x=...)` |
| 换主题后地图颜色没变 | 地图颜色已经和主题独立 | 用 `viz.maps.colors.set(...)` |
| 地图颜色改了没生效 | 图在 `set` 之前就画了 | 先 `set` 再画 |
| 汉字显示成方框 | 没装 Noto Serif CJK SC | 装字体，或主题文件里改 `font.family` |
| 单独调 `fill` 后区与区之间没有分界线 | `fill` 只填色 | 补 `geo.borders(ax)` |
| `freeze()` 坐标和最终图不一致 | 版面还没定 | 先 `finish` 或显示一次再 `freeze` |
| 警告"终点不在对应的区域里" | 套了别的底图的参数包 | 重新自动排一版再 `freeze` |
| 区名相关警告 | 名字和边界数据不一致（如少了"商圈"两字） | 按警告里的名字改 |
| 内边界上零星黑点 | 相邻区顶点错位约 165 米以上 | 用拓扑一致的边界数据 |
| 六边形不是正的、两张图格子大小不一样 | 旧写法按"横向 N 格"定格子 | `hexbin(ax, df, 500)` 按米给格宽 |
| 郊区的热力格子大片消失 | 先按基站滤掉不足 5 人的站 | `how="nunique"` 按格判断门槛；`small="gray"` 看哪些格子不够 |
| 放大框和右图之间的连接线只露出一小段 | `ConnectionPatch` 的 `zorder=0` 排在 axes 前面画，被白底盖住 | 不画线；要画用 `zoom(..., connect=True)` |
| 放大框压在深色格子上看不见 | 框和热力同色 | `zoom` 画的框自带白边 |
| 流向图中心一团线 | 小区挤在一起、条数太多 | `top` 调小，或先放大到城区再画；全部关系用热力矩阵 |
| 小多图里没有数字 | `text=True` 时放不下的不写 | `height` 调大，或只看颜色和蓝框 |

### 和上一轮交付相比的变化

- 本轮（maps v2.7.0）：新增热力矩阵 `viz.matrix`（`heatmatrix.py`）；`fill` / `text` / `label` / `plot` / `facets` 新增 `min_value` 小样本抑制，默认关闭，原来的图不受影响；地图颜色新增 `small_hatch`。
- 上一轮（maps v2.6.0）：新增 `layers.py` 和五个数据层 `hexbin` / `bubbles` / `flows` / `facets` / `locator`，模块级 `zoom` / `circle` / `colorbar` / `hexgrid`；地图颜色新增 `heat_low / heat_mid / heat_high / small`。原有接口、默认样式一个都没改，原 45 项测试照常通过。

更早几轮：


- `scale_bar` / `north_arrow` 再调用是替换（挪位置），不叠加；`base(scale=dict(km=10))` 可以直接写长度。
- 同一个 ax 画两遍底图（`base` 之后又 `plot`）会警告；文档新增 4.4 配色配方。
- 地图默认在 ax 里居中，多出的宽度两侧留白，标注排在留白里；裁白边存图也在正中。比例尺、指北针按地图框定位。
- 新增别名：`Regions(..., alias=)`、`geo.alias`、`label/text(..., alias=)`，只改显示名。
- 底图和数据层分开：新增 `geo.base()`，自带浅灰底色（`colors.land`），没数据时内边界也看得见；`plot()` 改为 `base()` + 数据层。
- 新增区内标注 `geo.text()`；`label(inside="auto")` 放得下写区内、放不下引到外面。
- 空数据不再报错：`fill(None, norm="log")`、`label(ax, {})`、名字全写错，都只是不画（写错会警告）。
- `plot(texts=True)` 没有 values 时写全部区名。
- 视觉变化：`plot()` 出的图多了一层浅灰底色，缺数据的区从"透明"变成"灰色"。不要底色传 `land=False`。
- 更早一轮：地图颜色和 `theme.py` 脱钩；`fill(colors=)`、`points(by=, colors=)`、比例尺位置 `x/y`。

### 从更早的旧版升级

- `fill` 默认不再画白色分区线，单独调 `fill` 的地方补 `geo.borders(ax)`；`plot()` 和 `DistrictMap` 已自动加上。
- 自动排版默认 `span` + 中线分侧；要旧效果传 `spread="fit"`。
- `co.dots` 是按区名取的字典。
- 旧接口 `DistrictMap(districts).figure(cols)` + `.draw(ax, values, texts, hot=...)` 仍能用，内部转给 `Regions`。

### 测试

`test_viz_maps.py`、`test_viz_layers.py`、`test_viz_matrix.py`、`test_viz_privacy.py` 和 `fake_geo.py` 放进 `tests/`，`pytest tests/` 运行，共 110 项（地图 45 项 + 数据层 29 项 + 热力矩阵 27 项 + 区域小样本抑制 9 项）。热力矩阵的测试里最重要的一条是"图上绝不出现小于 5 的人数"：六种组合（有无合计、三种占比、隐藏对角线）逐格检查；另一条是用 40 张随机表检查互补抑制后，每一行、每一列看不见的格子都不是恰好 1 个。新数据层测试覆盖：六边形网格几何（点落进最近的格、正六边形、格宽 = 中心距）、四种口径的计数、门槛、带洞区域的裁剪、色条刻度、气泡面积正比、流向的过滤与报告、往返标注不重叠、小多图共用色阶、放大框在已画底图的 ax 上不被撑满、比例尺跟着挪。本轮在沙箱里用真 pytest 跑，110 项全部通过。

原 45 项覆盖标注不重叠、引线不交叉、多尺度、参数包、分侧排序、样式优先级、内外边界。本轮新增四项：无数据底图（底色在、内边界可见）、数据层缺区与空数据不报错、区内标注与放不下的判断、`inside="auto"` 每个区只出现一次。最新一轮再加三项：宽 ax 里地图居中（裁白边后也居中）、放大后视窗不被拉回、别名只改显示。

### 第一次用真实数据的建议

1. `geo = viz.maps.Regions(areas)`，`print(geo)` 确认区域数和经纬度范围。
2. 先 `geo.base()` 只画底图，确认边界、底色、比例尺位置；再叠 `fill` 和 `label(..., inside="auto", debug=True)` 看标注。
3. 换 `split="balance"` 再出一张对比。
4. 满意后 `freeze()`，按需微调，存进 `viz/layouts/`；之后一律 `layout="包名"`。
