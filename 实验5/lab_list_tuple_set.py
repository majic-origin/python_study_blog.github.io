"""
实验：Python 列表、元组、集合 综合实训
课程：Python 程序设计        学时：2
说明：全部为 Python 标准库，无第三方依赖，Python 3.6+ 可直接运行。
"""


# ============================================================
# 任务1  切片删除深度探究
# 预判：
#   ls1  del ls1[::3]  -> 删除下标 0,3,6,9      -> [1, 2, 4, 5, 7, 8]
#   ls2  del ls2[1::3] -> 删除下标 1,4,7        -> [0, 2, 3, 5, 6, 8, 9]
#   ls3  del ls3[::-2] -> 删除下标 5,3,1        -> [0, 2, 4]
#   ls4  边遍历边 remove -> 结果不是 [1,3,5]，实际 [1, 3, 5]（有漏删）
# ============================================================
def task1():
    print("=" * 60)
    print("任务1  切片删除深度探究")
    print("=" * 60)

    # 1. 步长为 3 的正向切片删除
    ls1 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    print("ls1 原始：", ls1)
    del ls1[::3]
    print("del ls1[::3] 之后：", ls1)

    # 2. 起点为 1、步长为 3 的切片删除
    ls2 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    print("\nls2 原始：", ls2)
    del ls2[1::3]
    print("del ls2[1::3] 之后：", ls2)

    # 3. 负步长切片删除（从尾部往前）
    ls3 = [0, 1, 2, 3, 4, 5]
    print("\nls3 原始：", ls3)
    del ls3[::-2]
    print("del ls3[::-2] 之后：", ls3)

    # 4. 拓展坑：for 循环中边遍历边删
    ls4 = [1, 2, 3, 4, 5, 6]
    print("\nls4 原始：", ls4)
    for i in ls4:
        if i % 2 == 0:
            ls4.remove(i)
    print("循环删除偶数结果：", ls4)

    # 5. 追加验证：漏删的直观证据  、问题根源：**遍历列表的同时修改原列表，列表索引会自动前移，迭代器跟着错位**
    ls5 = [2, 4, 6, 8]
    print("\n[漏删证据] ls5 原始：", ls5)
    for i in ls5:
        if i % 2 == 0:
            ls5.remove(i)
    print("循环删除偶数结果：", ls5, "  <- 4 被漏掉了")

    # 6. 安全写法：用副本遍历，或列表推导式重建
    ls6 = [1, 2, 3, 4, 5, 6]
    for i in ls6[:]:                      # 遍历副本
        if i % 2 == 0:
            ls6.remove(i)
    print("[安全写法1 遍历副本]：", ls6)

    ls7 = [1, 2, 3, 4, 5, 6]
    ls7 = [x for x in ls7 if x % 2 != 0]  # 重建列表
    print("[安全写法2 列表推导式]：", ls7)

    # 7. 切片删除是一次性按原索引计算的证据
    ls8 = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    del ls8[1:8:2]                        # 删除 1,3,5,7
    print("\n[一次性计算证据] del ls8[1:8:2] ->", ls8)


# ============================================================
# 任务2  嵌套容器与可哈希深度辨析
# 结论：(1,2,3) 可哈希；frozenset 可哈希；
#       (1,[2,3])、[1,2]、{1,2} 均不可哈希 -> TypeError
# ============================================================
def task2():
    print("\n" + "=" * 60)
    print("任务2  嵌套容器与可哈希深度辨析")
    print("=" * 60)

    cases = [
        ("(1, 2, 3)",          lambda: (1, 2, 3)),
        ("(1, [2, 3])",        lambda: (1, [2, 3])),
        ("[1, 2]",             lambda: [1, 2]),
        ("frozenset({1, 2})",  lambda: frozenset({1, 2})),
        ("{1, 2}",             lambda: {1, 2}),
    ]

    s = set()
    for expr, maker in cases:
        try:
            s.add(maker())
            print("s.add(%-20s)  -> 成功" % expr)
        except TypeError as e:
            print("s.add(%-20s)  -> 报错：TypeError: %s" % (expr, e))

    print("\n最终集合内容：", s)

    # 逐个对象单独判定可哈希性
    print("\n--- hash() 直接验证 ---")
    for expr, maker in cases:
        obj = maker()
        try:
            hash(obj)
            print("hash(%-20s) 可用" % expr)
        except TypeError:
            print("hash(%-20s) 不可用（unhashable）" % expr)

    # 思考：集合里放集合 -> 用 frozenset
    outer = {frozenset({1, 2}), frozenset({3, 4})}
    print("\n用 frozenset 实现“集合套集合”：", outer)


