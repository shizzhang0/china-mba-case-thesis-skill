"""核对引文角标与参考文献表（GB/T 7714 顺序编码制）。既能查本方法的源稿，也能查别人的整篇稿件。
    python3 ref_check.py <源稿目录> [--refs 参考文献.md]                  # 本方法的源稿：每章一个文件
    python3 ref_check.py 第1章.md 第2章.md ... --refs 参考文献.md          # 按正文顺序列出文件
    python3 ref_check.py 论文.md  或  论文.docx                            # 整篇稿件：在“参考文献”标题处自动切开
常用选项：-o 引用核对.md   --plain   --terms Kraljic,COSO,BPR   --include-abstract
检查：
  1）缺号：角标里的编号在文献表中没有条目；
  2）未引用：文献表条目从未被正文引用；
  3）顺序：各编号首次出现的次序应为 1、2、3……；报出全部“出现晚了”的编号及其总数，并指出是哪个提前出现的编号造成的；
  4）文献表本身：编号重复、不连续，疑似重复条目（题名相同）；
  5）疑似漏加上标：源稿约定下，正文里不在 <sup> 内的 [n]。
另列出每条文献被引的位置（文件、行号、所在小节和句子），供人工判断引用是否与所在句相干、是否为凑“全部被引”而挂角标；
只在“[3-15]”这类区间里出现过的文献单独标出。--terms 列出每个关键词与哪些角标出现在同一分句，用来发现“同一理论引了不同编号”。
角标写法：
  源稿约定：<sup>[1]</sup>、<sup>[1][3]</sup>、<sup>[1,3]</sup>、<sup>[2-4]</sup>、<sup>[2]-[4]</sup>（-、–、—、~ 均可）；
  --plain：正文里的裸 [n] 也当角标（别人的稿件常这样写）。正文没有任何 <sup> 角标、却有裸 [n] 时自动按 --plain 处理，并在报告里注明；
  docx：上标格式的 [n] 当角标，非上标的裸 [n] 按上面的规则处理。
整篇稿件：取最后一个只写“参考文献”的标题行或段落（避开目录里的同名条目），到下一个标题或“附录 / 致谢”为止作为文献表，其余为正文；
文献表用 Word 自动编号、没有写出 [n] 时，按段落顺序编号并在报告里提示。
源稿约定下以 > 开头的写作备注（资料来源、注除外）、“## 本章待…”之后的内容和代码块不检查，与 build_docx.py 一致。
给目录时按“第N章”排序，其后是其他源稿（附录等）；摘要默认不参与顺序检查，但其中的角标会被报告。
只用标准库。发现缺号、未引用、顺序或文献表编号问题时退出码为 1。
"""
import argparse
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import OrderedDict

NOTE_RE = re.compile(r'^(资料来源|注)')
CUT_RE = re.compile(r'^##\s*(本章待|待补)')
CHAPTER_RE = re.compile(r'^第(\d+)章')
SUP_RE = re.compile(r'<sup>(.*?)</sup>', re.S)
BRACKET_RE = re.compile(r'\[([^\[\]]*)\]')
RANGE_RE = re.compile(r'^(\d+)\s*[-–—~～]\s*(\d+)$')
PAIR_RANGE_RE = re.compile(r'\[(\d+)\]\s*[-–—~～]\s*\[(\d+)\]')
REF_LINE_RE = re.compile(r'^\s*\[(\d+)\]\s*(.*\S)?\s*$')
BARE_CITE_RE = re.compile(r'(?<!!)\[\d+(?:\s*[-–—~～,，、]\s*\d+)*\](?:\s*[-–—~～]\s*\[\d+\])?(?!\()')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*\S)')
REFS_TITLE_RE = re.compile(r'^(#{1,6}\s*)?参\s*考\s*文\s*献\s*$')
AFTER_REFS_RE = re.compile(r'^(#{1,6}\s+\S|附\s*录|致\s*谢|攻读|作者简介|后\s*记)')
SENT_END = '。！？；!?;'
ORDER_SHOW = 10
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def parse_cite(inner):
    """'[1][3]'、'[1,3]'、'[2-4]'、'[2]-[4]' → ([编号...], 是否含区间)。不是数字角标时返回 ([], False)。"""
    inner = PAIR_RANGE_RE.sub(r'[\1-\2]', inner)
    nums, has_range = [], False
    groups = BRACKET_RE.findall(inner)
    if not groups or re.sub(r'\[[^\[\]]*\]', '', inner).strip():
        return [], False
    for g in groups:
        for part in re.split(r'[,，、]', g):
            part = part.strip()
            if not part:
                continue
            m = RANGE_RE.match(part)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                if a > b:
                    return [], False
                nums.extend(range(a, b + 1))
                has_range = True
            elif part.isdigit():
                nums.append(int(part))
            else:
                return [], False
    return nums, has_range


