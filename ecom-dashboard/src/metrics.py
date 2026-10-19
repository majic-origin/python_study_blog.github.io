"""
src/metrics.py —— 指标计算层
============================
把"数据"翻译成"业务指标"。所有页面只消费这里算好的结果，
保证同一个指标在卡片、图表、报告里口径完全一致。

口径约定（写进注释，方便答辩时解释）：
  · GMV / 订单量 / 客单价 / 客户数 / 毛利率 —— 只统计「已完成」订单
  · 退货率 —— 退货单数 / 全部订单数
  · 环比 —— 与「等长的上一周期」对比
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import DAILY_TARGET, KPI_META
from src.format import delta, money, num, pct

RADAR_DIMS = ["销售额", "订单量", "客单价", "毛利率", "客户数"]


# ---------------------------------------------------------------- 单期快照
def kpi_snapshot(df: pd.DataFrame) -> dict[str, float]:
    """一次算出 6 个核心指标。"""
    completed = df[df["is_completed"]]
    total_orders = df["order_id"].nunique()
    gmv = float(completed["amount"].sum())
    orders = float(completed["order_id"].nunique())
    return {
        "gmv": gmv,
        "orders": orders,
        "aov": gmv / orders if orders else 0.0,
        "gross_margin": float(completed["profit"].sum()) / gmv * 100 if gmv else 0.0,
        "customers": float(completed["customer_id"].nunique()),
        "return_rate": float(df["is_returned"].sum()) / total_orders * 100 if total_orders else 0.0,
    }


def target_progress(df: pd.DataFrame) -> tuple[float, float, float]:
    """返回 (完成率%, 实际, 目标)。目标 = 天数 × 日目标。"""
    days = max(df["date"].nunique(), 1)
    target = days * DAILY_TARGET
    actual = float(df.loc[df["is_completed"], "amount"].sum())
    return (actual / target * 100 if target else 0.0), actual, target


# ---------------------------------------------------------------- 卡片数据
def kpi_cards(df: pd.DataFrame, prev: pd.DataFrame) -> list[dict]:
    """生成 6 张指标卡所需的全部文案（含环比方向与"好坏"判断）。"""
    cur, last = kpi_snapshot(df), kpi_snapshot(prev)
    cards = []
    for key, meta in KPI_META.items():
        value = cur[key]
        rate, text = delta(value, last[key])

        # 环比方向 vs 指标好坏方向：退货率上升是"坏事"，要标红
        good = rate <= 0 if meta["better"] == "down" else rate >= 0
        direction = "up" if rate >= 0 else "down"

        if meta["fmt"] == "money":
            value_text = money(value)
        elif meta["fmt"] == "pct":
            value_text = pct(value)
        else:
            value_text = num(value)

        cards.append(
            {
                "key": key,
                "label": meta["label"],
                "icon": meta["icon"],
                "value": value,
                "value_text": value_text,
                "delta_text": text,
                "direction": direction,
                "good": good,
                "sub": f"环比上期 {text}" if text != "—" else "无可比周期",
            }
        )
    return cards


# ---------------------------------------------------------------- 趋势
def daily_trend(df: pd.DataFrame) -> pd.DataFrame:
    """按天聚合 + 7 日移动平均（消除周内波动，看清趋势）。"""
    completed = df[df["is_completed"]]
    g = (
        completed.groupby("date")
        .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"), aov=("amount", "mean"))
        .reset_index()
        .sort_values("date")
    )
    # 补齐没有成交的日期，折线才不会"跳日"
    full = pd.DataFrame({"date": pd.date_range(g["date"].min(), g["date"].max(), freq="D")})
    g = full.merge(g, on="date", how="left").fillna({"gmv": 0, "orders": 0, "aov": 0})
    g["gmv_ma7"] = g["gmv"].rolling(7, min_periods=1).mean().round(2)
    g["orders_ma7"] = g["orders"].rolling(7, min_periods=1).mean().round(2)
    return g


def weekly_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """星期 × 时段 的下单热度矩阵（用于热力图，回答"什么时候卖得好"）。"""
    pivot = (
        df.pivot_table(index="weekday", columns="hour", values="order_id", aggfunc="count")
        .reindex(["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        .reindex(columns=range(24))
        .fillna(0)
    )
    return pivot


# ---------------------------------------------------------------- 维度对比
def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    completed = df[df["is_completed"]]
    g = (
        completed.groupby("category")
        .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"), profit=("profit", "sum"))
        .reset_index()
    )
    g["aov"] = g["gmv"] / g["orders"].replace(0, np.nan)
    g["margin"] = g["profit"] / g["gmv"].replace(0, np.nan) * 100
    g["share"] = g["gmv"] / g["gmv"].sum() * 100
    return g.sort_values("gmv", ascending=False).reset_index(drop=True)


def channel_summary(df: pd.DataFrame) -> pd.DataFrame:
    completed = df[df["is_completed"]]
    g = completed.groupby("channel").agg(gmv=("amount", "sum"), orders=("order_id", "nunique")).reset_index()
    g["share"] = g["gmv"] / g["gmv"].sum() * 100
    return g.sort_values("gmv", ascending=False).reset_index(drop=True)


def region_category_matrix(df: pd.DataFrame) -> pd.DataFrame:
    completed = df[df["is_completed"]]
    return completed.pivot_table(index="region", columns="category", values="amount", aggfunc="sum").fillna(0)


def region_radar(df: pd.DataFrame) -> pd.DataFrame:
    """各区域 5 维能力雷达：先算原值，再做 min-max 归一化到 0-100。"""
    completed = df[df["is_completed"]]
    g = (
        completed.groupby("region")
        .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"),
             aov=("amount", "mean"), profit=("profit", "sum"), customers=("customer_id", "nunique"))
        .reset_index()
    )
    g["margin"] = g["profit"] / g["gmv"].replace(0, np.nan) * 100
    raw = g[["gmv", "orders", "aov", "margin", "customers"]].astype(float)
    norm = (raw - raw.min()) / (raw.max() - raw.min()).replace(0, np.nan)
    out = pd.DataFrame({"region": g["region"]})
    for col, name in zip(raw.columns, RADAR_DIMS):
        out[name] = (norm[col].fillna(0.5) * 100).round(1)
    return out.set_index("region")


def city_ranking(df: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    completed = df[df["is_completed"]]
    g = completed.groupby(["city", "region"]).agg(gmv=("amount", "sum"), orders=("order_id", "nunique")).reset_index()
    g = g.sort_values("gmv", ascending=False).head(top).reset_index(drop=True)
    g["share"] = g["gmv"] / g["gmv"].sum() * 100
    return g


def top_products(df: pd.DataFrame, top: int = 8) -> pd.DataFrame:
    completed = df[df["is_completed"]]
    g = (
        completed.groupby(["product", "category"])
        .agg(gmv=("amount", "sum"), qty=("quantity", "sum"))
        .reset_index()
        .sort_values("gmv", ascending=False)
        .head(top)
        .reset_index(drop=True)
    )
    return g


def segment_split(df: pd.DataFrame) -> pd.DataFrame:
    completed = df[df["is_completed"]]
    g = completed.groupby("segment").agg(gmv=("amount", "sum"), orders=("order_id", "nunique")).reset_index()
    g["share"] = g["gmv"] / g["gmv"].sum() * 100
    return g
