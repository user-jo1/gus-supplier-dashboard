#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为各区明细增加计件人数：7月明细行增加计时/计件字段，日均=计时+计件合计；
6月 people_supplier_chart daily_people 重算为含计件基准（按6月sheet）。"""
import json
import pandas as pd

XLSX = '/Users/mac/Desktop/GF_HR/01-劳务工:供应商管理/GUS_劳务供应商考核数据-7月.xlsx'
JSON_PATH = '/Users/mac/CodeBuddy/20260618112854/dashboard_data.json'

with open(JSON_PATH, encoding='utf-8') as f:
    d = json.load(f)

def fnum(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return f if f == f else 0.0  # NaN -> 0

# ── 1. 7月数据收集表（按 大区|仓库|供应商 取 计时/计件） ──
df7 = pd.read_excel(XLSX, sheet_name='数据收集表')
df7 = df7[df7['月份'] == '2026年 7月'].copy()
df7['_k'] = df7['大区'] + '|' + df7['仓库'] + '|' + df7['供应商']
map7 = {r['_k']: (fnum(r.get('计时使用人数（日均）')), fnum(r.get('计件使用人数（日均）')))
        for _, r in df7.iterrows()}

# 更新 detail_by_region_jul：每条记录增加 计时使用人数/计件使用人数，日均=合计
regions = list(d.get('detail_by_region_jul', {}).keys())
for reg in regions:
    for r in d['detail_by_region_jul'].get(reg, []):
        key = reg + '|' + r['仓库'] + '|' + r['供应商']
        tm, pc = map7.get(key, (fnum(r.get('日均使用人数')), 0.0))
        r['计时使用人数'] = round(tm)
        r['计件使用人数'] = round(pc)
        r['日均使用人数'] = round(tm + pc)

# ── 2. people_supplier_chart_jul daily_people = 计时+计件合计（按区） ──
for pc in d.get('people_supplier_chart_jul', []):
    reg = pc['region']
    sub = df7[df7['大区'] == reg]
    total = int(round(sub['计时使用人数（日均）'].sum() + sub['计件使用人数（日均）'].sum()))
    pc['daily_people'] = total

# ── 3. 6月 people_supplier_chart_jun daily_people 重算含计件（按6月sheet） ──
df6 = pd.read_excel(XLSX, sheet_name='6月各大区各仓库使用人数')
for pc in d.get('people_supplier_chart_jun', []):
    reg = pc['region']
    sub = df6[df6['大区'] == reg]
    total = int(round(sub['实际使用人数（日均）'].sum()))  # 计时+计件都已含在该sheet行内
    pc['daily_people'] = total

with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print('完成。验证：')
for pc in d['people_supplier_chart_jul']:
    print('  7月', pc['region'], 'daily_people=', pc['daily_people'])
print('--- 6月(新基准) ---')
for pc in d['people_supplier_chart_jun']:
    print('  6月', pc['region'], 'daily_people=', pc['daily_people'])
print('--- detail_jul CVG.H Grace / DFW.H B&A ---')
for reg in d['detail_by_region_jul']:
    for r in d['detail_by_region_jul'][reg]:
        if r['仓库'] == 'CVG.H' or (r['仓库'] == 'DFW.H' and r['供应商'] == 'B&A'):
            print(' ', reg, r['仓库'], r['供应商'], '计时=', r['计时使用人数'], '计件=', r['计件使用人数'], '日均=', r['日均使用人数'])
