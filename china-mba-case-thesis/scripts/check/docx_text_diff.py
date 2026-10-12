"""把两版 docx 转成纯文本、按句切开后对比，确认新版只有预期的改动。
    python3 docx_text_diff.py 旧版.docx 新版.docx [-o 差异.txt]
不依赖 pandoc；只比正文文字，不比格式。
"""
import sys, re, zipfile, difflib, argparse
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def paragraphs(path):
    root = ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    for p in root.iter(W + 'p'):
        # 只取 run 里的文字和制表符；pPr 里的 <w:tabs><w:tab/> 是制表位定义，不是内容
        t = ''.join('\t' if x.tag == W + 'tab' else (x.text or '') for r in p.iter(W + 'r') for x in r if x.tag in (W + 't', W + 'tab'))
        t = t.strip()
        if t:
            yield t


def sentences(path):
    out = []
    for para in paragraphs(path):
        out += [s for s in re.split(r'(?<=[。！？；])', para) if s.strip()]
    return out


ap = argparse.ArgumentParser()
ap.add_argument('old'); ap.add_argument('new'); ap.add_argument('-o', '--out')
a = ap.parse_args()
old, new = sentences(a.old), sentences(a.new)
diff = list(difflib.unified_diff(old, new, a.old, a.new, n=0, lineterm=''))
changed = sum(1 for l in diff if l[:1] in '+-' and not l.startswith(('+++', '---')))
text = '\n'.join(diff) if diff else '两版正文文字完全一致。'
if a.out:
    open(a.out, 'w', encoding='utf-8').write(text)
print(text if len(text) < 20000 else text[:20000] + '\n……（过长已截断，完整内容请用 -o 输出到文件）')
print(f'\n句子数：旧 {len(old)}，新 {len(new)}；变动行 {changed}')
