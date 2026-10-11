"""范文横向分析：批量提取范文 PDF 的全文，统计章节骨架、页数、图表数、参考文献数和关键词频次，输出一张表。
    python survey_samples.py <范文目录> [-o 结果.md] [--keywords 关键词1,关键词2,...]
范文目录可以有子目录（如“导师推荐”“本院同类”“外校”），子目录名会作为分组。
依赖：pdftotext（poppler）。没有的话 pip install pdfminer.six 也行（慢一些）。
统计是下限估计：跨行的图题可能漏计；目录解析依赖“第N章”“N.N”这类常见格式。
"""
import sys, os, re, subprocess, argparse, shutil
from collections import Counter

DEFAULT_KW = ['架构图', '数据库', 'E-R', 'UML', '用例', '开发环境', '微服务', '算法', '问卷', '访谈', '流程图', '对策', '保障措施', '预期效果']


def pdf_text(path):
    if shutil.which('pdftotext'):
        r = subprocess.run(['pdftotext', '-layout', path, '-'], capture_output=True)
        return r.stdout.decode('utf-8', 'ignore')
    from pdfminer.high_level import extract_text
    return extract_text(path)


def analyze(path, kws):
    t = pdf_text(path)
    pages = t.count('\f') + 1
    # 只认“第N章 标题”的目录/标题形式（阿拉伯数字），正文里“第一章是绪论”这类叙述不算
    chapters = re.findall(r'^\s*第\s*(\d+)\s*章\s*([^\n]{2,40})', t, re.M)
    seen, chap = set(), []
    for n, title in chapters:
        title = re.sub(r'[.…·\s]+\d*\s*$', '', title).strip()   # 去掉目录的引导点和页码
        if n not in seen and title:
            seen.add(n); chap.append(f'第{n}章 {title[:24]}')
    figs = set(re.findall(r'图\s*(\d+[.\-]\d+)', t))
    tabs = set(re.findall(r'表\s*(\d+[.\-]\d+)', t))
    refs = re.findall(r'^\s*\[(\d{1,3})\]', t, re.M)
    nref = max((int(x) for x in refs), default=0)
    has_appendix = bool(re.search(r'^\s*附\s*录', t, re.M))
    kw = {k: t.count(k) for k in kws}
    words = len(re.findall(r'[一-鿿]', t))
    return dict(pages=pages, chapters=chap, figs=len(figs), tabs=len(tabs), refs=nref, appendix=has_appendix, kw=kw, cn_chars=words)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('-o', '--out'); ap.add_argument('--keywords')
    a = ap.parse_args()
    kws = a.keywords.split(',') if a.keywords else DEFAULT_KW
    rows = []
    for dp, _, fns in os.walk(a.dir):
        group = os.path.relpath(dp, a.dir); group = '' if group == '.' else group
        for fn in sorted(fns):
            if fn.lower().endswith('.pdf'):
                try:
                    r = analyze(os.path.join(dp, fn), kws); r['name'] = fn[:-4]; r['group'] = group; rows.append(r)
                except Exception as e:
                    print('跳过', fn, e, file=sys.stderr)
    if not rows:
        sys.exit('没找到 PDF')
    out = ['# 范文横向分析（自动统计，下限估计）', '',
           '| 分组 | 论文 | 页数 | 汉字数(约) | 章数 | 图 | 表 | 文献 | 附录 | ' + ' | '.join(kws) + ' |',
           '|' + '---|' * (9 + len(kws))]
    for r in rows:
        out.append(f"| {r['group']} | {r['name'][:30]} | {r['pages']} | {r['cn_chars']//100*100} | {len(r['chapters'])} | {r['figs']} | {r['tabs']} | {r['refs']} | {'有' if r['appendix'] else '无'} | "
                   + ' | '.join(str(r['kw'][k]) for k in kws) + ' |')
    def med(key):
        v = sorted(x[key] for x in rows); return v[len(v) // 2]
    out += ['', f"中位数：页数 {med('pages')}，图 {med('figs')}，表 {med('tabs')}，文献 {med('refs')}", '', '## 章节骨架', '']
    for r in rows:
        out.append(f"**{r['name'][:30]}**（{r['group']}）"); out += [f'- {c}' for c in r['chapters']]; out.append('')
    text = '\n'.join(out)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text); print('已写入', a.out)
    else:
        print(text)


if __name__ == '__main__':
    main()
