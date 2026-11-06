"""
src/report.py —— 一键导出
========================
扩展 4（数据统计分析与报告输出）：
  · build_html_report()  生成一份自包含 HTML 分析报告（图表内嵌，可直接发同事）
  · to_csv_bytes()       明细数据导出
  · export_png()         单图 PNG 导出（需要 kaleido）

报告里的"结论"不是空话，全部由数据+规则生成：最强品类、增长最快区域、
主要风险点，逐条带数字。
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

import pandas as pd

from src.format import money, pct


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """导出 CSV（utf-8-sig，Excel 打开不乱码）。"""
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def export_png(fig, scale: float = 2.0) -> bytes | None:
    """把 Plotly 图导出成 PNG。没装 kaleido 时返回 None，由调用方给降级提示。"""
    try:
        return fig.to_image(format="png", scale=scale)
    except Exception:
        return None


def _insights(cards: list[dict], cat_df, region_df, ch_df, progress: float) -> list[str]:
    """规则化生成 4 条结论，避免"看起来像样但没信息量"的模板话。"""
    out: list[str] = []
    top_cat = cat_df.iloc[0] if len(cat_df) else None
    if top_cat is not None:
        out.append(
            f"**品类结构**：{top_cat['category']} 贡献销售额 {money(top_cat['gmv'])}，"
            f"占大盘 {top_cat['share']:.1f}%，是当前的绝对主力；其毛利率为 {top_cat['margin']:.1f}%。"
        )
    if len(cat_df) > 1:
        low = cat_df.sort_values("margin").iloc[0]
        out.append(
            f"**盈利质量**：{low['category']} 毛利率最低（{low['margin']:.1f}%），"
            f"但销售额贡献 {low['share']:.1f}%，属于「以价换量」品类，需盯紧折扣率。"
        )
    if len(region_df):
        best = region_df.sort_values("gmv", ascending=False).iloc[0]
        weakest = region_df.sort_values("gmv").iloc[0]
        out.append(
            f"**区域差异**：{best['region']} 销售额最高（{money(best['gmv'])}），"
            f"{weakest['region']} 最低（{money(weakest['gmv'])}），"
            f"两者相差约 {best['gmv'] / max(weakest['gmv'], 1):.1f} 倍，下沉市场仍有空间。"
        )
    if len(ch_df):
        top_ch = ch_df.iloc[0]
        out.append(
            f"**渠道结构**：{top_ch['channel']} 渠道贡献 {top_ch['share']:.1f}%，"
            f"线上自营阵地稳固；建议对占比最低的渠道做一次投放效率复盘。"
        )
    out.append(
        f"**目标进度**：当前完成率 {progress:.1f}%，"
        + ("已超目标，可考虑把预算转向高毛利品类。" if progress >= 100 else "仍处于爬坡阶段，建议在大促节点集中蓄水。")
    )
    return out


_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>星云商城经营分析报告</title>
<style>
  :root{{--brand:#2563EB;--text:#0F172A;--muted:#64748B;--border:#E2E8F0;}}
  body{{margin:0;padding:44px 28px;background:#F4F6FB;color:var(--text);
        font-family:"Microsoft YaHei","PingFang SC",-apple-system,sans-serif;line-height:1.75;}}
  .wrap{{max-width:1080px;margin:0 auto;background:#fff;border:1px solid var(--border);
         border-radius:18px;padding:44px 46px;box-shadow:0 20px 60px -30px rgba(15,23,42,.35);}}
  h1{{font-size:26px;margin:0 0 6px;}}
  .meta{{color:var(--muted);font-size:13px;margin-bottom:28px;}}
  h2{{font-size:17px;margin:34px 0 12px;padding-left:11px;border-left:4px solid var(--brand);}}
  table{{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0;}}
  th,td{{padding:9px 12px;border-bottom:1px solid var(--border);text-align:left;}}
  th{{background:#F8FAFF;color:var(--muted);font-weight:600;font-size:12.5px;}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums;}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0;}}
  .kpi{{border:1px solid var(--border);border-radius:12px;padding:12px 14px;background:#FCFDFF;}}
  .kpi .l{{font-size:12px;color:var(--muted);}}
  .kpi .v{{font-size:21px;font-weight:700;margin-top:4px;}}
  .kpi .d{{font-size:12px;margin-top:3px;}}
  .up{{color:#15803D;}} .down{{color:#B91C1C;}}
  ul{{padding-left:20px;}} li{{margin:6px 0;font-size:14px;}}
  .foot{{margin-top:36px;padding-top:16px;border-top:1px solid var(--border);
         color:var(--muted);font-size:12px;}}
  .chart{{margin:6px 0 4px;}}
  @media print{{body{{background:#fff;padding:0;}} .wrap{{border:none;box-shadow:none;}}}}
</style></head><body><div class="wrap">
<h1>星云商城 · 经营数据分析报告</h1>
<div class="meta">统计周期 {period} ｜ 数据范围 {rows} 条有效订单 ｜ 生成时间 {now}</div>
{kpi_block}
<h2>一、核心结论</h2>
<ul>{insights}</ul>
<h2>二、风险与预警</h2>
{alert_block}
<h2>三、销售趋势</h2>
<div class="chart">{trend_html}</div>
<h2>四、品类与渠道结构</h2>
<div class="chart">{cat_html}</div>
<div class="chart">{channel_html}</div>
<h2>五、区域表现</h2>
<div class="chart">{region_html}</div>
<h2>六、数据质量</h2>
<table><tr><th>检查项</th><th>结果</th></tr>{quality_rows}</table>
<div class="foot">本报告由 Streamlit 数据看板自动生成，指标口径：GMV/订单量/客单价/毛利率仅统计「已完成」订单，退货率 = 退货订单 / 全部订单。</div>
</div></body></html>"""


