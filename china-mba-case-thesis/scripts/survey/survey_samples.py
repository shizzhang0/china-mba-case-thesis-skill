"""范文横向分析：批量提取范文 PDF 的全文，统计章节骨架、页数、图表数、参考文献数和关键词频次，输出一张表。
    python survey_samples.py <范文目录> [-o 结果.md] [--keywords 关键词1,关键词2,...]
范文目录可以有子目录（如“导师推荐”“本院同类”“外校”），子目录名会作为分组。
依赖：pdftotext（poppler）。没有的话 pip install pdfminer.six 也行（慢一些）。
统计是下限估计：跨行的图题可能漏计；目录解析依赖“第N章”“N.N”这类常见格式。
"""
import sys, os, re, subprocess, argparse, shutil, tempfile
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错

DEFAULT_KW = ['架构图', '数据库', 'E-R', 'UML', '用例', '开发环境', '微服务', '算法', '问卷', '访谈', '流程图', '对策', '保障措施', '预期效果']


def pdf_text(path):
    if shutil.which('pdftotext'):
        # -enc UTF-8：xpdf 版 pdftotext 默认按 Latin1 输出，中文会丢；有的版本打不开中文路径，先复制成临时文件
        with tempfile.TemporaryDirectory() as d:
            tmp = os.path.join(d, 'in.pdf'); shutil.copyfile(path, tmp)
            r = subprocess.run(['pdftotext', '-enc', 'UTF-8', '-layout', tmp, '-'], capture_output=True)
        if r.returncode == 0:
            return r.stdout.decode('utf-8', 'ignore')
        print('pdftotext 失败，改用 pdfminer：', r.stderr.decode('utf-8', 'ignore').strip()[:200], file=sys.stderr)
    from pdfminer.high_level import extract_text
    return extract_text(path)


def analyze(path, kws):
    t = pdf_text(path)
    pages = t.count('\f') + (0 if t.rstrip('\r\n ').endswith('\f') else 1)   # 每页末尾各有一个分页符
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
    return dict(pages=pages, chapters=chap, figs=len(figs), tabs=len(tabs), refs=nref, appendix=has_appendix, kw=kw, cn_chars=words, text_ok=bool(words))


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
                    if r['cn_chars'] == 0:
                        print('警告', fn, '提取不到汉字（扫描版 PDF？），这一行的统计不可用', file=sys.stderr)
                except Exception as e:
                    print('跳过', fn, e, file=sys.stderr)
    if not rows:
        sys.exit('没找到 PDF')
    out = ['# 范文横向分析（自动统计；仅描述当前样本）', '',
           '> 自动统计是文本提取结果，不代表样本有代表性。汇总值按分组分别描述，不得直接当作写作规范；样本适用性由作者结合年份、院校、专业学位和案例类型判断。', '',
           '| 分组 | 论文 | 文本提取 | 页数 | 汉字数(约) | 章数 | 图 | 表 | 文献 | 附录 | ' + ' | '.join(kws) + ' |',
           '|' + '---|' * (10 + len(kws))]
    for r in rows:
        out.append(f"| {r['group'] or '未分组'} | {r['name'][:30]} | {'可用' if r['text_ok'] else '不可用'} | {r['pages'] if r['text_ok'] else '—'} | {r['cn_chars']//100*100 if r['text_ok'] else '—'} | {len(r['chapters']) if r['text_ok'] else '—'} | {r['figs'] if r['text_ok'] else '—'} | {r['tabs'] if r['text_ok'] else '—'} | {r['refs'] if r['text_ok'] else '—'} | {'有' if r['appendix'] else '无' if r['text_ok'] else '—'} | "
                   + ' | '.join(str(r['kw'][k]) if r['text_ok'] else '—' for k in kws) + ' |')
    out += ['', '## 分组描述性中位数（仅供描述，不作为目标值）', '']
    groups = sorted(set(r['group'] or '未分组' for r in rows))
    for group in groups:
        valid = [r for r in rows if (r['group'] or '未分组') == group and r['text_ok']]
        if not valid:
            out.append(f'- **{group}**：无可用文本，不能计算文本指标；扫描件请人工核对。')
            continue
        def med(key):
            v = sorted(x[key] for x in valid); return v[len(v) // 2]
        out.append(f"- **{group}**（可用文本 {len(valid)} 篇 / 收录 {sum((r['group'] or '未分组') == group for r in rows)} 篇）：页数 {med('pages')}，汉字数约 {med('cn_chars')//100*100}，图 {med('figs')}，表 {med('tabs')}，文献 {med('refs')}。是否可推广需人工判断。")
    out += ['', '## 章节骨架', '']
    for r in rows:
        if not r['text_ok']:
            continue
        out.append(f"**{r['name'][:30]}**（{r['group'] or '未分组'}）"); out += [f'- {c}' for c in r['chapters']]; out.append('')
    text = '\n'.join(out)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(text); print('已写入', a.out)
    else:
        print(text)


if __name__ == '__main__':
    main()