def find_cites(line, plain):
    """一行里的角标。返回 ([(位置, 编号列表, 是否区间)], [(位置, 裸角标文字)])；plain 时裸 [n] 也算角标。"""
    cites, bare = [], []
    for m in SUP_RE.finditer(line):
        nums, rng = parse_cite(m.group(1))
        if nums:
            cites.append((m.start(), nums, rng))
    if REF_LINE_RE.match(SUP_RE.sub('', line)):
        return cites, bare   # 像文献表条目的行，不当正文
    rest = SUP_RE.sub(lambda m: ' ' * len(m.group(0)), line)   # 保留位置
    for m in BARE_CITE_RE.finditer(rest):
        nums, rng = parse_cite(m.group(0))
        if not nums:
            continue
        if plain:
            cites.append((m.start(), nums, rng))
        else:
            bare.append((m.start(), m.group(0)))
    cites.sort(key=lambda c: c[0])
    return cites, bare


def body_lines(md):
    """(行号, 行) 列表：去掉写作备注、章末待办和代码块。"""
    out, in_code = [], False
    for i, line in enumerate(md.splitlines(), 1):
        s = line.strip()
        if s.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if CUT_RE.search(s):
            break
        if s.startswith('>') and not NOTE_RE.search(re.sub(r'^>\s*', '', s)):
            continue
        out.append((i, line))
    return out


def clean(s):
    s = re.sub(r'<sup>.*?</sup>', '', s)
    return re.sub(r'^[#>\s]+', '', s).strip()


def sentence_at(line, pos, width=60):
    """角标所在的句子（按中文句号等切分），过长时截断。"""
    start = max(line.rfind(c, 0, pos) for c in SENT_END) + 1
    ends = [e for e in (line.find(c, pos) for c in SENT_END) if e >= 0]
    end = (min(ends) + 1) if ends else len(line)
    s = clean(line[start:end])
    return s if len(s) <= width else s[:width] + '…'


def scan_citations(name, md, plain=False):
    """返回 (引用列表, 疑似漏上标列表)。引用：dict(file, line, section, nums, range, sentence)。"""
    cites, bare, section = [], [], ''
    for ln, line in body_lines(md):
        h = HEADING_RE.match(line.strip())
        if h:
            section = h.group(2)
        cs, bs = find_cites(line, plain)
        for pos, nums, rng in cs:
            cites.append(dict(file=name, line=ln, section=section, nums=nums, range=rng,
                              sentence=sentence_at(line, pos)))
        bare += [dict(file=name, line=ln, text=t) for _, t in bs]
    return cites, bare


CLAUSE_END = '，,' + SENT_END


def scan_terms(files, terms, plain):
    """{关键词: OrderedDict{编号: [位置...]}}。每处关键词取同一分句里的角标；分句里没有时，取同一句中它后面的第一个角标。"""
    out = OrderedDict((t, OrderedDict()) for t in terms)
    for name, md in files:
        for ln, line in body_lines(md):
            cs, _ = find_cites(line, plain)
            if not cs:
                continue
            low = line.lower()
            for t in terms:
                for m in re.finditer(re.escape(t.lower()), low):
                    k = m.start()
                    c0 = max(line.rfind(ch, 0, k) for ch in CLAUSE_END) + 1
                    c1 = min([e for e in (line.find(ch, m.end()) for ch in CLAUSE_END) if e >= 0] or [len(line)])
                    s1 = min([e for e in (line.find(ch, m.end()) for ch in SENT_END) if e >= 0] or [len(line)])
                    hit = [c for c in cs if c0 <= c[0] <= c1] or [c for c in cs if m.end() <= c[0] <= s1][:1]
                    for _, nums, _ in hit:
                        for n in nums:
                            out[t].setdefault(n, []).append(f'{name}:{ln}')
    return out


