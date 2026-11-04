"""用 Crossref 批量核对英文参考文献，输出《参考文献核对清单》初稿。
    python3 crossref_check.py 参考文献.md [-o 参考文献核对清单.md] [--mailto 你的邮箱] [--only 3,5-8]
做法：逐条解析 GB/T 7714 著录（作者. 题名[类型]. 刊名, 年, 卷(期): 页码.）；条目里有 DOI 的按 DOI 查，
否则用“题名 + 第一作者”检索，取前 5 条结果比对。
判定（与 references/成文.md 的核对规则一致：只有完全吻合才算通过）：
  通过      题名一致，且作者、年、卷、期、页码中能比对的项都一致；Crossref 没有页码和文章编号时注明“页码未比对”
  有出入    题名一致，但有字段不一致：逐项列出 Crossref 的值，回原文 PDF 或出版方页面确认后改著录
  仅相近    没有题名一致的记录，只有相似的：不算通过，人工核对（可能是题名写错，也可能文献不存在）
  未查到    Crossref 没有相近记录：图书、会议论文和部分期刊不在 Crossref，换出版方页面、图书馆目录核对
  跳过      中文文献（题名含汉字）：不在 Crossref 的覆盖范围，按 成文.md 的中文渠道核对
  查询失败  网络或接口错误：稍后重跑，或用 --only 只查这几条
页码：Crossref 只有文章编号（article-number）没有页码的期刊，著录页码与文章编号不同即判“有出入”，避免“1-17”这类自拟页码被放过。
第一作者：按“姓在前、缩写名在后”解析，容忍 van、de、El 等姓氏前缀的写法差异；复合姓、中文拼音姓名等仍可能误报“有出入”，以原文为准。
注意：脚本会把英文文献的题名、第一作者和 DOI 发送给 api.crossref.org；只发这些公开书目信息，不发正文。
Crossref 建议在请求里附联系邮箱（--mailto，进入其“polite pool”，更稳定）；不给也能用。
只用标准库。存在“有出入”“仅相近”“未查到”或“查询失败”时退出码为 1。
"""
import argparse
import difflib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = 'https://api.crossref.org/works'
USER_AGENT = 'china-mba-case-thesis-crossref-check/0.5 (+https://github.com/shizzhang0/china-mba-case-thesis-skill)'
REF_LINE_RE = re.compile(r'^\s*\[(\d+)\]\s*(.+?)\s*$')
TYPE_RE = re.compile(r'\[([A-Z]{1,2})(?:/[A-Z]{1,2})?\]')
DOI_RE = re.compile(r'(?:doi\s*[:：]\s*|doi\.org/)(10\.\d{4,9}/[^\s，。]+?)[.。]?\s*$', re.I)
CJK_RE = re.compile(r'[\u3400-\u9fff]')
SIMILAR = 0.85   # 题名相似度阈值：低于它算“未查到”


def norm(s):
    return re.sub(r'[\W_]+', '', (s or '').lower())


def parse_entry(text):
    """GB/T 7714 著录 → dict(authors, first_family, title, type, journal, year, volume, issue, pages, doi)。解析不出的字段为 None。"""
    e = dict(raw=text, authors=None, first_author=None, first_family=None, title=None, type=None, journal=None,
             year=None, volume=None, issue=None, pages=None, doi=None)
    m = DOI_RE.search(text)
    if m:
        e['doi'] = m.group(1)
        text = text[:m.start()].rstrip(' .')
    t = TYPE_RE.search(text)
    head = text[:t.start()] if t else text
    tail = text[t.end():] if t else ''
    if t:
        e['type'] = t.group(1)
    # 作者与题名以第一个“. ”分开（GB/T 7714 的作者缩写不带点，如 Deming W E）
    k = head.find('. ')
    if k > 0:
        e['authors'], e['title'] = head[:k].strip(), head[k + 2:].strip()
    else:
        e['title'] = head.strip()
    if e['authors']:
        first = re.split(r'[,，;]', e['authors'])[0].strip()
        e['first_author'] = first or None
        # 姓在前、缩写名在后（Deming W E；van der Berg J）：去掉末尾的大写缩写，余下的是姓，可能带 van、de、El 等前缀
        toks = first.split()
        while len(toks) > 1 and re.fullmatch(r'[A-Z]{1,2}(?:-[A-Z])?\.?', toks[-1]):
            toks.pop()
        e['first_family'] = ' '.join(toks) or None
    tail = tail.lstrip('. ')
    if e['type'] == 'J':
        j = tail.split(',')[0].strip()
        e['journal'] = j or None
    y = re.search(r'(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)', tail)
    if y:
        e['year'] = y.group(1)
        after = tail[y.end():]
        vi = re.match(r'\s*,\s*([\w-]+)?\s*(?:\(([^)]+)\))?', after)
        if vi:
            e['volume'], e['issue'] = vi.group(1), vi.group(2)
    p = re.search(r'[:：]\s*([A-Za-z]?\d+(?:\s*[-–—]\s*[A-Za-z]?\d+)?)\s*\.?\s*$', tail)
    if p:
        e['pages'] = re.sub(r'\s*[-–—]\s*', '-', p.group(1))
    return e


