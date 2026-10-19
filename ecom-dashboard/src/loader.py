"""
src/loader.py —— 数据加载（带缓存）
==================================
Streamlit 每次交互都会重跑整个脚本，所以"读文件 + 清洗"必须缓存，
否则每次点击筛选都要重新清洗 1.5 万行，体验会很卡。

@st.cache_data 会把 (DataFrame, report) pickle 起来，key 是函数参数；
这里没有参数，等价于"进程内只算一次"。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import RAW_DATA
from src.preprocess import clean_orders


@st.cache_data(show_spinner="正在加载并清洗订单数据…")
def load_orders() -> tuple[pd.DataFrame, dict]:
    if not RAW_DATA.exists():
        raise FileNotFoundError(
            f"未找到数据文件：{RAW_DATA}\n请先运行  python scripts/generate_data.py  生成模拟数据。"
        )
    raw = pd.read_csv(RAW_DATA, encoding="utf-8-sig")
    return clean_orders(raw)


@st.cache_data(show_spinner=False)
def date_bounds(df: pd.DataFrame) -> tuple:
    return df["date"].min().date(), df["date"].max().date()