def parse_refs(md):
    """文献表 → (OrderedDict{编号: 著录}, 问题列表)。没有写出 [n] 的自动编号文献表按段落顺序编号。"""
    refs, issues = OrderedDict(), []
    lines = md.splitlines()
    for ln, line in enumerate(lines, 1):
        m = REF_LINE_RE.match(line)
        if not m:
            continue
        n, text = int(m.group(1)), (m.group(2) or '').strip()
        if n in refs:
            issues.append(f'文献表编号 [{n}] 重复（第 {ln} 行）')
            continue
        refs[n] = text
    if not refs:
        entries = [l.strip() for l in lines if l.strip() and not REFS_TITLE_RE.match(l.strip())]
        if entries:
            for k, text in enumerate(entries, 1):
                refs[k] = text
            issues.append(f'文献表没有写出 [n] 编号（可能是 Word 自动编号），已按段落顺序编为 [1]–[{len(entries)}]，请核对是否与稿件一致')
            return refs, issues
    nums = list(refs)
    if nums and nums != list(range(1, len(nums) + 1)):
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            issues.append('文献表编号不连续，缺：' + '、'.join(f'[{x}]' for x in missing))
        if nums != sorted(nums):
            issues.append('文献表编号没有按顺序排列')
    seen = {}
    for n, text in refs.items():
        key = title_key(text)
        if key and key in seen:
            issues.append(f'[{seen[key]}] 与 [{n}] 题名相同，疑似重复条目')
        elif key:
            seen[key] = n
    return refs, issues


def title_key(entry):
    """取著录中“作者. 题名[类型]”的题名部分做比较键。"""
    m = re.search(r'\.\s*(.+?)\s*\[[A-Z]{1,2}(?:/[A-Z]{1,2})?\]', entry)
    t = m.group(1) if m else entry
    return re.sub(r'[\W_]+', '', t).lower()


def split_single(text):
    """整篇稿件 → (正文, 文献表)。正文里文献表所在行换成空行，保持行号不变。找不到“参考文献”标题时返回 (原文, None)。"""
    lines = text.splitlines()
    starts = [k for k, l in enumerate(lines) if REFS_TITLE_RE.match(l.strip())]
    if not starts:
        return text, None
    a = starts[-1]
    b = next((k for k in range(a + 1, len(lines)) if AFTER_REFS_RE.match(lines[k].strip())), len(lines))
    refs = '\n'.join(lines[a:b])
    body = lines[:a] + [''] * (b - a) + lines[b:]
    return '\n'.join(body), refs


def docx_to_md(path):
    """docx → 近似 Markdown：标题样式转为 #，上标文字包进 <sup>，每段一行。"""
    with zipfile.ZipFile(path) as z:
        doc = ET.fromstring(z.read('word/document.xml'))
        styles = ET.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None
    level = {}
    if styles is not None:
        for st in styles.iter(W + 'style'):
            sid = st.get(W + 'styleId')
            name = st.find(W + 'name')
            nm = (name.get(W + 'val') if name is not None else '') or ''
            m = re.match(r'(?i)(?:heading|标题)\s*(\d)$', nm.strip())
            if sid and m:
                level[sid] = int(m.group(1))
    out = []
    for p in doc.iter(W + 'p'):
        ps = p.find(W + 'pPr/' + W + 'pStyle')
        lv = level.get(ps.get(W + 'val')) if ps is not None else None
        parts, sup = [], []
        for r in p.iter(W + 'r'):
            va = r.find(W + 'rPr/' + W + 'vertAlign')
            is_sup = va is not None and va.get(W + 'val') == 'superscript'
            t = ''.join(x.text or '' for x in r.iter(W + 't'))
            if not t:
                continue
            if is_sup:
                sup.append(t)
                continue
            if sup:
                parts.append('<sup>' + ''.join(sup) + '</sup>')
                sup = []
            parts.append(t)
        if sup:
            parts.append('<sup>' + ''.join(sup) + '</sup>')
        text = ''.join(parts).strip()
        out.append(('#' * lv + ' ' + text) if lv and text else text)
    return '\n'.join(out)


def order_files(paths, refs_path, include_abstract):
    chapters, others, abstracts = [], [], []
    for p in paths:
        if os.path.abspath(p) == os.path.abspath(refs_path):
            continue
        base = os.path.basename(p)
        m = CHAPTER_RE.match(base)
        if m:
            chapters.append((int(m.group(1)), base, p))
        elif base.startswith('摘要'):
            abstracts.append(p)
        else:
            others.append(p)
    ordered = [p for _, _, p in sorted(chapters)] + sorted(others)
    return (abstracts + ordered) if include_abstract else ordered, ([] if include_abstract else abstracts)


def order_check(used):
    """首次出现顺序：出现得比更大编号晚的，记为一处问题，并记下造成它的那个提前出现的编号。"""
    late, max_n, max_c = [], 0, None
    for n, cs in used.items():
        if n < max_n:
            late.append(dict(n=n, at=cs[0], after=max_n, after_at=max_c))
        elif n > max_n:
            max_n, max_c = n, cs[0]
    return late


