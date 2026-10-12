"""图3.3 近12个月客户投诉件数与损失金额（示例数据）。  python3 f33.py"""
import os, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, ticker
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错
CANDIDATES = ['SimSun', 'Songti SC', 'Noto Serif CJK SC', 'Source Han Serif SC', 'Microsoft YaHei', 'Noto Sans CJK SC']
installed = {f.name for f in fm.fontManager.ttflist}
plt.rcParams['font.family'] = next((c for c in CANDIDATES if c in installed), 'sans-serif')
plt.rcParams['axes.unicode_minus'] = False
m = ['2025-10', '2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09']
tot = [11, 9, 8, 7, 4, 9, 10, 8, 9, 8, 7, 8]
dim = [5, 4, 3, 3, 2, 4, 4, 3, 4, 3, 3, 3]      # 尺寸超差
app = [4, 3, 3, 2, 1, 3, 3, 3, 3, 3, 2, 3]      # 外观缺陷
oth = [a - b - c for a, b, c in zip(tot, dim, app)]
amt = [16800, 13200, 11900, 9800, 5600, 13500, 15100, 12400, 13800, 12100, 10200, 12600]
assert sum(tot) == 98 and sum(dim) == 41 and sum(app) == 33, '与台账合计不一致'
fig, ax = plt.subplots(figsize=(6.3, 3.4), dpi=300); x = range(len(m))
ax.bar(x, dim, width=0.6, color='#595959', label='尺寸超差', zorder=2)
ax.bar(x, app, width=0.6, bottom=dim, color='#9e9e9e', label='外观缺陷', zorder=2)
ax.bar(x, oth, width=0.6, bottom=[a + b for a, b in zip(dim, app)], color='#d0d0d0', label='其他', zorder=2)
for i, t in enumerate(tot): ax.text(i, t + 0.3, str(t), ha='center', va='bottom', fontsize=7.5)
ax.set_ylabel('投诉件数（件）', fontsize=9); ax.set_ylim(0, 16)
ax.set_xticks(list(x)); ax.set_xticklabels(m, rotation=45, ha='right', fontsize=7.5); ax.tick_params(axis='y', labelsize=8)
ax.grid(axis='y', color='#e6e6e6', lw=0.6, zorder=0); ax.spines['top'].set_visible(False)
ax2 = ax.twinx()
ax2.plot(list(x), amt, color='#1f1f1f', lw=1.2, marker='o', ms=3.5, mfc='white', label='损失金额', zorder=3)
ax2.set_ylabel('损失金额（元）', fontsize=9); ax2.set_ylim(0, 25000); ax2.tick_params(axis='y', labelsize=8)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f'{int(v):,}'.replace(',', ' '))); ax2.spines['top'].set_visible(False)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc='upper right', fontsize=8, frameon=False, ncol=4)
fig.tight_layout()
name = '../图3.3_YT公司近12个月客户投诉件数与损失金额'
fig.savefig(name + '.png', dpi=300); fig.savefig(name + '.svg'); print('已生成', name)
