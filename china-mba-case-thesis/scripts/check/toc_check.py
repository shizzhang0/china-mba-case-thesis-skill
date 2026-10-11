"""核对 Word 目录：
  1）文字：目录条目与正文标题是否一致（能查出改了标题、目录却没更新）；
  2）页码：用 Word 保存时留下的分页标记（lastRenderedPageBreak）推算每个标题实际所在页，与目录页码比对。
    python3 toc_check.py 论文.docx
前提：文件必须是在 Word 里“更新整个目录”之后保存的。脚本刚生成、未经 Word 保存的文件没有目录内容，也没有分页标记。
局限：Word 不在表格内部留分页标记。脚本会在“标题前经过了表格且目录正好多 1 页”时按跨页表格自动修正并提示；
      其他差异需到 Word 里核实。
"""
import sys, re, zipfile
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
norm = lambda s: re.sub(r'\s+', '', s or '')


def roman(n):
    vals = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'),
            (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]
    s = ''
    for v, r in vals:
        while n >= v:
            s += r; n -= v
    return s


def pginfo(s):
    p = s.find(W + 'pgNumType')
    if p is None:
        return None, None
    st = p.get(W + 'start')
    return (int(st) if st else None), p.get(W + 'fmt')


def main(path):
    root = ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    body = root.find(W + 'body')
    sects = list(body.iter(W + 'sectPr'))
    has_marks = any(True for _ in body.iter(W + 'lastRenderedPageBreak'))

    phys, sec, started = 1, 0, True
    st0, fmt = pginfo(sects[0]) if sects else (None, None)
    offset = (1 - st0) if st0 else 0
    bm_page, bm_text, pending, toc = {}, {}, [], []
    table_since_break = False   # 自上一个分页标记以来是否经过了表格（表格内部不会留分页标记）
    bm_after_table = {}

    def disp(ph):
        n = ph - offset
        return roman(n) if fmt and 'Roman' in fmt else str(n)

    def walk(parent, in_table):
        for ch in parent:
            if ch.tag == W + 'tbl':
                yield from walk(ch, True)
            elif ch.tag == W + 'p':
                yield ch, in_table
            elif ch.tag in (W + 'tr', W + 'tc', W + 'sdt', W + 'sdtContent'):
                yield from walk(ch, in_table)

    for p, in_table in walk(body, False):
        if in_table:
            table_since_break = True
        instr = ''.join(x.text or '' for x in p.iter(W + 'instrText'))
        m = re.search(r'PAGEREF\s+(_Toc\d+)', instr)
        if m:  # 目录条目：条目文字 + PAGEREF 域结果（页码）
            state, label, result = 0, [], []
            for el in p.iter():
                if el.tag == W + 'instrText' and 'PAGEREF' in (el.text or ''):
                    state = 1
                elif el.tag == W + 'fldChar':
                    t = el.get(W + 'fldCharType')
                    if t == 'separate' and state == 1: state = 2
                    elif t == 'end' and state == 2: state = 0
                elif el.tag == W + 't' and el.text:
                    (result if state == 2 else label).append(el.text)
            toc.append((''.join(label).strip(), m.group(1), ''.join(result).strip()))
            continue
        ptext = ''.join(t.text or '' for t in p.iter(W + 't'))
        for el in p.iter():
            if el.tag == W + 'lastRenderedPageBreak':
                phys += 1; table_since_break = False
                if not started:  # 新一节的第一页：按该节的页码设置换算
                    started = True
                    st, fmt = pginfo(sects[sec]) if sec < len(sects) else (None, None)
                    if st is not None:
                        offset = phys - st
            elif el.tag == W + 'bookmarkStart' and (el.get(W + 'name') or '').startswith('_Toc'):
                pending.append(el.get(W + 'name')); bm_text[el.get(W + 'name')] = ptext
            elif el.tag == W + 't' and el.text and pending:
                for b in pending:
                    bm_page[b] = disp(phys); bm_after_table[b] = table_since_break
                pending = []
        ppr = p.find(W + 'pPr')
        if ppr is not None and ppr.find(W + 'sectPr') is not None:
            sec += 1; started = False

    if not toc:
        sys.exit('没找到目录条目（PAGEREF 域）：目录可能还没在 Word 里更新并保存。')

    # 1）文字核对
    text_bad = [(l, bm_text.get(b, '（找不到对应标题）')) for l, b, _ in toc if norm(l) != norm(bm_text.get(b))]
    print(f'【文字】共 {len(toc)} 条，{len(toc) - len(text_bad)} 条与正文标题一致。')
    for l, h in text_bad:
        print(f'  × 目录：{l}\n    正文：{h}')

    # 2）页码核对
    if not has_marks:
        print('【页码】文件里没有分页标记，跳过页码核对（请在 Word 中更新目录并保存后再查）。')
        return
    print('【页码】')
    corr, prev_delta, bad, fixed = 0, 0, 0, 0   # corr：因跨页表格累计补上的页数
    for l, b, shown in toc:
        act = bm_page.get(b)
        if not (shown.isdigit() and act and act.isdigit()):
            if shown != act:
                print(f'  ? 目录写 {shown}，推算 {act}　{l[:40]}'); bad += 1
            continue
        est = int(act) + corr
        delta = int(shown) - est
        if delta == 1 and bm_after_table.get(b):
            # 该标题之前经过了表格且目录正好多 1 页：按跨页表格处理，之后的推算整体加 1
            corr += 1; fixed += 1; delta = 0
            print(f'  ~ 「{l[:30]}」之前有跨页表格，推算页码从此加 1（目录 {shown} 视为正确）')
        if delta != prev_delta:
            if delta:
                print(f'  ! 从「{l[:30]}」起，目录页码比推算值多 {delta} 页，请在 Word 中核实。')
            else:
                print(f'  ✓ 从「{l[:30]}」起恢复一致。')
            prev_delta = delta
        bad += delta != 0
    print(f'  共 {len(toc)} 条，{len(toc) - bad} 条与推算一致' + (f'（其中 {fixed} 处按跨页表格修正）' if fixed else '') + '。')


if __name__ == '__main__':
    main(sys.argv[1])
