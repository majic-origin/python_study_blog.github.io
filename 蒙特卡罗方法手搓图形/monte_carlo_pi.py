# -*- coding: utf-8 -*-
"""
蒙特卡罗方法手搓图形 —— 用蒙特卡罗方法估算圆周率 π，并亲手绘制图形
========================================================================
作业：用蒙特卡罗方法“手搓”一个图形（估算 π 的撒点图 + 收敛曲线）。

核心思路（先用处，再原理）：
    用处：蒙特卡罗方法是用“大量随机采样 + 统计”去逼近精确数值的通用手段，
          特别适合那些没有解析解、或者计算起来很麻烦的问题。
    原理：我们往一个边长为 1 的正方形里随机撒点，落在 1/4 圆内的点占比，
          会收敛到圆面积与正方形面积之比 = (π/4) / 1 = π/4，
          所以 π ≈ 4 × (圆内点数 / 总点数)。

“手搓”体现在：随机撒点、判断是否在圆内、统计占比，全部用 Python 原生代码
自己实现，不调用现成的求 π 函数；绘图只借助 matplotlib 把结果画出来。

运行环境：Python 3.x，只需安装 matplotlib（pip install matplotlib）。
"""

import math                # math 库：提供参考值 math.pi，以及画圆弧用的 cos/sin
import random              # random 库：Python 内置，生成 [0,1) 均匀随机数
import matplotlib
matplotlib.use("Agg")               # 用无界面后端：不弹窗口，直接把图形保存成文件
import matplotlib.pyplot as plt     # matplotlib：绘图库，把图形画出来并保存


# ----------------------------------------------------------------------
# 让 matplotlib 正确显示中文字符（Windows 上使用微软雅黑，避免标题乱码）
# ----------------------------------------------------------------------
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False   # 正常显示负号


def estimate_pi(num_points: int) -> float:
    """
    用蒙特卡罗方法估算圆周率 π。

    参数：
        num_points (int): 撒点的总数，越大估算越准（但耗时越长）。

    返回：
        float: 估算得到的 π 值，约为 3.1~3.2 之间的一个数。
    """
    inside_count: int = 0            # int：记录落在 1/4 圆内的点数
    for _ in range(num_points):      # 循环撒 num_points 个点
        x: float = random.random()   # float：横坐标，[0,1) 均匀随机
        y: float = random.random()   # float：纵坐标，[0,1) 均匀随机
        # 判断是否落在四分之一圆内：x² + y² <= 1（单位圆方程）
        if x * x + y * y <= 1.0:
            inside_count += 1        # 圆内，计数加 1
    ratio: float = inside_count / num_points   # float：圆内点的占比
    return 4.0 * ratio               # π ≈ 4 × 圆内占比


def collect_points(num_points: int):
    """
    撒 num_points 个点，把“圆内”和“圆外”的点分别收集起来，供画撒点图使用。

    参数：
        num_points (int): 撒点的总数。

    返回：
        tuple: (圆内x列表, 圆内y列表, 圆外x列表, 圆外y列表)，均为 list[float]。
    """
    in_x: list = []                  # list[float]：圆内点的横坐标
    in_y: list = []                  # list[float]：圆内点的纵坐标
    out_x: list = []                 # list[float]：圆外点的横坐标
    out_y: list = []                 # list[float]：圆外点的纵坐标
    for _ in range(num_points):
        x: float = random.random()
        y: float = random.random()
        if x * x + y * y <= 1.0:     # 在 1/4 圆内
            in_x.append(x)
            in_y.append(y)
        else:                        # 在圆外
            out_x.append(x)
            out_y.append(y)
    return in_x, in_y, out_x, out_y


def plot_scatter(num_points: int, save_path: str = "mc_scatter.png") -> None:
    """
    绘制撒点图：在边长为 1 的正方形里随机撒点，
    圆内用蓝色、圆外用红色，并画出参考的 1/4 圆弧。

    参数：
        num_points (int): 撒点总数。
        save_path (str): 图片保存路径，默认 mc_scatter.png。
    """
    in_x, in_y, out_x, out_y = collect_points(num_points)
    pi_est: float = 4.0 * len(in_x) / num_points   # 由本次撒点算出的 π

    fig, ax = plt.subplots(figsize=(6.2, 6.2))
    ax.scatter(in_x, in_y, s=6, c="steelblue", label="圆内")   # 蓝色点：圆内
    ax.scatter(out_x, out_y, s=6, c="tomato", label="圆外")    # 红色点：圆外

    # 画 1/4 圆弧：x = cosθ, y = sinθ, θ ∈ [0, π/2]
    theta_list: list = [i / 200 * (math.pi / 2) for i in range(201)]
    arc_x: list = [math.cos(t) for t in theta_list]
    arc_y: list = [math.sin(t) for t in theta_list]
    ax.plot(arc_x, arc_y, "k-", lw=2, label="x²+y²=1")

    ax.set_aspect("equal")                       # 保持横纵比例一致，圆形才不变形
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(f"蒙特卡罗估算 π（N={num_points}，π≈{pi_est:.4f}）")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    print(f"撒点图已保存：{save_path}")


def plot_convergence(max_points: int, step: int, save_path: str = "mc_convergence.png") -> None:
    """
    绘制收敛曲线：随着撒点数 N 增加，估算的 π 逐渐逼近真实值 π=3.14159...。

    参数：
        max_points (int): 撒点数的上限（终点）。
        step (int):       采样步长，每隔 step 个点记录一次估算结果。
        save_path (str):  图片保存路径，默认 mc_convergence.png。
    """
    n_list: list = []        # list[int]：横坐标，撒点数 N
    pi_list: list = []       # list[float]：纵坐标，对应的估算 π
    for n in range(step, max_points + 1, step):
        n_list.append(n)
        pi_list.append(estimate_pi(n))     # 每次重新撒 n 个点并估算

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.plot(n_list, pi_list, "o-", lw=1, ms=3, label="估算 π")
    ax.axhline(math.pi, color="red", ls="--", lw=1.5, label="真实 π≈3.14159")
    ax.set_xlabel("撒点数 N")
    ax.set_ylabel("估算的 π")
    ax.set_title("蒙特卡罗估算 π 的收敛性")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    print(f"收敛曲线已保存：{save_path}")


def main() -> None:
    """
    主函数：依次演示三种结果。
    1. 打印 10 万次撒点的估算结果；
    2. 画 5000 个点的撒点图；
    3. 画到 5 万点的收敛曲线。
    """
    # 1) 直接估算：撒 10 万点
    pi_100k: float = estimate_pi(100_000)
    print(f"估算结果（10 万点）：π ≈ {pi_100k:.4f}，"
          f"与真实值误差 ≈ {abs(pi_100k - math.pi):.4f}")

    # 2) 撒点图（适合肉眼观察随机点在圆内/圆外的分布）
    plot_scatter(5000)

    # 3) 收敛曲线（观察估算值如何随点数增加逼近真实值）
    plot_convergence(50_000, step=1000)


if __name__ == "__main__":
    main()
