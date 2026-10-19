# 星云商城 · 经营数据看板（Streamlit + Pandas + Plotly）

> 实验 2《数据看板的设计与实现》完整工程。
> 覆盖：基础任务 1~5 ｜ 进阶任务 1~3 ｜ 扩展任务 1~5。

![看板概览](assets/dashboard_light.png)

---

## 1. 快速开始

```bash
# 1) 安装依赖（建议虚拟环境）
pip install -r requirements.txt

# 2) 生成模拟数据（1.5 万行，含 6 类"脏数据"）
python scripts/generate_data.py

# 3) 离线跑一遍清洗流水线，产出 CSV / XLSX / 质量报告
python scripts/prepare_data.py

# 4) 启动看板
streamlit run app.py
```

浏览器打开 <http://localhost:8501> 即可。

---

## 2. 目录结构

```
ecom-dashboard/
├── app.py                    # 主入口：页面编排 + 交互逻辑（唯一需要"读"的文件）
├── config.py                 # 全局配置：路径 / 配色 / 主题 token / 阈值 / 指标元信息
├── requirements.txt
├── README.md
│
├── scripts/                  # 离线脚本（一次性执行，不参与页面运行）
│   ├── generate_data.py      #   ① 模拟订单数据生成（可复现，seed=42）
│   └── prepare_data.py       #   ② 清洗 → orders_clean.csv / orders.xlsx / quality_report.json
│
├── data/                     # 数据层
│   ├── orders_raw.csv        #   原始数据（含缺失/重复/负数/异常值/非法时间）
│   ├── orders_clean.csv      #   清洗后明细（utf-8-sig，Excel 可直接打开）
│   ├── orders.xlsx           #   清洗后明细 + 数据质量 + 品类汇总 三个 Sheet
│   └── quality_report.json   #   8 步清洗日志
│
├── src/                      # 应用层（每个模块只干一件事）
│   ├── preprocess.py         #   清洗流水线 + 特征衍生
│   ├── loader.py             #   数据加载（st.cache_data 缓存）
│   ├── metrics.py            #   指标计算（口径集中在这里）
│   ├── charts.py             #   Plotly 图表工厂（一类图一个函数）
│   ├── components.py         #   自研 HTML 组件（指标卡 / 排行 / 预警 / 页头）
│   ├── theme.py              #   亮暗双主题 CSS（约 250 行）
│   ├── alerts.py             #   阈值预警引擎
│   ├── report.py             #   一键导出 HTML 报告 / CSV / PNG
│   └── format.py             #   金额、百分比、环比格式化
│
├── .streamlit/config.toml     # 主题主色、端口等
└── assets/                    # 截图（博客 / 实验报告用）
```

**分层原则**：`config → data → metrics → charts/components → app`，上层依赖下层，下层不感知上层。
改配色只动 `config.py`，改口径只动 `metrics.py`，改样式只动 `theme.py`。

---

## 3. 功能与实验任务的对应关系

| 实验任务 | 实现位置 | 说明 |
|---|---|---|
| 基础 1 需求分析与版面设计 | `app.py` 四大分区 + `theme.py` | 概览区 / 维度区 / 趋势区 / 明细区，主色 `#2563EB` |
| 基础 2 数据准备与预处理 | `scripts/generate_data.py`、`src/preprocess.py` | 8 步清洗，产出 CSV + XLSX + 质量报告 |
| 基础 3 基础图表 | `src/charts.py` | 指标卡、条形图、折线图、环形图（不止 3 种） |
| 基础 4 静态看板整合 | `app.py`、`src/theme.py` | 栅格化布局、卡片化、统一间距与字体层级 |
| 基础 5 验证与总结 | 本 README + 博客 | 数据准确性、页面美观度、问题与解决 |
| 进阶 1 动态视觉 | `components.kpi_cards`、`render_carousel` | 数字滚动、渐入动画、环形抽离、自适应断点 |
| 进阶 2 联动与筛选 | `app.py` 的 `cross()` + `on_select="rerun"` | 时间/区域/品类/渠道/客群筛选 + 图表点击下钻 |
| 进阶 3 多维分析 | `charts.py` | 排行榜、热力图、雷达图、仪表盘 |
| 扩展 1 实时看板 | `render_live()` + `st.fragment(run_every=…)` | 秒级刷新的增量订单流 |
| 扩展 2 预警监控 | `src/alerts.py` + 侧边栏阈值 | 变色、闪烁、顶部告警条 |
| 扩展 3 大屏/移动适配 | `theme.py` 断点 + `initial_sidebar_state="auto"` | 1680 大屏 / 笔记本 / 430 手机三档 |
| 扩展 4 分析报告输出 | `src/report.py` | HTML 报告（图表内嵌）、CSV、图表 HTML/PNG |
| 扩展 5 个性化 | 侧边栏主题开关、下钻、排行、阈值 | 亮/暗一键切换 |

