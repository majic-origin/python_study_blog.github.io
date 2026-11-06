# Python turtle 绘制田字格

> 一篇面向初学者的实操笔记：用 Python 自带的 `turtle` 海龟绘图库，画出带米字辅助线（水平中线 + 垂直中线）的田字格，并在格子中央写入汉字或英文字符。文末附上虚拟环境下 `tkinter` 找不到 Tcl/Tk 库的常见报错及修复方法。

## 一、这个项目是用来干什么的

**用途**：这是一份 Python 课程作业，目标是用代码在窗口里批量绘制"田字格"（一个正方形外框 + 一条水平中线 + 一条垂直中线），并可在格心写字，效果类似小学练字本上的格子。

**为什么用 `turtle`**：

- **开箱即用**：`turtle` 是 Python 标准库的一部分，`pip` 不需要安装，`import turtle` 就能用，适合课堂作业。
- **类比现实中的海龟**：可以把它理解成一只画笔海龟，你告诉它"向前走多少、右转多少度"，它就在屏幕上画线，直观理解坐标系和角度。
- **适合教学**：所有绘图动作都是显式指令（移动、落笔、转向、写文字），方便拆解讲解循环、函数封装、参数传递等基础语法。

**可扩展方向**：把 `draw_tian_grid()` 封装好之后，画一行字帖、一页练字纸、多行列阵都只是重复调用函数 + 修改坐标的事。

## 二、完整可复制代码

```python
import os

# 虚拟环境运行时保留这两行，放在最前面
# 手动指定 Tcl/Tk 运行时库路径，解决 venv 下找不到 tkinter 依赖的问题
os.environ['TCL_LIBRARY'] = r"C:\Program Files\Python313\tcl\tcl8.6"
os.environ['TK_LIBRARY'] = r"C:\Program Files\Python313\tcl\tk8.6"

import turtle

# ---------- 1. 创建绘图窗口 ----------
screen = turtle.Screen()          # Screen 类型：屏幕对象
screen.title("田字格绘制")         # 窗口标题（字符串 str）
screen.setup(800, 600)            # 窗口宽 800、高 600（单位：像素 int）
screen.bgcolor("white")           # 背景色（字符串 str）

# ---------- 2. 创建画笔 ----------
pen = turtle.Turtle()              # Turtle 类型：海龟画笔对象
pen.speed(0)                      # 画笔速度，0 为最快（无动画延迟）
# pen.hideturtle()                 # 可选：隐藏海龟箭头

# ---------- 3. 封装：绘制单个田字格 ----------
def draw_tian_grid(start_x, start_y, size, char=""):
    """
    绘制单个田字格
    :param start_x: 左上角 x 坐标（float/int）
    :param start_y: 左上角 y 坐标（float/int）
    :param size:    格子边长（float/int，单位：像素）
    :param char:    需要写在田字格中间的字符（str，默认为空串，即画空格）
    """
    half = size / 2                # half: float，边长的一半，用于定位两条中线

    # 移动到左上角，不落笔
    pen.penup()
    pen.goto(start_x, start_y)
    pen.pendown()

    # 1. 画外框正方形：前进 size，右转 90 度，重复 4 次
    for _ in range(4):
        pen.forward(size)
        pen.right(90)

    # 2. 画水平中线：移到左边中点，向右画一条横线
    pen.penup()
    pen.goto(start_x, start_y - half)
    pen.pendown()
    pen.forward(size)

    # 3. 画垂直中线：移到上边中点，转向朝下画一条竖线
    pen.penup()
    pen.goto(start_x + half, start_y)
    pen.pendown()
    pen.right(90)                  # 顺时针转 90°，朝向由"右"变为"下"
    pen.forward(size)
    pen.left(90)                   # 转回朝向"右"，复位画笔方向

    # 4. 在田字格中心写入字符（char 非空时才写）
    if char != "":
        pen.penup()
        pen.goto(start_x + half, start_y - size + 8)  # 定位到格子中下部，8px 为基线微调
        pen.write(char, align="center", font=("SimHei", 72))

# ========== 调用示例 ==========
# 画 3 个并排田字格，分别写：字、符、A（横向间距 150，格子边长 120）
draw_tian_grid(-300, 100, 120, "字")
draw_tian_grid(-150, 100, 120, "符")
draw_tian_grid(0, 100, 120, "A")

# 画一个单独的空白田字格（不传 char，使用默认值 ""）
draw_tian_grid(150, 100, 120)

turtle.done()                    # 保持窗口显示，直到手动关闭
```

## 三、分步实现讲解

### 3.1 准备工作：屏幕与画笔

```python
screen = turtle.Screen()
screen.setup(800, 600)
pen = turtle.Turtle()
pen.speed(0)
```

- `screen` 是窗口对象，负责标题、尺寸、背景色；
- `pen` 是画笔对象，所有画线动作都通过它发出；
- `speed(0)` 表示最快绘制，作业演示时不会慢慢画线。

### 3.2 函数 `draw_tian_grid` 的参数约定

