"""图3.1 YT公司组织结构图。  python3 f31.py"""
import _common
from figlib import Fig, C
W, H = 1500, 420; f = Fig(W, H)
f.box(750, 70, 220, 70, '总经理')
depts = ['生产部', '技术部', '质量部', '信息部', '销售部', '采购部', '财务部', '办公室']
n = len(depts); bw, gap = 150, 30; x0 = (W - (n * bw + (n - 1) * gap)) / 2
xs = [x0 + bw / 2 + i * (bw + gap) for i in range(n)]
f.line([(750, 105), (750, 170)], arrow=False)
f.line([(xs[0], 170), (xs[-1], 170)], arrow=False)
for x, d in zip(xs, depts):
    f.line([(x, 170), (x, 212)], arrow=False)
    hi = d in ('生产部', '技术部', '质量部', '采购部')
    f.box(x, 250, bw, 76, d, fs=24, fill=C['hi'] if hi else C['fill'])
f.box(xs[0], 360, bw, 60, '注塑车间', fs=22, fill=C['fill2'])
f.line([(xs[0], 288), (xs[0], 330)], arrow=False)
f.text(1320, 360, '底色为与本文直接相关的部门', fs=20, color=C['gray'])
f.save('图3.1_YT公司组织结构图', outdir='..')
