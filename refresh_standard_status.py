#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""保留手工版 standard_status 的档位归属与占比上限(用户确认版)，
用重新合并后的供应商数据(7月各仓库使用人数 sheet 计时+计件合并)刷新每仓
现有家数/最高占比/达标状态/7月日均操作量/7月实际使用人数。
同时把 warehouse_550/660(单量已分档正确)注入。"""
import json
import re
import pandas as pd

HTML = '/Users/mac/CodeBuddy/20260618112854/dashboard_peaksupply.html'
BACKUP = '/Users/mac/CodeBuddy/20260618112854/dashboard_peaksupply_backup_20260902.html'
XLSX = '/Users/mac/Desktop/GF_HR/01-劳务工:供应商管理/GUS_劳务供应商考核数据-7月.xlsx'

def extract(text, key):
    start = text.find('"' + key + '": [')
    s = text.find('[', start)
    depth = 0; i = s
    while i < len(text):
        if text[i] == '[': depth += 1
        elif text[i] == ']':
            depth -= 1
            if depth == 0: return s, i + 1
        i += 1
    raise SystemExit('未找到 ' + key)

def get_json(text, key):
    s, e = extract(text, key)
    return json.loads(text[s:e])

# ── 1. 从备份取手工版 standard / standard_status（含档位归属 + 新占比上限） ──
with open(BACKUP, encoding='utf-8') as f:
    cb = f.read()
old_standard = get_json(cb, 'standard')
old_status = get_json(cb, 'standard_status')

# 手工档位归属：仓库 -> (档位key, 要求家数, 占比上限值)
tier_wh = {}
for t in old_status:
    for w in t['现状']:
        tier_wh[w['仓库']] = {
            '档位': t['档位'],
            '要求家数': w['要求家数'],
            '占比上限': w['占比上限'],
        }

# ── 2. 读取新 HTML(已注入的 model) 获取 warehouse / supplier ──
with open(HTML, encoding='utf-8') as f:
    c = f.read()
wh550 = get_json(c, 'warehouse_550')
wh660 = get_json(c, 'warehouse_660')
sup550 = get_json(c, 'supplier_550')
sup660 = get_json(c, 'supplier_660')

# ── 3. 货量 map（7月日均操作量） ──
df_vol = pd.read_excel(XLSX, sheet_name='7月各大区仓库货量')
df_vol['仓库'] = df_vol['仓库'].replace({'LAX.H': 'LAV.H', 'CNO.G': 'ONT.G', 'OG 美西区': 'ONT.G'})
vol_map = dict(zip(df_vol['仓库'], df_vol['日均操作量']))

# 各仓 7月日均操作量（来自 warehouse_660 已补充）
jul_vol_map = {w['仓库']: w.get('7月日均操作量', 0) for w in wh660}

# 供应商级（660 口径，含所有启用供应商=7月在岗>0）
sup_map = {}  # wh -> list of {供应商, 7月在岗}
for s in sup660:
    sup_map.setdefault(s['仓库'], []).append(s)

# ── 4. 重算 standard_status ──
new_status = []
for t in old_status:
    details = []
    for w in t['现状']:
        wh = w['仓库']
        req_n = w['要求家数']
        cap = w['占比上限']
        sups = [s for s in sup_map.get(wh, []) if s['7月在岗人数'] > 0]
        n = len(sups)
        max_r = max([s['供给占比'] for s in sups], default=0)
        # 达标判定: 家数>=要求 且 最高占比<=上限
        status = '达标' if (n >= req_n and max_r <= cap) else '预警'
        jul_mp = sum(s['7月在岗人数'] for s in sups)
        details.append({
            '仓库': wh,
            '现有家数': n,
            '要求家数': req_n,
            '最高占比': round(max_r, 4),
            '占比上限': cap,
            '7月日均操作量': round(jul_vol_map.get(wh, 0), 0),
            '7月实际使用人数': round(jul_mp, 0),
            '状态': status,
        })
    ok = sum(1 for x in details if x['状态'] == '达标')
    new_status.append({
        '档位': t['档位'],
        '仓库数': len(details),
        '达标数': ok,
        '预警数': len(details) - ok,
        '现状': details,
    })

# ── 5. 替换 HTML 中的 standard / standard_status ──
for key, data in [('standard', old_standard), ('standard_status', new_status)]:
    s, e = extract(c, key)
    c = c[:s] + json.dumps(data, ensure_ascii=False, indent=2) + c[e:]

with open(HTML, 'w', encoding='utf-8') as f:
    f.write(c)
print('standard_status 刷新完成')

# 验证
s2, e2 = extract(c, 'standard_status')
for t in json.loads(c[s2:e2]):
    print(f"{t['档位']}: 仓库{len(t['现状'])} 达标{t['达标数']} 预警{t['预警数']}")
    for w in t['现状']:
        print(f"    {w['仓库']}: 家数{w['现有家数']}/{w['要求家数']} 最高占比{w['最高占比']*100:.0f}% 上限{w['占比上限']*100:.0f}% {w['状态']} 在岗{w['7月实际使用人数']}")
