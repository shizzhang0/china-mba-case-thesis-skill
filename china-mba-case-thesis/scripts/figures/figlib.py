"""示意图辅助模块：按像素坐标排版（原点在左上角，y 向下），用 matplotlib 输出 SVG 和 2 倍分辨率 PNG。

用法见 example_diagram.py。全文的图都从这里取字体和颜色，保证风格统一；
要换风格只改 STYLE 和 C，不在单张图里写颜色值。
依赖：pip install matplotlib
"""
import math, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager, patches, patheffects

STYLE = dict(
    fonts=['SimSun', 'Songti SC', 'Noto Serif CJK SC', 'Source Han Serif SC', 'STSong'],  # 接近宋体的衬线中文字体，按顺序取第一个已安装的
    latin=['Times New Roman', 'Liberation Serif', 'DejaVu Serif'],                          # 西文字体，与论文正文的“宋体 + Times New Roman”一致
    fs=26,            # 默认字号（px），画布约 1500 px 宽时 20–28 较合适
    sw=2,             # 默认线宽（px）
)
# 配色：灰黑线条文字，白/浅灰两档底色，只有一种强调色（及其浅色填充），问题/断点用红色
C = dict(line='#262626', text='#1a1a1a', gray='#595959', lgray='#8c8c8c',
         fill='#ffffff', fill2='#f2f2f2', fill3='#e6e6e6',
         hi='#dbe7f3', hiline='#2f5597', red='#c00000')

DPI = 100                 # 1 px = 1/100 英寸，坐标与字号都按 px 写
PT = 72 / DPI             # px → pt
_installed = {f.name for f in font_manager.fontManager.ttflist}
_font = next((f for f in STYLE['fonts'] if f in _installed), None)
if _font is None:
    raise SystemExit('没有可用的中文衬线字体：Windows 有宋体即可；Linux 装 Noto Serif CJK，或先运行 extract_cjk_font.py')
_latin = next((f for f in STYLE['latin'] if f in _installed), None)
# 字体按顺序回退：西文字符用 _latin，它没有的字形（中文）再用 _font
plt.rcParams.update({'font.family': [f for f in (_latin, _font) if f], 'svg.fonttype': 'path', 'lines.scale_dashes': False})


