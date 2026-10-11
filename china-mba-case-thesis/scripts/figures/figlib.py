"""示意图辅助模块：用坐标排版生成 SVG，再用无头 Chromium 按 2 倍分辨率截成 PNG。

用法见 example_diagram.py。全文的图都从这里取字体和颜色，保证风格统一；
要换风格只改 STYLE，不在单张图里写颜色值。
依赖：pip install playwright；Chromium（playwright install chromium，或已有的 Chromium）
"""
import html, os, pathlib

STYLE = dict(
    font="'Noto Serif CJK SC','Source Han Serif SC','Songti SC','SimSun',serif",  # 接近宋体的衬线中文字体
    fs=26,            # 默认字号（px），画布约 1500 px 宽时 20–28 较合适
    sw=2,             # 默认线宽
)
# 配色：灰黑线条文字，白/浅灰两档底色，只有一种强调色（及其浅色填充），问题/断点用红色
C = dict(line='#262626', text='#1a1a1a', gray='#595959', lgray='#8c8c8c',
         fill='#ffffff', fill2='#f2f2f2', fill3='#e6e6e6',
         hi='#dbe7f3', hiline='#2f5597', red='#c00000')


class Fig:
    def __init__(s, w, h):
        s.w, s.h = w, h
        s.el = []
        s.markers = set()

    def add(s, x):
        s.el.append(x)

    def text(s, x, y, t, fs=None, anchor='middle', color=None, weight='normal', italic=False):
        """多行文字用 \\n 分隔，以 (x, y) 为整体中心。"""
        fs = fs or STYLE['fs']
        lines = t.split('\n'); lh = fs * 1.3
        y0 = y - (len(lines) - 1) * lh / 2
        it = ' font-style="italic"' if italic else ''
        col = color or C['text']
        for i, l in enumerate(lines):
            s.add(f'<text x="{x:.1f}" y="{y0 + i * lh:.1f}" font-size="{fs}" text-anchor="{anchor}" '
                  f'dominant-baseline="central" fill="{col}" font-weight="{weight}"{it}>{html.escape(l)}</text>')

    def rect(s, x, y, w, h, fill=None, stroke=None, sw=None, dash=False, rx=0):
        d = ' stroke-dasharray="10,6"' if dash else ''
        s.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill or C["fill"]}" '
              f'stroke="{stroke or C["line"]}" stroke-width="{sw or STYLE["sw"]}"{d}/>')

    def box(s, cx, cy, w, h, t='', fs=None, fill=None, stroke=None, sw=None, dash=False, rx=0, weight='normal', color=None):
        """以中心点定位的方框；dash=True 表示组织外部环节（如委外）。返回 (cx, cy, w, h) 便于连线。"""
        s.rect(cx - w / 2, cy - h / 2, w, h, fill, stroke, sw, dash, rx)
        if t:
            s.text(cx, cy, t, fs, color=color, weight=weight)
        return (cx, cy, w, h)

    def line(s, pts, color=None, sw=None, dash=False, arrow=True, start_arrow=False, dasharray='10,6'):
        """折线，pts 为 [(x, y), ...]；默认终点带箭头。"""
        d = 'M ' + ' L '.join(f'{x:.1f} {y:.1f}' for x, y in pts)
        c = color or C['line']; mid = c.replace('#', '')
        s.markers.add(c)
        a = f' marker-end="url(#ah{mid})"' if arrow else ''
        a += f' marker-start="url(#as{mid})"' if start_arrow else ''
        da = f' stroke-dasharray="{dasharray}"' if dash else ''
        s.add(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw or STYLE["sw"]}"{da}{a}/>')

    def diamond(s, cx, cy, w, h, t, fs=None, fill=None):
        """判断框。"""
        pts = f'{cx},{cy - h / 2} {cx + w / 2},{cy} {cx},{cy + h / 2} {cx - w / 2},{cy}'
        s.add(f'<polygon points="{pts}" fill="{fill or C["fill"]}" stroke="{C["line"]}" stroke-width="{STYLE["sw"]}"/>')
        s.text(cx, cy, t, fs or STYLE['fs'] - 2)

    def cross(s, cx, cy, r=13, color=None, sw=4):
        """红色叉号，标记断点或问题。"""
        c = color or C['red']
        s.add(f'<path d="M{cx - r} {cy - r} L{cx + r} {cy + r} M{cx - r} {cy + r} L{cx + r} {cy - r}" '
              f'stroke="{c}" stroke-width="{sw}" stroke-linecap="round"/>')

    def circle(s, cx, cy, r, t='', fs=22, fill='#262626', color='#ffffff', stroke=None):
        """编号圆点。"""
        s.add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke or fill}" stroke-width="2"/>')
        if t:
            s.text(cx, cy, t, fs, color=color, weight='bold')

    def raw(s, x):
        s.add(x)

    def svg(s):
        defs = ''.join(
            f'<marker id="ah{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="16" markerHeight="16" '
            f'markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
            f'<marker id="as{c[1:]}" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="16" markerHeight="16" '
            f'markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>'
            for c in sorted(s.markers))
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{s.w}" height="{s.h}" viewBox="0 0 {s.w} {s.h}" '
                f'font-family="{STYLE["font"]}"><defs>{defs}</defs><rect width="100%" height="100%" fill="#ffffff"/>'
                + '\n'.join(s.el) + '</svg>')

    def save(s, name, outdir='out', png=True):
        """写出 <name>.svg，并截成 <name>.png。name 建议用“图x.x_图题”，与 Word 生成脚本的查找规则一致。
        图内不写图题，图题放在 Word 里。"""
        os.makedirs(outdir, exist_ok=True)
        p = os.path.join(outdir, name + '.svg')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(s.svg())
        if png:
            render(p, os.path.join(outdir, name + '.png'), s.w, s.h)
        return p


def render(svgpath, pngpath, w, h, scale=2):
    from playwright.sync_api import sync_playwright
    exe = os.environ.get('CHROMIUM_PATH')  # 已有 Chromium 时可指定路径，避免另行下载
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={'width': w, 'height': h}, device_scale_factor=scale)
        pg.goto(pathlib.Path(svgpath).resolve().as_uri())   # Windows 路径也能转成合法的 file:/// 地址
        pg.wait_for_timeout(300)
        pg.screenshot(path=pngpath, full_page=False)
        b.close()
