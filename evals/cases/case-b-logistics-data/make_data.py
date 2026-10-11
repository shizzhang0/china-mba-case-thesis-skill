"""生成案例 B（HX 物流）的虚构企业数据，并计算标准答案。"""
import csv, random, os, sys, json

out = sys.argv[1]
d = os.path.join(out, 'materials', '企业数据')
os.makedirs(d, exist_ok=True)
rnd = random.Random(20250402)

# 车辆台账：自有 18 台，外包承运商车辆 26 台
rows = []
for i in range(1, 19):
    rows.append((f'ZY{i:03d}', '自有', rnd.choice(['4.2米厢式', '6.8米厢式', '9.6米厢式']), rnd.choice([2019, 2020, 2021, 2022, 2023])))
for i in range(1, 27):
    rows.append((f'WB{i:03d}', '外包', rnd.choice(['4.2米厢式', '6.8米厢式', '9.6米厢式', '冷藏车']), ''))
with open(os.path.join(d, '车辆台账.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['车辆编号', '归属', '车型', '购置年份']); w.writerows(rows)

# 近 12 个月配送准时情况（2024-04 至 2025-03）
months = [f'2024-{m:02d}' for m in range(4, 13)] + [f'2025-{m:02d}' for m in range(1, 4)]
ot = []
for m in months:
    n = rnd.randint(2600, 3400)
    rate = rnd.uniform(0.83, 0.91)
    ot.append((m, n, round(n * rate)))
with open(os.path.join(d, '配送准时情况_近12个月.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['月份', '配送单数', '准时送达单数']); w.writerows(ot)

# 仓库设备清单
eq = [('电动叉车', 6), ('手动液压搬运车', 14), ('RF 手持终端', 12), ('标签打印机', 4), ('货架（组）', 220)]
with open(os.path.join(d, '仓库设备清单.csv'), 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.writer(f); w.writerow(['设备', '数量']); w.writerows(eq)

tot_n = sum(x[1] for x in ot); tot_ok = sum(x[2] for x in ot)
key = {
    '自有车辆': 18, '外包车辆': 26, '外包占比': f'{26 / 44:.1%}',
    '近12个月准时率（按单数加权）': f'{tot_ok / tot_n:.1%}',
    '近12个月准时率（月度简单平均）': f'{sum(x[2] / x[1] for x in ot) / 12:.1%}',
    '上年度准时率（经营简表）': '91.2%',
    '仓库面积': '16000 平方米',
    'RF 手持终端': 12,
    '员工人数': 158,
    '应识别的冲突': ['自有车辆 30 台 vs 台账 18 台（另有外包 26 台）',
                  '准时率约 95% vs 近12个月约 {:.1%}、上年度 91.2%'.format(tot_ok / tot_n),
                  '仓库面积约 2 万平方米 vs 16000 平方米',
                  '拣货全部人工纸单 vs 有 12 台 RF 手持终端'],
    '不应误报为冲突': '员工约 160 人 vs 158 人（一致）',
    '统计期间陷阱': '准时率有两个口径：近 12 个月（2024-04 至 2025-03）与上年度（2024 年），需作者确认用哪个并在正文写明',
    '未到位': '运输成本明细',
}
json.dump(key, open(os.path.join(out, 'answer_key.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(json.dumps(key, ensure_ascii=False, indent=1))