def check(files, refs_md, plain=False, terms=()):
    """files：[(名称, 内容)]，按正文顺序。返回结果字典，供命令行和测试使用。
    plain=False 且正文没有任何 <sup> 角标、却有裸 [n] 时，自动按 plain 处理（auto_plain=True）。"""
    refs, ref_issues = parse_refs(refs_md)
    auto_plain = False

    def scan(pl):
        cs, bs = [], []
        for name, md in files:
            c, b = scan_citations(name, md, pl)
            cs += c
            bs += b
        return cs, bs
    cites, bare = scan(plain)
    if not plain and not cites and bare:
        plain = auto_plain = True
        cites, bare = scan(True)
    used = OrderedDict()
    for c in cites:
        for n in c['nums']:
            used.setdefault(n, []).append(c)
    late = order_check(used)
    return dict(refs=refs, ref_issues=ref_issues, cites=cites, used=used,
                missing=sorted(n for n in used if n not in refs), unused=[n for n in refs if n not in used],
                late=late, first_order=list(used), range_only=[n for n in used if all(c['range'] for c in used[n])],
                bare=bare, plain=plain, auto_plain=auto_plain,
                terms=scan_terms(files, list(terms), plain) if terms else None)


def loc(c):
    return f'{c["file"]}:{c["line"]}'


def order_lines(late):
    if not late:
        return []
    causes = OrderedDict()
    for x in late:
        causes.setdefault((x['after'], loc(x['after_at'])), []).append(x['n'])
    out = [f'共 {len(late)} 处编号首次出现得比更大的编号晚，按造成问题的提前出现的编号归并：', '']
    for (n, where), ns in causes.items():
        out.append(f'- [{n}]（{where} 首次出现）之后才首次出现的编号 {len(ns)} 个：' + '、'.join(f'[{k}]' for k in ns[:15])
                   + ('…' if len(ns) > 15 else ''))
    out += ['', f'前 {min(ORDER_SHOW, len(late))} 处明细：', '']
    out += [f'- {loc(x["at"])} 首次出现 [{x["n"]}]，此前 {loc(x["after_at"])} 已出现 [{x["after"]}]' for x in late[:ORDER_SHOW]]
    return out


def report(r, abstract_cites=()):
    L = ['# 引用核对', '']
    mode = '裸 [n] 也计为角标（--plain）' if r['plain'] else '只认 <sup> 角标（源稿约定）'
    L.append(f'角标识别：{mode}。文献表 {len(r["refs"])} 条；正文角标 {len(r["cites"])} 处，涉及 {len(r["used"])} 条文献。')
    if r['auto_plain']:
        L.append('')
        L.append('注意：正文没有 <sup> 角标，但有裸 [n]，判断稿件不按源稿约定书写，已自动按 --plain 处理。如裸 [n] 并非引文，结论需人工复核。')
    L.append('')
    bullets = lambda xs: [f'- {x}' for x in xs]
    problems = [('缺号（角标有、文献表没有）', len(r['missing']), bullets('[%d] 见 %s' % (n, '、'.join(loc(c) for c in r['used'][n])) for n in r['missing'])),
                ('未引用（文献表有、正文没有）', len(r['unused']), bullets('[%d] %s' % (n, r['refs'][n][:60]) for n in r['unused'])),
                ('首次出现顺序', len(r['late']), order_lines(r['late'])),
                ('文献表本身', len(r['ref_issues']), bullets(r['ref_issues']))]
    if not r['plain']:
        problems.append(('疑似漏加上标（正文中未放在 <sup> 内的 [n]）', len(r['bare']), bullets(f'{loc(b)} {b["text"]}' for b in r['bare'])))
    for title, n, lines in problems:
        L.append(f'## {title}：{n if n else "无"}')
        if lines:
            L.append('')
        L += lines
        L.append('')
    if abstract_cites:
        L.append('## 摘要中的角标（不计入顺序检查）')
        L.append('摘要一般不引文献；如学校允许，用 --include-abstract 把摘要计入。')
        L += [f'- {loc(c)} ' + ''.join(f'[{n}]' for n in c['nums']) for c in abstract_cites]
        L.append('')
    if r['terms'] is not None:
        L.append('## 关键词与同处角标')
        L.append('同一理论、模型或定义出现了多个编号的，核对是否应统一为一条文献。')
        L.append('')
        L.append('| 关键词 | 同处角标（次数） | 多个编号 | 位置 |')
        L.append('|---|---|---|---|')
        for t, nums in r['terms'].items():
            if not nums:
                L.append(f'| {t} | — |  | 未在带角标的句子中出现 |')
                continue
            cnt = '、'.join(f'[{n}]×{len(v)}' for n, v in nums.items())
            where = '<br>'.join(f'[{n}] ' + '、'.join(v) for n, v in nums.items())
            L.append(f'| {t} | {cnt} | {"是" if len(nums) > 1 else ""} | {where} |')
        L.append('')
    L.append('## 每条文献被引位置')
    L.append('逐条看被引句子与文献内容是否相干；“只在区间中”的文献是凑引用的高发处，优先核对。')
    L.append('')
    L.append('| 编号 | 被引次数 | 只在区间中 | 位置 | 被引句子 |')
    L.append('|---|---|---|---|---|')
    for n in r['refs']:
        cs = r['used'].get(n, [])
        if not cs:
            L.append(f'| [{n}] | 0 | — | — | 未引用 |')
            continue
        pos = '<br>'.join(f'{loc(c)}（{c["section"] or "无小节"}）' for c in cs)
        sent = '<br>'.join(c['sentence'].replace('|', '\\|') for c in cs)
        L.append(f'| [{n}] | {len(cs)} | {"是" if n in r["range_only"] else ""} | {pos} | {sent} |')
    return '\n'.join(L) + '\n'


