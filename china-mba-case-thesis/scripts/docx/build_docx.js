// 把 Markdown 源稿整份生成学位论文 Word（docx-js）
// 用法：node build_docx.js <配置.json> [输出.docx]
// 学校格式、封面字段、路径全部来自配置文件；本脚本只保留通用逻辑。
const fs = require('fs');
const path = require('path');
const D = require('docx');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, BorderStyle,
  AlignmentType, HeadingLevel, Header, Footer, PageNumber, NumberFormat, TableOfContents, VerticalAlign,
  LineRuleType, TabStopType,
} = D;

const cfgPath = process.argv[2];
if (!cfgPath) { console.error('用法：node build_docx.js <配置.json> [输出.docx]'); process.exit(1); }
const CFG = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const BASE = path.dirname(path.resolve(cfgPath));
const rel = p => path.isAbsolute(p) ? p : path.join(BASE, p);
const SRC = rel(CFG.paths.src);
const IMG = rel(CFG.paths.img);
const OUT = process.argv[3] || rel(CFG.paths.out || 'out.docx');

// ---------- 字号（中文“号”→ 半磅） ----------
const HAO = { '初号': 84, '小初': 72, '一号': 52, '小一': 48, '二号': 44, '小二': 36, '三号': 32, '小三': 30,
  '四号': 28, '小四': 24, '五号': 21, '小五': 18, '六号': 15 };
const sz = v => (typeof v === 'number' ? v : HAO[v]) || 24;

// ---------- 字体：每处同时设西文与中文 ----------
const F = CFG.fonts;
const font = (east, latin) => ({ ascii: latin || F.latin, hAnsi: latin || F.latin, eastAsia: east, cs: latin || F.latin });
const FONTS = { song: font(F.song), hei: font(F.hei), kai: font(F.kai), coverLatin: font(F.song, F.coverLatin || 'Arial') };
const fnt = k => FONTS[k] || FONTS.song;

const B = CFG.body;
const LINE_BODY = { line: Math.round(240 * (B.lineSpacing || 1.5)), lineRule: LineRuleType.AUTO };
const FIRST = Math.round((B.firstLineChars || 2) * sz(B.size) * 10);   // 首行缩进 n 字（twip）
const PG = CFG.page;
const TEXT_W = PG.widthTw - PG.marginTw.left - PG.marginTw.right;      // 版心宽（twip）
const NOTE_RE = new RegExp('^(' + (CFG.noteMarkers || ['资料来源', '注']).join('|') + ')');
const CUT_RE = new RegExp(CFG.cutSectionPattern || '^##\\s*(本章待|待补)');

// ---------- 行内：<sup>角标</sup>、**加粗** ----------
function runs(text, opt = {}) {
  const out = []; const re = /(<sup>(.*?)<\/sup>|\*\*(.+?)\*\*)/g; let last = 0, m;
  const base = { font: opt.font || FONTS.song, size: opt.size || sz(B.size), bold: opt.bold || false };
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ ...base, text: text.slice(last, m.index) }));
    if (m[2] !== undefined) out.push(new TextRun({ ...base, text: m[2], superScript: true }));
    else out.push(new TextRun({ ...base, text: m[3], bold: true }));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(new TextRun({ ...base, text: text.slice(last) }));
  return out;
}
const bodyPara = text => new Paragraph({ children: runs(text), spacing: LINE_BODY, indent: { firstLine: FIRST }, alignment: AlignmentType.JUSTIFIED });

