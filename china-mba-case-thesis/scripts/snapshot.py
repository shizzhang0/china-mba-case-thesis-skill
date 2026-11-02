"""把工作目录打成一个带日期和事件名的 zip 快照，放进 <工作目录>/归档/。
    python snapshot.py <工作目录> <事件名> [--exclude-dir 目录名 ...]
    例：python snapshot.py 写作过程 标题调整前 --exclude-dir 参考论文
默认排除常见临时目录；其他目录默认纳入。显式排除时会打印提醒。同一天同一事件名重复运行会加序号。
"""
import sys, os, zipfile, datetime
sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')   # Windows 下输出被重定向时默认编码不是 UTF-8，打印中文会报错

EXCLUDE = {'归档', 'tmp', '__pycache__', 'node_modules', '.git'}


def main(root, event, extra_excludes=()):
    root = os.path.abspath(root)
    arc_dir = os.path.join(root, '归档')
    os.makedirs(arc_dir, exist_ok=True)
    stamp = datetime.date.today().strftime('%Y%m%d')
    safe = ''.join(c for c in event if c not in '\\/:*?"<>|').strip() or '快照'
    out = os.path.join(arc_dir, f'{stamp}_{safe}.zip')
    k = 2
    while os.path.exists(out):
        out = os.path.join(arc_dir, f'{stamp}_{safe}_{k}.zip'); k += 1
    excluded = EXCLUDE | set(extra_excludes)
    files, total = [], 0
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in excluded]
        for fn in fns:
            p = os.path.join(dp, fn)
            files.append(p); total += os.path.getsize(p)
    print(f'快照将包含 {len(files)} 个文件，未压缩约 {total / 1024 / 1024:.1f} MiB。')
    if total >= 100 * 1024 * 1024:
        print('提示：快照内容较大；检查是否要用 --exclude-dir 明确排除不需要归档的资料目录。')
    if extra_excludes:
        print('本次明确排除目录：' + ', '.join(extra_excludes) + '（不会进入快照，请确认已有其他备份或确实无需归档）。')
    n = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, os.path.relpath(p, root)); n += 1
    print(f'已快照 {n} 个文件 → {out}')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?')
    parser.add_argument('event', nargs='?')
    parser.add_argument('--exclude-dir', action='append', default=[], help='明确排除一个目录名；可重复指定')
    args = parser.parse_args()
    if not args.root or not args.event:
        sys.exit(__doc__)
    main(args.root, args.event, args.exclude_dir)
