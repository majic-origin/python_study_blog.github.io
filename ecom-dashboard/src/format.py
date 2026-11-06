"""src/format.py —— 数字/金额/百分比格式化小工具（统一口径，避免各页面各写一套）"""

from __future__ import annotations


def money(v: float, unit: str = "元", digits: int = 0) -> str:
    """12345678 -> 1234.6万 / 1.23亿"""
    v = float(v or 0)
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿{unit}"
    if abs(v) >= 1e4:
        return f"{v / 1e4:,.1f}万{unit}"
    return f"{v:,.{digits}f}{unit}"


def money_exact(v: float) -> str:
    return f"¥{float(v or 0):,.0f}"


def num(v: float) -> str:
    v = float(v or 0)
    if abs(v) >= 1e4:
        return f"{v / 1e4:.1f}万"
    return f"{int(round(v)):,}"


def pct(v: float, digits: int = 1) -> str:
    return f"{float(v or 0):.{digits}f}%"


def delta(cur: float, prev: float) -> tuple[float, str]:
    """返回 (变化率%, 展示文本)。prev 为 0 时退化为 '—'。"""
    if not prev:
        return 0.0, "—"
    rate = (cur - prev) / abs(prev) * 100
    arrow = "▲" if rate >= 0 else "▼"
    return rate, f"{arrow} {abs(rate):.1f}%"
