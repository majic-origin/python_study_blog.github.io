"""
src/charts.py —— Plotly 图表工厂
================================
一类图一个函数，只接收"已经算好的 DataFrame + 主题 token"，
不在这里做任何数据计算 —— 图表层和数据层彻底解耦。

设计要点：
  · 统一模板：apply_theme() 负责背景透明、网格、字体、hover、图例位置；
  · 统一配色：品类/渠道用固定色板（见 config.py），跨图颜色一致；
  · 统一交互：hover 提示写清楚"是什么、多少、占比多少"。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from config import BRAND, CATEGORY_COLORS, CHANNEL_COLORS, SEQUENTIAL_SCALE
from src.format import money

FONT_FAMILY = (
    '"Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", '
    '"Source Han Sans SC", -apple-system, "Segoe UI", sans-serif'
)

PLOT_CONFIG = {
    "displayModeBar": False,      # 隐藏工具栏，保持看板干净
    "scrollZoom": False,
    "displaylogo": False,
}


# ---------------------------------------------------------------- 统一主题
def apply_theme(fig: go.Figure, t: dict, height: int = 320, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        template=t["plot_template"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=12, t=50, b=54 if legend else 10),
        font=dict(family=FONT_FAMILY, color=t["text"], size=12),
        hoverlabel=dict(bgcolor=t["panel"], bordercolor=t["border"], font=dict(color=t["text"], size=12)),
        showlegend=legend,
        # 图例放底部：标题在左上是"标题区"，底部横排图例不会和标题抢位置
        legend=dict(orientation="h", yanchor="top", y=-0.14, xanchor="left", x=0, font=dict(size=11)),
        hovermode="x unified",
        transition=dict(duration=350, easing="cubic-in-out"),   # 数据变化时平滑过渡
    )
    axis = dict(
        gridcolor=t["grid"],
        zeroline=False,
        linecolor=t["border"],
        tickfont=dict(size=11, color=t["muted"]),
        title=dict(font=dict(size=11, color=t["muted"])),
    )
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def _title(text: str, t: dict, size: int = 14) -> dict:
    # yref="paper" + yanchor="bottom"：标题底边贴在绘图区顶部，整体落在上边距里，
    # 不会被 SVG 画布裁掉（container 坐标系下部分版本会把标题顶到画布外）
    return {"text": text, "font": dict(size=size, color=t["text"]),
            "x": 0.012, "xanchor": "left", "y": 1.0, "yref": "paper", "yanchor": "bottom"}



# ---------------------------------------------------------------- 坐标轴中文单位
def _wan(v: float) -> str:
    """把 2000000 这类大数写成「200万」，符合中文看板阅读习惯。"""
    if v >= 1e8:
        return f"{v / 1e8:g}亿"
    if v >= 1e4:
        return f"{v / 1e4:g}万"
    return f"{v:g}"


def yaxis_wan(fig: go.Figure, vmax: float, nticks: int = 5) -> go.Figure:
    """按 1/2/2.5/5 ×10^n 取整刻度，并把刻度文本缩写成万/亿。"""
    import math

    raw = max(vmax, 1) / nticks
    mag = 10 ** math.floor(math.log10(raw))
    for k in (1, 2, 2.5, 5, 10):
        if raw / mag <= k:
            step = k * mag
            break
    else:
        step = 10 * mag
    ticks = [i * step for i in range(int(vmax / step) + 2)]
    fig.update_yaxes(tickvals=ticks, ticktext=[_wan(t) for t in ticks])
    return fig


# ---------------------------------------------------------------- 趋势折线
def trend_chart(trend: pd.DataFrame, t: dict, focus: str | None = None, metric: str = "gmv") -> go.Figure:
    """销售额日趋势 + 7 日移动平均。双击/悬浮可读数，点击联动由页面层处理。"""
    col, ma_col, label = ("gmv", "gmv_ma7", "销售额") if metric == "gmv" else ("orders", "orders_ma7", "订单量")
    color = BRAND["primary"]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend["date"], y=trend[col], name=f"日{label}", mode="lines",
            line=dict(color=color, width=1.4),
            fill="tozeroy", fillcolor="rgba(37,99,235,.12)",
            hovertemplate=f"%{{x|%m-%d}}  {label} %{{y:,.0f}}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend["date"], y=trend[ma_col], name="7 日均线", mode="lines",
            line=dict(color=BRAND["accent"], width=2.6, shape="spline"),
            hovertemplate=f"7日均 %{{y:,.0f}}<extra></extra>",
        )
    )
    # 标注区间最高点，让"峰值在哪"一眼可见
    if len(trend):
        peak = trend.loc[trend[col].idxmax()]
        fig.add_trace(
            go.Scatter(
                x=[peak["date"]], y=[peak[col]], mode="markers+text", name="峰值",
                marker=dict(size=9, color=BRAND["danger"], line=dict(width=2, color=t["panel"])),
                text=[f"峰值 {money(peak[col])}"], textposition="top center",
                textfont=dict(size=10, color=BRAND["danger"]),
                hovertemplate="峰值 %{y:,.0f}<extra></extra>",
            )
        )
    title = f"{label}趋势 · 日粒度" + (f"（已下钻：{focus}）" if focus else "")
    fig.update_layout(title=_title(title, t), bargap=0.2)
    fig.update_xaxes(tickformat="%m-%d", nticks=10)
    apply_theme(fig, t, height=340)
    return yaxis_wan(fig, float(trend[col].max()) * 1.12)


# ---------------------------------------------------------------- 分类柱状
def category_bar(cat: pd.DataFrame, t: dict, selected: str | None = None) -> go.Figure:
    """品类销售额排行（横向条形图：类目名长时横向阅读更自然）。"""
    d = cat.sort_values("gmv")
    colors = [CATEGORY_COLORS.get(c, BRAND["primary"]) for c in d["category"]]
    if selected:
        colors = [c if cat_name == selected else _fade(c) for c, cat_name in zip(colors, d["category"])]

    fig = go.Figure(
        go.Bar(
            x=d["gmv"], y=d["category"], orientation="h",
            marker=dict(color=colors, line=dict(width=0), cornerradius=6),
            text=[f"  {money(v)} · {s:.1f}%" for v, s in zip(d["gmv"], d["share"])],
            textposition="outside", textfont=dict(size=11, color=t["text"]), cliponaxis=False,
            customdata=np.stack([d["category"], d["orders"], d["share"]], axis=-1),
            hovertemplate="<b>%{customdata[0]}</b><br>销售额 %{x:,.0f} 元<br>订单 %{customdata[1]:,} 单<br>占比 %{customdata[2]:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(title=_title("品类销售额排行 · 点击下钻", t), showlegend=False)
    fig.update_xaxes(showgrid=True, visible=False, range=[0, d["gmv"].max() * 1.55])
    fig.update_yaxes(showgrid=False, tickfont=dict(size=12, color=t["text"]))
    fig = apply_theme(fig, t, height=330, legend=False)
    fig.update_layout(hovermode="closest", margin=dict(l=8, r=110, t=50, b=10))
    return fig


def _fade(hex_color: str, alpha: str = "40") -> str:
    """把十六进制色变成半透明，用于"未选中项降噪"。"""
    return f"{hex_color}{alpha}"


# ---------------------------------------------------------------- 环形图
def donut_chart(
    df: pd.DataFrame, t: dict, name_col: str, value_col: str = "gmv",
    title: str = "渠道结构", colors: dict | None = None, center_label: str = "总销售额",
    highlight: str | None = None,
) -> go.Figure:
    palette = colors or CHANNEL_COLORS
    # 被选中的扇区"抽出来"一点，其余保持原位，形成选择反馈
    pulls = [0.06 if (highlight and str(k) == str(highlight)) else 0.0 for k in df[name_col]]
    fig = go.Figure(
        go.Pie(
            labels=df[name_col], values=df[value_col], hole=0.62, sort=False,
            marker=dict(colors=[palette.get(k, BRAND["primary"]) for k in df[name_col]],
                        line=dict(color=t["panel"], width=2)),
            textinfo="percent", textposition="inside",
            insidetextfont=dict(size=11, color="#FFFFFF"),
            hovertemplate="<b>%{label}</b><br>销售额 %{value:,.0f} 元<br>占比 %{percent}<extra></extra>",
            pull=pulls,
        )
    )
    total = df[value_col].sum()
    fig.add_annotation(
        text=f"<span style='font-size:11px;color:{t['muted']}'>{center_label}</span><br>"
             f"<b style='font-size:17px;color:{t['text']}'>{money(total)}</b>",
        showarrow=False, x=0.5, y=0.5,
    )
    fig.update_layout(title=_title(title, t))
    fig = apply_theme(fig, t, height=330)
    fig.update_layout(hovermode="closest", margin=dict(l=8, r=8, t=50, b=54))
    return fig


# ---------------------------------------------------------------- 热力图
def weekday_hour_heatmap(pivot: pd.DataFrame, t: dict) -> go.Figure:
    """星期 × 时段下单热力：一眼看出"什么时间卖得好"。"""
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=[f"{h}时" for h in pivot.columns],
            y=pivot.index.tolist(),
            colorscale=SEQUENTIAL_SCALE,
            xgap=2, ygap=2,
            colorbar=dict(thickness=8, len=0.8, tickfont=dict(size=10, color=t["muted"]), outlinewidth=0),
            hovertemplate="%{y} %{x}<br>订单 %{z:,.0f} 单<extra></extra>",
        )
    )
    fig.update_layout(title=_title("下单时段热力图 · 周内分布", t))
    fig = apply_theme(fig, t, height=300, legend=False)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, tickvals=[f"{h}时" for h in range(0, 24, 3)])
    return fig


# ---------------------------------------------------------------- 雷达图
def radar_chart(radar: pd.DataFrame, t: dict, highlight: str | None = None) -> go.Figure:
    """区域 5 维能力雷达（0-100 归一化），高亮选中区域、其余淡化。"""
    dims = radar.columns.tolist()
    fig = go.Figure()
    for region in radar.index:
        is_hi = (highlight == region) or (highlight is None and region == radar["销售额"].idxmax())
        fig.add_trace(
            go.Scatterpolar(
                r=radar.loc[region, dims].tolist() + [radar.loc[region, dims[0]]],
                theta=dims + [dims[0]],
                name=region, mode="lines+markers",
                line=dict(width=2.4 if is_hi else 1, color=BRAND["primary"] if is_hi else t["muted"]),
                marker=dict(size=5 if is_hi else 3),
                fill="toself" if is_hi else "none",
                fillcolor="rgba(37,99,235,.16)",
                hovertemplate=f"<b>{region}</b><br>%{{theta}} 得分 %{{r:.0f}}<extra></extra>",
            )
        )
    fig.update_layout(
        title=_title("区域综合能力雷达 · 归一化得分", t),
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], showticklabels=False, gridcolor=t["grid"], linecolor=t["border"]),
            angularaxis=dict(gridcolor=t["grid"], linecolor=t["border"], tickfont=dict(size=11, color=t["muted"])),
        ),
    )
    apply_theme(fig, t, height=392)
    fig.update_layout(hovermode="closest", margin=dict(l=30, r=30, t=46, b=62),
                      polar=dict(radialaxis=dict(range=[0, 100], showticklabels=False,
                                                 gridcolor=t["grid"], linecolor=t["border"]),
                                 angularaxis=dict(gridcolor=t["grid"], linecolor=t["border"],
                                                  tickfont=dict(size=10.5, color=t["muted"]))))
    return fig


# ---------------------------------------------------------------- 仪表盘
def gauge_chart(value: float, target: float, actual: float, t: dict) -> go.Figure:
    """目标完成率仪表盘：<80% 红、80-100% 橙、≥100% 绿。"""
    color = BRAND["success"] if value >= 100 else (BRAND["warning"] if value >= 80 else BRAND["danger"])
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=round(value, 1),
            number=dict(suffix="%", font=dict(size=34, color=t["text"], family=FONT_FAMILY)),
            gauge=dict(
                axis=dict(range=[0, 130], tickwidth=1, tickcolor=t["border"], tickfont=dict(size=10, color=t["muted"])),
                bar=dict(color=color, thickness=0.66),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                steps=[
                    dict(range=[0, 80], color="rgba(239,68,68,.10)"),
                    dict(range=[80, 100], color="rgba(245,158,11,.12)"),
                    dict(range=[100, 130], color="rgba(22,163,74,.12)"),
                ],
                threshold=dict(line=dict(color=BRAND["danger"], width=2), thickness=0.8, value=100),
            ),
        )
    )
    fig.add_annotation(
        text=f"实际 {money(actual)} ｜ 目标 {money(target)}",
        showarrow=False, xref="paper", yref="paper", x=0.5, y=0.02,
        font=dict(size=10.5, color=t["muted"]),
    )
    fig.update_layout(title=_title("销售目标完成率", t), height=272, margin=dict(l=22, r=22, t=46, b=26))
    return apply_theme(fig, t, height=300, legend=False)


# ---------------------------------------------------------------- 实时折线
def live_line(values: list[float], labels: list[str], t: dict) -> go.Figure:
    """实时模式下滚动的"最近 N 个刷新周期 GMV"迷你曲线。"""
    fig = go.Figure(
        go.Scatter(
            x=labels, y=values, mode="lines", line=dict(color=BRAND["info"], width=2.2, shape="spline"),
            fill="tozeroy", fillcolor="rgba(14,165,233,.14)",
            hovertemplate="%{x}<br>GMV %{y:,.0f} 元<extra></extra>",
        )
    )
    fig.update_layout(title=None, showlegend=False)
    fig = apply_theme(fig, t, height=150, legend=False)
    fig.update_layout(margin=dict(l=4, r=4, t=6, b=4), hovermode="closest")
    fig.update_xaxes(showticklabels=False, showgrid=False)
    fig.update_yaxes(showgrid=True, tickfont=dict(size=9))
    return yaxis_wan(fig, max(values) * 1.15, nticks=3)


# ---------------------------------------------------------------- 双轴对比
def region_bar_line(df: pd.DataFrame, t: dict) -> go.Figure:
    """区域销售额（柱）+ 毛利率（折线，右轴）—— 规模与质量一起看。"""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["region"], y=df["gmv"], name="销售额",
            marker=dict(color=BRAND["primary"], cornerradius=6, opacity=0.9),
            hovertemplate="<b>%{x}</b><br>销售额 %{y:,.0f} 元<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["region"], y=df["margin"], name="毛利率", yaxis="y2", mode="lines+markers",
            line=dict(color=BRAND["accent"], width=2.4), marker=dict(size=7),
            hovertemplate="毛利率 %{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title=_title("区域销售额与毛利率", t),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, ticksuffix="%",
                    tickfont=dict(size=11, color=t["muted"]), range=[0, max(df["margin"].max() * 1.6, 40)]),
    )
    apply_theme(fig, t, height=340)
    fig.update_layout(bargap=0.45, hovermode="x unified", margin=dict(l=8, r=54, t=50, b=54))
    yaxis_wan(fig, float(df["gmv"].max()) * 1.15)      # 只对左轴生效后，右轴再单独校准
    top = float(df["margin"].max() * 1.6)
    ticks = [0, top / 2, top]
    fig.update_layout(yaxis2=dict(range=[0, top], tickvals=ticks,
                                  ticktext=[f"{x:.0f}%" for x in ticks], ticksuffix=""))
    return fig
