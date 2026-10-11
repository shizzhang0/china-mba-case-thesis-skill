"""数据图示例：柱线组合双轴图。数据直接写在脚本里，并用 assert 与原始台账的合计核对。
    python3 example_datachart.py
中文字体：先运行 extract_cjk_font.py 得到 NotoSerifSC.otf，或把 FONT_FILE 改成本机已有的中文字体文件。
"""
import os, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm, ticker

# 中文字体：先找同目录的字体文件，再按顺序找系统已装的中文字体（Windows 有宋体 / 微软雅黑，Linux 常见 Noto / 思源）
FONT_FILE = 'NotoSerifSC.otf'
CANDIDATES = ['SimSun', 'Songti SC', 'Noto Serif CJK SC', 'Source Han Serif SC', 'Microsoft YaHei', 'Noto Sans CJK SC', 'PingFang SC']
if os.path.exists(FONT_FILE):
    fm.fontManager.addfont(FONT_FILE)
    plt.rcParams['font.family'] = fm.FontProperties(fname=FONT_FILE).get_name()
else:
    installed = {f.name for f in fm.fontManager.ttflist}
    chosen = next((c for c in CANDIDATES if c in installed), None)
    if chosen is None:
        sys.exit('没有可用的中文字体：请先运行 extract_cjk_font.py，或安装宋体 / Noto Serif CJK')
    plt.rcParams['font.family'] = chosen
plt.rcParams['axes.unicode_minus'] = False

# ---- 数据（示例数字，替换成台账里的真实数据）----
months = ['01', '02', '03', '04', '05', '06']
total = [12, 9, 7, 11, 8, 10]       # 每月件数
main = [10, 8, 6, 9, 7, 9]          # 其中主要类型
amount = [8200, 5600, 4300, 7900, 5100, 6600]
assert sum(total) == 57 and sum(main) == 49, '与台账合计不一致'   # 合计必须与原始台账一致
other = [a - b for a, b in zip(total, main)]

# ---- 绘图：灰度柱 + 黑色折线，去掉顶部边框，只留浅色横向网格 ----
fig, ax = plt.subplots(figsize=(6.3, 3.4), dpi=300)
x = range(len(months))
ax.bar(x, main, width=0.6, color='#595959', label='主要类型', zorder=2)
ax.bar(x, other, width=0.6, bottom=main, color='#c8c8c8', label='其他', zorder=2)
for i, t in enumerate(total):
    ax.text(i, t + 0.4, str(t), ha='center', va='bottom', fontsize=7.5)
ax.set_ylabel('件数（件）', fontsize=9)
ax.set_xticks(list(x)); ax.set_xticklabels(months, fontsize=8)
ax.grid(axis='y', color='#e6e6e6', lw=0.6, zorder=0)
ax.spines['top'].set_visible(False)

ax2 = ax.twinx()
ax2.plot(list(x), amount, color='#1f1f1f', lw=1.2, marker='o', ms=3.5, mfc='white', label='金额', zorder=3)
ax2.set_ylabel('金额（元）', fontsize=9)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, p: f'{int(v):,}'.replace(',', ' ')))
ax2.spines['top'].set_visible(False)

h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc='upper right', fontsize=8, frameon=False, ncol=3)
fig.tight_layout()
os.makedirs('out', exist_ok=True)
name = 'out/图9.2_示例数据图'
fig.savefig(name + '.png', dpi=300)
fig.savefig(name + '.svg')
print('已生成', name)
