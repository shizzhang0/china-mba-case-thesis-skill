"""图1.1 技术路线图：自上而下的研究步骤，右侧标出对应章节。  python3 f11.py"""
import _common
from figlib import Fig, C
W, H = 1100, 760; f = Fig(W, H)
cx, bw, bh = 420, 520, 76
rows = [('研究背景与问题提出', '第1章'), ('理论基础与文献综述', '第2章'),
        ('YT公司质量管理现状调研', '第3章'), ('问题识别与原因分析', '第3章'),
        ('改进方案设计', '第4章'), ('实施保障与预期效果', '第5章'), ('结论与展望', '第6章')]
ys = [70 + i * 104 for i in range(len(rows))]
for (t, ch), y in zip(rows, ys):
    f.box(cx, y, bw, bh, t, fill=C['hi'] if ch in ('第3章', '第4章') else C['fill'])
    f.text(cx + bw / 2 + 90, y, ch, fs=24, color=C['gray'])
for a, b in zip(ys, ys[1:]):
    f.line([(cx, a + bh / 2 + 2), (cx, b - bh / 2 - 2)])
f.text(cx + bw / 2 + 90, ys[0] - 58, '对应章节', fs=22, color=C['gray'])
f.save('图1.1_技术路线图', outdir='..')
