"""核对 Markdown 源稿的引文角标与参考文献表（GB/T 7714 顺序编码制）。
    python3 ref_check.py <源稿目录> [--refs 参考文献.md] [-o 引用核对.md] [--include-abstract]
    python3 ref_check.py 第1章-绪论.md 第2章-理论基础.md ... --refs 参考文献.md
检查：
  1）缺号：角标里的编号在文献表中没有条目；
  2）未引用：文献表条目从未被正文引用；
  3）顺序：按章节顺序，各编号首次出现的次序应为 1、2、3……；
  4）文献表本身：编号重复、不连续，疑似重复条目（题名相同）；
  5）疑似漏加上标：正文里不在 <sup> 内的 [n] 形式。
另列出每条文献被引的位置（文件、行号、所在小节和句子），用来人工判断引用是否与所在句相干、是否为凑“全部被引”而挂角标；
只在“[3-15]”这类连续区间里出现过的文献会单独标出，优先人工核对。
认的角标写法：<sup>[1]</sup>、<sup>[1][3]</sup>、<sup>[1,3]</sup>、<sup>[1，3]</sup>、<sup>[2-4]</sup>（-、–、—、~ 均可）。
解析规则与 build_docx.py 一致：以 > 开头的写作备注（资料来源、注除外）和“## 本章待…”之后的内容不检查，代码块也跳过。
给目录时按“第N章”排序，其后是其他源稿（附录等）；摘要默认不参与顺序检查，但其中的角标会被报告（摘要一般不宜引文献）。
只用标准库。发现缺号、未引用、顺序或文献表编号问题时退出码为 1。
"""
import argparse
import os
import re
import sys
from collections import OrderedDict

NOTE_RE = re.compile(r'^(资料来源|注)')
CUT_RE = re.compile(r'^##\s*(本章待|待补)')
CHAPTER_RE = re.compile(r'^第(\d+)章')
SUP_RE = re.compile(r'<sup>(.*?)</sup>', re.S)
BRACKET_RE = re.compile(r'\[([^\[\]]*)\]')
RANGE_RE = re.compile(r'^(\d+)\s*[-–—~～]\s*(\d+)$')
REF_LINE_RE = re.compile(r'^\s*\[(\d+)\]\s*(.*\S)?\s*$')
BARE_CITE_RE = re.compile(r'(?<![!\]])\[(\d+(?:\s*[-–—~～,，、]\s*\d+)*)\](?!\()')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*\S)')


def parse_cite(inner):
    """'[1][3]'、'[1,3]'、'[2-4]' 这类上标内容 → ([编号...], 是否含区间)。不是数字角标时返回 ([], False)。"""
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


def sentence_at(line, pos, width=60):
    """角标所在的句子（按中文句号等切分），过长时截断。"""
    start = max(line.rfind(c, 0, pos) for c in '。！？；!?;') + 1
    ends = [line.find(c, pos) for c in '。！？；!?;']
    ends = [e for e in ends if e >= 0]
    end = (min(ends) + 1) if ends else len(line)
    s = re.sub(r'<sup>.*?</sup>', '', line[start:end]).strip()
    s = re.sub(r'^[#>\s]+', '', s)
    return s if len(s) <= width else s[:width] + '…'


def scan_citations(name, md):
    """返回 (引用列表, 疑似漏上标列表)。引用：dict(file, line, section, nums, range, sentence)。"""
    cites, bare, section = [], [], ''
    for ln, line in body_lines(md):
        h = HEADING_RE.match(line.strip())
        if h:
            section = h.group(2)
        for m in SUP_RE.finditer(line):
            nums, has_range = parse_cite(m.group(1))
            if nums:
                cites.append(dict(file=name, line=ln, section=section, nums=nums, range=has_range,
                                  sentence=sentence_at(line, m.start())))
        rest = SUP_RE.sub('', line)
        if REF_LINE_RE.match(rest) and rest.lstrip().startswith('['):
            continue   # 像文献表条目的行，不当正文
        for m in BARE_CITE_RE.finditer(rest):
            bare.append(dict(file=name, line=ln, text=m.group(0)))
    return cites, bare


def parse_refs(md):
    """文献表 → (OrderedDict{编号: 著录}, 问题列表)。"""
    refs, issues = OrderedDict(), []
    for ln, line in enumerate(md.splitlines(), 1):
        m = REF_LINE_RE.match(line)
        if not m:
            continue
        n, text = int(m.group(1)), (m.group(2) or '').strip()
        if n in refs:
            issues.append(f'文献表编号 [{n}] 重复（第 {ln} 行）')
            continue
        refs[n] = text
    nums = list(refs)
    if nums:
        expected = list(range(1, len(nums) + 1))
        if nums != expected:
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


