"""
app.py —— 星云商城 · 经营数据看板（主入口）
==========================================

页面结构（对应实验任务 1 的四大模块）：
    ① 数据概览区  —— 6 张核心指标卡 + 目标完成率
    ② 维度统计区  —— 品类排行 / 渠道结构 / 区域对比 / 城市榜 / 时段热力 / 能力雷达
    ③ 趋势分析区  —— 日趋势折线 + 目标仪表盘 + 品类聚焦轮播 + 实时监控
    ④ 明细数据区  —— 可筛选明细表 + CSV / 报告 / PNG 导出

运行：
    streamlit run app.py

交互说明：
    · 点击品类条形图 / 渠道环形图 / 区域柱状图 → 全局下钻，其余图表同步联动
    · 侧边栏可切换亮/暗主题、筛选时间与维度、调整预警阈值、开启实时模式
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from config import (
    APP_ICON, APP_SUBTITLE, APP_TITLE, DEFAULT_THRESHOLDS,
    CATEGORIES, CHANNELS, CHANNEL_COLORS, REGIONS, SEGMENTS,
)
from src import charts
from src.alerts import check_alerts
from src.components import alert_stack, drill_chip, kpi_cards, page_header, quality_lines, ranking, section
from src.format import money
from src.loader import date_bounds, load_orders
from src.metrics import (
    category_summary, channel_summary, city_ranking, daily_trend, kpi_cards as build_cards,
    kpi_snapshot, region_radar, target_progress, top_products, weekly_pattern,
)
from src.report import build_html_report, export_png, to_csv_bytes
from src.theme import inject_theme

# ================================================================ 页面配置
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="auto",   # auto：桌面展开、手机自动收起
)

SS = st.session_state
SS.setdefault("theme_mode", "亮色")
SS.setdefault("drill", None)          # {"dim": "category", "val": "数码家电"}
SS.setdefault("ignore_sig", "")
SS.setdefault("carousel_idx", 0)

theme_key = "dark" if SS["theme_mode"] == "暗色" else "light"
T = inject_theme(theme_key)

# ================================================================ 数据
try:
    df_all, quality = load_orders()
except FileNotFoundError as exc:  # 友好提示，而不是一屏红字
    st.error(str(exc))
    st.stop()

d_min, d_max = date_bounds(df_all)

# ================================================================ 侧边栏
with st.sidebar:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:10px;padding:2px 0 12px;">
          <div style="width:34px;height:34px;border-radius:10px;display:grid;place-items:center;
                      background:linear-gradient(135deg,#2563EB,#60A5FA);font-size:17px;">📊</div>
          <div>
            <div style="font-size:.95rem;font-weight:700;">{APP_TITLE}</div>
            <div style="font-size:.68rem;color:{T['muted']};letter-spacing:.08em;">CONTROL PANEL</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 主题切换必须走 on_change 回调：回调在整页重跑之前执行，
    # 这样页面顶部读到的 theme_mode 已经是新值，不会出现"点了暗色但页面还是亮的"延迟。
    def _sync_theme() -> None:
        SS["theme_mode"] = SS["theme_radio"]

    SS.setdefault("theme_radio", SS["theme_mode"])
    st.radio("外观主题", ["亮色", "暗色"], horizontal=True, key="theme_radio",
             on_change=_sync_theme, help="切换后图表、卡片、表格配色同步更新")

    st.markdown("---")
    st.caption("① 时间范围")
    default_start = max(d_min, d_max - timedelta(days=89))   # 默认看最近 90 天
    picked = st.date_input(
        "统计区间", value=(default_start, d_max), min_value=d_min, max_value=d_max,
        format="YYYY-MM-DD", label_visibility="collapsed",
    )
    if isinstance(picked, (tuple, list)) and len(picked) == 2:
        d0, d1 = picked
    else:  # 用户只点了一个端点
        d0, d1 = d_min, d_max

    st.caption("② 维度筛选")
    sel_region = st.multiselect("区域", REGIONS, default=[], placeholder="全部区域")
    sel_cat = st.multiselect("品类", CATEGORIES, default=[], placeholder="全部品类")
    sel_ch = st.multiselect("渠道", CHANNELS, default=[], placeholder="全部渠道")
    sel_seg = st.radio("客群", ["全部"] + SEGMENTS, horizontal=True, index=0)

    st.markdown("---")
    st.caption("③ 实时监控")
    live_on = st.toggle("开启实时数据流", value=False, help="模拟秒级刷新，观察实时大屏效果")
    live_interval = st.slider("刷新间隔（秒）", 2, 10, 3, disabled=not live_on)

    with st.expander("④ 预警阈值"):
        th = {
            "gmv_progress": st.slider("目标完成率下限 %", 50.0, 110.0, DEFAULT_THRESHOLDS["gmv_progress"], 1.0),
            "gross_margin": st.slider("毛利率下限 %", 10.0, 50.0, DEFAULT_THRESHOLDS["gross_margin"], 1.0),
            "return_rate": st.slider("退货率上限 %", 1.0, 12.0, DEFAULT_THRESHOLDS["return_rate"], 0.5),
            "aov": st.slider("客单价下限 元", 200.0, 1200.0, DEFAULT_THRESHOLDS["aov"], 10.0),
        }

    with st.expander("⑤ 数据质量"):
        quality_lines(quality)
        st.caption("清洗流水线 8 个步骤的明细见「明细数据区 → 数据质量报告」")

    st.markdown("---")
    st.caption("数据说明：全部为程序生成的模拟数据，不含真实用户信息")

# ================================================================ 过滤
mask = (df_all["date"] >= pd.Timestamp(d0)) & (df_all["date"] <= pd.Timestamp(d1))
if sel_region:
    mask &= df_all["region"].isin(sel_region)
if sel_cat:
    mask &= df_all["category"].isin(sel_cat)
if sel_ch:
    mask &= df_all["channel"].isin(sel_ch)
if sel_seg != "全部":
    mask &= df_all["segment"].eq(sel_seg)

df = df_all[mask].copy()

if df.empty:
    st.warning("当前筛选条件下没有数据，请放宽时间范围或维度条件。")
    st.stop()

# 上一周期（等长），用于计算环比
span = (pd.Timestamp(d1) - pd.Timestamp(d0)).days + 1
prev_mask = (
    (df_all["date"] >= pd.Timestamp(d0) - timedelta(days=span))
    & (df_all["date"] < pd.Timestamp(d0))
)
if sel_region:
    prev_mask &= df_all["region"].isin(sel_region)
if sel_cat:
    prev_mask &= df_all["category"].isin(sel_cat)
if sel_ch:
    prev_mask &= df_all["channel"].isin(sel_ch)
if sel_seg != "全部":
    prev_mask &= df_all["segment"].eq(sel_seg)
df_prev = df_all[prev_mask]

# 下钻视图：维度图用全量 df（避免点一下图就塌成一根柱），其余图表用 df_view
drill = SS["drill"]
df_view, df_prev_view = df, df_prev
if drill:
    same = df[drill["dim"]] == drill["val"]
    if same.any():
        df_view = df[same]
        df_prev_view = df_prev[df_prev[drill["dim"]] == drill["val"]]
    else:
        SS["drill"], drill = None, None

if not df_view["is_completed"].any():
    st.warning("当前筛选条件下没有「已完成」订单，无法统计指标。")
    st.stop()

# ================================================================ 指标
kpi = kpi_snapshot(df_view)
cards = build_cards(df_view, df_prev_view)
progress, actual_gmv, target_gmv = target_progress(df_view)

# 交叉过滤原则：一张图不被"自己这一维"的下钻过滤，否则点一下就会塌成一根柱。
# 例如下钻品类时，品类榜仍展示全量并高亮选中项，而渠道/区域图则跟着品类过滤。
def cross(dim: str) -> pd.DataFrame:
    if drill and drill["dim"] != dim:
        return df[df[drill["dim"]] == drill["val"]]
    return df


cat_df = category_summary(cross("category"))
ch_df = channel_summary(cross("channel"))
radar_df = region_radar(df_view)
city_df = city_ranking(df_view, top=10)
trend_df = daily_trend(df_view)
weekly = weekly_pattern(df_view)
prod_df = top_products(df_view, top=8)

region_source = cross("region")
region_df = (
    region_source[region_source["is_completed"]]
    .groupby("region")
    .agg(gmv=("amount", "sum"), margin=("margin", "mean"))
    .reset_index()
    .sort_values("gmv", ascending=False)
)
region_df["margin"] = region_df["margin"] * 100

alerts = check_alerts(kpi, progress, th, cat_df)

# ---------------------------------------------------------------- 轮播组件（提前定义，供 03 区调用）
def render_carousel(cat_source: pd.DataFrame, tokens: dict, interval: str = "6s") -> None:
    """品类聚焦轮播：每 6 秒自动切换一个品类卡片（st.fragment 局部刷新，不重跑全页）。"""

    @st.fragment(run_every=interval)
    def _inner():
        top = cat_source.head(4)
        if top.empty:
            return
        idx = SS.get("carousel_idx", 0) % len(top)
        row = top.iloc[idx]
        SS["carousel_idx"] = idx + 1
        share_w = min(float(row["share"]) / max(float(top["share"].max()), 0.01) * 100, 100)
        st.markdown(
            f"""
            <div style="background:{tokens['panel']};border:1px solid {tokens['border']};border-radius:16px;
                        padding:14px 16px;box-shadow:{tokens['shadow']};min-height:104px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:.72rem;color:{tokens['muted']};letter-spacing:.08em;">品类聚焦 · 自动轮播</span>
                <span style="font-size:.68rem;color:{tokens['muted']};">{idx + 1}/{len(top)}</span>
              </div>
              <div style="display:flex;align-items:baseline;gap:10px;margin-top:8px;">
                <b style="font-size:1.05rem;">{row['category']}</b>
                <span style="font-size:1.28rem;font-weight:700;color:#2563EB;">{money(row['gmv'])}</span>
                <span style="font-size:.75rem;color:{tokens['muted']};">占比 {row['share']:.1f}%</span>
              </div>
              <div style="height:6px;border-radius:99px;background:{tokens['grid']};margin-top:10px;overflow:hidden;">
                <div style="height:100%;width:{share_w:.0f}%;border-radius:99px;
                            background:linear-gradient(90deg,#60A5FA,#2563EB);transition:width .6s ease;"></div>
              </div>
              <div style="font-size:.74rem;color:{tokens['muted']};margin-top:7px;">
                订单 {int(row['orders']):,} 单 ｜ 客单价 ¥{row['aov']:.0f} ｜ 毛利率 {row['margin']:.1f}%
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _inner()


# ================================================================ 页头
period_text = f"{d0:%Y-%m-%d} ~ {d1:%Y-%m-%d}（{span} 天）"
page_header(
    APP_TITLE,
    APP_SUBTITLE,
    chips=[
        ("数据更新 ", f"{df_view['order_time'].max():%m-%d %H:%M}"),
        ("有效订单 ", f"{len(df_view):,}"),
        ("统计周期 ", f"{span} 天"),
        ("状态 ", "实时运行" if live_on else "静态快照"),
    ],
    live=live_on,
)

# 预警条
alert_stack(alerts)

# 下钻提示
if drill:
    c_l, c_r = st.columns([4, 1])
    with c_l:
        drill_chip(f"{drill['dim']} = {drill['val']}（其余图表已联动过滤）")
    with c_r:
        if st.button("清除下钻", width="stretch"):
            SS["drill"] = None
            SS["ignore_sig"] = SS.get("last_sig", "")
            st.rerun()


# ================================================================ ① 数据概览
section("01", "数据概览", "6 项核心指标 · 环比上一等长周期 · 数字滚动动画")
kpi_cards(cards, T)

# ================================================================ ② 维度统计
section("02", "维度统计", "点击图表可下钻，其余图表同步联动")

col_a, col_b = st.columns([1.28, 1], gap="medium")
with col_a:
    ev_cat = st.plotly_chart(
        charts.category_bar(cat_df, T, selected=drill["val"] if drill and drill["dim"] == "category" else None),
        theme=None, config=charts.PLOT_CONFIG, key="cat_bar", on_select="rerun", selection_mode="points",
    )
with col_b:
    ev_ch = st.plotly_chart(
        charts.donut_chart(ch_df, T, "channel", colors=CHANNEL_COLORS, title="渠道销售额结构",
                           highlight=drill["val"] if drill and drill["dim"] == "channel" else None),
        theme=None, config=charts.PLOT_CONFIG, key="ch_donut", on_select="rerun", selection_mode="points",
    )


def _clicked(ev) -> str | None:
    """从 plotly 选中事件里取出被点击的分类名（不同图表字段不同，做一次兜底）。"""
    try:
        pts = (ev or {}).get("selection", {}).get("points", [])
        if not pts:
            return None
        p = pts[0]
        for k in ("y", "x", "label"):
            if isinstance(p.get(k), str) and p[k]:
                return p[k]
        cd = p.get("customdata")
        if isinstance(cd, (list, tuple)) and cd:
            return str(cd[0])
    except Exception:
        return None
    return None


def _apply_drill(dim: str, val: str | None) -> None:
    """记录下钻状态；用 ignore_sig 防止"清除后又被旧选中状态拉回去"。"""
    if not val:
        return
    sig = f"{dim}:{val}"
    SS["last_sig"] = sig
    if sig == SS["ignore_sig"]:
        return
    if SS["drill"] != {"dim": dim, "val": val}:
        SS["drill"] = {"dim": dim, "val": val}
        st.rerun()


_apply_drill("category", _clicked(ev_cat))
_apply_drill("channel", _clicked(ev_ch))

col_c, col_d = st.columns([1.28, 1], gap="medium")
with col_c:
    ev_reg = st.plotly_chart(
        charts.region_bar_line(region_df, T), theme=None, config=charts.PLOT_CONFIG,
        key="region_bar", on_select="rerun", selection_mode="points",
    )
with col_d:
    with st.container(border=True):
        st.markdown(
            f'<div style="font-size:.9rem;font-weight:650;margin-bottom:10px;">'
            f'城市销售额 TOP10 <span style="font-size:.72rem;color:{T["muted"]};font-weight:400;">'
            f"· 点击品类图可继续下钻</span></div>",
            unsafe_allow_html=True,
        )
        ranking(city_df, "city", "gmv", sub_col="region")

_apply_drill("region", _clicked(ev_reg))

col_e, col_f = st.columns([1.55, 1], gap="medium")
with col_e:
    st.plotly_chart(charts.weekday_hour_heatmap(weekly, T), theme=None, config=charts.PLOT_CONFIG, key="heat")
with col_f:
    hi_region = drill["val"] if drill and drill["dim"] == "region" else None
    st.plotly_chart(charts.radar_chart(radar_df, T, highlight=hi_region), theme=None,
                    config=charts.PLOT_CONFIG, key="radar")

# ================================================================ ③ 趋势分析
section("03", "趋势分析", "日粒度趋势 · 目标达成 · 品类聚焦轮播")

col_g, col_h = st.columns([1.95, 1], gap="medium")
with col_g:
    st.plotly_chart(charts.trend_chart(trend_df, T, focus=drill["val"] if drill else None),
                    theme=None, config=charts.PLOT_CONFIG, key="trend")
with col_h:
    st.plotly_chart(charts.gauge_chart(progress, target_gmv, actual_gmv, T),
                    theme=None, config=charts.PLOT_CONFIG, key="gauge")
    st.write("")
    render_carousel(cat_df, T)



if live_on:
    # ---------------- 扩展 1：实时数据流 ----------------
    section("03+", "实时监控", f"每 {live_interval} 秒刷新 · 模拟增量订单流")
    base_aov = max(kpi["aov"], 1.0)          # 用当前客单价当作模拟下单的金额中枢

    def render_live(interval: int, tokens: dict, aov: float) -> None:
        @st.fragment(run_every=f"{interval}s")
        def _live():
            import random
            from datetime import datetime as _dt

            buf = SS.setdefault("live_buf", {"labels": [], "values": [], "total": 0.0, "last": 0.0})

            # 一个刷新周期内新增若干笔订单，单笔金额围绕客单价波动
            n = random.randint(6, 14)
            amounts = [min(max(random.gauss(aov, aov * 0.35), aov * 0.15), aov * 4) for _ in range(n)]
            batch = sum(amounts)

            buf["labels"].append(_dt.now().strftime("%H:%M:%S"))
            buf["values"].append(round(batch, 2))
            buf["total"] += batch
            buf["last"] = amounts[-1]
            for k in ("labels", "values"):
                if len(buf[k]) > 40:
                    buf[k] = buf[k][-40:]

            c1, c2, c3 = st.columns([1, 1, 1.9])
            c1.metric("实时累计 GMV", money(buf["total"]), f"+{n} 单/周期")
            c2.metric("最新一单", f"¥{buf['last']:,.0f}", "模拟成交")
            with c3:
                st.plotly_chart(
                    charts.live_line(buf["values"], buf["labels"], tokens),
                    theme=None, config=charts.PLOT_CONFIG, key="live_line",
                )

        _live()

    render_live(live_interval, T, base_aov)

# ================================================================ ④ 明细数据
section("04", "明细数据", "按筛选条件实时过滤 · 支持导出")

with st.container(border=True):
    view = df_view[
        ["order_id", "order_time", "region", "city", "category", "product",
         "channel", "segment", "quantity", "amount", "profit", "order_status"]
    ].copy()
    view["order_time"] = view["order_time"].dt.strftime("%Y-%m-%d %H:%M")
    view = view.rename(
        columns={
            "order_id": "订单号", "order_time": "下单时间", "region": "区域", "city": "城市",
            "category": "品类", "product": "商品", "channel": "渠道", "segment": "客群",
            "quantity": "数量", "amount": "金额(元)", "profit": "毛利(元)", "order_status": "状态",
        }
    )

    head_l, head_r = st.columns([2, 1])
    head_l.markdown(
        f'<div style="font-size:.9rem;font-weight:650;">订单明细 <span style="font-size:.72rem;'
        f'color:{T["muted"]};font-weight:400;">共 {len(view):,} 条，展示前 200 条</span></div>',
        unsafe_allow_html=True,
    )
    with head_r:
        st.download_button(
            "⬇ 导出 CSV", to_csv_bytes(view), file_name=f"orders_{d0}_{d1}.csv",
            mime="text/csv", width="stretch",
        )

    st.dataframe(
        view.head(200), width="stretch", height=380, hide_index=True,
        column_config={
            "金额(元)": st.column_config.NumberColumn(format="%.2f"),
            "毛利(元)": st.column_config.NumberColumn(format="%.2f"),
        },
    )

with st.expander("📦 爆款商品 TOP8"):
    ranking(prod_df, "product", "gmv", sub_col="category")

with st.expander("🧪 数据质量报告（8 步清洗流水线）"):
    st.dataframe(
        pd.DataFrame(quality["steps"]).rename(
            columns={"step": "步骤", "action": "处理动作", "affected": "影响行数", "note": "说明"}
        ),
        width="stretch", hide_index=True,
    )
    st.caption(
        f"原始 {quality['raw_rows']:,} 行 → 清洗后 {quality['clean_rows']:,} 行，"
        f"留存率 {quality['keep_ratio']}%；剔除记录不会进入任何图表。"
    )

with st.expander("📤 导出：一键分析报告 / 图表 PNG"):
    ec1, ec2 = st.columns(2)
    with ec1:
        if st.button("生成 HTML 分析报告", width="stretch"):
            figs = {
                "trend": charts.trend_chart(trend_df, T),
                "category": charts.category_bar(cat_df, T),
                "channel": charts.donut_chart(ch_df, T, "channel", title="渠道结构"),
                "region": charts.region_bar_line(region_df, T),
            }
            html = build_html_report(
                cards=cards, progress=progress, alerts=alerts, cat_df=cat_df,
                region_df=region_df, ch_df=ch_df, figs=figs, report=quality,
                period_text=period_text, rows=len(df_view),
            )
            SS["report_html"] = html
        if SS.get("report_html"):
            st.download_button(
                "⬇ 下载报告 HTML", SS["report_html"].encode("utf-8"),
                file_name="星云商城_经营分析报告.html", mime="text/html", width="stretch",
            )
    with ec2:
        if st.button("生成趋势图 PNG", width="stretch"):
            png = export_png(charts.trend_chart(trend_df, T))
            if png:
                SS["png_bytes"] = png
            else:
                st.info("导出 PNG 需要额外安装 `pip install kaleido`；未安装时可用下方的「图表 HTML」。")
        if SS.get("png_bytes"):
            st.download_button("⬇ 下载 PNG", SS["png_bytes"], file_name="trend.png",
                               mime="image/png", width="stretch")
        if st.button("导出趋势图 HTML（可交互）", width="stretch"):
            SS["chart_html"] = charts.trend_chart(trend_df, T).to_html(
                include_plotlyjs="cdn", full_html=True, config=charts.PLOT_CONFIG
            )
        if SS.get("chart_html"):
            st.download_button("⬇ 下载图表 HTML", SS["chart_html"].encode("utf-8"),
                               file_name="趋势图.html", mime="text/html", width="stretch")

st.markdown(
    f'<div style="margin-top:26px;padding-top:14px;border-top:1px solid {T["border"]};'
    f'font-size:.72rem;color:{T["muted"]};display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;">'
    f"<span>数据口径：GMV / 订单量 / 客单价 / 毛利率仅统计「已完成」订单；退货率 = 退货单 / 全部订单</span>"
    f"<span>Streamlit + Pandas + Plotly · 实验 2 数据看板</span></div>",
    unsafe_allow_html=True,
)
