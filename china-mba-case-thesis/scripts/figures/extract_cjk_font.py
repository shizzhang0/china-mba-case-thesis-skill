"""从 Noto/思源 CJK 字体集合（.ttc）中取出简体中文字形，存成单独的 .otf，供 matplotlib 加载。
matplotlib 读 .ttc 时常常选错语言版本，导致中文缺字或用成日文字形。
    python3 extract_cjk_font.py [字体集合.ttc] [输出.otf]
依赖：pip install fonttools
"""
import sys, glob
from fontTools.ttLib import TTCollection

src = sys.argv[1] if len(sys.argv) > 1 else None
if not src:
    cands = glob.glob('/usr/share/fonts/**/NotoSerifCJK-Regular.ttc', recursive=True) + \
            glob.glob('/usr/share/fonts/**/SourceHanSerif*.ttc', recursive=True)
    if not cands:
        sys.exit('没找到 CJK 字体集合，请把 .ttc 路径作为第一个参数传入')
    src = cands[0]
out = sys.argv[2] if len(sys.argv) > 2 else 'NotoSerifSC.otf'
for f in TTCollection(src).fonts:
    if 'SC' in (f['name'].getDebugName(1) or ''):
        f.save(out)
        print('已保存', out, '←', f['name'].getDebugName(1))
        break
else:
    sys.exit('集合中没有简体中文（SC）字形')
