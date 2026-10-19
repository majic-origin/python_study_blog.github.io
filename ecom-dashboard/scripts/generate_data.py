"""
scripts/generate_data.py —— 模拟电商订单数据集生成器
====================================================
用途：为看板提供一份"像真的"业务明细数据（不含真实用户隐私）。

刻意设计的 5 类业务规律：
  1. 增长趋势：月均自然增长约 2.5%，用于观察折线图斜率；
  2. 周内周期：周末单量约为工作日的 1.25 倍；
  3. 大促脉冲：618 / 双11 / 38 节 等节点单量 x2.6；
  4. 时段分布：10-12 点、20-22 点两个下单高峰；
  5. 品类结构：数码客单高、毛利低；美妆毛利高、客单低。

同时刻意注入 6 类"脏数据"，供后面演示清洗流程：
  缺失值、重复行、负数销量、极端异常金额、非法时间、空商品名。

运行：
    python scripts/generate_data.py            # 默认 15000 行
    python scripts/generate_data.py --rows 30000 --seed 7
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

# ------------------------------------------------------------------ 维度配置
# 品类 -> (商品池, 价格区间, 毛利率, 被选中的权重)
CATEGORY_PROFILE = {
    "数码家电": (["智能手机", "轻薄笔记本", "无线耳机", "智能手表", "平板电脑", "扫地机器人"], (699, 7999), 0.18, 0.26),
    "服饰鞋包": (["冲锋衣", "休闲西装", "运动跑鞋", "双肩背包", "针织连衣裙", "牛仔裤"], (129, 1299), 0.42, 0.24),
    "食品生鲜": (["车厘子礼盒", "冷鲜牛排", "有机牛奶", "坚果组合", "现磨咖啡豆", "海鲜礼包"], (39, 599), 0.28, 0.20),
    "美妆个护": (["精华液", "防晒霜", "口红套装", "洗发水", "面膜", "香水"], (69, 899), 0.52, 0.16),
    "家居日用": (["乳胶枕", "四件套", "收纳柜", "炒锅套装", "香薰机", "懒人沙发"], (49, 1599), 0.35, 0.09),
    "母婴玩具": (["婴儿推车", "积木套装", "儿童安全座椅", "纸尿裤", "绘本套装", "毛绒玩具"], (59, 2499), 0.38, 0.05),
}

# 区域 -> (城市列表, 权重)
REGION_PROFILE = {
    "华东": (["上海", "杭州", "南京", "苏州", "宁波", "合肥"], 0.30),
    "华北": (["北京", "天津", "石家庄", "太原", "济南"], 0.18),
    "华南": (["广州", "深圳", "东莞", "佛山", "厦门"], 0.19),
    "华中": (["武汉", "长沙", "郑州", "南昌"], 0.13),
    "西南": (["成都", "重庆", "昆明", "贵阳"], 0.11),
    "东北": (["沈阳", "大连", "长春", "哈尔滨"], 0.05),
    "西北": (["西安", "兰州", "乌鲁木齐", "银川"], 0.04),
}

CHANNEL_PROFILE = {"APP": 0.42, "小程序": 0.31, "网页": 0.17, "线下门店": 0.10}
PAYMENT_PROFILE = {"支付宝": 0.36, "微信支付": 0.41, "银行卡": 0.18, "货到付款": 0.05}
SEGMENT_PROFILE = {"新客": 0.46, "老客": 0.54}

# 下单时段权重（0-23 点）
HOUR_WEIGHTS = np.array(
    [1, 1, 1, 1, 1, 1, 2, 4, 7, 10, 14, 15, 12, 9, 8, 8, 8, 9, 12, 16, 19, 18, 12, 5],
    dtype=float,
)

START_DATE = datetime(2026, 1, 1)
END_DATE = datetime(2026, 9, 30)
CAMPAIGN_DAYS = {
    "2026-02-14": 1.6,  # 情人节
    "2026-03-08": 2.2,  # 女王节
    "2026-05-20": 1.8,  # 520
    "2026-06-18": 2.8,  # 618
    "2026-07-15": 1.5,  # 暑期季
    "2026-09-09": 2.0,  # 99 划算节
}


# ------------------------------------------------------------------ 工具函数
def _weighted_choice(rng: random.Random, mapping: dict) -> str:
    items = list(mapping)
    weights = [mapping[k] if not isinstance(mapping[k], tuple) else mapping[k][-1] for k in items]
    return rng.choices(items, weights=weights, k=1)[0]


def _day_pool(rng: np.random.Generator) -> tuple[list[datetime], np.ndarray]:
    """构造"日期池 + 抽样权重"，把趋势 / 周末 / 大促都编码进权重里。"""
    days, weights = [], []
    total_days = (END_DATE - START_DATE).days + 1
    for i in range(total_days):
        d = START_DATE + timedelta(days=i)
        w = 1.0
        w *= 1.25 if d.weekday() >= 5 else 1.0                      # 周末效应
        w *= 1.0 + 0.025 * (i / 30.0)                                # 月度增长趋势
        w *= CAMPAIGN_DAYS.get(d.strftime("%Y-%m-%d"), 1.0)          # 大促脉冲
        # 大促前 3 天蓄水，后 2 天回落（更真实的曲线形状）
        for camp, _ in CAMPAIGN_DAYS.items():
            camp_d = datetime.strptime(camp, "%Y-%m-%d")
            gap = (d - camp_d).days
            if -3 <= gap <= -1:
                w *= 1.25
            elif 1 <= gap <= 2:
                w *= 0.7
        days.append(d)
        weights.append(w)
    weights = np.array(weights, dtype=float)
    return days, weights / weights.sum()


# ------------------------------------------------------------------ 主生成逻辑
def build_orders(rows: int = 15_000, seed: int = 42) -> pd.DataFrame:
    rng_py = random.Random(seed)
    rng_np = np.random.default_rng(seed)

    days, day_prob = _day_pool(rng_np)
    hour_prob = HOUR_WEIGHTS / HOUR_WEIGHTS.sum()

    records = []
    for i in range(rows):
        day = rng_py.choices(days, weights=day_prob, k=1)[0]
        hour = int(rng_py.choices(range(24), weights=hour_prob, k=1)[0])
        ts = day + timedelta(hours=hour, minutes=rng_py.randint(0, 59), seconds=rng_py.randint(0, 59))

        region = _weighted_choice(rng_py, REGION_PROFILE)
        city = rng_py.choice(REGION_PROFILE[region][0])
        category = _weighted_choice(rng_py, CATEGORY_PROFILE)

        products, (lo, hi), margin, _ = CATEGORY_PROFILE[category]
        product = rng_py.choice(products)

        # 价格取对数均匀分布：低价商品多、高价商品少，更贴近真实成交结构
        unit_price = float(np.exp(rng_np.uniform(np.log(lo), np.log(hi))))
        unit_price = round(unit_price, 2)

        quantity = int(rng_py.choices([1, 2, 3, 4, 5], weights=[62, 22, 9, 4, 3], k=1)[0])
        discount = 1.0 if rng_py.random() < 0.58 else round(rng_py.uniform(0.72, 0.96), 2)

        amount = round(unit_price * quantity * discount, 2)
        # 毛利率做 ±6% 扰动，避免毛利率在图上是一条直线
        real_margin = min(max(margin + rng_py.uniform(-0.06, 0.06), 0.05), 0.7)
        cost = round(amount * (1 - real_margin), 2)

        status = rng_py.choices(["已完成", "已退货", "已取消"], weights=[93, 4, 3], k=1)[0]
        records.append(
            {
                "order_id": f"DD{ts:%Y%m%d}{i:06d}",
                "order_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "customer_id": f"C{rng_py.randint(1, 6_500):05d}",
                "region": region,
                "city": city,
                "category": category,
                "product": product,
                "channel": _weighted_choice(rng_py, CHANNEL_PROFILE),
                "payment": _weighted_choice(rng_py, PAYMENT_PROFILE),
                "segment": _weighted_choice(rng_py, SEGMENT_PROFILE),
                "quantity": quantity,
                "unit_price": unit_price,
                "discount": discount,
                "amount": amount,
                "cost": cost,
                "order_status": status,
                "review_score": rng_py.choices([5, 4, 3, 2, 1], weights=[56, 27, 10, 4, 3], k=1)[0],
            }
        )

    df = pd.DataFrame(records).sort_values("order_time").reset_index(drop=True)
    return df


def inject_dirty(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """故意弄脏数据 —— 没有脏数据，清洗模块就没有存在意义。"""
    rng = np.random.default_rng(seed)
    df = df.copy()
    n = len(df)

    # 1) 缺失值：城市 / 支付方式
    miss_idx = rng.choice(n, size=int(n * 0.018), replace=False)
    df.loc[miss_idx, "city"] = np.nan
    pay_idx = rng.choice(n, size=int(n * 0.008), replace=False)
    df.loc[pay_idx, "payment"] = np.nan

    # 2) 负数销量（录入符号错误）
    neg_idx = rng.choice(n, size=int(n * 0.006), replace=False)
    df.loc[neg_idx, "quantity"] = -df.loc[neg_idx, "quantity"]

    # 3) 极端异常金额（单位错误，放大了 60 倍）
    out_idx = rng.choice(n, size=int(n * 0.004), replace=False)
    df.loc[out_idx, "amount"] = (df.loc[out_idx, "amount"] * 60).round(2)

    # 4) 非法时间字符串
    bad_idx = rng.choice(n, size=int(n * 0.004), replace=False)
    df.loc[bad_idx, "order_time"] = "2026-13-45 09:00:00"

    # 5) 空商品名
    empty_idx = rng.choice(n, size=int(n * 0.004), replace=False)
    df.loc[empty_idx, "product"] = ""

    # 6) 完全重复的行（埋点重复上报）
    dup = df.sample(n=int(n * 0.012), random_state=seed)
    df = pd.concat([df, dup], ignore_index=True)

    return df.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成电商订单模拟数据")
    parser.add_argument("--rows", type=int, default=15_000, help="订单行数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子，保证可复现")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw = inject_dirty(build_orders(args.rows, args.seed), args.seed)
    out = DATA_DIR / "orders_raw.csv"
    # utf-8-sig：让 Excel 双击打开不乱码
    raw.to_csv(out, index=False, encoding="utf-8-sig")

    print(f"✓ 已生成 {len(raw):,} 行（含脏数据） -> {out}")
    print(f"  字段：{', '.join(raw.columns)}")
    print(f"  时间范围：{raw['order_time'].min()} ~ {raw['order_time'].max()}")
    print(f"  预估 GMV：¥{raw['amount'].sum():,.0f}")


if __name__ == "__main__":
    main()
