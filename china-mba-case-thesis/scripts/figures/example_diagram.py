"""示意图示例：一条带外协环节和断点标记的流程。一图一脚本，运行后输出到 out/。
    python3 example_diagram.py
"""
from figlib import Fig, C

W, H = 1500, 360
f = Fig(W, H)
steps = ['接收订单', '工艺设计', '生产加工', '外协加工', '质量检验', '交付客户']
bw, gap = 190, 52
x0 = (W - (len(steps) * bw + (len(steps) - 1) * gap)) / 2
xs = [x0 + bw / 2 + i * (bw + gap) for i in range(len(steps))]
y, bh = 130, 96

for i, (x, t) in enumerate(zip(xs, steps)):
    outside = (t == '外协加工')                     # 组织外部环节用虚线框
    f.box(x, y, bw, bh, t, dash=outside, fill=C['fill2'] if outside else C['fill'])
    if i:
        f.line([(xs[i - 1] + bw / 2 + 4, y), (x - bw / 2 - 4, y)])

# 断点：外协环节的数据没有回到系统
mid = (xs[3] + xs[4]) / 2
f.cross(mid, y - 34)
f.text(mid, y - 72, '数据断点', fs=22, color=C['red'])

# 强调色只用一种：标出改进的范围
f.rect(xs[1] - bw / 2 - 16, y + bh / 2 + 30, xs[4] - xs[1] + bw + 32, 70, fill=C['hi'], stroke=C['hiline'])
f.text((xs[1] + xs[4]) / 2, y + bh / 2 + 65, '改进覆盖的范围', fs=24, color=C['hiline'], weight='bold')

f.save('图9.1_示例流程图')
