"""把 Markdown 源稿整份生成学位论文 Word。只用 Python 标准库，直接写 OOXML。
    python build_docx.py <配置.json> [输出.docx]
学校格式、封面字段、路径全部来自配置文件；本脚本只保留通用逻辑。源稿写法见 references/源稿约定.md。
生成后打印各章汉字数，供对照学校的字数要求。

也可以在别的脚本里导入使用：
    from build_docx import Builder, load_config
    b = Builder(*load_config('配置.json'))
    b.build('输出.docx')          # 生成 Word，返回输出路径
    b.word_counts()               # 只统计字数，不生成 Word：[(名称, 汉字数), ...]
"""
import sys, os, re, json, math, zipfile, datetime
from urllib.parse import unquote
from xml.sax.saxutils import escape


class BuildError(Exception):
    """源稿或配置有问题，无法生成。命令行运行时打印信息后退出。"""


# ---------- 通用工具（与配置无关） ----------
def jsround(x):
    return int(math.floor(x + 0.5))


def esc(s):
    return escape(s, {'"': '&quot;'})


# 字号：中文“号”→ 半磅
HAO = {'初号': 84, '小初': 72, '一号': 52, '小一': 48, '二号': 44, '小二': 36, '三号': 32, '小三': 30,
       '四号': 28, '小四': 24, '五号': 21, '小五': 18, '六号': 15}


def sz(v):
    return v if isinstance(v, (int, float)) and v else HAO.get(v, 24)


ALIGN = {'left': 'left', 'center': 'center', 'right': 'right', 'both': 'both'}
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'


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


def jc(a):
    return f'<w:jc w:val="{a}"/>'


def png_size(b):
    return int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big')


def disp_len(s):
    s = re.sub(r'<[^>]+>|\*\*', '', s)
    return sum(0.55 if ord(c) <= 0xFF else 1 for c in s)


def parse_row(l):
    return [s.strip() for s in re.sub(r'\|$', '', re.sub(r'^\|', '', l.strip())).split('|')]


# ---------- 字数（只数汉字，不含写作备注、图片行和章末待办） ----------
CJK = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')   # CJK 统一汉字及扩展 A、兼容汉字
DEFAULT_NOTE_RE = re.compile('^(资料来源|注)')
DEFAULT_CUT_RE = re.compile(r'^##\s*(本章待|待补)')


def cjk_count(md, note_re=DEFAULT_NOTE_RE, cut_re=DEFAULT_CUT_RE):
    L = md.splitlines()
    cut = next((k for k, l in enumerate(L) if cut_re.search(l)), None)
    if cut is not None:
        L = L[:cut]
    keep = [l for l in L if not l.startswith('![') and not (l.startswith('>') and not note_re.search(re.sub(r'^>\s*', '', l)))]
    return len(CJK.findall('\n'.join(keep)))


def abstract_body_count(md, note_re=DEFAULT_NOTE_RE, cut_re=DEFAULT_CUT_RE):
    """中文摘要只数正文：去掉第一段题目和关键词及其后的内容。"""
    zh = re.split(r'^# Abstract\s*$', md, maxsplit=1, flags=re.M)[0]
    L = [l for l in zh.splitlines() if l.strip() and not l.startswith('>') and not l.startswith('# ')]
    k = next((i for i, l in enumerate(L) if re.match(r'^\*\*(关键词|Key ?words)', l.strip(), re.I)), len(L))
    return cjk_count('\n'.join(L[1:k]), note_re, cut_re)


def load_config(path):
    """读配置，返回 (配置, 配置文件所在目录)；配置里的相对路径都相对这个目录。"""
    return json.load(open(path, encoding='utf-8-sig')), os.path.dirname(os.path.abspath(path))


