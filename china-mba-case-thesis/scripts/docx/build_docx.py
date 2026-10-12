"""把 Markdown 源稿整份生成学位论文 Word。只用 Python 标准库，直接写 OOXML。
    python build_docx.py <配置.json> [输出.docx]
学校格式、封面字段、路径全部来自配置文件；本脚本只保留通用逻辑。源稿写法见 references/源稿约定.md。
"""
import sys, os, re, json, math, zipfile, datetime
from urllib.parse import unquote
from xml.sax.saxutils import escape

sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错

if len(sys.argv) < 2:
    sys.exit('用法：python build_docx.py <配置.json> [输出.docx]')
CFG_PATH = sys.argv[1]
CFG = json.load(open(CFG_PATH, encoding='utf-8-sig'))
BASE = os.path.dirname(os.path.abspath(CFG_PATH))
rel = lambda p: p if os.path.isabs(p) else os.path.join(BASE, p)
SRC = rel(CFG['paths']['src'])
IMG = rel(CFG['paths']['img'])
OUT = os.path.normpath(sys.argv[2] if len(sys.argv) > 2 else rel(CFG['paths'].get('out', 'out.docx')))


def jsround(x):
    return int(math.floor(x + 0.5))


def esc(s):
    return escape(s, {'"': '&quot;'})


# ---------- 字号（中文“号”→ 半磅） ----------
HAO = {'初号': 84, '小初': 72, '一号': 52, '小一': 48, '二号': 44, '小二': 36, '三号': 32, '小三': 30,
       '四号': 28, '小四': 24, '五号': 21, '小五': 18, '六号': 15}


def sz(v):
    return v if isinstance(v, (int, float)) and v else HAO.get(v, 24)


# ---------- 字体：每处同时设西文与中文 ----------
F = CFG['fonts']
FONTS = {'song': (F['song'], F['latin']), 'hei': (F['hei'], F['latin']), 'kai': (F['kai'], F['latin']),
         'coverLatin': (F['song'], F.get('coverLatin', 'Arial'))}
fnt = lambda k: FONTS.get(k) or FONTS['song']

B = CFG['body']
LINE_BODY = {'line': jsround(240 * B.get('lineSpacing', 1.5))}
FIRST = jsround(B.get('firstLineChars', 2) * sz(B['size']) * 10)        # 首行缩进 n 字（twip）
PG = CFG['page']
TEXT_W = PG['widthTw'] - PG['marginTw']['left'] - PG['marginTw']['right']  # 版心宽（twip）
NOTE_RE = re.compile('^(' + '|'.join(CFG.get('noteMarkers', ['资料来源', '注'])) + ')')
CUT_RE = re.compile(CFG.get('cutSectionPattern', r'^##\s*(本章待|待补)'))
ALIGN = {'left': 'left', 'center': 'center', 'right': 'right', 'both': 'both'}


# ---------- 段落与文字 ----------
def rpr(font=None, size=None, bold=False, sup=False, color=None):
    east, latin = font or FONTS['song']
    s = sz(size or B['size'])
    x = f'<w:rFonts w:ascii="{esc(latin)}" w:hAnsi="{esc(latin)}" w:cs="{esc(latin)}" w:eastAsia="{esc(east)}"/>'
    if bold:
        x += '<w:b/><w:bCs/>'
    if color:
        x += f'<w:color w:val="{color}"/>'
    x += f'<w:sz w:val="{s}"/><w:szCs w:val="{s}"/>'
    if sup:
        x += '<w:vertAlign w:val="superscript"/>'
    return '<w:rPr>' + x + '</w:rPr>'


def run(text, **o):
    return f'<w:r>{rpr(**o)}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def runs(text, font=None, size=None, bold=False):
    """行内：<sup>角标</sup>、**加粗**。"""
    out, last = [], 0
    for m in re.finditer(r'<sup>(.*?)</sup>|\*\*(.+?)\*\*', text):
        if m.start() > last:
            out.append(run(text[last:m.start()], font=font, size=size, bold=bold))
        if m.group(1) is not None:
            out.append(run(m.group(1), font=font, size=size, bold=bold, sup=True))
        else:
            out.append(run(m.group(2), font=font, size=size, bold=True))
        last = m.end()
    if last < len(text):
        out.append(run(text[last:], font=font, size=size, bold=bold))
    return ''.join(out)


