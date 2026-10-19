"""
src/theme.py —— 主题与样式注入
=============================
Streamlit 本身只提供"毛坯房"，看板的视觉质感几乎全部来自这一份 CSS。

做法：用 CSS 变量 + 一套 HTML 组件类，实现
  · 亮色 / 暗色一键切换（所有颜色都走变量，图表颜色由 Python 侧同步传入）
  · 面板化布局（卡片圆角 + 细边框 + 柔和阴影）
  · 组件渐入动画、预警闪烁、实时状态呼吸灯
  · 响应式：宽度 < 1100px 自动降级为单列，避免大屏排版在笔记本上错位
"""

from __future__ import annotations

from string import Template

import streamlit as st

from config import THEMES

_CSS = Template(
    """
<style>
:root{
  --bg:${bg};
  --bg-grad:${bg_grad};
  --panel:${panel};
  --panel-alt:${panel_alt};
  --text:${text};
  --muted:${muted};
  --border:${border};
  --grid:${grid};
  --shadow:${shadow};
  --brand:#2563EB;
  --brand-soft:#93B4FD;
  --accent:#F59E0B;
  --danger:#EF4444;
  --success:#16A34A;
  --radius:16px;
}

/* ---------- 基础排版 ---------- */
html, body, .stApp{
  font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB","Noto Sans CJK SC",
              -apple-system,"Segoe UI",sans-serif;
}
/* 图标字体必须保护：否则全局字体覆盖会把 material 图标渲染成 "keyboard_arrow_right" 这样的字面量 */
[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded, .material-symbols-outlined{
  font-family:"Material Symbols Rounded","Material Icons",sans-serif !important;
}
.stApp{ background:var(--bg-grad); color:var(--text); }
[data-testid="stHeader"]{ background:transparent; }
[data-testid="stToolbar"]{ right:.8rem; }
#MainMenu, footer{ visibility:hidden; }
[data-testid="stAppDeployButton"]{ display:none; }   /* 隐藏 Deploy 按钮，保持成品感 */
[data-testid="stStatusWidget"]{ display:none; }
.block-container{ padding:1.2rem 2.2rem 3rem; max-width:1600px; }

h1,h2,h3,h4,p,span,label,div{ color:var(--text); }
a{ color:var(--brand); }

/* ---------- 侧边栏 ---------- */
[data-testid="stSidebar"]{
  background:var(--panel);
  border-right:1px solid var(--border);
}
[data-testid="stSidebar"] > div:first-child{ padding-top:.8rem; }
[data-testid="stSidebar"] hr{ border-color:var(--border); }
[data-testid="stWidgetLabel"] p{
  color:var(--muted) !important; font-size:.78rem !important;
  letter-spacing:.02em; font-weight:500;
}

/* ---------- 控件外观 ---------- */
/* 输入控件外壳：新版 Streamlit 用 react-aria，直接认 data-testid 最稳 */
[data-testid="stMultiSelect"] div[role="group"],
[data-testid="stDateInputField"]{
  background:var(--panel-alt) !important;
  border:1px solid var(--border) !important;
  border-radius:10px !important;
}
[data-testid="stMultiSelect"] input{ background:transparent !important; color:var(--text) !important; }
[data-testid="stMultiSelect"] input::placeholder{ color:var(--muted) !important; opacity:1 !important; }
[data-testid="stDateInputField"] span,
[data-testid="stDateInputField"] input{ color:var(--text) !important; }
[data-testid="stDateInputField"] svg{ color:var(--muted) !important; }
[data-baseweb="select"] > div,
[data-baseweb="input"] > div,
.stTextInput input, .stNumberInput input{
  background:var(--panel-alt) !important;
  border-color:var(--border) !important;
  color:var(--text) !important;
}
[data-baseweb="tag"]{
  background:rgba(37,99,235,.12) !important;
  color:var(--brand) !important;
  border-radius:8px !important;
}
[data-baseweb="popover"] li{ color:var(--text); }
[data-testid="stDateInput"] input{ color:var(--text) !important; }

.stButton > button, .stDownloadButton > button{
  background:var(--panel-alt); color:var(--text);
  border:1px solid var(--border); border-radius:11px;
  font-size:.85rem; font-weight:500; transition:all .18s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover{
  border-color:var(--brand); color:var(--brand);
  box-shadow:0 0 0 3px rgba(37,99,235,.10);
}

[data-testid="stExpander"] details{
  background:var(--panel); border:1px solid var(--border);
  border-radius:14px; overflow:hidden;
}
[data-testid="stExpander"] summary{ font-size:.86rem; color:var(--text); }
[data-testid="stExpander"] summary:hover{ color:var(--brand); }

/* ---------- 指标卡 iframe：高度跟随栅格换行 ---------- */
iframe[title="st.iframe"]{ height:116px !important; }
[data-testid="stIFrame"],
[data-testid="stElementContainer"]:has(> [data-testid="stIFrame"]),
[data-testid="stCustomComponentV1"]{ height:auto !important; }
@media (max-width:1180px){
  iframe[title="st.iframe"]{ height:232px !important; }   /* 3 列 -> 2 行 */
}
@media (max-width:640px){
  iframe[title="st.iframe"]{ height:348px !important; }   /* 2 列 -> 3 行 */
}

/* ---------- 图表 / 表格 卡片化 ---------- */
[data-testid="stPlotlyChart"]{
  background:var(--panel);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:4px 8px 2px;
  box-shadow:var(--shadow);
  transition:box-shadow .25s ease, transform .25s ease;
}
[data-testid="stPlotlyChart"]:hover{
  box-shadow:0 12px 32px -14px rgba(37,99,235,.35);
}
[data-testid="stDataFrame"], [data-testid="stTable"]{
  border:1px solid var(--border); border-radius:14px; overflow:hidden;
  background:var(--panel);
}
[data-testid="stMetric"]{
  background:var(--panel); border:1px solid var(--border);
  border-radius:var(--radius); padding:.7rem .9rem;
}

/* ---------- 自研组件：页头 ---------- */
.dash-head{
  display:flex; align-items:flex-end; justify-content:space-between;
  gap:16px; flex-wrap:wrap;
  padding:6px 4px 16px;
  border-bottom:1px solid var(--border);
  margin-bottom:14px;
}
.dash-head .brand{ display:flex; align-items:center; gap:12px; }
.dash-head .mark{
  width:42px; height:42px; border-radius:13px; flex:none;
  display:grid; place-items:center; font-size:20px;
  background:linear-gradient(135deg,#2563EB,#60A5FA);
  box-shadow:0 8px 20px -8px rgba(37,99,235,.7);
}
.dash-head h1{
  font-size:1.42rem; font-weight:700; margin:0; letter-spacing:.01em; line-height:1.2;
}
.dash-head .sub{ font-size:.76rem; color:var(--muted); margin-top:3px; letter-spacing:.06em; }
.chips{ display:flex; gap:8px; flex-wrap:wrap; }
.chip{
  display:inline-flex; align-items:center; gap:6px;
  padding:5px 11px; border-radius:999px;
  background:var(--panel); border:1px solid var(--border);
  font-size:.74rem; color:var(--muted); white-space:nowrap;
}
.chip b{ color:var(--text); font-weight:600; }
.chip .dot{ width:7px; height:7px; border-radius:50%; background:var(--success); }
.chip.live .dot{ animation:pulse 1.6s infinite; }

/* ---------- 自研组件：分区标题 ---------- */
.sec{ display:flex; align-items:center; gap:10px; margin:6px 0 10px; }
.sec .bar{ width:4px; height:17px; border-radius:3px; background:linear-gradient(180deg,#2563EB,#60A5FA); }
.sec .no{
  font-size:.68rem; font-weight:700; color:var(--brand);
  background:rgba(37,99,235,.10); padding:2px 7px; border-radius:6px; letter-spacing:.06em;
}
.sec .tt{ font-size:1rem; font-weight:650; color:var(--text); }
.sec .ds{ font-size:.75rem; color:var(--muted); margin-left:2px; }

/* ---------- 自研组件：排行榜 ---------- */
.rank{ display:flex; flex-direction:column; gap:9px; }
.rank-row{ display:grid; grid-template-columns:22px 1fr auto; align-items:center; gap:10px; }
.rank-row .idx{
  font-size:.72rem; font-weight:700; color:var(--muted); text-align:center;
}
.rank-row.top1 .idx{ color:#fff; background:linear-gradient(135deg,#F59E0B,#FBBF24); border-radius:6px; }
.rank-row .meta{ font-size:.82rem; color:var(--text); display:flex; align-items:baseline; gap:6px; }
.rank-row .meta small{ color:var(--muted); font-size:.72rem; }
.rank-row .track{ height:6px; border-radius:99px; background:var(--grid); overflow:hidden; margin-top:5px; }
.rank-row .fill{
  height:100%; border-radius:99px;
  background:linear-gradient(90deg,#60A5FA,#2563EB);
  animation:grow .8s cubic-bezier(.2,.8,.2,1) both;
}
.rank-row .val{ font-size:.82rem; font-weight:650; color:var(--text); font-variant-numeric:tabular-nums; }

/* ---------- 自研组件：预警条 ---------- */
.alert{
  display:flex; align-items:flex-start; gap:10px;
  padding:10px 14px; border-radius:12px; margin-bottom:8px;
  font-size:.82rem; border:1px solid transparent;
}
.alert.warn{ background:rgba(245,158,11,.10); border-color:rgba(245,158,11,.35); color:#B45309; }
.alert.danger{ background:rgba(239,68,68,.10); border-color:rgba(239,68,68,.35); color:#B91C1C; }
.alert.ok{ background:rgba(22,163,74,.08); border-color:rgba(22,163,74,.30); color:#15803D; }
.alert .ico{ font-size:.95rem; line-height:1.2; }
.alert.danger .ico{ animation:blink 1.4s infinite; }
.alert b{ font-weight:650; }

/* ---------- 自研组件：数据质量 ---------- */
.qa-line{ display:flex; justify-content:space-between; font-size:.8rem; padding:4px 0; border-bottom:1px dashed var(--border); }
.qa-line:last-child{ border-bottom:none; }
.qa-line .k{ color:var(--muted); }
.qa-line .v{ color:var(--text); font-weight:600; font-variant-numeric:tabular-nums; }

/* ---------- 自研组件：钻取提示 ---------- */
.drill{
  display:inline-flex; align-items:center; gap:8px;
  padding:6px 12px; border-radius:10px; font-size:.8rem;
  background:rgba(37,99,235,.08); border:1px solid rgba(37,99,235,.25); color:var(--brand);
}

/* ---------- 动画 ---------- */
@keyframes fadeUp{ from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:none;} }
@keyframes grow{ from{width:0;} }
@keyframes pulse{ 0%,100%{opacity:1; transform:scale(1);} 50%{opacity:.35; transform:scale(.82);} }
@keyframes blink{ 0%,100%{opacity:1;} 50%{opacity:.25;} }

[data-testid="stVerticalBlockBorderWrapper"]{ animation:fadeUp .45s ease both; }
[data-testid="stPlotlyChart"]{ animation:fadeUp .55s ease both; }

/* ---------- 响应式：笔记本 / 平板 / 手机 ---------- */
@media (max-width: 1280px){
  .block-container{ padding:1rem 1.2rem 2.4rem; }
  .dash-head h1{ font-size:1.24rem; }
}
@media (max-width: 900px){
  .block-container{ padding:.8rem .7rem 2rem; }
  .dash-head{ align-items:flex-start; }
  .dash-head h1{ font-size:1.08rem; }
  .chips{ width:100%; }
  .chip{ font-size:.68rem; padding:4px 9px; }
  .sec .ds{ display:none; }
  [data-testid="stPlotlyChart"]{ padding:2px 4px 0; }
}
</style>
"""
)


def inject_theme(mode: str = "light") -> dict:
    """注入 CSS 并返回当前主题的 token 字典（图表、HTML 组件都从它取色）。"""
    tokens = THEMES.get(mode, THEMES["light"])
    st.markdown(_CSS.safe_substitute(**tokens), unsafe_allow_html=True)
    return tokens