| 参数 | 数据类型 | 含义 |
|---|---|---|
| `start_x` | `int` / `float` | 田字格**左上角**的 x 坐标 |
| `start_y` | `int` / `float` | 田字格**左上角**的 y 坐标 |
| `size` | `int` / `float` | 正方形边长，单位像素 |
| `char` | `str`，默认 `""` | 格心文字；不传就画空格 |

> 注意：我们约定 `start_x, start_y` 是**左上角**，而不是中心，这一点和 `turtle` 默认从原点出发的习惯不同，后续所有中线坐标都基于这个约定推算。

### 3.3 画外框正方形（循环 4 次）

```python
pen.goto(start_x, start_y)
for _ in range(4):
    pen.forward(size)   # 向前走一个边长
    pen.right(90)       # 顺时针右转 90°
```

海龟默认朝向**右（东）**。从左上角出发：右走一条边 → 右转朝下 → 下走一条边 → 右转朝左 → ……重复 4 次正好闭合一个正方形，这是 `turtle` 里画正方形的经典写法。

### 3.4 画两条中线

```python
# 水平中线：y = start_y - half，从左走到右
pen.goto(start_x, start_y - half)
pen.forward(size)

# 垂直中线：x = start_x + half，从上走到下
pen.goto(start_x + half, start_y)
pen.right(90)
pen.forward(size)
pen.left(90)   # 复位朝向，避免影响下一次绘图
```

两条线都要先 `penup()` 抬笔移动，否则移动过程会把多余的辅助线画出来。画完竖线后用 `left(90)` 把朝向转回来，保持画笔状态干净。

### 3.5 在格子中央写字符

```python
if char != "":
    pen.goto(start_x + half, start_y - size + 8)
    pen.write(char, align="center", font=("SimHei", 72))
```

- `align="center"`：文字以落点为中心水平居中；
- `font=("SimHei", 72)`：黑体、72 号字；
- `start_y - size + 8`：`turtle.write` 的 y 坐标是**文字基线**位置，直接落到格子中心会显得字偏上，`+8` 是手动微调让视觉居中。

### 3.6 调用：一排 4 个格子

```python
draw_tian_grid(-300, 100, 120, "字")
draw_tian_grid(-150, 100, 120, "符")
draw_tian_grid(0, 100, 120, "A")
draw_tian_grid(150, 100, 120)
```

格子边长 120，相邻左上角 x 相差 150，因此格子之间留出 30px 间隙，不会粘连。

## 四、初学者容易卡住的知识点

### 4.1 turtle 坐标系：原点在窗口正中心，y 轴向上为正

`turtle` 窗口的坐标原点 `(0, 0)` 在**屏幕中心**，不是左上角；x 向右为正，y **向上为正**。所以代码里 `start_y = 100` 表示在中心偏上的位置，`start_y - size` 才是格子底边。

### 4.2 角度：`right(90)` 是顺时针，`left(90)` 是逆时针

默认朝右（0°）：`right(90)` 后朝下，`left(90)` 后朝上。画竖线时先 `right(90)` 朝下，画完必须 `left(90)` 复位，否则下一个格子的外框方向就错了。

### 4.3 抬笔 `penup()` / 落笔 `pendown()` 的区别

- `penup()`：移动画笔但不画线（用于跳到下一个绘图起点）；
- `pendown()`：移动时画线。

忘记 `penup()` 是初学者最常见的 bug：格子之间会多出一串连线。

### 4.4 虚拟环境报错：`Can't find Tcl library` / `No module named tkinter`

在 venv 虚拟环境里直接 `import turtle` 时，经常报找不到 Tcl/Tk 运行时库，原因是虚拟环境没有继承系统 Python 的 tcl/tk 路径。代码开头这两行就是修复手段：

```python
os.environ['TCL_LIBRARY'] = r"C:\Program Files\Python313\tcl\tcl8.6"
os.environ['TK_LIBRARY'] = r"C:\Program Files\Python313\tcl\tk8.6"
```

- 必须放在 `import turtle` **之前**；
- 路径里的 `Python313`、`tcl8.6` 要替换成你本机实际安装的版本号（在系统 Python 安装目录的 `tcl` 文件夹下查看）；
- 前面的 `r"..."` 是原始字符串，避免 Windows 反斜杠 `\` 被当成转义符。

### 4.5 字体 `SimHei` 显示不出汉字怎么办

`SimHei`（黑体）是 Windows 自带字体；在 macOS / Linux 上可换成 `"PingFang SC"`、`"Noto Sans CJK SC"` 等系统中文字体，否则汉字会显示成方块。

## 五、运行方式

1. 把代码保存为 `tian_grid.py`；
2. 命令行执行：

```bash
python tian_grid.py
```

3. 弹出 800×600 白色窗口，显示"字 / 符 / A"三个带中线的田字格和一个空格，关闭窗口后程序结束（`turtle.done()` 保证窗口不会一闪而过）。

## 六、可以自己动手改的练习

- 把 4 个格子改成 2 行 2 列，体会用双重循环批量计算坐标；
- 把 `char` 参数改成从列表 `["我", "爱", "编", "程"]` 依次传入；
- 给外框换成红色、中线换成灰色虚线（`pen.pencolor()`、`pen.pensize()`、`pen.screen.colormode()`）；
- 尝试画米字格（再加两条对角线），作为下一次作业的延伸。