class Builder:
    """一次生成用一个 Builder：转换过程中收集的图片、关系、页眉页脚和标题都存在实例上。"""

    def __init__(self, cfg, base='.'):
        self.cfg, self.base = cfg, base
        self.src = self.rel(cfg['paths']['src'])
        self.img = self.rel(cfg['paths']['img'])
        F = cfg['fonts']
        # 字体：每处同时设西文与中文
        self.fonts = {'song': (F['song'], F['latin']), 'hei': (F['hei'], F['latin']), 'kai': (F['kai'], F['latin']),
                      'coverLatin': (F['song'], F.get('coverLatin', 'Arial'))}
        self.B = cfg['body']
        self.line_body = {'line': jsround(240 * self.B.get('lineSpacing', 1.5))}
        self.first = jsround(self.B.get('firstLineChars', 2) * sz(self.B['size']) * 10)        # 首行缩进 n 字（twip）
        self.pg = cfg['page']
        self.text_w = self.pg['widthTw'] - self.pg['marginTw']['left'] - self.pg['marginTw']['right']  # 版心宽（twip）
        self.note_re = re.compile('^(' + '|'.join(cfg.get('noteMarkers', ['资料来源', '注'])) + ')')
        self.cut_re = re.compile(cfg.get('cutSectionPattern', r'^##\s*(本章待|待补)'))
        self.fig = cfg.get('figures', {})
        self.cap = cfg.get('captions', {})
        self.T = cfg.get('table', {})
        self.ab = cfg.get('abstract', {})
        self.hd, self.ft = cfg.get('header', {}), cfg.get('footer', {})
        self.pn = cfg.get('pageNumbers', {})
        self.toc = cfg.get('toc', {})
        self.fl = cfg.get('files', {})
        self.img_files = sorted(f for f in os.listdir(self.img) if f.lower().endswith('.png')) if os.path.isdir(self.img) else []
        # 转换过程中收集的内容
        self.media = []      # (文件名, 字节)
        self.rels = []       # (rId, type, target)
        self.parts = []      # (文件名, 内容类型, xml)
        self.headings = []   # (级别, 文字)，用于书签和预填目录
        self.docpr = 0

    def rel(self, p):
        return p if os.path.isabs(p) else os.path.join(self.base, p)

    def fnt(self, k):
        return self.fonts.get(k) or self.fonts['song']

    # ---------- 段落与文字 ----------
    def rpr(self, font=None, size=None, bold=False, sup=False, color=None):
        east, latin = font or self.fonts['song']
        s = sz(size or self.B['size'])
        x = f'<w:rFonts w:ascii="{esc(latin)}" w:hAnsi="{esc(latin)}" w:cs="{esc(latin)}" w:eastAsia="{esc(east)}"/>'
        if bold:
            x += '<w:b/><w:bCs/>'
        if color:
            x += f'<w:color w:val="{color}"/>'
        x += f'<w:sz w:val="{s}"/><w:szCs w:val="{s}"/>'
        if sup:
            x += '<w:vertAlign w:val="superscript"/>'
        return '<w:rPr>' + x + '</w:rPr>'

    def run(self, text, **o):
        return f'<w:r>{self.rpr(**o)}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'

    def runs(self, text, font=None, size=None, bold=False):
        """行内：<sup>角标</sup>、**加粗**。"""
        out, last = [], 0
        for m in re.finditer(r'<sup>(.*?)</sup>|\*\*(.+?)\*\*', text):
            if m.start() > last:
                out.append(self.run(text[last:m.start()], font=font, size=size, bold=bold))
            if m.group(1) is not None:
                out.append(self.run(m.group(1), font=font, size=size, bold=bold, sup=True))
            else:
                out.append(self.run(m.group(2), font=font, size=size, bold=True))
            last = m.end()
        if last < len(text):
            out.append(self.run(text[last:], font=font, size=size, bold=bold))
        return ''.join(out)

    def body_para(self, text):
        return Para(self.runs(text), spacing=spacing(**self.line_body), ind=f'<w:ind w:firstLine="{self.first}"/>', jc=jc('both'))

    # ---------- 图 ----------
    def add_rel(self, kind, target):
        rid = f'rId{len(self.rels) + 1}'
        self.rels.append((rid, kind, target))
        return rid

    def drawing(self, data, ext, w_px, h_px):
        name = f'image{len(self.media) + 1}.{ext}'
        self.media.append((name, data))
        rid = self.add_rel('image', 'media/' + name)
        self.docpr += 1
        n = self.docpr
        cx, cy = w_px * 9525, h_px * 9525
        return (f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
                f'<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{n}" name="图片 {n}"/>'
                '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
                '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
                f'<pic:nvPicPr><pic:cNvPr id="0" name="{name}"/><pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')

    def image_para(self, num, md_path):
        # 源稿里写的路径存在就直接用（相对源稿目录）；否则按“图x.x_”前缀到配置的图片目录找
        full = os.path.normpath(os.path.join(self.src, unquote(md_path))) if md_path else None
        if not full or not os.path.exists(full):
            f = next((x for x in self.img_files if x.startswith(self.fig.get('filePrefix', '图') + num + '_')), None)
            if not f:
                raise BuildError(f'找不到图片：图 {num}（源稿路径不存在，{self.img} 下也没有以“图{num}_”开头的 PNG）')
            full = os.path.join(self.img, f)
        if not full.lower().endswith('.png'):
            raise BuildError('图片须为 PNG：' + full)
        data = open(full, 'rb').read()
        w, h = png_size(data)
        W = self.fig.get('widthsPx', {}).get(num) or jsround(self.fig.get('defaultWidthCm', 14.5) / 2.54 * 96)
        H = jsround(W * h / w)
        MAXH = self.fig.get('maxHeightPx', 780)
        if H > MAXH:
            H = MAXH; W = jsround(H * w / h)
        return Para(self.drawing(data, 'png', W, H), keepNext='<w:keepNext/>', spacing=spacing(120, 60), jc=jc('center'))

    def caption_para(self, text, table):
        r = self.run(text, font=self.fnt(self.cap.get('font', 'hei')), size=self.cap.get('size', self.B['size']), bold=bool(self.cap.get('bold')))
        if table:   # 表题在表上，与表同页
            return Para(r, keepNext='<w:keepNext/>', spacing=spacing(200, 80), jc=jc('center'))
        return Para(r, spacing=spacing(60, 120, 300), jc=jc('center'))

    def note_para(self, text, center=False):
        return Para(self.runs(text, size=self.T.get('noteSize', '五号')),
                    spacing=spacing(40, 160, 280), jc=jc('center' if center else 'left'))

    # ---------- 三线表 ----------
    def border(self, side, kind):
        if kind == 'none':
            return f'<w:{side} w:val="nil"/>'
        size = self.T.get('outerRule8ths', 12) if kind == 'thick' else self.T.get('headRule8ths', 6)
        return f'<w:{side} w:val="single" w:sz="{size}" w:space="0" w:color="000000"/>'

    def build_table(self, rows):
        T, text_w = self.T, self.text_w
        ncol = len(rows[0]); wts = []
        for j in range(ncol):
            lens = [disp_len(r[j] or '') for r in rows]
            mx, avg = max(lens), sum(lens) / len(lens)
            wts.append(max(3, min(math.sqrt(mx) * 2 + avg, 60)))
        tot = sum(wts)
        widths = [jsround(text_w * w / tot) for w in wts]
        mins = [jsround(n * 215 + 220) if (n := disp_len(h)) <= 6 else 0 for h in rows[0]]
        for _ in range(3):   # 短表头的列保证放得下一行
            fixed = [w < m for w, m in zip(widths, mins)]
            if not any(fixed):
                break
            need = sum(m - w for w, m, f in zip(widths, mins, fixed) if f)
            pool = sum(w for w, f in zip(widths, fixed) if not f)
            widths = [m if f else jsround(w - need * w / pool) for w, m, f in zip(widths, mins, fixed)]
        widths[-1] += text_w - sum(widths)
        out = [f'<w:tbl><w:tblPr><w:tblW w:w="{text_w}" w:type="dxa"/><w:jc w:val="center"/>'
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
                p = Para(self.runs(c, size=T.get('size', '五号'), bold=(i == 0 and T.get('boldHeader', True) is not False)),
                         keepNext='<w:keepNext/>' if i < last else '', keepLines='<w:keepLines/>',
                         spacing=spacing(line=260), jc=jc('center' if (i == 0 or disp_len(c) <= 8) else 'left'))
                out.append(f'<w:tc><w:tcPr><w:tcW w:w="{widths[j]}" w:type="dxa"/><w:tcBorders>'
                           + self.border('top', top) + self.border('left', 'none') + self.border('bottom', bottom) + self.border('right', 'none')
                           + '</w:tcBorders><w:tcMar><w:top w:w="40" w:type="dxa"/><w:left w:w="80" w:type="dxa"/>'
                           '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar><w:vAlign w:val="center"/></w:tcPr>'
                           + p.xml() + '</w:tc>')
            out.append('</w:tr>')
        out.append('</w:tbl>')
        return ''.join(out)

    # ---------- 章节源稿 → 段落 ----------
    def heading(self, level, text):
        self.headings.append((level, text))
        n = len(self.headings)
        return Para(f'<w:bookmarkStart w:id="{n}" w:name="_Toc{n}"/><w:r><w:t xml:space="preserve">{esc(text)}</w:t></w:r>'
                    f'<w:bookmarkEnd w:id="{n}"/>', pStyle=f'<w:pStyle w:val="Heading{level}"/>')

    def convert_chapter(self, md):
        L = md.splitlines()
        cut = next((k for k, l in enumerate(L) if self.cut_re.search(l)), None)
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
                blocks.append(self.heading(level, text)); i += 1; continue
            if l.startswith('!['):
                m = re.search(r'图\s*([A-Z\d]+\.\d+)', l)   # 正文“图 3.1”，附录“图 A.1”
                if not m:
                    raise BuildError('图片行缺少“图 x.x”或“图 A.x”：' + l)
                pm = re.search(r'\]\(([^)]+)\)', l)
                blocks.append(self.image_para(m.group(1), pm.group(1).strip() if pm else None)); i += 1; continue
            if l.startswith('【图'):
                t = re.sub(r'^【|】$', '', l.strip()); blocks.append(self.caption_para(t, False))
                n = (re.search(r'图\s*([A-Z\d]+\.\d+)', t) or [None, None])[1]; i += 1
                # 图下紧跟的 > 资料来源/注 行作为图注输出，其余 > 行是写作备注
                j = i
                while j < len(L) and L[j].strip() == '':
                    j += 1
                if j < len(L) and L[j].startswith('>'):
                    while j < len(L) and L[j].startswith('>'):
                        s = re.sub(r'^>\s*', '', L[j])
                        if self.note_re.search(s):
                            blocks.append(self.note_para(s, True))
                        j += 1
                    i = j
                if n and self.fig.get('notes', {}).get(n):
                    blocks.append(self.note_para(self.fig['notes'][n], True))
                continue
            if l.startswith('【表'):
                blocks.append(self.caption_para(re.sub(r'^【|】$', '', l.strip()), True)); i += 1; continue
            if l.startswith('|'):
                rows = []
                while i < len(L) and L[i].startswith('|'):
                    if not re.match(r'^\|\s*:?-{2,}', L[i]):
                        rows.append(parse_row(L[i]))
                    i += 1
                n = max(len(r) for r in rows)
                for r in rows:
                    r.extend([''] * (n - len(r)))
                blocks.append(self.build_table(rows))
                j = i
                while j < len(L) and L[j].strip() == '':
                    j += 1
                if j < len(L) and L[j].startswith('>') and self.note_re.search(re.sub(r'^>\s*', '', L[j])):
                    while j < len(L) and L[j].startswith('>'):
                        t = re.sub(r'^>\s*', '', L[j])
                        if self.note_re.search(t):
                            blocks.append(self.note_para(t))
                        j += 1
                    i = j
                else:
                    blocks.append(Para(spacing=spacing(after=60)))
                continue
            if l.startswith('>') or re.match(r'^-{3,}\s*$', l) or l.strip() == '':
                i += 1; continue
            blocks.append(self.body_para(l.strip())); i += 1
        return title, blocks

    # ---------- 摘要（中文在前，“# Abstract”之后为英文） ----------
    def convert_abstract(self, md):
        parts = re.split(r'^# Abstract\s*$', md, maxsplit=1, flags=re.M)
        ab = self.ab

        def make(txt, head, en):
            out = [Para(self.run(head, font=self.fonts['hei'], size=ab.get('headSize', '三号'), bold=not en),
                        spacing=spacing(240, 360), jc=jc('center'))]
            first = True
            for raw in (txt or '').splitlines():
                if raw.startswith('>') or re.match(r'^-{3,}', raw) or raw.startswith('# '):
                    continue
                l = raw.strip()
                if not l:
                    continue
                if first:   # 第一段是论文题目
                    out.append(Para(self.run(l, size=ab.get('titleSize', '四号')), spacing=spacing(after=240, **self.line_body), jc=jc('center')))
                    first = False; continue
                if re.match(r'^\*\*(关键词|Key ?words)', l, re.I):
                    out.append(Para(self.run(l.replace('**', ''), bold=True), spacing=spacing(before=360, **self.line_body))); continue
                if l.startswith('　　') or re.match(r'^\s{2,}', raw):
                    out.append(Para(self.runs(re.sub(r'^　+', '', l)), spacing=spacing(**self.line_body), ind=f'<w:ind w:left="{self.first}"/>')); continue
                out.append(self.body_para(l))
            return out
        return make(parts[0], ab.get('zhHead', '摘　　要'), False), (make(parts[1], ab.get('enHead', 'Abstract'), True) if len(parts) > 1 else None)

    # ---------- 参考文献 ----------
    def convert_refs(self, md):
        out = [self.heading(1, self.cfg.get('referencesTitle', '参考文献'))]
        for l in md.splitlines():
            m = re.match(r'^\[(\d+)\]\s*(.*)$', l)
            if m:
                out.append(Para(self.run(f'[{m.group(1)}] {m.group(2)}', size=self.cfg.get('referencesSize', '五号')),
                                spacing=spacing(after=40, line=320), ind=f'<w:ind w:left="{self.first}" w:hanging="{self.first}"/>', jc=jc('left')))
        return out

    # ---------- 页眉页脚 ----------
    def add_part(self, kind, inner):
        n = sum(1 for p in self.parts if p[0].startswith(kind)) + 1
        name = f'{kind}{n}.xml'
        tag = 'hdr' if kind == 'header' else 'ftr'
        self.parts.append((name, kind, f'{XML_HEAD}<w:{tag} {NS}>{inner}</w:{tag}>'))
        return self.add_rel(kind, name)

    def header_with(self, text):
        hd = self.hd
        if hd.get('enabled') is False:
            return self.add_part('header', '<w:p/>')
        bdr = '' if hd.get('borderBottom') is False else '<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/></w:pBdr>'
        p = Para(self.run(text, font=self.fnt(hd.get('font', 'kai')), size=hd.get('size', '小五')), pBdr=bdr, jc=jc(ALIGN[hd.get('align', 'center')]))
        return self.add_part('header', p.xml())

    def footer_page(self):
        r = self.rpr(size=self.ft.get('size', '小五'))
        p = Para(f'<w:r>{r}<w:fldChar w:fldCharType="begin"/></w:r><w:r>{r}<w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
                 f'<w:r>{r}<w:fldChar w:fldCharType="separate"/></w:r><w:r>{r}<w:t>1</w:t></w:r><w:r>{r}<w:fldChar w:fldCharType="end"/></w:r>',
                 jc=jc(ALIGN[self.ft.get('align', 'right')]))
        return self.add_part('footer', p.xml())

    def empty_header(self):
        return self.add_part('header', '<w:p/>')

    def empty_footer(self):
        return self.add_part('footer', '<w:p/>')

    def sect_pr(self, hdr, ftr, start=None, fmt=None):
        PG = self.pg; m = PG['marginTw']
        pn = ''.join(f' w:{k}="{v}"' for k, v in (('fmt', fmt), ('start', start)) if v is not None)
        return (f'<w:sectPr><w:headerReference w:type="default" r:id="{hdr}"/><w:footerReference w:type="default" r:id="{ftr}"/>'
                f'<w:pgSz w:w="{PG["widthTw"]}" w:h="{PG["heightTw"]}"/>'
                f'<w:pgMar w:top="{m["top"]}" w:right="{m["right"]}" w:bottom="{m["bottom"]}" w:left="{m["left"]}" '
                f'w:header="{m.get("header", 851)}" w:footer="{m.get("footer", 992)}" w:gutter="0"/>'
                f'<w:pgNumType{pn}/><w:docGrid w:linePitch="360"/></w:sectPr>')

    # ---------- 封面 / 扉页（字段与版式都在配置里） ----------
    def render_layout(self, items):
        out = []
        for it in items or []:
            o = dict(font=self.fnt(it.get('font')), size=it.get('size', self.B['size']), bold=bool(it.get('bold')))
            if it.get('blank'):
                out += [Para(self.run('', **o), spacing=spacing(line=240)) for _ in range(it['blank'])]
            elif it.get('pair'):   # 左右两栏的一行（如“分类号 / 单位代码”）
                out.append(Para(self.run(it['pair'][0], **o) + '<w:r>' + self.rpr(**o) + '<w:tab/></w:r>' + self.run(it['pair'][1], **o),
                                tabs=f'<w:tabs><w:tab w:val="left" w:pos="{it.get("tabTw", 6000)}"/></w:tabs>'))
            elif it.get('image'):
                p = self.rel(it['image']); ext = os.path.splitext(p)[1].lower().lstrip('.').replace('jpeg', 'jpg')
                px = it.get('px', 113)
                out.append(Para(self.drawing(open(p, 'rb').read(), ext, px, px), jc=jc('center')))
            elif it.get('rule'):
                out.append(Para(pBdr='<w:pBdr><w:bottom w:val="single" w:sz="8" w:space="1" w:color="000000"/></w:pBdr>',
                                ind='<w:ind w:left="600" w:right="600"/>'))
            elif it.get('info'):   # 标签 + 值，整体左缩进
                out.append(Para(self.run(it['info'][0], **o) + self.run(it['info'][1], **o),
                                spacing=spacing(line=440), ind=f'<w:ind w:left="{it.get("indentTw", 2200)}"/>'))
            else:
                out.append(Para(self.run(it.get('text', ''), **o), spacing=spacing(it.get('before', 0), it.get('after', 0)),
                                jc=jc(ALIGN[it.get('align', 'center')])))
        return out

    # ---------- 目录（预填条目，Word 打开时更新页码） ----------
    def toc_blocks(self):
        toc = self.toc
        lv = toc.get('levels', '1-3'); lo, hi = (int(x) for x in lv.split('-'))
        title = Para(self.run(toc.get('title', '目　　录'), font=self.fonts['hei'], size=toc.get('titleSize', '三号')),
                     spacing=spacing(240, 360), jc=jc('center'))
        begin = (f'<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
                 f'<w:r><w:instrText xml:space="preserve"> TOC \\o &quot;{lo}-{hi}&quot; \\h \\z \\u </w:instrText></w:r>'
                 '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
        tabs = f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{self.text_w}"/></w:tabs>'
        paras, first = [], True
        for n, (level, text) in enumerate(self.headings, 1):
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

    # ---------- 读源稿 ----------
    def read_src(self, name):
        p = os.path.join(self.src, name)
        if not os.path.exists(p):
            raise BuildError('找不到源稿：' + p)
        return open(p, encoding='utf-8-sig').read()

    def load_sources(self):
        """读全部源稿，返回 dict：abstract、chapters [(文件名, 文本)]、front、refs（可能为 None）、back [(文件名, 文本)]。"""
        fl = self.fl
        ch_re = re.compile(fl.get('chapterPattern', r'^第\d+章'))
        ch_files = sorted((f for f in os.listdir(self.src) if ch_re.search(f) and f.endswith('.md')),
                          key=lambda f: int(re.search(r'\d+', f).group()))
        refs_file = os.path.join(self.src, fl.get('references', '参考文献.md'))
        return dict(abstract=self.read_src(fl.get('abstract', '摘要.md')),
                    front=[(e, self.read_src(e)) for e in self.cfg.get('extraFrontFiles', [])],
                    chapters=[(f, self.read_src(f)) for f in ch_files],
                    refs=open(refs_file, encoding='utf-8-sig').read() if os.path.exists(refs_file) else None,
                    back=[(e, self.read_src(e)) for e in self.cfg.get('extraBackFiles', [])])

    # ---------- 字数 ----------
    def word_counts(self, sources=None):
        """[(名称, 汉字数)]：中文摘要、各章、正文合计、参考文献、后置部分。不生成 Word。"""
        s = sources or self.load_sources()

        def title(md, fallback):   # 与 convert_chapter 取标题的规则一致：章末待办之前最后一个一级标题
            L = md.splitlines()
            cut = next((k for k, l in enumerate(L) if self.cut_re.search(l)), len(L))
            found = [m.group(1).strip() for l in L[:cut] if (m := re.match(r'^# (.*)', l))]
            return found[-1] if found else fallback
        counts = [(title(md, f), cjk_count(md, self.note_re, self.cut_re)) for f, md in s['chapters']]
        rows = [('中文摘要（不含题目和关键词）', abstract_body_count(s['abstract'], self.note_re, self.cut_re))] + counts
        rows.append(('正文合计', sum(n for _, n in counts)))
        if s['refs']:
            rows.append((self.cfg.get('referencesTitle', '参考文献'), cjk_count(s['refs'], self.note_re, self.cut_re)))
        rows += [(title(md, e), cjk_count(md, self.note_re, self.cut_re)) for e, md in s['back']]
        return rows

    # ---------- 组装 ----------
    def document_xml(self, s):
        cfg = self.cfg
        abs_zh, abs_en = self.convert_abstract(s['abstract'])
        extras = [self.convert_chapter(md)[1] for _, md in s['front']]
        chapters = [self.convert_chapter(md) for _, md in s['chapters']]
        refs = self.convert_refs(s['refs']) if s['refs'] else None
        # 参考文献之后的部分（附录、致谢、攻读学位期间成果等），按配置顺序各占一节，标题进目录
        backs = []
        for e, md in s['back']:
            title, blocks = self.convert_chapter(md)
            if not title:
                raise BuildError(f'{e} 缺少一级标题（如“# 附录 A　访谈提纲”“# 致　　谢”）')
            backs.append((title, blocks))

        front_fmt, body_fmt = self.pn.get('front', 'upperRoman'), self.pn.get('body', 'decimal')
        sections = []   # (块列表, sectPr)
        if cfg.get('cover') and cfg['cover'].get('enabled') is not False:
            sections.append((self.render_layout(cfg['cover'].get('layout')), self.sect_pr(self.empty_header(), self.empty_footer())))
        if cfg.get('titlePage') and cfg['titlePage'].get('enabled'):
            sections.append((self.render_layout(cfg['titlePage'].get('layout')), self.sect_pr(self.empty_header(), self.empty_footer())))
        for blocks in extras:   # 可选：声明页等，按普通段落排
            sections.append((blocks, self.sect_pr(self.empty_header(), self.empty_footer())))
        sections.append((abs_zh, self.sect_pr(self.empty_header(), self.footer_page(), start=1, fmt=front_fmt)))
        if abs_en:
            sections.append((abs_en, self.sect_pr(self.empty_header(), self.footer_page(), fmt=front_fmt)))
        toc_index = len(sections)
        sections.append((None, self.sect_pr(self.empty_header(), self.footer_page(), fmt=front_fmt)))   # 目录要等全部标题收集完再生成
        for k, (title, blocks) in enumerate(chapters):
            sections.append((blocks, self.sect_pr(self.header_with(title), self.footer_page(), start=1 if k == 0 else None, fmt=body_fmt)))
        if refs:
            sections.append((refs, self.sect_pr(self.header_with(cfg.get('referencesTitle', '参考文献')), self.footer_page(), fmt=body_fmt)))
        for title, blocks in backs:
            sections.append((blocks, self.sect_pr(self.header_with(title), self.footer_page(), fmt=body_fmt)))
        sections[toc_index] = (self.toc_blocks(), sections[toc_index][1])

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
        return f'{XML_HEAD}<w:document {NS}><w:body>{"".join(body)}</w:body></w:document>'

    # ---------- 样式 ----------
    def styles_xml(self):
        H = self.cfg.get('headings', [])
        hs = lambda i, d: {**d, **(H[i] if i < len(H) else {})}
        h_cfg = [hs(0, {'size': '三号', 'bold': True, 'align': 'center'}), hs(1, {'size': '四号', 'bold': True, 'align': 'left'}),
                 hs(2, {'size': '小四', 'bold': True, 'align': 'left'})]
        h_space = [(240, 480, ''), (360, 240, '<w:keepNext/>'), (240, 120, '<w:keepNext/>')]
        toc_ind = self.toc.get('indentChars', 1); toc_size = sz(self.toc.get('entrySize', '四号'))
        styles = [f'<w:docDefaults><w:rPrDefault>{self.rpr()}</w:rPrDefault><w:pPrDefault/></w:docDefaults>',
                  '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>',
                  '<w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont"><w:name w:val="Default Paragraph Font"/><w:uiPriority w:val="1"/><w:semiHidden/></w:style>',
                  '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/><w:semiHidden/>'
                  '<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
                  '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>',
                  '<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:basedOn w:val="DefaultParagraphFont"/></w:style>']
        for k, h in enumerate(h_cfg):
            before, after, keep = h_space[k]
            r = self.rpr(font=self.fnt(h.get('font')), size=h['size'], bold=h.get('bold', True), color='000000')
            styles.append(f'<w:style w:type="paragraph" w:styleId="Heading{k + 1}"><w:name w:val="heading {k + 1}"/><w:basedOn w:val="Normal"/>'
                          f'<w:next w:val="Normal"/><w:qFormat/><w:pPr>{keep}{spacing(before, after, 360)}{jc(ALIGN[h["align"]])}'
                          f'<w:outlineLvl w:val="{k}"/></w:pPr>{r}</w:style>')
        for k in range(3):
            styles.append(f'<w:style w:type="paragraph" w:styleId="TOC{k + 1}"><w:name w:val="toc {k + 1}"/><w:basedOn w:val="Normal"/>'
                          f'<w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:pPr>{spacing(line=360)}<w:ind w:left="{jsround(k * toc_ind * toc_size * 10)}"/></w:pPr>'
                          f'{self.rpr(size=toc_size)}</w:style>')
        return f'{XML_HEAD}<w:styles {NS}>{"".join(styles)}</w:styles>'

    # ---------- 打包 ----------
    def build(self, out, sources=None):
        """生成 Word 写到 out，返回输出路径。一个 Builder 只调用一次。"""
        if self.rels:
            raise BuildError('一个 Builder 只能生成一次，请新建一个')
        s = sources or self.load_sources()
        document = self.document_xml(s)
        styles_xml = self.styles_xml()
        settings_xml = (f'{XML_HEAD}<w:settings {NS}>'
                        '<w:defaultTabStop w:val="420"/><w:characterSpacingControl w:val="compressPunctuation"/><w:updateFields w:val="true"/>'
                        '<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
                        '</w:settings>')   # updateFields：打开时提示更新域，由 Word 填目录页码
        R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        self.add_rel('styles', 'styles.xml'); self.add_rel('settings', 'settings.xml')
        doc_rels = ''.join(f'<Relationship Id="{i}" Type="{R}{t}" Target="{esc(g)}"/>' for i, t, g in self.rels)
        CT = 'application/vnd.openxmlformats-officedocument.wordprocessingml.'
        overrides = ''.join(f'<Override PartName="/word/{n}" ContentType="{CT}{k}+xml"/>' for n, k, _ in self.parts)
        content_types = (f'{XML_HEAD}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
                         '<Default Extension="jpg" ContentType="image/jpeg"/>'
                         f'<Override PartName="/word/document.xml" ContentType="{CT}document.main+xml"/>'
                         f'<Override PartName="/word/styles.xml" ContentType="{CT}styles+xml"/>'
                         f'<Override PartName="/word/settings.xml" ContentType="{CT}settings+xml"/>'
                         '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                         f'{overrides}</Types>')
        root_rels = (f'{XML_HEAD}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     f'<Relationship Id="rId1" Type="{R}officeDocument" Target="word/document.xml"/>'
                     '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                     '</Relationships>')
        now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        core = (f'{XML_HEAD}<cp:coreProperties '
                'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" '
                'xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
                '</cp:coreProperties>')

        out = os.path.normpath(out)
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml', content_types)
            z.writestr('_rels/.rels', root_rels)
            z.writestr('docProps/core.xml', core)
            z.writestr('word/document.xml', document)
            z.writestr('word/styles.xml', styles_xml)
            z.writestr('word/settings.xml', settings_xml)
            z.writestr('word/_rels/document.xml.rels',
                       f'{XML_HEAD}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{doc_rels}</Relationships>')
            for name, _, xml in self.parts:
                z.writestr('word/' + name, xml)
            for name, data in self.media:
                z.writestr('word/media/' + name, data)
        return out


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错
    if len(argv) < 2:
        sys.exit('用法：python build_docx.py <配置.json> [输出.docx]')
    cfg, base = load_config(argv[1])
    b = Builder(cfg, base)
    out = argv[2] if len(argv) > 2 else b.rel(cfg['paths'].get('out', 'out.docx'))
    try:
        sources = b.load_sources()
        out = b.build(out, sources)
    except BuildError as e:
        sys.exit(str(e))
    print('已生成', out, '章数', len(sources['chapters']), '大小', os.path.getsize(out))
    print('\n汉字数（不含写作备注、图片行和章末待办；学校按 Word 字数统计的，以 Word 为准）：')
    for name, n in b.word_counts(sources):
        print(f'  {n:>7}  {name}')


if __name__ == '__main__':
    main(sys.argv)