// ---------- 图 ----------
const FIG = CFG.figures || {};
function pngSize(p) { const b = fs.readFileSync(p); return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
const imgFiles = fs.existsSync(IMG) ? fs.readdirSync(IMG).filter(f => f.endsWith('.png')) : [];
function imagePara(num, mdPath) {
  // 源稿里写的路径存在就直接用（相对源稿目录）；否则按“图x.x_”前缀到配置的图片目录找
  let full = mdPath ? path.resolve(SRC, decodeURI(mdPath)) : null;
  if (!full || !fs.existsSync(full)) {
    const f = imgFiles.find(x => x.startsWith((FIG.filePrefix || '图') + num + '_'));
    if (!f) throw new Error('找不到图片：图 ' + num + '（源稿路径不存在，' + IMG + ' 下也没有以“图' + num + '_”开头的 PNG）');
    full = path.join(IMG, f);
  }
  if (!full.toLowerCase().endsWith('.png')) throw new Error('图片须为 PNG：' + full);
  const { w, h } = pngSize(full);
  let W = (FIG.widthsPx || {})[num] || Math.round((FIG.defaultWidthCm || 14.5) / 2.54 * 96);
  let H = Math.round(W * h / w);
  const MAXH = FIG.maxHeightPx || 780;
  if (H > MAXH) { H = MAXH; W = Math.round(H * w / h); }
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
    children: [new ImageRun({ type: 'png', data: fs.readFileSync(full), transformation: { width: W, height: H } })] });
}
const CAP = CFG.captions || {};
const captionPara = (text, keepNext) => new Paragraph({ alignment: AlignmentType.CENTER, keepNext,
  spacing: keepNext ? { before: 200, after: 80 } : { before: 60, after: 120, line: 300, lineRule: LineRuleType.AUTO },
  children: [new TextRun({ text, font: fnt(CAP.font || 'hei'), size: sz(CAP.size || B.size), bold: !!CAP.bold })] });
const notePara = (text, center) => new Paragraph({ alignment: center ? AlignmentType.CENTER : AlignmentType.LEFT,
  spacing: { before: 40, after: 160, line: 280, lineRule: LineRuleType.AUTO }, children: runs(text, { size: sz((CFG.table || {}).noteSize || '五号') }) });