class Fig:
    def __init__(s, w, h):
        s.w, s.h = w, h
        s.fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI, facecolor='white')
        s.ax = s.fig.add_axes([0, 0, 1, 1])
        s.ax.set_xlim(0, w); s.ax.set_ylim(h, 0); s.ax.axis('off')

    def text(s, x, y, t, fs=None, anchor='middle', color=None, weight='normal', italic=False):
        """多行文字用 \\n 分隔，以 (x, y) 为整体中心。anchor：start / middle / end。"""
        fs = fs or STYLE['fs']
        lines = t.split('\n'); lh = fs * 1.3
        y0 = y - (len(lines) - 1) * lh / 2
        ha = {'start': 'left', 'middle': 'center', 'end': 'right'}[anchor]
        col = color or C['text']
        # 宋体没有粗体字形，加粗用同色描边模拟
        fx = [patheffects.withStroke(linewidth=fs * PT * 0.06, foreground=col)] if weight == 'bold' else None
        for i, l in enumerate(lines):
            s.ax.text(x, y0 + i * lh, l, fontsize=fs * PT, ha=ha, va='center', color=col,
                      fontstyle='italic' if italic else 'normal', path_effects=fx, zorder=5)

    def rect(s, x, y, w, h, fill=None, stroke=None, sw=None, dash=False, rx=0):
        kw = dict(facecolor=fill or C['fill'], edgecolor=stroke or C['line'], linewidth=(sw or STYLE['sw']) * PT, zorder=2)
        if dash:
            kw['linestyle'] = (0, (10 * PT, 6 * PT))
        if rx:
            p = patches.FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={rx}', **kw)
        else:
            p = patches.Rectangle((x, y), w, h, **kw)
        s.ax.add_patch(p)

    def box(s, cx, cy, w, h, t='', fs=None, fill=None, stroke=None, sw=None, dash=False, rx=0, weight='normal', color=None):
        """以中心点定位的方框；dash=True 表示组织外部环节（如委外）。返回 (cx, cy, w, h) 便于连线。"""
        s.rect(cx - w / 2, cy - h / 2, w, h, fill, stroke, sw, dash, rx)
        if t:
            s.text(cx, cy, t, fs, color=color, weight=weight)
        return (cx, cy, w, h)

    def _head(s, tip, frm, color):
        """在 tip 处画实心三角箭头（长 16 px、宽 16 px），返回箭头底边中点，线画到这里为止。"""
        dx, dy = tip[0] - frm[0], tip[1] - frm[1]
        d = math.hypot(dx, dy) or 1
        ux, uy = dx / d, dy / d
        bx, by = tip[0] - ux * 16, tip[1] - uy * 16
        s.ax.add_patch(patches.Polygon([tip, (bx - uy * 8, by + ux * 8), (bx + uy * 8, by - ux * 8)],
                                       closed=True, facecolor=color, edgecolor='none', zorder=4))
        return (bx + ux * 1, by + uy * 1)

    def line(s, pts, color=None, sw=None, dash=False, arrow=True, start_arrow=False, dasharray='10,6'):
        """折线，pts 为 [(x, y), ...]；默认终点带箭头。"""
        c = color or C['line']; pts = [tuple(p) for p in pts]
        if arrow:
            pts[-1] = s._head(pts[-1], pts[-2], c)
        if start_arrow:
            pts[0] = s._head(pts[0], pts[1], c)
        kw = dict(color=c, linewidth=(sw or STYLE['sw']) * PT, solid_capstyle='butt', zorder=3)
        if dash:
            on, off = (float(v) for v in dasharray.split(','))
            kw['linestyle'] = (0, (on * PT, off * PT))
        s.ax.plot([p[0] for p in pts], [p[1] for p in pts], **kw)

    def diamond(s, cx, cy, w, h, t, fs=None, fill=None):
        """判断框。"""
        s.ax.add_patch(patches.Polygon([(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)], closed=True,
                                       facecolor=fill or C['fill'], edgecolor=C['line'], linewidth=STYLE['sw'] * PT, zorder=2))
        s.text(cx, cy, t, fs or STYLE['fs'] - 2)

    def cross(s, cx, cy, r=13, color=None, sw=4):
        """红色叉号，标记断点或问题。"""
        c = color or C['red']
        for (x1, y1), (x2, y2) in (((cx - r, cy - r), (cx + r, cy + r)), ((cx - r, cy + r), (cx + r, cy - r))):
            s.ax.plot([x1, x2], [y1, y2], color=c, linewidth=sw * PT, solid_capstyle='round', zorder=4)

    def circle(s, cx, cy, r, t='', fs=22, fill='#262626', color='#ffffff', stroke=None):
        """编号圆点。"""
        s.ax.add_patch(patches.Circle((cx, cy), r, facecolor=fill, edgecolor=stroke or fill, linewidth=2 * PT, zorder=4))
        if t:
            s.text(cx, cy, t, fs, color=color, weight='bold')

    def save(s, name, outdir='out', png=True):
        """写出 <name>.svg，并输出 2 倍分辨率的 <name>.png。name 建议用“图x.x_图题”，与 Word 生成脚本的查找规则一致。
        图内不写图题，图题放在 Word 里。"""
        os.makedirs(outdir, exist_ok=True)
        p = os.path.join(outdir, name + '.svg')
        s.fig.savefig(p, facecolor='white')
        if png:
            s.fig.savefig(os.path.join(outdir, name + '.png'), dpi=DPI * 2, facecolor='white')
        plt.close(s.fig)
        return p