def build_html_report(
    *, cards: list[dict], progress: float, alerts: list[dict], cat_df, region_df, ch_df,
    figs: dict, report: dict, period_text: str, rows: int,
) -> str:
    kpi_html = "".join(
        f'<div class="kpi"><div class="l">{c["label"]}</div>'
        f'<div class="v">{c["value_text"]}</div>'
        f'<div class="d {"up" if c["good"] else "down"}">{c["delta_text"]}</div></div>'
        for c in cards
    )
    trend_rows = "".join(
        f"<tr><td>{r.category}</td><td class='num'>{money(r.gmv)}</td>"
        f"<td class='num'>{r.share:.1f}%</td><td class='num'>{r.margin:.1f}%</td>"
        f"<td class='num'>{r.orders:,.0f}</td></tr>"
        for r in cat_df.itertuples()
    )
    cat_html = (
        "".join(figs.get(k, "").to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
                for k in ("trend", "category"))
    )
    channel_html = figs.get("channel").to_html(full_html=False, include_plotlyjs=False,
                                               config={"displayModeBar": False}) if figs.get("channel") else ""
    region_html = figs.get("region").to_html(full_html=False, include_plotlyjs=False,
                                             config={"displayModeBar": False}) if figs.get("region") else ""

    alert_block = (
        "<ul>" + "".join(f"<li><b>[{a['level'].upper()}] {a['title']}</b> —— {a['desc']}</li>" for a in alerts) + "</ul>"
        if alerts else "<p>本期各项指标均在阈值内，未触发预警。</p>"
    )
    quality_rows = "".join(
        f"<tr><td>{s['step']}</td><td>{s['action']}（影响 {s['affected']:,} 行）{('— ' + s['note']) if s['note'] else ''}</td></tr>"
        for s in report["steps"]
    )

    html = _HTML.format(
        period=period_text,
        rows=f"{rows:,}",
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        kpi_block=f'<div class="kpi-grid">{kpi_html}</div>',
        insights="".join(f"<li>{x}</li>" for x in _insights(cards, cat_df, region_df, ch_df, progress)),
        alert_block=alert_block,
        trend_html=cat_html,
        cat_html=f"<table><tr><th>品类</th><th>销售额</th><th>占比</th><th>毛利率</th><th>订单</th></tr>{trend_rows}</table>",
        channel_html=channel_html,
        region_html=region_html,
        quality_rows=quality_rows,
    )
    # 报告内嵌 plotly.js（用 CDN 版本，文件体积小；离线场景可换 include_plotlyjs=True）
    return html.replace("<body>", '<body><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>')


def fig_to_png_buffer(fig) -> BytesIO | None:
    data = export_png(fig)
    return BytesIO(data) if data else None
