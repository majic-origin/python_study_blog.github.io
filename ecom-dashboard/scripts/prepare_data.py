"""
scripts/prepare_data.py —— 离线数据准备（任务 2 的交付物）
========================================================
1) 读取 data/orders_raw.csv（含脏数据）
2) 走一遍 src/preprocess.py 的 8 步清洗流水线
3) 落盘三份文件：
     data/orders_clean.csv   清洗后明细（utf-8-sig，Excel 直接打开）
     data/orders.xlsx        同名 Excel + 一张「数据质量」工作表
     data/quality_report.json 清洗报告（每一步影响多少行）

运行：
    python scripts/prepare_data.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import CLEAN_CSV, CLEAN_XLSX, QUALITY_JSON, RAW_DATA  # noqa: E402
from src.preprocess import clean_orders  # noqa: E402


def main() -> None:
    if not RAW_DATA.exists():
        raise SystemExit(f"缺少原始数据 {RAW_DATA}，请先执行：python scripts/generate_data.py")

    raw = pd.read_csv(RAW_DATA, encoding="utf-8-sig")
    clean, report = clean_orders(raw)

    clean.to_csv(CLEAN_CSV, index=False, encoding="utf-8-sig")
    QUALITY_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with pd.ExcelWriter(CLEAN_XLSX, engine="openpyxl") as writer:
        clean.to_excel(writer, sheet_name="订单明细", index=False)
        pd.DataFrame(report["steps"]).to_excel(writer, sheet_name="数据质量", index=False)
        # 维度汇总页，方便老师/同事直接看结论
        done = clean[clean["is_completed"]]
        (
            done.groupby("category")
            .agg(销售额=("amount", "sum"), 订单数=("order_id", "nunique"), 毛利=("profit", "sum"))
            .sort_values("销售额", ascending=False)
            .to_excel(writer, sheet_name="品类汇总")
        )

    print(f"✓ 清洗完成：{report['raw_rows']:,} → {report['clean_rows']:,} 行（留存 {report['keep_ratio']}%）")
    for s in report["steps"]:
        flag = f"影响 {s['affected']:>6,} 行" if s["affected"] else "无删除"
        print(f"   {s['step']:<16} {flag}  {s['action']}")
    print(f"✓ 已输出：\n   {CLEAN_CSV}\n   {CLEAN_XLSX}\n   {QUALITY_JSON}")


if __name__ == "__main__":
    main()
