"""用 LibreOffice 打开 docx、更新目录后导出 PDF，可选生成每页缩略图，用来抽查版面。
    python3 render_pdf.py 论文.docx 论文.pdf [--thumbs 缩略图目录] [--docx 另存.docx]
注意：没有装论文所用字体（宋体、Times New Roman 等）的机器上，排出来的页码会和 Word 差一两页。
这一步只看版面，页码以 Word 为准。
依赖：LibreOffice（soffice）及其 Python UNO 模块；缩略图需要 pdftoppm（poppler）。
必须用能 import uno 的 Python 运行（通常是系统自带的 python3）。
"""
import sys, os, time, subprocess, argparse
import uno
from com.sun.star.beans import PropertyValue


def pv(n, v):
    p = PropertyValue(); p.Name = n; p.Value = v; return p


ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('pdf')
ap.add_argument('--thumbs'); ap.add_argument('--docx', help='把更新过目录的文档另存一份 docx（仅供查看，不要拿它覆盖源稿生成的文件）')
ap.add_argument('--port', default='2002')
a = ap.parse_args()
src, pdf = os.path.abspath(a.src), os.path.abspath(a.pdf)

proc = subprocess.Popen(['soffice', '--headless', '--invisible', '--norestore',
                         f'--accept=socket,host=localhost,port={a.port};urp;'])
ctx = None
for _ in range(60):
    try:
        local = uno.getComponentContext()
        res = local.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', local)
        ctx = res.resolve(f'uno:socket,host=localhost,port={a.port};urp;StarOffice.ComponentContext'); break
    except Exception:
        time.sleep(1)
if ctx is None:
    proc.kill(); sys.exit('连不上 LibreOffice')
desk = ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
doc = desk.loadComponentFromURL('file://' + src, '_blank', 0, (pv('Hidden', True),))
idx = doc.getDocumentIndexes()
n_idx = idx.getCount()
for i in range(n_idx):
    idx.getByIndex(i).update()
doc.refresh()
doc.storeToURL('file://' + pdf, (pv('FilterName', 'writer_pdf_Export'),))
if a.docx:
    doc.storeToURL('file://' + os.path.abspath(a.docx), (pv('FilterName', 'MS Word 2007 XML'),))
doc.close(True)
try:
    desk.terminate()
except Exception:
    pass
proc.wait(timeout=30)
print('已导出', pdf, '（更新目录', n_idx, '个）')
if a.thumbs:
    os.makedirs(a.thumbs, exist_ok=True)
    subprocess.run(['pdftoppm', '-png', '-r', '40', pdf, os.path.join(a.thumbs, 'p')], check=True)
    print('缩略图在', a.thumbs)