class Para:
    """段落：pPr 片段按 OOXML 规定的顺序拼接；分节时把 sectPr 放进最后一段的 pPr。"""
    ORDER = ['pStyle', 'keepNext', 'keepLines', 'pBdr', 'tabs', 'spacing', 'ind', 'jc']

    def __init__(self, inner='', **ppr):
        self.inner, self.ppr, self.sect = inner, ppr, ''

    def xml(self):
        p = ''.join(self.ppr[k] for k in self.ORDER if self.ppr.get(k)) + self.sect
        return '<w:p>' + (f'<w:pPr>{p}</w:pPr>' if p else '') + self.inner + '</w:p>'


def spacing(before=None, after=None, line=None):
    a = ''.join(f' w:{k}="{v}"' for k, v in (('before', before), ('after', after)) if v is not None)
    if line is not None:
        a += f' w:line="{line}" w:lineRule="auto"'
    return f'<w:spacing{a}/>'


jc = lambda a: f'<w:jc w:val="{a}"/>'


def body_para(text):
    return Para(runs(text), spacing=spacing(**LINE_BODY), ind=f'<w:ind w:firstLine="{FIRST}"/>', jc=jc('both'))


# ---------- 图 ----------
MEDIA = []   # (文件名, 字节)
RELS = []    # (rId, type, target)
_docpr = [0]


def add_rel(kind, target):
    rid = f'rId{len(RELS) + 1}'
    RELS.append((rid, kind, target))
    return rid


def drawing(data, ext, w_px, h_px):
    name = f'image{len(MEDIA) + 1}.{ext}'
    MEDIA.append((name, data))
    rid = add_rel('image', 'media/' + name)
    _docpr[0] += 1
    cx, cy = w_px * 9525, h_px * 9525
    return (f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{_docpr[0]}" name="图片 {_docpr[0]}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
            f'<pic:nvPicPr><pic:cNvPr id="0" name="{name}"/><pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')


FIG = CFG.get('figures', {})
IMG_FILES = sorted(f for f in os.listdir(IMG) if f.lower().endswith('.png')) if os.path.isdir(IMG) else []


def png_size(b):
    return int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big')


def image_para(num, md_path):
    # 源稿里写的路径存在就直接用（相对源稿目录）；否则按“图x.x_”前缀到配置的图片目录找
    full = os.path.normpath(os.path.join(SRC, unquote(md_path))) if md_path else None
    if not full or not os.path.exists(full):
        f = next((x for x in IMG_FILES if x.startswith(FIG.get('filePrefix', '图') + num + '_')), None)
        if not f:
            sys.exit(f'找不到图片：图 {num}（源稿路径不存在，{IMG} 下也没有以“图{num}_”开头的 PNG）')
        full = os.path.join(IMG, f)
    if not full.lower().endswith('.png'):
        sys.exit('图片须为 PNG：' + full)
    data = open(full, 'rb').read()
    w, h = png_size(data)
    W = FIG.get('widthsPx', {}).get(num) or jsround(FIG.get('defaultWidthCm', 14.5) / 2.54 * 96)
    H = jsround(W * h / w)
    MAXH = FIG.get('maxHeightPx', 780)
    if H > MAXH:
        H = MAXH; W = jsround(H * w / h)
    return Para(drawing(data, 'png', W, H), keepNext='<w:keepNext/>', spacing=spacing(120, 60), jc=jc('center'))


CAP = CFG.get('captions', {})


def caption_para(text, table):
    r = run(text, font=fnt(CAP.get('font', 'hei')), size=CAP.get('size', B['size']), bold=bool(CAP.get('bold')))
    if table:   # 表题在表上，与表同页
        return Para(r, keepNext='<w:keepNext/>', spacing=spacing(200, 80), jc=jc('center'))
    return Para(r, spacing=spacing(60, 120, 300), jc=jc('center'))


def note_para(text, center=False):
    return Para(runs(text, size=CFG.get('table', {}).get('noteSize', '五号')),
                spacing=spacing(40, 160, 280), jc=jc('center' if center else 'left'))


# ---------- 三线表 ----------
T = CFG.get('table', {})


def disp_len(s):
    s = re.sub(r'<[^>]+>|\*\*', '', s)
    return sum(0.55 if ord(c) <= 0xFF else 1 for c in s)