// ---------- 三线表 ----------
const T = CFG.table || {};
const NONE = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const THICK = { style: BorderStyle.SINGLE, size: T.outerRule8ths || 12, color: '000000' };
const THIN = { style: BorderStyle.SINGLE, size: T.headRule8ths || 6, color: '000000' };
function dispLen(s) { s = s.replace(/<[^>]+>|\*\*/g, ''); let n = 0; for (const c of s) n += /[\u0000-ÿ]/.test(c) ? 0.55 : 1; return n; }
function buildTable(rows) {
  const ncol = rows[0].length; const wts = [];
  for (let j = 0; j < ncol; j++) {
    const lens = rows.map(r => dispLen(r[j] || '')); const mx = Math.max(...lens), avg = lens.reduce((a, b) => a + b, 0) / lens.length;
    wts.push(Math.max(3, Math.min(Math.sqrt(mx) * 2 + avg, 60)));
  }
  const tot = wts.reduce((a, b) => a + b, 0);
  let widths = wts.map(w => Math.round(TEXT_W * w / tot));
  const mins = rows[0].map(h => { const n = dispLen(h); return n <= 6 ? Math.round(n * 215 + 220) : 0; });
  for (let it = 0; it < 3; it++) {
    const fixed = widths.map((w, j) => w < mins[j]); if (!fixed.some(x => x)) break;
    const need = widths.reduce((s, w, j) => s + (fixed[j] ? mins[j] - w : 0), 0);
    const pool = widths.reduce((s, w, j) => s + (fixed[j] ? 0 : w), 0);
    widths = widths.map((w, j) => fixed[j] ? mins[j] : Math.round(w - need * w / pool));
  }
  widths[widths.length - 1] += TEXT_W - widths.reduce((a, b) => a + b, 0);
  const trs = rows.map((r, i) => new TableRow({ tableHeader: i === 0, cantSplit: true,
    children: r.map((c, j) => new TableCell({ width: { size: widths[j], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
      margins: { top: 40, bottom: 40, left: 80, right: 80 },
      borders: { top: i === 0 ? THICK : NONE, bottom: i === 0 ? THIN : (i === rows.length - 1 ? THICK : NONE), left: NONE, right: NONE },
      children: [new Paragraph({ keepNext: i < rows.length - 1, keepLines: true,
        alignment: (i === 0 || dispLen(c) <= 8) ? AlignmentType.CENTER : AlignmentType.LEFT,
        spacing: { line: 260, lineRule: LineRuleType.AUTO },
        children: runs((c || '').trim(), { size: sz(T.size || '五号'), bold: i === 0 && T.boldHeader !== false }) })] })) }));
  return new Table({ width: { size: TEXT_W, type: WidthType.DXA }, columnWidths: widths, rows: trs, alignment: AlignmentType.CENTER });
}
const parseRow = l => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(s => s.trim());

// ---------- 章节源稿 → 段落 ----------
function convertChapter(md) {
  let L = md.split(/\r?\n/);
  const cut = L.findIndex(l => CUT_RE.test(l)); if (cut >= 0) L = L.slice(0, cut);
  const blocks = []; let title = ''; let i = 0;
  while (i < L.length) {
    const l = L[i];
    if (/^# /.test(l)) { title = l.slice(2).trim(); blocks.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(title)] })); i++; continue; }
    if (/^## /.test(l)) { blocks.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(l.slice(3).trim())] })); i++; continue; }
    if (/^### /.test(l)) { blocks.push(new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(l.slice(4).trim())] })); i++; continue; }
    if (/^!\[/.test(l)) {
      const m = l.match(/图\s*(\d+\.\d+)/); if (!m) throw new Error('图片行缺少“图 x.x”：' + l);
      const pm = l.match(/\]\(([^)]+)\)/); blocks.push(imagePara(m[1], pm ? pm[1].trim() : null)); i++; continue;
    }
    if (/^【图/.test(l)) {
      const t = l.trim().replace(/^【|】$/g, ''); blocks.push(captionPara(t, false));
      const n = (t.match(/图\s*(\d+\.\d+)/) || [])[1]; i++;
      // 图下紧跟的 > 资料来源/注 行作为图注输出，其余 > 行是写作备注
      let j = i; while (j < L.length && L[j].trim() === '') j++;
      if (j < L.length && L[j].startsWith('>')) {
        while (j < L.length && L[j].startsWith('>')) { const s = L[j].replace(/^>\s*/, ''); if (NOTE_RE.test(s)) blocks.push(notePara(s, true)); j++; }
        i = j;
      }
      if (n && (FIG.notes || {})[n]) blocks.push(notePara(FIG.notes[n], true));
      continue;
    }
    if (/^【表/.test(l)) { blocks.push(captionPara(l.trim().replace(/^【|】$/g, ''), true)); i++; continue; }
    if (/^\|/.test(l)) {
      const rows = [];
      while (i < L.length && /^\|/.test(L[i])) { if (!/^\|\s*:?-{2,}/.test(L[i])) rows.push(parseRow(L[i])); i++; }
      const n = Math.max(...rows.map(r => r.length)); rows.forEach(r => { while (r.length < n) r.push(''); });
      blocks.push(buildTable(rows));
      let j = i; while (j < L.length && L[j].trim() === '') j++;
      if (j < L.length && L[j].startsWith('>') && NOTE_RE.test(L[j].replace(/^>\s*/, ''))) {
        while (j < L.length && L[j].startsWith('>')) { const t = L[j].replace(/^>\s*/, ''); if (NOTE_RE.test(t)) blocks.push(notePara(t)); j++; }
        i = j;
      } else blocks.push(new Paragraph({ spacing: { after: 60 }, children: [] }));
      continue;
    }
    if (l.startsWith('>') || /^-{3,}\s*$/.test(l) || l.trim() === '') { i++; continue; }
    blocks.push(bodyPara(l.trim())); i++;
  }
  return { title, blocks };
}

// ---------- 摘要（中文在前，“# Abstract”之后为英文） ----------
const AB = CFG.abstract || {};
function convertAbstract(md) {
  const parts = md.split(/^# Abstract\s*$/m);
  const make = (txt, head, en) => {
    const L = (txt || '').split(/\r?\n/).filter(l => !l.startsWith('>') && !/^-{3,}/.test(l) && !/^# /.test(l));
    const out = [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 240, after: 360 },
      children: [new TextRun({ text: head, font: FONTS.hei, size: sz(AB.headSize || '三号'), bold: !en })] })];
    let first = true;
    for (const raw of L) {
      const l = raw.trim(); if (!l) continue;
      if (first) { out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240, ...LINE_BODY }, children: [new TextRun({ text: l, font: FONTS.song, size: sz(AB.titleSize || '四号') })] })); first = false; continue; }
      if (/^\*\*(关键词|Key ?words)/i.test(l)) { out.push(new Paragraph({ spacing: { before: 360, ...LINE_BODY }, children: [new TextRun({ text: l.replace(/\*\*/g, ''), font: FONTS.song, size: sz(B.size), bold: true })] })); continue; }
      if (/^　　/.test(l) || /^\s{2,}/.test(raw)) { out.push(new Paragraph({ spacing: LINE_BODY, indent: { left: FIRST }, children: runs(l.replace(/^　+/, '')) })); continue; }
      out.push(bodyPara(l));
    }
    return out;
  };
  return { zh: make(parts[0], AB.zhHead || '摘　　要', false), en: parts[1] ? make(parts[1], AB.enHead || 'Abstract', true) : null };
}