# ============================================================
# 任务3  集合全部运算 + 集合推导式
# ============================================================
def task3():
    print("\n" + "=" * 60)
    print("任务3  集合全部运算 + 集合推导式")
    print("=" * 60)

    A = {2, 4, 6, 8, 10, 12}
    B = {3, 6, 9, 12, 15}
    print("A =", A)
    print("B =", B)

    print("\n交集   A & B :", A & B, "（同时属于 A 和 B）")
    print("并集   A | B :", A | B, "（属于 A 或 B）")
    print("差集   A - B :", A - B, "（属于 A 不属于 B）")
    print("差集   B - A :", B - A, "（属于 B 不属于 A）")
    print("对称差 A ^ B :", A ^ B, "（只属于其中一个）")

    # 用方法形式再算一遍，验证与运算符等价
    print("\n--- 方法形式验证 ---")
    print("A.intersection(B) :", A.intersection(B))
    print("A.union(B)        :", A.union(B))
    print("A.difference(B)   :", A.difference(B))
    print("A.symmetric_difference(B) :", A.symmetric_difference(B))

    # 集合推导式：1~30 中能被 4 整除的数
    set_compre = {x for x in range(1, 31) if x % 4 == 0}
    print("\n集合推导式 {x for x in range(1,31) if x % 4 == 0} ：")
    print(sorted(set_compre), " 共", len(set_compre), "个")

    # 补充：嵌套推导式与条件表达式
    odd_square = {x * x for x in range(1, 11) if x % 2 == 1}
    print("1~10 中奇数的平方集合：", sorted(odd_square))


# ============================================================
# 任务4  去重算法对比（保序 vs 无序）
# ============================================================
def task4():
    print("\n" + "=" * 60)
    print("任务4  去重算法对比")
    print("=" * 60)

    data = [5, 2, 7, 2, 5, 9, 7, 3, 9, 1]
    print("原始列表：", data)

    # 方案1：set 去重（丢失顺序）
    res1 = list(set(data))
    print("\n方案1 list(set(data)) ：", res1, "  <- 顺序被打乱")

    # 方案2：手写保序去重
    res2 = []
    for num in data:
        if num not in res2:
            res2.append(num)
    print("方案2 手写保序去重   ：", res2, "  <- 保留首次出现顺序")

    # 拓展：dict.fromkeys 一行保序去重
    res3 = list(dict.fromkeys(data))
    print("拓展  dict.fromkeys   ：", res3, "  <- 一行且保序")

    # 拓展：集合推导式 + sorted 也不能恢复原始顺序（说明为什么）
    print("\n注意：sorted(set(data)) =", sorted(set(data)), "得到的是升序，不是原始顺序")


# ============================================================
# 任务5  综合设计题（必做）
# ============================================================
def task5():
    print("\n" + "=" * 60)
    print("任务5  综合设计题：学生选课统计")
    print("=" * 60)

    class1 = [101, 103, 105, 107, 109, 103, 101]
    class2 = [102, 104, 106, 108, 109, 107, 102]
    print("1班选课编号（原始）：", class1)
    print("2班选课编号（原始）：", class2)

    # ① 分别获取两个班不重复的选课编号（保序）
    s1_list = list(dict.fromkeys(class1))
    s2_list = list(dict.fromkeys(class2))
    print("\n① 1班去重（保序）：", s1_list)
    print("   2班去重（保序）：", s2_list)

    s1 = set(class1)
    s2 = set(class2)

    # ② 同时选两门课
    both = s1 & s2
    print("\n② 同时选两门课（交集）：", sorted(both), " 共", len(both), "人")

    # ③ 只选其中一门课（对称差）
    only_one = s1 ^ s2
    print("③ 只选其中一门（对称差）：", sorted(only_one), " 共", len(only_one), "人")

    # ④ 选了1班但没选2班
    only_c1 = s1 - s2
    print("④ 选1班未选2班（差集）：", sorted(only_c1), " 共", len(only_c1), "人")

    # ⑤ 交集结果转元组
    t_both = tuple(sorted(both))
    print("⑤ 交集转元组：", t_both)
    print("   再放回集合：", {t_both}, "  （元组元素全是 int，可哈希，所以能放进集合）")

    # 附加：维恩图分区，一次性输出全部 4 个区域
    print("\n--- 附加：四区域分区统计 ---")
    print("只选1班   :", sorted(s1 - s2))
    print("只选2班   :", sorted(s2 - s1))
    print("两班都选  :", sorted(s1 & s2))
    print("至少选一门:", sorted(s1 | s2))
    print("校验：|A∪B| =", len(s1 | s2),
          "= |A|+|B|-|A∩B| =", len(s1), "+", len(s2), "-", len(s1 & s2),
          "=", len(s1) + len(s2) - len(s1 & s2))


# ============================================================
# 拓展题  嵌套列表去重
# ============================================================
def task_extra():
    print("\n" + "=" * 60)
    print("拓展题  嵌套列表去重")
    print("=" * 60)

    nest = [[1, 2], [3, 4], [1, 2], [5, 6]]
    print("原始嵌套列表：", nest)

    # 内层 list 不可哈希 -> 先转 tuple，去重后再转回 list
    seen = set()
    result = []
    for item in nest:
        key = tuple(item)          # 转成可哈希的元组
        if key not in seen:
            seen.add(key)
            result.append(list(key))   # 按需转回列表
    print("去重结果（保序）：", result)

    # 一行写法
    one_line = [list(t) for t in dict.fromkeys(tuple(x) for x in nest)]
    print("一行写法        ：", one_line)

    # 反证：直接 set(nest) 会怎样
    try:
        set(nest)
    except TypeError as e:
        print("直接 set(nest) 报错：TypeError:", e)


if __name__ == "__main__":
    task1()
    task2()
    task3()
    task4()
    task5()
    task_extra()
    print("\n" + "=" * 60)
    print("全部任务执行完毕")
    print("=" * 60)
