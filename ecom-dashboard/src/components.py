"""
src/components.py —— 自研 UI 组件
================================
Streamlit 原生控件负责"能用"，这里的 HTML 组件负责"好看"。
每个函数只返回/渲染一段 HTML，不做数据计算。

组件清单：
    page_header()   页头（品牌 + 时间范围徽章 + 数据新鲜度）
    section()       分区标题（编号 + 标题 + 一句话说明）
    kpi_cards()     指标卡（含数字滚动动画，跑在独立 iframe 里）
    ranking()       排行榜（进度条动画）
    alert_stack()   预警条（危险项闪烁）
    drill_chip()    当前下钻维度的提示胶囊
    quality_lines() 数据质量明细
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as stc

from config import KPI_META
from src.format import money, num


# ---------------------------------------------------------------- 页头
def page_header(title: str, subtitle: str, chips: list[tuple[str, str]], live: bool = False) -> None:
    chip_html = "".join(
        f'<span class="chip{" live" if (live and i == 0) else ""}">'
        f'<span class="dot"></span>{label}<b>{value}</b></span>'
        for i, (label, value) in enumerate(chips)
    )
    st.markdown(
        f"""
        <div class="dash-head">
          <div class="brand">
            <div class="mark">📊</div>
            <div>
              <h1>{title}</h1>
              <div class="sub">{subtitle}</div>
            </div>
          </div>
          <div class="chips">{chip_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- 分区标题
def section(no: str, title: str, desc: str = "") -> None:
    st.markdown(
        f'<div class="sec"><span class="bar"></span><span class="no">{no}</span>'
        f'<span class="tt">{title}</span><span class="ds">{desc}</span></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- 指标卡
_KPI_TPL = """
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  *{{box-sizing:border-box; margin:0; padding:0;}}
  body{{background:transparent; font-family:"Microsoft YaHei","PingFang SC",-apple-system,sans-serif;}}
  .grid{{
    display:grid; grid-template-columns:repeat(6,1fr); gap:12px;
  }}
  .kpi{{
    position:relative; overflow:hidden;
    background:{panel}; border:1px solid {border}; border-radius:16px;
    padding:13px 15px 12px; box-shadow:{shadow};
    opacity:0; transform:translateY(12px);
    animation:cardIn .5s cubic-bezier(.2,.8,.2,1) forwards;
  }}
  .kpi::after{{
    content:""; position:absolute; left:0; top:0; width:100%; height:3px;
    background:linear-gradient(90deg,{brand},rgba(96,165,250,.15));
  }}
  .kpi .top{{display:flex; align-items:center; gap:6px; font-size:12px; color:{muted};}}
  .kpi .top .ico{{font-size:13px;}}
  .kpi .val{{
    margin-top:7px; font-size:26px; font-weight:700; color:{text};
    letter-spacing:-.02em; line-height:1.15; font-variant-numeric:tabular-nums;
  }}
  .kpi .foot{{margin-top:7px; display:flex; align-items:center; gap:6px; font-size:11px; color:{muted};}}
  .kpi .delta{{
    display:inline-flex; align-items:center; gap:3px;
    padding:1px 6px; border-radius:6px; font-weight:600; font-size:11px;
  }}
  .kpi .delta.good{{color:#15803D; background:rgba(22,163,74,.12);}}
  .kpi .delta.bad{{color:#B91C1C; background:rgba(239,68,68,.12);}}
  .kpi .delta.flat{{color:{muted}; background:rgba(100,116,139,.12);}}
  @keyframes cardIn{{to{{opacity:1; transform:none;}}}}
  @media (max-width:1180px){{ .grid{{grid-template-columns:repeat(3,1fr);}} .kpi .val{{font-size:23px;}} }}
  @media (max-width:640px){{ .grid{{grid-template-columns:repeat(2,1fr);}} .kpi .val{{font-size:20px;}} }}
</style></head><body>
<div class="grid">{cards}</div>
<script>
const fmt = (v, kind) => {{
  if (kind === 'money') {{
    if (Math.abs(v) >= 1e8) return (v/1e8).toFixed(2) + '亿';
    if (Math.abs(v) >= 1e4) return (v/1e4).toFixed(1) + '万';
    return Math.round(v).toLocaleString('zh-CN');
  }}
  if (kind === 'pct') return v.toFixed(1) + '%';
  return Math.round(v).toLocaleString('zh-CN');
}};
document.querySelectorAll('.kpi .val').forEach((el, i) => {{
  const target = parseFloat(el.dataset.v) || 0;
  const kind = el.dataset.kind;
  const dur = 950, t0 = performance.now();
  el.textContent = fmt(0, kind);
  const step = (t) => {{
    const p = Math.min((t - t0) / dur, 1);
    const eased = 1 - Math.pow(1 - p, 3);              // easeOutCubic
    el.textContent = fmt(target * eased, kind);
    if (p < 1) requestAnimationFrame(step);
    else el.textContent = fmt(target, kind);
  }};
  setTimeout(() => requestAnimationFrame(step), 90 + i * 70);
}});

// 卡片在窄屏会换成 3 列 / 2 列，高度必须跟着内容走 ——
// 用 Streamlit 组件协议的 setFrameHeight 告诉父页面 iframe 该多高
function fitFrame() {{
  const h = Math.ceil(document.querySelector('.grid').getBoundingClientRect().height) + 4;
  window.parent.postMessage({{ isStreamlitMessage: true, type: 'streamlit:setFrameHeight', height: h }}, '*');
}}
fitFrame();
window.addEventListener('resize', fitFrame);
setTimeout(fitFrame, 300);
</script></body></html>
"""

_KPI_CARD = """
<div class="kpi" style="animation-delay:{delay}ms">
  <div class="top"><span class="ico">{icon}</span><span>{label}</span></div>
  <div class="val" data-v="{value}" data-kind="{kind}">0</div>
  <div class="foot"><span class="delta {cls}">{delta}</span><span>{sub}</span></div>
</div>
"""


def kpi_cards(cards: list[dict], t: dict) -> None:
    """6 张指标卡：CSS 卡片 + JS 数字滚动（easeOutCubic，约 0.95s 到位）。"""
    html_cards = []
    for i, c in enumerate(cards):
        cls = "flat" if c["delta_text"] == "—" else ("good" if c["good"] else "bad")
        html_cards.append(
            _KPI_CARD.format(
                delay=i * 60,
                icon=c["icon"],
                label=c["label"],
                value=f"{c['value']:.4f}",
                kind=KPI_META[c["key"]]["fmt"],
                cls=cls,
                delta=c["delta_text"],
                sub="环比上期" if c["delta_text"] != "—" else "无可比周期",
            )
        )
    html = _KPI_TPL.format(
        panel=t["panel"], border=t["border"], shadow=t["shadow"], muted=t["muted"],
        text=t["text"], brand="#2563EB", cards="".join(html_cards),
    )
    stc.html(html, height=132, scrolling=False)


# ---------------------------------------------------------------- 排行榜
def ranking(df, label_col: str, value_col: str, sub_col: str | None = None) -> None:
    """排行榜：名次 + 名称 + 进度条 + 数值，第一名用金色徽标。"""
    vmax = float(df[value_col].max()) or 1
    rows = []
    for i, row in df.reset_index(drop=True).iterrows():
        w = float(row[value_col]) / vmax * 100
        sub = f"<small>{row[sub_col]}</small>" if sub_col else ""
        rows.append(
            f'<div class="rank-row{" top1" if i == 0 else ""}">'
            f'<div class="idx">{i + 1}</div>'
            f'<div><div class="meta"><span>{row[label_col]}</span>{sub}</div>'
            f'<div class="track"><div class="fill" style="width:{w:.1f}%"></div></div></div>'
            f'<div class="val">{money(row[value_col])}</div>'
            f"</div>"
        )
    st.markdown(f'<div class="rank">{"".join(rows)}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- 预警条
def alert_stack(alerts: list[dict]) -> None:
    if not alerts:
        st.markdown(
            '<div class="alert ok"><span class="ico">✓</span>'
            "<span>全部核心指标处于健康区间，无需干预。</span></div>",
            unsafe_allow_html=True,
        )
        return
    icons = {"danger": "▲", "warn": "!", "ok": "✓"}
    html = "".join(
        f'<div class="alert {a["level"]}"><span class="ico">{icons[a["level"]]}</span>'
        f'<span><b>{a["title"]}</b> {a["desc"]}</span></div>'
        for a in alerts
    )
    st.markdown(html, unsafe_allow_html=True)


def drill_chip(label: str) -> None:
    st.markdown(f'<div class="drill">🔎 当前下钻：<b>{label}</b></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- 数据质量
def quality_lines(report: dict) -> None:
    rows = [
        ("原始记录", f"{report['raw_rows']:,} 行"),
        ("清洗后留存", f"{report['clean_rows']:,} 行（{report['keep_ratio']}%）"),
        ("剔除记录", f"{report['drop_rows']:,} 行"),
        ("修复缺失单元格", f"{report.get('missing_cells_before', 0):,} 个"),
        ("时间跨度", f"{report['time_range'][0][:10]} ~ {report['time_range'][1][:10]}"),
    ]
    html = "".join(f'<div class="qa-line"><span class="k">{k}</span><span class="v">{v}</span></div>' for k, v in rows)
    st.markdown(html, unsafe_allow_html=True)


def text_stat(label: str, value: str) -> str:
    return f'<div class="qa-line"><span class="k">{label}</span><span class="v">{value}</span></div>'


def stat_line(label: str, value: float, kind: str = "money") -> str:
    v = money(value) if kind == "money" else num(value)
    return f'<div class="qa-line"><span class="k">{label}</span><span class="v">{v}</span></div>'
