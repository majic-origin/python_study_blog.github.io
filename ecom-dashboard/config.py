"""
config.py —— 全局配置中心
=========================
所有"可调参数"集中在这里：路径、配色、业务维度、预警阈值、目标值。
改样式 / 改阈值 / 换主题色，只动这一个文件，不用翻业务代码。
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------- 路径
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
RAW_DATA = DATA_DIR / "orders_raw.csv"
CLEAN_CSV = DATA_DIR / "orders_clean.csv"
CLEAN_XLSX = DATA_DIR / "orders.xlsx"
QUALITY_JSON = DATA_DIR / "quality_report.json"

# ---------------------------------------------------------------- 应用信息
APP_TITLE = "星云商城 · 经营数据看板"
APP_SUBTITLE = "E-commerce Operation Dashboard"
APP_ICON = "📊"

# ---------------------------------------------------------------- 品牌色
# 主色（品牌蓝） + 辅助色（用于多系列图表，色相间隔 ≥ 30°，保证可辨识）
BRAND = {
    "primary": "#2563EB",
    "primary_soft": "#93B4FD",
    "accent": "#F59E0B",
    "success": "#16A34A",
    "danger": "#EF4444",
    "warning": "#F97316",
    "info": "#0EA5E9",
}

# 分类维度固定配色：同一个品类在任何图表里颜色都不变（认知一致性原则）
CATEGORY_COLORS = {
    "数码家电": "#2563EB",
    "服饰鞋包": "#8B5CF6",
    "食品生鲜": "#16A34A",
    "美妆个护": "#EC4899",
    "家居日用": "#F59E0B",
    "母婴玩具": "#06B6D4",
}

CHANNEL_COLORS = {
    "APP": "#2563EB",
    "小程序": "#16A34A",
    "网页": "#F59E0B",
    "线下门店": "#8B5CF6",
}

# 连续色阶（热力图 / 柱状图渐变）
SEQUENTIAL_SCALE = [
    [0.0, "#EFF6FF"],
    [0.25, "#BFDBFE"],
    [0.5, "#60A5FA"],
    [0.75, "#2563EB"],
    [1.0, "#1E3A8A"],
]

# ---------------------------------------------------------------- 主题
# 亮色 / 暗色两套 token，图表与 HTML 组件都从这里取色，保证一键换肤
THEMES = {
    "light": {
        "name": "亮色",
        "bg": "#F4F6FB",
        "bg_grad": "radial-gradient(1200px 600px at 8% -10%, #E8EEFF 0%, #F4F6FB 55%, #F7F8FC 100%)",
        "panel": "#FFFFFF",
        "panel_alt": "#F8FAFF",
        "text": "#0F172A",
        "muted": "#64748B",
        "border": "#E2E8F0",
        "grid": "#EDF1F7",
        "shadow": "0 1px 2px rgba(15,23,42,.04), 0 8px 24px -12px rgba(15,23,42,.18)",
        "plot_template": "plotly_white",
    },
    "dark": {
        "name": "暗色",
        "bg": "#070C16",
        "bg_grad": "radial-gradient(1100px 650px at 12% -15%, #10203F 0%, #080E1A 55%, #05090F 100%)",
        "panel": "#0F172A",
        "panel_alt": "#111C31",
        "text": "#E6EDF7",
        "muted": "#8CA3C3",
        "border": "#1E2B42",
        "grid": "#17223A",
        "shadow": "0 1px 2px rgba(0,0,0,.4), 0 12px 32px -16px rgba(0,0,0,.8)",
        "plot_template": "plotly_dark",
    },
}

# ---------------------------------------------------------------- 业务常量
REGIONS = ["华东", "华北", "华南", "华中", "西南", "东北", "西北"]
CATEGORIES = list(CATEGORY_COLORS)
CHANNELS = list(CHANNEL_COLORS)
SEGMENTS = ["新客", "老客"]

# 预警阈值（可在侧边栏实时调整）
DEFAULT_THRESHOLDS = {
    "gmv_progress": 80.0,   # 销售额目标完成率下限（%）
    "gross_margin": 20.0,   # 毛利率下限（%）
    "return_rate": 4.0,     # 退货率上限（%）
    "aov": 520.0,           # 客单价下限（元）
}

# 指标字典：统一名称、单位、图标、是否"越大越好"
KPI_META = {
    "gmv": {"label": "销售额 GMV", "unit": "元", "icon": "💰", "better": "up", "fmt": "money"},
    "orders": {"label": "订单量", "unit": "单", "icon": "🧾", "better": "up", "fmt": "int"},
    "aov": {"label": "客单价", "unit": "元", "icon": "🛒", "better": "up", "fmt": "money"},
    "gross_margin": {"label": "毛利率", "unit": "%", "icon": "📈", "better": "up", "fmt": "pct"},
    "customers": {"label": "成交客户数", "unit": "人", "icon": "👥", "better": "up", "fmt": "int"},
    "return_rate": {"label": "退货率", "unit": "%", "icon": "↩️", "better": "down", "fmt": "pct"},
}

# 目标：按天设定的销售目标（元/天），用于仪表盘"目标完成率"
DAILY_TARGET = 118_000