def border(side, kind):
    if kind == 'none':
        return f'<w:{side} w:val="nil"/>'
    size = T.get('outerRule8ths', 12) if kind == 'thick' else T.get('headRule8ths', 6)
    return f'<w:{side} w:val="single" w:sz="{size}" w:space="0" w:color="000000"/>'


def build_table(rows):
    ncol = len(rows[0]); wts = []
    for j in range(ncol):
        lens = [disp_len(r[j] or '') for r in rows]
        mx, avg = max(lens), sum(lens) / len(lens)
        wts.append(max(3, min(math.sqrt(mx) * 2 + avg, 60)))
    tot = sum(wts)
    widths = [jsround(TEXT_W * w / tot) for w in wts]
    mins = [jsround(n * 215 + 220) if (n := disp_len(h)) <= 6 else 0 for h in rows[0]]
    for _ in range(3):   # 短表头的列保证放得下一行
        fixed = [w < m for w, m in zip(widths, mins)]
        if not any(fixed):
            break
        need = sum(m - w for w, m, f in zip(widths, mins, fixed) if f)
        pool = sum(w for w, f in zip(widths, fixed) if not f)
        widths = [m if f else jsround(w - need * w / pool) for w, m, f in zip(widths, mins, fixed)]
    widths[-1] += TEXT_W - sum(widths)
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="{TEXT_W}" w:type="dxa"/><w:jc w:val="center"/>'
           '<w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/><w:bottom w:val="nil"/><w:right w:val="nil"/>'
           '<w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid>']
    out += [f'<w:gridCol w:w="{w}"/>' for w in widths]
    out.append('</w:tblGrid>')
    last = len(rows) - 1
    for i, r in enumerate(rows):
        out.append('<w:tr><w:trPr><w:cantSplit/>' + ('<w:tblHeader/>' if i == 0 else '') + '</w:trPr>')
        top = 'thick' if i == 0 else 'none'
        bottom = 'thin' if i == 0 else ('thick' if i == last else 'none')
        for j, c in enumerate(r):
            c = (c or '').strip()
            p = Para(runs(c, size=T.get('size', '五号'), bold=(i == 0 and T.get('boldHeader', True) is not False)),
                     keepNext='<w:keepNext/>' if i < last else '', keepLines='<w:keepLines/>',
                     spacing=spacing(line=260), jc=jc('center' if (i == 0 or disp_len(c) <= 8) else 'left'))
            out.append(f'<w:tc><w:tcPr><w:tcW w:w="{widths[j]}" w:type="dxa"/><w:tcBorders>'
                       + border('top', top) + border('left', 'none') + border('bottom', bottom) + border('right', 'none')
                       + '</w:tcBorders><w:tcMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
                       '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar><w:vAlign w:val="center"/></w:tcPr>'
                       + p.xml() + '</w:tc>')
        out.append('</w:tr>')
    out.append('</w:tbl>')
    return ''.join(out)


def parse_row(l):
    return [s.strip() for s in re.sub(r'\|$', '', re.sub(r'^\|', '', l.strip())).split('|')]


# ---------- 章节源稿 → 段落 ----------
HEADINGS = []   # (级别, 文字)，用于书签和预填目录


def heading(level, text):
    HEADINGS.append((level, text))
    n = len(HEADINGS)
    return Para(f'<w:bookmarkStart w:id="{n}" w:name="_Toc{n}"/><w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
                f'<w:bookmarkEnd w:id="{n}"/>', pStyle=f'<w:pStyle w:val="Heading{level}"/>')