def has_errors(r):
    return bool(r['missing'] or r['unused'] or r['late'] or r['ref_issues'])


def read(p):
    if p.lower().endswith('.docx'):
        return docx_to_md(p)
    with open(p, encoding='utf-8-sig') as f:
        return f.read()


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8
    ap = argparse.ArgumentParser(description='核对引文角标与参考文献表')
    ap.add_argument('paths', nargs='+', help='源稿目录；按正文顺序列出的源稿文件；或一整篇 .md/.docx 稿件')
    ap.add_argument('--refs', help='参考文献源稿（目录模式默认为目录下的 参考文献.md；整篇稿件可不给）')
    ap.add_argument('-o', '--output', help='把报告写入 Markdown 文件（默认打印）')
    ap.add_argument('--plain', action='store_true', help='正文里的裸 [n] 也当角标（不按源稿约定书写的稿件）')
    ap.add_argument('--terms', help='逗号分隔的关键词，列出与它们同一分句出现的角标，如 Kraljic,COSO,BPR')
    ap.add_argument('--include-abstract', action='store_true', help='目录模式下摘要计入顺序检查')
    a = ap.parse_args(argv)

    skipped = []
    if len(a.paths) == 1 and os.path.isdir(a.paths[0]):
        d = a.paths[0]
        refs_path = a.refs or os.path.join(d, '参考文献.md')
        if not os.path.exists(refs_path):
            ap.error(f'找不到参考文献源稿：{refs_path}')
        paths = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.md')]
        ordered, skipped = order_files(paths, refs_path, a.include_abstract)
        files, refs_md = [(os.path.basename(p), read(p)) for p in ordered], read(refs_path)
    elif len(a.paths) == 1 and not a.refs:
        p = a.paths[0]
        if not os.path.exists(p):
            ap.error(f'找不到文件：{p}')
        body, refs_md = split_single(read(p))
        if refs_md is None:
            ap.error('稿件里找不到只写“参考文献”的标题行；用 --refs 另给文献表')
        files = [(os.path.basename(p), body)]
    else:
        if not a.refs:
            ap.error('列出多个文件时须用 --refs 指定参考文献源稿')
        for p in a.paths + [a.refs]:
            if not os.path.exists(p):
                ap.error(f'找不到文件：{p}')
        files = [(os.path.basename(p), read(p)) for p in a.paths if os.path.abspath(p) != os.path.abspath(a.refs)]
        refs_md = read(a.refs)

    terms = [t.strip() for t in re.split(r'[,，]', a.terms or '') if t.strip()]
    r = check(files, refs_md, plain=a.plain, terms=terms)
    abstract_cites = [c for p in skipped for c in scan_citations(os.path.basename(p), read(p), r['plain'])[0]]
    text = report(r, abstract_cites)
    if a.output:
        with open(a.output, 'w', encoding='utf-8') as f:
            f.write(text)
        print('已写入', a.output)
    else:
        print(text)
    print('结论：' + ('有问题，见上' if has_errors(r) else '缺号、未引用、顺序均无问题；相关性仍需人工逐条判断'),
          file=sys.stderr)
    return 1 if has_errors(r) else 0


if __name__ == '__main__':
    sys.exit(main())