def is_chinese(e):
    return bool(CJK_RE.search(e['title'] or e['raw']))


def record_fields(item):
    """Crossref 的 work 记录 → 与 parse_entry 同名的字段。"""
    title = ' '.join(item.get('title') or [])
    sub = ' '.join(item.get('subtitle') or [])
    if sub and norm(sub) not in norm(title):
        title = f'{title}: {sub}'
    year = None
    for key in ('published-print', 'published-online', 'issued', 'published'):
        parts = (item.get(key) or {}).get('date-parts') or [[None]]
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break
    authors = item.get('author') or []
    fam = authors[0].get('family') if authors else None
    return dict(title=title, first_family=fam, year=year, volume=item.get('volume'), issue=item.get('issue'),
                pages=(item.get('page') or '').replace('–', '-') or None, article_number=item.get('article-number'),
                journal=' '.join(item.get('container-title') or []) or None, doi=item.get('DOI'),
                authors='; '.join(' '.join(x for x in (a.get('family'), a.get('given')) if x) for a in authors) or None)


def same_family(ours, theirs):
    """第一作者的姓是否一致。容忍前缀写法差异：van der Berg / Berg、El Amrani / Amrani。"""
    a, b = norm(ours), norm(theirs)
    if a == b:
        return True
    last = lambda x: norm(x.split()[-1]) if x.split() else ''
    return bool(last(ours)) and last(ours) == last(theirs)


def compare(e, rec):
    """返回 (不一致的字段 [(字段, 著录值, Crossref 值)], 未能比对的字段说明 [...])；只比两边都有值的字段。"""
    diffs, unchecked = [], []

    def pair(name, a, b):
        if a and b and norm(a) != norm(b):
            diffs.append((name, a, b))
    if e['first_family'] and rec['first_family'] and not same_family(e['first_family'], rec['first_family']):
        diffs.append(('第一作者', e['first_family'], rec['first_family']))
    pair('年', e['year'], rec['year'])
    pair('卷', e['volume'], rec['volume'])
    pair('期', e['issue'], rec['issue'])
    if e['pages'] and rec['pages']:
        a, b = e['pages'].split('-'), rec['pages'].split('-')
        if norm(a[0]) != norm(b[0]) or (len(a) > 1 and len(b) > 1 and norm(a[-1]) != norm(b[-1])):
            diffs.append(('页码', e['pages'], rec['pages']))
    elif e['pages'] and rec.get('article_number'):
        # 只有文章编号的期刊：著录写成“1-17”这类页码无从核对，不能当作一致
        if norm(e['pages']) != norm(rec['article_number']):
            diffs.append(('页码', e['pages'], f'无页码，文章编号 {rec["article_number"]}'))
    elif e['pages']:
        unchecked.append('Crossref 无页码和文章编号，页码未比对')
    return diffs, unchecked


def title_score(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def judge(e, items):
    """e：parse_entry 结果；items：Crossref 返回的 work 列表。返回 dict(status, diffs, rec, score)。"""
    best, best_score = None, 0.0
    for it in items:
        rec = record_fields(it)
        s = title_score(e['title'] or '', rec['title'])
        if norm(rec['title']) == norm(e['title']):
            s = 1.0
        if s > best_score:
            best, best_score = rec, s
    if best is None or best_score < SIMILAR:
        return dict(status='未查到', diffs=[], rec=best, score=best_score)
    if best_score < 1.0:
        return dict(status='仅相近', diffs=[], rec=best, score=best_score)
    diffs, unchecked = compare(e, best)
    return dict(status='有出入' if diffs else '通过', diffs=diffs, rec=best, score=best_score,
                note='；'.join(unchecked) or None)


def fetch(url, timeout=20, retries=2):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for k in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            if k == retries or err.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError):
            if k == retries:
                raise
        time.sleep(2 * (k + 1))


def query(e, mailto=None):
    """返回 (Crossref work 列表, 依据 URL)。"""
    extra = {'mailto': mailto} if mailto else {}
    if e['doi']:
        url = f'{API}/{urllib.parse.quote(e["doi"], safe="/")}'
        if extra:
            url += '?' + urllib.parse.urlencode(extra)
        data = fetch(url)
        if data and data.get('message'):
            return [data['message']], f'https://doi.org/{e["doi"]}'
    q = ' '.join(x for x in (e['title'], e['first_family']) if x)
    params = dict(extra, **{'query.bibliographic': q, 'rows': 5})
    url = f'{API}?{urllib.parse.urlencode(params)}'
    data = fetch(url) or {}
    items = (data.get('message') or {}).get('items') or []
    shown = f'{API}?{urllib.parse.urlencode({"query.bibliographic": q, "rows": 5})}'
    return items, shown