// ---------- 参考文献 ----------
function convertRefs(md) {
  const out = [new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(CFG.referencesTitle || '参考文献')] })];
  for (const l of md.split(/\r?\n/)) {
    const m = l.match(/^\[(\d+)\]\s*(.*)$/); if (!m) continue;
    out.push(new Paragraph({ spacing: { line: 320, lineRule: LineRuleType.AUTO, after: 40 }, indent: { left: FIRST, hanging: FIRST }, alignment: AlignmentType.LEFT,
      children: [new TextRun({ text: `[${m[1]}] ${m[2]}`, font: FONTS.song, size: sz(CFG.referencesSize || '五号') })] }));
  }
  return out;
}

// ---------- 页眉页脚 ----------
const HD = CFG.header || {}; const FT = CFG.footer || {};
const ALIGN = { left: AlignmentType.LEFT, center: AlignmentType.CENTER, right: AlignmentType.RIGHT };
const mkHeader = t => new Header({ children: [new Paragraph({ alignment: ALIGN[HD.align || 'center'],
  border: HD.borderBottom === false ? undefined : { bottom: { style: BorderStyle.SINGLE, size: 6, color: '000000', space: 1 } },
  children: [new TextRun({ text: t, font: fnt(HD.font || 'kai'), size: sz(HD.size || '小五') })] })] });
const mkFooter = () => new Footer({ children: [new Paragraph({ alignment: ALIGN[FT.align || 'right'],
  children: [new TextRun({ children: [PageNumber.CURRENT], font: FONTS.song, size: sz(FT.size || '小五') })] })] });
const emptyHeader = () => new Header({ children: [new Paragraph({ children: [] })] });
const emptyFooter = () => new Footer({ children: [new Paragraph({ children: [] })] });
const NUMFMT = { upperRoman: NumberFormat.UPPER_ROMAN, lowerRoman: NumberFormat.LOWER_ROMAN, decimal: NumberFormat.DECIMAL };
const PN = CFG.pageNumbers || {};
const page = { size: { width: PG.widthTw, height: PG.heightTw }, margin: PG.marginTw };
const bodyHeader = t => HD.enabled === false ? emptyHeader() : mkHeader(t);

// ---------- 封面 / 扉页（字段与版式都在配置里） ----------
const tr = (text, o = {}) => new TextRun({ text, font: fnt(o.font), size: sz(o.size || B.size), bold: !!o.bold });
const P = (children, o = {}) => new Paragraph({ children, ...o });
const blank = n => Array.from({ length: n }, () => P([tr('')], { spacing: { line: 240, lineRule: LineRuleType.AUTO } }));
function renderLayout(items) {
  const out = [];
  for (const it of items || []) {
    if (it.blank) { out.push(...blank(it.blank)); continue; }
    if (it.pair) { // 左右两栏的一行（如“分类号 / 单位代码”）
      out.push(P([tr(it.pair[0], it), new TextRun({ text: '\t' + it.pair[1], font: fnt(it.font), size: sz(it.size || B.size), bold: !!it.bold })],
        { tabStops: [{ type: TabStopType.LEFT, position: it.tabTw || 6000 }] })); continue;
    }
    if (it.image) { out.push(P([new ImageRun({ type: path.extname(it.image).slice(1).replace('jpeg', 'jpg'), data: fs.readFileSync(rel(it.image)), transformation: { width: it.px || 113, height: it.px || 113 } })], { alignment: AlignmentType.CENTER })); continue; }
    if (it.rule) { out.push(P([], { border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: '000000', space: 1 } }, indent: { left: 600, right: 600 } })); continue; }
    if (it.info) { // 标签 + 值，整体左缩进
      out.push(P([tr(it.info[0], it), tr(it.info[1], it)], { indent: { left: it.indentTw || 2200 }, spacing: { line: 440, lineRule: LineRuleType.AUTO } })); continue;
    }
    out.push(P([tr(it.text, it)], { alignment: ALIGN[it.align || 'center'], spacing: { after: it.after || 0, before: it.before || 0 } }));
  }
  return out;
}

// ---------- 组装 ----------
const FL = CFG.files || {};
const abs = convertAbstract(fs.readFileSync(path.join(SRC, FL.abstract || '摘要.md'), 'utf8'));
const chRe = new RegExp(FL.chapterPattern || '^第\\d+章');
const chFiles = fs.readdirSync(SRC).filter(f => chRe.test(f) && f.endsWith('.md'))
  .sort((a, b) => parseInt(a.match(/\d+/)) - parseInt(b.match(/\d+/)));