---

## 4. 数据字典（清洗后 17 个原始字段 + 11 个衍生字段）

| 字段 | 类型 | 说明 |
|---|---|---|
| `order_id` | str | 订单号（主键） |
| `order_time` | datetime | 下单时间 |
| `customer_id` | str | 客户 ID（用于去重客户数、复购分析） |
| `region` / `city` | str | 区域 / 城市 |
| `category` / `product` | str | 品类 / 商品 |
| `channel` / `payment` | str | 渠道 / 支付方式 |
| `segment` | str | 新客 / 老客 |
| `quantity` / `unit_price` / `discount` | num | 数量 / 单价 / 折扣 |
| `amount` / `cost` / `profit` | num | 成交额 / 成本 / 毛利 |
| `order_status` | str | 已完成 / 已退货 / 已取消 |
| `review_score` | int | 评价分 1~5 |
| 衍生 | | `date` `month` `week` `weekday` `hour` `time_slot` `margin` `is_completed` `is_returned` |

**指标口径**（写死在 `metrics.py` 顶部注释里）：
- 销售额 / 订单量 / 客单价 / 毛利率 / 客户数：只统计「已完成」订单
- 退货率 = 退货订单数 ÷ 全部订单数
- 环比 = 与「等长的上一周期」对比

---

## 5. 交互一览

| 操作 | 效果 |
|---|---|
| 侧边栏时间 / 区域 / 品类 / 渠道 / 客群 | 全页指标与图表同步过滤 |
| 点击品类条形图 / 渠道环形图 / 区域柱状图 | 全局下钻，其余图表联动；顶部出现「当前下钻」胶囊，可一键清除 |
| 侧边栏「开启实时数据流」 | 每 N 秒刷新一次实时增量曲线与实时 GMV |
| 侧边栏「外观主题」 | 亮色 / 暗色即时切换（图表、卡片、控件同步） |
| 「④ 预警阈值」 | 拖动即改判定线，告警条实时增删 |
| 明细区「导出 CSV / 生成报告 / PNG」 | 交付物导出 |

---

## 6. 一个设计细节：为什么点图不会"塌成一根柱"

下钻时如果所有图表都用过滤后的数据重算，你点中的那张图会只剩一个分类，失去了对比意义。
所以 `app.py` 里定义了一个交叉过滤函数：

```python
def cross(dim: str) -> pd.DataFrame:
    """一张图不被"自己这一维"的下钻过滤。"""
    if drill and drill["dim"] != dim:
        return df[df[drill["dim"]] == drill["val"]]
    return df
```

点「数码家电」时：品类榜仍展示 6 个品类并高亮选中项，而渠道环形图、区域柱线图、趋势图、明细表全部切换到该品类。
这就是 BI 工具里常说的「highlight 与 filter 分离」。

---

## 7. 常见问题

**Q：启动报 `未找到数据文件`？**
A：先执行 `python scripts/generate_data.py`。

**Q：PNG 导出没反应？**
A：`pip install kaleido`；不装也能用「导出趋势图 HTML」。

**Q：换成自己的数据？**
A：把 CSV 放到 `data/orders_raw.csv`，保证 `config.py` 里 `REQUIRED_COLUMNS` 的字段名一致即可，清洗与图表无需改动。

---

## 8. 截图

| 亮色 | 暗色 |
|---|---|
| ![](assets/dashboard_light.png) | ![](assets/dashboard_dark.png) |

| 下钻联动 | 移动端 |
|---|---|
| ![](assets/dashboard_drill.png) | ![](assets/dashboard_mobile.png) |

| 趋势分析区 | 实时数据流 |
|---|---|
| ![](assets/dashboard_trend.png) | ![](assets/dashboard_live.png) |