def convert_chapter(md):
    L = md.splitlines()
    cut = next((k for k, l in enumerate(L) if CUT_RE.search(l)), None)
    if cut is not None:
        L = L[:cut]
    blocks, title, i = [], '', 0
    while i < len(L):
        l = L[i]
        m = re.match(r'^(#{1,3}) (.*)', l)
        if m:
            level = len(m.group(1)); text = m.group(2).strip()
            if level == 1:
                title = text
            blocks.append(heading(level, text)); i += 1; continue
        if l.startswith('!['):
            m = re.search(r'图\s*(\d+\.\d+)', l)
            if not m:
                sys.exit('图片行缺少“图 x.x”：' + l)
            pm = re.search(r'\]\(([^)]+)\)', l)
            blocks.append(image_para(m.group(1), pm.group(1).strip() if pm else None)); i += 1; continue
        if l.startswith('【图'):
            t = re.sub(r'^【|】$', '', l.strip()); blocks.append(caption_para(t, False))
            n = (re.search(r'图\s*(\d+\.\d+)', t) or [None, None])[1]; i += 1
            # 图下紧跟的 > 资料来源/注 行作为图注输出，其余 > 行是写作备注
            j = i
            while j < len(L) and L[j].strip() == '':
                j += 1
            if j < len(L) and L[j].startswith('>'):
                while j < len(L) and L[j].startswith('>'):
                    s = re.sub(r'^>\s*', '', L[j])
                    if NOTE_RE.search(s):
                        blocks.append(note_para(s, True))
                    j += 1
                i = j
            if n and FIG.get('notes', {}).get(n):
                blocks.append(note_para(FIG['notes'][n], True))
            continue
        if l.startswith('【表'):
            blocks.append(caption_para(re.sub(r'^【|】$', '', l.strip()), True)); i += 1; continue
        if l.startswith('|'):
            rows = []
            while i < len(L) and L[i].startswith('|'):
                if not re.match(r'^\|\s*:?-{2,}', L[i]):
                    rows.append(parse_row(L[i]))
                i += 1
            n = max(len(r) for r in rows)
            for r in rows:
                r.extend([''] * (n - len(r)))
            blocks.append(build_table(rows))
            j = i
            while j < len(L) and L[j].strip() == '':
                j += 1
            if j < len(L) and L[j].startswith('>') and NOTE_RE.search(re.sub(r'^>\s*', '', L[j])):
                while j < len(L) and L[j].startswith('>'):
                    t = re.sub(r'^>\s*', '', L[j])
                    if NOTE_RE.search(t):
                        blocks.append(note_para(t))
                    j += 1
                i = j
            else:
                blocks.append(Para(spacing=spacing(after=60)))
            continue
        if l.startswith('>') or re.match(r'^-{3,}\s*$', l) or l.strip() == '':
            i += 1; continue
        blocks.append(body_para(l.strip())); i += 1
    return title, blocks


# ---------- 摘要（中文在前，“# Abstract”之后为英文） ----------
AB = CFG.get('abstract', {})


def convert_abstract(md):
    parts = re.split(r'^# Abstract\s*$', md, maxsplit=1, flags=re.M)

    def make(txt, head, en):
        out = [Para(run(head, font=FONTS['hei'], size=AB.get('headSize', '三号'), bold=not en),
                    spacing=spacing(240, 360), jc=jc('center'))]
        first = True
        for raw in (txt or '').splitlines():
            if raw.startswith('>') or re.match(r'^-{3,}', raw) or raw.startswith('# '):
                continue
            l = raw.strip()
            if not l:
                continue
            if first:   # 第一段是论文题目
                out.append(Para(run(l, size=AB.get('titleSize', '四号')), spacing=spacing(after=240, **LINE_BODY), jc=jc('center')))
                first = False; continue
            if re.match(r'^\*\*(关键词|Key ?words)', l, re.I):
                out.append(Para(run(l.replace('**', ''), bold=True), spacing=spacing(before=360, **LINE_BODY))); continue
            if l.startswith('　　') or re.match(r'^\s{2,}', raw):
                out.append(Para(runs(re.sub(r'^　+', '', l)), spacing=spacing(**LINE_BODY), ind=f'<w:ind w:left="{FIRST}"/>')); continue
            out.append(body_para(l))
        return out
    return make(parts[0], AB.get('zhHead', '摘　　要'), False), (make(parts[1], AB.get('enHead', 'Abstract'), True) if len(parts) > 1 else None)


# ---------- 参考文献 ----------
def convert_refs(md):
    out = [heading(1, CFG.get('referencesTitle', '参考文献'))]
    for l in md.splitlines():
        m = re.match(r'^\[(\d+)\]\s*(.*)$', l)
        if m:
            out.append(Para(run(f'[{m.group(1)}] {m.group(2)}', size=CFG.get('referencesSize', '五号')),
                            spacing=spacing(after=40, line=320), ind=f'<w:ind w:left="{FIRST}" w:hanging="{FIRST}"/>', jc=jc('left')))
    return out