def parse_only(spec):
    out = set()
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def cell(s):
    return (s or '').replace('|', '\\|').replace('\n', ' ')


def render(rows):
    count = {}
    for r in rows:
        count[r['status']] = count.get(r['status'], 0) + 1
    order = ['通过', '有出入', '仅相近', '未查到', '查询失败', '跳过']
    L = ['# 参考文献核对清单', '',
         '由 crossref_check.py 生成的初稿。“通过”以外的条目逐条回原文 PDF、出版方页面或数据库核对，核对结果和依据写回本表；核不到的留空，不编。', '',
         '统计：' + '，'.join(f'{k} {count[k]}' for k in order if k in count), '',
         '| 编号 | 著录 | 状态 | 不一致项 / 说明 | Crossref 记录 | 依据 |', '|---|---|---|---|---|---|']
    for r in rows:
        rec = r.get('rec')
        rec_s = ''
        if rec:
            vol = rec['volume'] or ''
            if rec['issue']:
                vol += f'({rec["issue"]})'
            an = rec.get('article_number')
            rec_s = '；'.join(x for x in (rec['title'], rec['authors'], rec['journal'], rec['year'], vol,
                                         rec['pages'], f'文章编号 {an}' if an else None,
                                         f'DOI {rec["doi"]}' if rec['doi'] else None) if x)
        diffs = '；'.join(f'{f}：著录“{a}”，Crossref“{b}”' for f, a, b in r.get('diffs', []))
        note = '；'.join(x for x in (diffs, r.get('note')) if x)
        L.append(f'| [{r["n"]}] | {cell(r["raw"][:90])} | {r["status"]} | {cell(note)} | {cell(rec_s)} | {cell(r.get("source"))} |')
    return '\n'.join(L) + '\n'


def run(refs_md, mailto=None, only=None, delay=1.0, query_fn=query, log=None):
    rows = []
    for line in refs_md.splitlines():
        m = REF_LINE_RE.match(line)
        if not m:
            continue
        n, raw = int(m.group(1)), m.group(2)
        if only and n not in only:
            continue
        e = parse_entry(raw)
        row = dict(n=n, raw=raw)
        if is_chinese(e):
            row.update(status='跳过', note='中文文献：对照期刊官网、ncpssd.cn 或学校数据库核对')
        elif not e['title']:
            row.update(status='未查到', note='著录解析不出题名，检查格式后人工核对')
        else:
            try:
                items, src = query_fn(e, mailto)
                row.update(judge(e, items), source=src)
                if row['status'] == '有出入' and e['type'] == 'M':
                    row['note'] = '图书常有多个版本，Crossref 记录可能是再版或电子版，以所用版本的版权页为准'
                elif row['status'] == '仅相近':
                    row['note'] = f'最接近记录题名相似度 {row["score"]:.2f}，不算通过，人工核对'
                elif row['status'] == '未查到':
                    row['note'] = 'Crossref 无相近记录；图书、会议论文常不在 Crossref，换出版方或图书馆目录核对'
                    row['rec'] = None
            except Exception as err:   # 网络错误不影响其他条目
                row.update(status='查询失败', note=f'{type(err).__name__}: {err}')
            if delay:
                time.sleep(delay)
        if log:
            log(f'[{n}] {row["status"]}')
        rows.append(row)
    return rows


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, 'reconfigure'):
            s.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8
    ap = argparse.ArgumentParser(description='用 Crossref 批量核对英文参考文献')
    ap.add_argument('refs', help='参考文献源稿（每条写作 [n] …）')
    ap.add_argument('-o', '--output', help='把核对清单写入 Markdown 文件（默认打印）')
    ap.add_argument('--mailto', help='附在请求里的联系邮箱（Crossref 建议提供，可不填）')
    ap.add_argument('--only', help='只查这些编号，如 3,5-8')
    ap.add_argument('--delay', type=float, default=1.0, help='两次请求之间的间隔秒数（默认 1）')
    a = ap.parse_args(argv)
    with open(a.refs, encoding='utf-8-sig') as f:
        md = f.read()
    rows = run(md, a.mailto, parse_only(a.only) if a.only else None, a.delay,
               log=lambda s: print(s, file=sys.stderr))
    text = render(rows)
    if a.output:
        with open(a.output, 'w', encoding='utf-8') as f:
            f.write(text)
        print('已写入', a.output, file=sys.stderr)
    else:
        print(text)
    bad = [r for r in rows if r['status'] not in ('通过', '跳过')]
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