const chapters = chFiles.map(f => convertChapter(fs.readFileSync(path.join(SRC, f), 'utf8')));
const refsFile = path.join(SRC, FL.references || '参考文献.md');
const refs = fs.existsSync(refsFile) ? convertRefs(fs.readFileSync(refsFile, 'utf8')) : null;

const sections = [];
const front = (start, children) => ({ properties: { page: { ...page, pageNumbers: { ...(start ? { start: 1 } : {}), formatType: NUMFMT[PN.front || 'upperRoman'] } } },
  headers: { default: emptyHeader() }, footers: { default: mkFooter() }, children });
if (CFG.cover && CFG.cover.enabled !== false) sections.push({ properties: { page }, headers: { default: emptyHeader() }, footers: { default: emptyFooter() }, children: renderLayout(CFG.cover.layout) });
if (CFG.titlePage && CFG.titlePage.enabled) sections.push({ properties: { page }, headers: { default: emptyHeader() }, footers: { default: emptyFooter() }, children: renderLayout(CFG.titlePage.layout) });
for (const extra of CFG.extraFrontFiles || []) { // 可选：声明页等，按普通段落排
  const t = fs.readFileSync(path.join(SRC, extra), 'utf8'); sections.push({ properties: { page }, headers: { default: emptyHeader() }, footers: { default: emptyFooter() }, children: convertChapter(t).blocks });
}
sections.push(front(true, abs.zh));
if (abs.en) sections.push(front(false, abs.en));
const TOC = CFG.toc || {};
sections.push(front(false, [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 240, after: 360 }, children: [new TextRun({ text: TOC.title || '目　　录', font: FONTS.hei, size: sz(TOC.titleSize || '三号') })] }),
  new TableOfContents('目录', { hyperlink: true, headingStyleRange: TOC.levels || '1-3' }),
]));
chapters.forEach((c, k) => sections.push({
  properties: { page: k === 0 ? { ...page, pageNumbers: { start: 1, formatType: NUMFMT[PN.body || 'decimal'] } } : page },
  headers: { default: bodyHeader(c.title) }, footers: { default: mkFooter() }, children: c.blocks }));
if (refs) sections.push({ properties: { page }, headers: { default: bodyHeader(CFG.referencesTitle || '参考文献') }, footers: { default: mkFooter() }, children: refs });

const H = CFG.headings || [];
const hs = (i, d) => ({ ...d, ...(H[i] || {}) });
const h1 = hs(0, { size: '三号', bold: true, align: 'center' }), h2 = hs(1, { size: '四号', bold: true, align: 'left' }), h3 = hs(2, { size: '小四', bold: true, align: 'left' });
const tocInd = TOC.indentChars || 1; const tocSize = sz(TOC.entrySize || '四号');
const doc = new Document({
  features: { updateFields: true },   // 打开时提示更新域，由 Word 填目录页码
  styles: {
    default: { document: { run: { font: FONTS.song, size: sz(B.size) } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: fnt(h1.font), size: sz(h1.size), bold: h1.bold, color: '000000' },
        paragraph: { alignment: ALIGN[h1.align], spacing: { before: 240, after: 480, line: 360, lineRule: LineRuleType.AUTO }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: fnt(h2.font), size: sz(h2.size), bold: h2.bold, color: '000000' },
        paragraph: { alignment: ALIGN[h2.align], spacing: { before: 360, after: 240, line: 360, lineRule: LineRuleType.AUTO }, keepNext: true, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: fnt(h3.font), size: sz(h3.size), bold: h3.bold, color: '000000' },
        paragraph: { alignment: ALIGN[h3.align], spacing: { before: 240, after: 120, line: 360, lineRule: LineRuleType.AUTO }, keepNext: true, outlineLevel: 2 } },
      ...[0, 1, 2].map(k => ({ id: 'TOC' + (k + 1), name: 'toc ' + (k + 1), basedOn: 'Normal', next: 'Normal', run: { font: FONTS.song, size: tocSize },
        paragraph: { indent: { left: Math.round(k * tocInd * tocSize * 10) }, spacing: { line: 360, lineRule: LineRuleType.AUTO } } })),
    ],
  },
  sections,
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log('已生成', OUT, '章数', chapters.length, '大小', b.length); });