def check(files, refs_md):
    """files：[(名称, 内容)]，按正文顺序。返回结果字典，供命令行和测试使用。"""
    refs, ref_issues = parse_refs(refs_md)
    cites, bare = [], []
    for name, md in files:
        c, b = scan_citations(name, md)
        cites += c
        bare += b
    used = OrderedDict()
    for c in cites:
        for n in c['nums']:
            used.setdefault(n, []).append(c)
    missing = sorted(n for n in used if n not in refs)
    unused = [n for n in refs if n not in used]
    first_order = list(used)
    order_issues, expect = [], 1
    for n in first_order:
        if n != expect:
            c = used[n][0]
            order_issues.append(f'{c["file"]}:{c["line"]} 首次出现 [{n}]，按顺序此处应首次出现 [{expect}]')
            break
        expect += 1
    range_only = [n for n in used if all(c['range'] for c in used[n])]
    return dict(refs=refs, ref_issues=ref_issues, cites=cites, used=used, missing=missing, unused=unused,
                order_issues=order_issues, first_order=first_order, range_only=range_only, bare=bare)


def report(r, abstract_cites=()):
    L = ['# 引用核对', '']
    L.append(f'文献表 {len(r["refs"])} 条；正文角标 {len(r["cites"])} 处，涉及 {len(r["used"])} 条文献。')
    L.append('')
    problems = [('缺号（角标有、文献表没有）', ['[%d] 见 %s' % (n, '、'.join(f'{c["file"]}:{c["line"]}' for c in r['used'][n])) for n in r['missing']]),
                ('未引用（文献表有、正文没有）', ['[%d] %s' % (n, r['refs'][n][:60]) for n in r['unused']]),
                ('首次出现顺序', r['order_issues']),
                ('文献表本身', r['ref_issues']),
                ('疑似漏加上标（正文中未放在 <sup> 内的 [n]）', [f'{b["file"]}:{b["line"]} {b["text"]}' for b in r['bare']])]
    for title, items in problems:
        L.append(f'## {title}：{"无" if not items else len(items)}')
        L += [f'- {x}' for x in items]
        L.append('')
    if abstract_cites:
        L.append('## 摘要中的角标（不计入顺序检查）')
        L.append('摘要一般不引文献；如学校允许，用 --include-abstract 把摘要计入。')
        L += [f'- {c["file"]}:{c["line"]} ' + ''.join(f'[{n}]' for n in c['nums']) for c in abstract_cites]
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
        pos = '<br>'.join(f'{c["file"]}:{c["line"]}（{c["section"] or "无小节"}）' for c in cs)
        sent = '<br>'.join(c['sentence'].replace('|', '\\|') for c in cs)
        L.append(f'| [{n}] | {len(cs)} | {"是" if n in r["range_only"] else ""} | {pos} | {sent} |')
    return '\n'.join(L) + '\n'


def has_errors(r):
    return bool(r['missing'] or r['unused'] or r['order_issues'] or r['ref_issues'])


def read(p):
    with open(p, encoding='utf-8-sig') as f:
        return f.read()


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8
    ap = argparse.ArgumentParser(description='核对 Markdown 源稿的引文角标与参考文献表')
    ap.add_argument('paths', nargs='+', help='源稿目录，或按正文顺序列出的源稿文件')
    ap.add_argument('--refs', help='参考文献源稿（默认：目录下的 参考文献.md）')
    ap.add_argument('-o', '--output', help='把报告写入 Markdown 文件（默认打印）')
    ap.add_argument('--include-abstract', action='store_true', help='摘要计入顺序检查')
    a = ap.parse_args(argv)

    if len(a.paths) == 1 and os.path.isdir(a.paths[0]):
        d = a.paths[0]
        refs_path = a.refs or os.path.join(d, '参考文献.md')
        paths = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.md')]
        ordered, skipped = order_files(paths, refs_path, a.include_abstract)
    else:
        if not a.refs:
            ap.error('列出文件时须用 --refs 指定参考文献源稿')
        refs_path = a.refs
        ordered = [p for p in a.paths if os.path.abspath(p) != os.path.abspath(refs_path)]
        skipped = []
    if not os.path.exists(refs_path):
        ap.error(f'找不到参考文献源稿：{refs_path}')

    r = check([(os.path.basename(p), read(p)) for p in ordered], read(refs_path))
    abstract_cites = [c for p in skipped for c in scan_citations(os.path.basename(p), read(p))[0]]
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
