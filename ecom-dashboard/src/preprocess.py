"""
src/preprocess.py —— 数据清洗与特征工程
=======================================
一条"可审计"的清洗流水线：每一步都记录删掉/修正了多少行，
最终产出 (干净数据, 质量报告)。看板侧边栏会把这七步展示成"数据质量"面板。

清洗规则（对应实验任务 2）：
    S1 字段规范化   —— 去空白、统一列名
    S2 时间解析     —— 非法时间 -> NaT -> 剔除
    S3 主键去重     —— 按 order_id 保留首单
    S4 类型转换     —— 数值列 to_numeric，无法转换记缺失
    S5 缺失值处理   —— 类别列填「未知」，数值列用中位数
    S6 逻辑校验     —— 负销量取绝对值；金额与单价*数量*折扣不一致 -> 重算
    S7 异常值处理   —— 按品类做 IQR 上界缩尾（winsorize），避免把真实大单误删
    S8 特征衍生     —— 日期 / 月 / 星期 / 时段 / 利润 / 毛利率
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 业务上必须存在的列
REQUIRED_COLUMNS = [
    "order_id", "order_time", "customer_id", "region", "city", "category",
    "product", "channel", "payment", "segment", "quantity", "unit_price",
    "discount", "amount", "cost", "order_status", "review_score",
]

NUMERIC_COLUMNS = ["quantity", "unit_price", "discount", "amount", "cost", "review_score"]
CATEGORY_COLUMNS = ["region", "city", "category", "product", "channel", "payment", "segment", "order_status"]

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _time_slot(hour: int) -> str:
    if 0 <= hour < 6:
        return "凌晨"
    if hour < 9:
        return "早晨"
    if hour < 12:
        return "上午"
    if hour < 14:
        return "午间"
    if hour < 18:
        return "下午"
    if hour < 22:
        return "晚间"
    return "深夜"


def clean_orders(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """执行完整清洗流水线，返回 (干净数据, 质量报告)。"""
    report: dict = {"steps": []}
    df = raw.copy()
    report["raw_rows"] = int(len(df))

    def log(step: str, action: str, affected: int, note: str = "") -> None:
        report["steps"].append(
            {"step": step, "action": action, "affected": int(affected), "note": note}
        )

    # ------------------------------------------------ S1 字段规范化
    df.columns = [str(c).strip() for c in df.columns]
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    df = df[REQUIRED_COLUMNS]
    log("S1 字段规范化", "列名去空格 + 缺失列补齐", 0, f"共 {len(REQUIRED_COLUMNS)} 个标准字段")

    # ------------------------------------------------ S2 时间解析
    df["order_time"] = pd.to_datetime(df["order_time"], errors="coerce")
    bad_time = int(df["order_time"].isna().sum())
    df = df.dropna(subset=["order_time"])
    log("S2 时间解析", "非法时间剔除", bad_time, "如 2026-13-45 这类脏值")

    # ------------------------------------------------ S3 去重
    before = len(df)
    df = df.drop_duplicates(subset=["order_id"], keep="first")
    log("S3 主键去重", "按 order_id 去重", before - len(df), "埋点重复上报")

    # ------------------------------------------------ S4 类型转换
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in CATEGORY_COLUMNS:
        df[col] = df[col].astype("string").str.strip()

    # ------------------------------------------------ S5 缺失值
    missing_cells = int(df.isna().sum().sum())
    for col in ["city", "payment", "product"]:
        df[col] = df[col].replace({"": pd.NA}).fillna("未知")
    for col in ["quantity", "unit_price", "amount", "cost"]:
        df[col] = df[col].fillna(df[col].median())
    df["discount"] = df["discount"].fillna(1.0)
    df["review_score"] = df["review_score"].fillna(df["review_score"].median())
    # 仍然没有分类值的行（region / category 等）直接丢弃，无法归属维度就没有分析价值
    before = len(df)
    df = df.dropna(subset=["region", "category", "channel", "segment", "order_status"])
    log("S5 缺失值处理", "分类填充「未知」+ 数值填充中位数", missing_cells, f"再剔除 {before - len(df)} 行无法归属维度的记录")

    # ------------------------------------------------ S6 逻辑校验
    neg = int((df["quantity"] <= 0).sum())
    df["quantity"] = df["quantity"].abs().replace(0, 1)
    log("S6 逻辑校验", "负销量取绝对值", neg, "录入符号错误")

    calc = (df["unit_price"] * df["quantity"] * df["discount"]).round(2)
    mismatch = int((np.abs(calc - df["amount"]) > 1.0).sum())
    df["amount"] = np.where(np.abs(calc - df["amount"]) > 1.0, calc, df["amount"])
    log("S6 逻辑校验", "金额与明细不一致则重算", mismatch, "单价×数量×折扣")

    # ------------------------------------------------ S7 异常值（分品类 IQR 缩尾）
    clipped = 0
    for _, idx in df.groupby("category").groups.items():
        q1, q3 = df.loc[idx, "amount"].quantile([0.25, 0.75])
        upper = q3 + 1.5 * (q3 - q1)
        mask = df.loc[idx, "amount"] > upper
        clipped += int(mask.sum())
        df.loc[df.loc[idx][mask].index, "amount"] = round(upper, 2)
    df["cost"] = np.minimum(df["cost"], df["amount"] * 0.98)
    log("S7 异常值处理", "分品类 IQR 上界缩尾", clipped, "保留大单，避免误删真实峰值")

    # ------------------------------------------------ S8 特征衍生
    df["date"] = df["order_time"].dt.normalize()
    df["month"] = df["order_time"].dt.strftime("%Y-%m")
    df["week"] = df["order_time"].dt.isocalendar().week.astype(int)
    df["weekday"] = df["order_time"].dt.weekday.map(dict(enumerate(WEEKDAY_CN)))
    df["hour"] = df["order_time"].dt.hour
    df["time_slot"] = df["hour"].map(_time_slot)
    df["profit"] = (df["amount"] - df["cost"]).round(2)
    df["margin"] = np.where(df["amount"] > 0, df["profit"] / df["amount"], 0.0)
    df["is_completed"] = df["order_status"].eq("已完成")
    df["is_returned"] = df["order_status"].eq("已退货")
    log("S8 特征衍生", "新增 11 个分析字段", 0, "日期/时段/利润/毛利率/状态标记")

    df = df.sort_values("order_time").reset_index(drop=True)

    report["clean_rows"] = int(len(df))
    report["drop_rows"] = int(report["raw_rows"] - len(df))
    report["keep_ratio"] = round(len(df) / max(report["raw_rows"], 1) * 100, 2)
    report["time_range"] = [str(df["order_time"].min()), str(df["order_time"].max())]
    report["missing_cells_before"] = missing_cells
    return df, report


def build_dimension_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """把明细宽表拆成几张便于复用的维度汇总表（避免在渲染层反复 groupby）。"""
    completed = df[df["is_completed"]]
    return {
        "by_date": (
            completed.groupby("date", as_index=False)
            .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"), customers=("customer_id", "nunique"))
            .assign(aov=lambda d: d["gmv"] / d["orders"].replace(0, np.nan))
        ),
        "by_category": (
            completed.groupby("category", as_index=False)
            .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"), profit=("profit", "sum"))
            .assign(aov=lambda d: d["gmv"] / d["orders"].replace(0, np.nan),
                    margin=lambda d: d["profit"] / d["gmv"].replace(0, np.nan) * 100)
            .sort_values("gmv", ascending=False)
        ),
        "by_region": (
            completed.groupby("region", as_index=False)
            .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"), customers=("customer_id", "nunique"), profit=("profit", "sum"))
            .assign(aov=lambda d: d["gmv"] / d["orders"].replace(0, np.nan),
                    margin=lambda d: d["profit"] / d["gmv"].replace(0, np.nan) * 100)
            .sort_values("gmv", ascending=False)
        ),
        "by_channel": (
            completed.groupby("channel", as_index=False)
            .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"))
        ),
        "by_city": (
            completed.groupby(["city", "region"], as_index=False)
            .agg(gmv=("amount", "sum"), orders=("order_id", "nunique"))
            .sort_values("gmv", ascending=False)
        ),
    }
