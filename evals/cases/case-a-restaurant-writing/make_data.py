"""生成案例 A（FS 连锁餐饮）的虚构数据，并计算标准答案。"""
import csv, random, os, sys, json
from collections import defaultdict

out = sys.argv[1]
os.makedirs(os.path.join(out, 'materials', '企业数据'), exist_ok=True)
rnd = random.Random(20250311)

stores = [f'S{i:02d}' for i in range(1, 13)]
base_rate = dict(zip(stores, [0.031, 0.024, 0.058, 0.036, 0.029, 0.067, 0.042, 0.033, 0.021, 0.047, 0.039, 0.052]))
months = [f'2024-{m:02d}' for m in range(1, 13)]

rows = []
for s in stores:
    for m in months:
        use = round(rnd.uniform(180000, 320000), -2)
        rate = base_rate[s] * rnd.uniform(0.85, 1.15)
        loss = round(use * rate, -1)
        rows.append((s, m, int(use), int(loss)))

with open(os.path.join(out, 'materials', '企业数据', '门店月度领用与报损_2024.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['门店代号', '月份', '领用金额（元）', '报损金额（元）']); w.writerows(rows)

# 报损单明细：把每个门店每月的报损金额拆成若干张报损单，原因和供应商随机
reasons = [('过期变质', 0.46), ('储存不当', 0.22), ('加工失误', 0.18), ('运输破损', 0.09), ('其他', 0.05)]
suppliers = ['华东鲜达食品有限公司', '沪南冷链农产品有限公司', '金穗粮油贸易有限公司', '海川水产供应链有限公司']
detail = []
for s, m, use, loss in rows:
    n = rnd.randint(3, 6)
    cuts = sorted(rnd.sample(range(1, loss // 10), n - 1))
    parts = [b - a for a, b in zip([0] + cuts, cuts + [loss // 10])]
    for k, p in enumerate(parts):
        r = rnd.choices([x[0] for x in reasons], [x[1] for x in reasons])[0]
        day = rnd.randint(1, 28)
        detail.append((f'{m}-{day:02d}', s, r, rnd.choice(suppliers), p * 10))
detail.sort()
with open(os.path.join(out, 'materials', '企业数据', '报损单明细_2024.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['日期', '门店代号', '报损原因', '供应商', '金额（元）']); w.writerows(detail)

# 标准答案
tot_use = sum(r[2] for r in rows); tot_loss = sum(r[3] for r in rows)
assert tot_loss == sum(d[4] for d in detail)
by_store = defaultdict(lambda: [0, 0])
for s, m, u, l in rows:
    by_store[s][0] += u; by_store[s][1] += l
srate = {s: l / u for s, (u, l) in by_store.items()}
hi = max(srate, key=srate.get); lo = min(srate, key=srate.get)
by_reason = defaultdict(int)
for d in detail:
    by_reason[d[2]] += d[4]
key = {
    '领用金额合计（元）': tot_use, '报损金额合计（元）': tot_loss,
    '全年整体损耗率': f'{tot_loss / tot_use:.2%}',
    '最高门店': [hi, f'{srate[hi]:.2%}'], '最低门店': [lo, f'{srate[lo]:.2%}'],
    '最高最低之比': round(srate[hi] / srate[lo], 2),
    '各门店损耗率': {s: f'{srate[s]:.2%}' for s in stores},
    '报损原因构成（按金额）': {r: f'{v / tot_loss:.1%}' for r, v in sorted(by_reason.items(), key=lambda x: -x[1])},
    '报损单张数': len(detail),
    '供应商名称（不得出现在正文）': suppliers,
}
json.dump(key, open(os.path.join(out, 'answer_key.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(json.dumps(key, ensure_ascii=False, indent=1))
