"""把工作目录打成一个带日期和事件名的 zip 快照，放进 <工作目录>/归档/。
    python snapshot.py <工作目录> <事件名>
    例：python snapshot.py 写作过程 标题调整前   →  写作过程/归档/20250315_标题调整前.zip
排除 归档/ 和 tmp/。同一天同一事件名重复运行会加序号。
"""
import sys, os, zipfile, datetime
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错

EXCLUDE = {'归档', 'tmp', '__pycache__', 'node_modules', '.git'}


def main(root, event):
    root = os.path.abspath(root)
    arc_dir = os.path.join(root, '归档')
    os.makedirs(arc_dir, exist_ok=True)
    stamp = datetime.date.today().strftime('%Y%m%d')
    safe = ''.join(c for c in event if c not in '\\/:*?"<>|').strip() or '快照'
    out = os.path.join(arc_dir, f'{stamp}_{safe}.zip')
    k = 2
    while os.path.exists(out):
        out = os.path.join(arc_dir, f'{stamp}_{safe}_{k}.zip'); k += 1
    n = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in EXCLUDE]
            for fn in fns:
                p = os.path.join(dp, fn)
                z.write(p, os.path.relpath(p, root)); n += 1
    print(f'已快照 {n} 个文件 → {out}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
