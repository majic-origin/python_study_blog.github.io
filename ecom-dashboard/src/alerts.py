"""
src/alerts.py —— 阈值预警引擎
============================
把"红色的数字"变成"可读的告警"。规则与阈值解耦：
    规则在 RULES 里声明，阈值由侧边栏实时传入（用户可调）。

扩展 2（数据预警与异常监控）的核心逻辑就在这 80 行里。
"""

from __future__ import annotations

from src.format import money, pct


def _fmt(v: float, unit: str) -> str:
    return pct(v) if unit == "%" else money(v)


def check_alerts(kpi: dict, progress: float, thresholds: dict, cat_df=None) -> list[dict]:
    """返回告警列表，按严重程度排序（danger > warn > ok）。"""
    alerts: list[dict] = []

    # 1) 目标完成率：低于阈值 -> 危险/警告
    if progress < thresholds["gmv_progress"]:
        gap = thresholds["gmv_progress"] - progress
        alerts.append(
            {
                "level": "danger" if gap > 15 else "warn",
                "title": f"销售目标完成率仅 {progress:.1f}%",
                "desc": f"距离 {thresholds['gmv_progress']:.0f}% 的警戒线还差 {gap:.1f} 个百分点，"
                        f"建议加大投放或推高客单。",
            }
        )

    # 2) 毛利率：低于阈值 -> 盈利质量预警
    if kpi["gross_margin"] < thresholds["gross_margin"]:
        alerts.append(
            {
                "level": "warn",
                "title": f"毛利率 {pct(kpi['gross_margin'])} 低于健康线 {pct(thresholds['gross_margin'])}",
                "desc": "折扣力度可能过深，建议检查高折扣订单占比与品类毛利结构。",
            }
        )

    # 3) 退货率：高于阈值 -> 危险（影响口碑与履约成本）
    if kpi["return_rate"] > thresholds["return_rate"]:
        alerts.append(
            {
                "level": "danger",
                "title": f"退货率 {pct(kpi['return_rate'])} 超过上限 {pct(thresholds['return_rate'])}",
                "desc": "优先排查退货率最高的品类与渠道，可能是商品描述或物流时效问题。",
            }
        )

    # 4) 客单价：低于阈值
    if kpi["aov"] < thresholds["aov"]:
        alerts.append(
            {
                "level": "warn",
                "title": f"客单价 ¥{kpi['aov']:.0f} 低于目标 ¥{thresholds['aov']:.0f}",
                "desc": "可尝试满减门槛上移、关联推荐、套装组合等提升件单价的手段。",
            }
        )

    # 5) 品类级：毛利率异常低的品类（低于 20%）
    if cat_df is not None and len(cat_df):
        weak = cat_df[(cat_df["margin"].notna()) & (cat_df["margin"] < 20)]
        if len(weak):
            names = "、".join(weak["category"].tolist()[:3])
            alerts.append(
                {
                    "level": "warn",
                    "title": f"{len(weak)} 个品类毛利率低于 20%",
                    "desc": f"{names} 的促销可能已在亏损边缘，建议核对成本价与折扣策略。",
                }
            )

    order = {"danger": 0, "warn": 1, "ok": 2}
    return sorted(alerts, key=lambda a: order[a["level"]])