# ---------- 页眉页脚 ----------
HD = CFG.get('header', {}); FT = CFG.get('footer', {})
PARTS = []   # (文件名, 内容类型, xml)
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def add_part(kind, inner):
    n = sum(1 for p in PARTS if p[0].startswith(kind)) + 1
    name = f'{kind}{n}.xml'
    tag = 'hdr' if kind == 'header' else 'ftr'
    PARTS.append((name, kind, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:{tag} {NS}>{inner}</w:{tag}>'))
    return add_rel(kind, name)


def header_with(text):
    if HD.get('enabled') is False:
        return add_part('header', '<w:p/>')
    bdr = '' if HD.get('borderBottom') is False else '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/></w:pBdr>'
    p = Para(run(text, font=fnt(HD.get('font', 'kai')), size=HD.get('size', '小五')), pBdr=bdr, jc=jc(ALIGN[HD.get('align', 'center')]))
    return add_part('header', p.xml())


def footer_page():
    r = rpr(size=FT.get('size', '小五'))
    p = Para(f'<w:r>{r}<w:fldChar w:fldCharType="begin"/></w:r><w:r>{r}<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
             f'<w:r>{r}<w:fldChar w:fldCharType="separate"/></w:r><w:r>{r}<w:t>1</w:t></w:r><w:r>{r}<w:fldChar w:fldCharType="end"/></w:r>',
             jc=jc(ALIGN[FT.get('align', 'right')]))
    return add_part('footer', p.xml())


empty_header = lambda: add_part('header', '<w:p/>')
empty_footer = lambda: add_part('footer', '<w:p/>')
PN = CFG.get('pageNumbers', {})


def sect_pr(hdr, ftr, start=None, fmt=None):
    m = PG['marginTw']
    pn = ''.join(f' w:{k}="{v}"' for k, v in (('fmt', fmt), ('start', start)) if v is not None)
    return (f'<w:sectPr><w:headerReference w:type="default" r:id="{hdr}"/><w:footerReference w:type="default" r:id="{ftr}"/>'
            f'<w:pgSz w:w="{PG["widthTw"]}" w:h="{PG["heightTw"]}"/>'
            f'<w:pgMar w:top="{m["top"]}" w:right="{m["right"]}" w:bottom="{m["bottom"]}" w:left="{m["left"]}" '
            f'w:header="{m.get("header", 851)}" w:footer="{m.get("footer", 992)}" w:gutter="0"/>'
            f'<w:pgNumType{pn}/><w:docGrid w:linePitch="360"/></w:sectPr>')


# ---------- 封面 / 扉页（字段与版式都在配置里） ----------
def render_layout(items):
    out = []
    for it in items or []:
        o = dict(font=fnt(it.get('font')), size=it.get('size', B['size']), bold=bool(it.get('bold')))
        if it.get('blank'):
            out += [Para(run('', **o), spacing=spacing(line=240)) for _ in range(it['blank'])]
        elif it.get('pair'):   # 左右两栏的一行（如“分类号 / 单位代码”）
            out.append(Para(run(it['pair'][0], **o) + '<w:r>' + rpr(**o) + '<w:tab/></w:r>' + run(it['pair'][1], **o),
                            tabs=f'<w:tabs><w:tab w:val="left" w:pos="{it.get("tabTw", 6000)}"/></w:tabs>'))
        elif it.get('image'):
            p = rel(it['image']); ext = os.path.splitext(p)[1].lower().lstrip('.').replace('jpeg', 'jpg')
            px = it.get('px', 113)
            out.append(Para(drawing(open(p, 'rb').read(), ext, px, px), jc=jc('center')))
        elif it.get('rule'):
            out.append(Para(pBdr='<w:pBdr><w:bottom w:val="single" w:sz="8" w:space="1" w:color="000000"/></w:pBdr>',
                            ind='<w:ind w:left="600" w:right="600"/>'))
        elif it.get('info'):   # 标签 + 值，整体左缩进
            out.append(Para(run(it['info'][0], **o) + run(it['info'][1], **o),
                            spacing=spacing(line=440), ind=f'<w:ind w:left="{it.get("indentTw", 2200)}"/>'))
        else:
            out.append(Para(run(it.get('text', ''), **o), spacing=spacing(it.get('before', 0), it.get('after', 0)),
                            jc=jc(ALIGN[it.get('align', 'center')])))
    return out


# ---------- 目录（预填条目，Word 打开时更新页码） ----------
TOC = CFG.get('toc', {})


def toc_blocks():
    lv = TOC.get('levels', '1-3'); lo, hi = (int(x) for x in lv.split('-'))
    title = Para(run(TOC.get('title', '目　　录'), font=FONTS['hei'], size=TOC.get('titleSize', '三号')),
                 spacing=spacing(240, 360), jc=jc('center'))
    begin = (f'<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
             f'<w:r><w:instrText xml:space="preserve"> TOC \\o &quot;{lo}-{hi}&quot; \\h \\z \\u </w:instrText></w:r>'
             '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
    tabs = f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{TEXT_W}"/></w:tabs>'
    paras, first = [], True
    for n, (level, text) in enumerate(HEADINGS, 1):
        if not lo <= level <= hi:
            continue
        entry = (f'<w:hyperlink w:anchor="_Toc{n}" w:history="1"><w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
                 f'<w:r><w:tab/></w:r><w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
                 f'<w:r><w:instrText xml:space="preserve"> PAGEREF _Toc{n} \\h </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink>')
        paras.append(Para((begin if first else '') + entry, pStyle=f'<w:pStyle w:val="TOC{level}"/>', tabs=tabs).xml())
        first = False
    if first:
        paras.append(Para(begin).xml())
    paras.append(Para('<w:r><w:fldChar w:fldCharType="end"/></w:r>').xml())
    sdt = '<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/><w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>' \
          + ''.join(paras) + '</w:sdtContent></w:sdt>'
    return [title, sdt]


# ---------- 组装 ----------
FL = CFG.get('files', {})
abs_zh, abs_en = convert_abstract(open(os.path.join(SRC, FL.get('abstract', '摘要.md')), encoding='utf-8-sig').read())
ch_re = re.compile(FL.get('chapterPattern', r'^第\d+章'))
ch_files = sorted((f for f in os.listdir(SRC) if ch_re.search(f) and f.endswith('.md')),
                  key=lambda f: int(re.search(r'\d+', f).group()))
extras = [convert_chapter(open(os.path.join(SRC, e), encoding='utf-8-sig').read())[1] for e in CFG.get('extraFrontFiles', [])]
chapters = [convert_chapter(open(os.path.join(SRC, f), encoding='utf-8-sig').read()) for f in ch_files]
refs_file = os.path.join(SRC, FL.get('references', '参考文献.md'))
refs = convert_refs(open(refs_file, encoding='utf-8-sig').read()) if os.path.exists(refs_file) else None

FRONT_FMT, BODY_FMT = PN.get('front', 'upperRoman'), PN.get('body', 'decimal')
sections = []   # (块列表, sectPr)
if CFG.get('cover') and CFG['cover'].get('enabled') is not False:
    sections.append((render_layout(CFG['cover'].get('layout')), sect_pr(empty_header(), empty_footer())))
if CFG.get('titlePage') and CFG['titlePage'].get('enabled'):
    sections.append((render_layout(CFG['titlePage'].get('layout')), sect_pr(empty_header(), empty_footer())))
for blocks in extras:   # 可选：声明页等，按普通段落排
    sections.append((blocks, sect_pr(empty_header(), empty_footer())))
sections.append((abs_zh, sect_pr(empty_header(), footer_page(), start=1, fmt=FRONT_FMT)))
if abs_en:
    sections.append((abs_en, sect_pr(empty_header(), footer_page(), fmt=FRONT_FMT)))
toc_index = len(sections)
sections.append((None, sect_pr(empty_header(), footer_page(), fmt=FRONT_FMT)))   # 目录要等全部标题收集完再生成
for k, (title, blocks) in enumerate(chapters):
    sections.append((blocks, sect_pr(header_with(title), footer_page(), start=1 if k == 0 else None, fmt=BODY_FMT)))
if refs:
    sections.append((refs, sect_pr(header_with(CFG.get('referencesTitle', '参考文献')), footer_page(), fmt=BODY_FMT)))
sections[toc_index] = (toc_blocks(), sections[toc_index][1])

body = []
for k, (blocks, sp) in enumerate(sections):
    last = k == len(sections) - 1
    xs = [b.xml() if isinstance(b, Para) else b for b in blocks[:-1]] if blocks else []
    tail = blocks[-1] if blocks else None
    if last:
        xs.append(tail.xml() if isinstance(tail, Para) else (tail or ''))
        body.append(''.join(xs) + sp)
    else:   # 分节符放进本节最后一段；最后是表格或目录时补一个空段承载
        if isinstance(tail, Para):
            tail.sect = sp; xs.append(tail.xml())
        else:
            xs.append(tail or ''); p = Para(); p.sect = sp; xs.append(p.xml())
        body.append(''.join(xs))

document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{"".join(body)}</w:body></w:document>'

# ---------- 样式 ----------
H = CFG.get('headings', [])
hs = lambda i, d: {**d, **(H[i] if i < len(H) else {})}
h_cfg = [hs(0, {'size': '三号', 'bold': True, 'align': 'center'}), hs(1, {'size': '四号', 'bold': True, 'align': 'left'}),
         hs(2, {'size': '小四', 'bold': True, 'align': 'left'})]
h_space = [(240, 480, ''), (360, 240, '<w:keepNext/>'), (240, 120, '<w:keepNext/>')]
toc_ind = TOC.get('indentChars', 1); toc_size = sz(TOC.get('entrySize', '四号'))
styles = [f'<w:docDefaults><w:rPrDefault>{rpr()}</w:rPrDefault><w:pPrDefault/></w:docDefaults>',
          '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>',
          '<w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont"><w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/></w:style>',
          '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:semiHidden/>'
          '<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
          '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>',
          '<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:basedOn w:val="DefaultParagraphFont"/></w:style>']
for k, h in enumerate(h_cfg):
    before, after, keep = h_space[k]
    r = rpr(font=fnt(h.get('font')), size=h['size'], bold=h.get('bold', True), color='000000')
    styles.append(f'<w:style w:type="paragraph" w:styleId="Heading{k + 1}"><w:name w:val="heading {k + 1}"/><w:basedOn w:val="Normal"/>'
                  f'<w:next w:val="Normal"/><w:qFormat/><w:pPr>{keep}{spacing(before, after, 360)}{jc(ALIGN[h["align"]])}'
                  f'<w:outlineLvl w:val="{k}"/></w:pPr>{r}</w:style>')
for k in range(3):
    styles.append(f'<w:style w:type="paragraph" w:styleId="TOC{k + 1}"><w:name w:val="toc {k + 1}"/><w:basedOn w:val="Normal"/>'
                  f'<w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:pPr>{spacing(line=360)}<w:ind w:left="{jsround(k * toc_ind * toc_size * 10)}"/></w:pPr>'
                  f'{rpr(size=toc_size)}</w:style>')
styles_xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {NS}>{"".join(styles)}</w:styles>'
settings_xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings {NS}>'
                '<w:defaultTabStop w:val="420"/><w:characterSpacingControl w:val="compressPunctuation"/><w:updateFields w:val="true"/>'
                '<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
                '</w:settings>')   # updateFields：打开时提示更新域，由 Word 填目录页码

# ---------- 打包 ----------
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
rid_styles = add_rel('styles', 'styles.xml'); rid_settings = add_rel('settings', 'settings.xml')
doc_rels = ''.join(f'<Relationship Id="{i}" Type="{R}{t}" Target="{esc(g)}"/>' for i, t, g in RELS)
CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.'
overrides = ''.join(f'<Override PartName="/word/{n}" ContentType="{CT}{k}+xml"/>' for n, k, _ in PARTS)
content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
                 '<Default Extension="jpg" ContentType="image/jpeg"/>'
                 f'<Override PartName="/word/document.xml" ContentType="{CT}document.main+xml"/>'
                 f'<Override PartName="/word/styles.xml" ContentType="{CT}styles+xml"/>'
                 f'<Override PartName="/word/settings.xml" ContentType="{CT}settings+xml"/>'
                 '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                 f'{overrides}</Types>')
root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             f'<Relationship Id="rId1" Type="{R}officeDocument" Target="word/document.xml"/>'
             '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
             '</Relationships>')
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        '</cp:coreProperties>')

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml', content_types)
    z.writestr('_rels/.rels', root_rels)
    z.writestr('docProps/core.xml', core)
    z.writestr('word/document.xml', document)
    z.writestr('word/styles.xml', styles_xml)
    z.writestr('word/settings.xml', settings_xml)
    z.writestr('word/_rels/document.xml.rels',
               f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{doc_rels}</Relationships>')
    for name, _, xml in PARTS:
        z.writestr('word/' + name, xml)
    for name, data in MEDIA:
        z.writestr('word/media/' + name, data)
print('已生成', OUT, '章数', len(chapters), '大小', os.path.getsize(OUT))
