"""图3.2 YT公司注塑生产流程图：主流程 + 分支，外协用虚线框。  python3 f32.py"""
import _common
from figlib import Fig, C
W, H = 1500, 420; f = Fig(W, H)
main = ['原料干燥', '注塑成型', '去浇口', '检验', '包装入库']
bw, gap, y, bh = 190, 70, 120, 90
x0 = (W - (len(main) * bw + (len(main) - 1) * gap)) / 2
xs = [x0 + bw / 2 + i * (bw + gap) for i in range(len(main))]
for i, (x, t) in enumerate(zip(xs, main)):
    f.box(x, y, bw, bh, t, fill=C['hi'] if t == '注塑成型' else C['fill'])
    if i: f.line([(xs[i - 1] + bw / 2 + 4, y), (x - bw / 2 - 4, y)])
# 分支：喷涂 / 组装，在去浇口之后、检验之前
bx = (xs[2] + xs[3]) / 2
f.box(xs[2], 290, bw, 76, '喷涂', fs=24)
f.box(xs[3], 290, bw, 76, '组装（嵌件）', fs=24)
f.line([(xs[2], y + bh / 2 + 2), (xs[2], 290 - 40)])
f.line([(xs[2] + bw / 2 + 2, 290), (xs[3] - bw / 2 - 2, 290)])
f.line([(xs[3], 290 - 40), (xs[3], y + bh / 2 + 2)])
f.text(bx, 350, '喷涂件 / 组装件走分支，本色件直接检验', fs=20, color=C['gray'])
# 外协：模具维修
f.box(xs[1], 290, bw, 76, '模具维修（外协）', fs=22, dash=True, fill=C['fill2'])
f.line([(xs[1], 290 - 40), (xs[1], y + bh / 2 + 2)], dash=True, start_arrow=True, arrow=True)
f.save('图3.2_YT公司注塑生产流程图', outdir='..')
