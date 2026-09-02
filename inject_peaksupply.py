#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 model_data_7.json 嵌入 dashboard_peaksupply.html 的 D 对象，并补充
每个仓库的 7月日均操作量（取自《7月各大区仓库货量》sheet 日均操作量列）。"""
import json
import re
import pandas as pd

HTML = '/Users/mac/CodeBuddy/20260618112854/dashboard_peaksupply.html'
JSON = '/Users/mac/CodeBuddy/20260618112854/model_data_7.json'
XLSX = '/Users/mac/Desktop/GF_HR/01-劳务工:供应商管理/GUS_劳务供应商考核数据-7月.xlsx'

with open(JSON, encoding='utf-8') as f:
    d = json.load(f)

# 补充 7月日均操作量（7月各大区仓库货量 sheet）
df_vol = pd.read_excel(XLSX, sheet_name='7月各大区仓库货量')
df_vol['仓库'] = df_vol['仓库'].replace({'LAX.H': 'LAV.H', 'CNO.G': 'ONT.G', 'OG 美西区': 'ONT.G'})
vol_map = dict(zip(df_vol['仓库'], df_vol['日均操作量']))

for key in ['warehouse_550', 'warehouse_660']:
    for w in d.get(key, []):
        w['7月日均操作量'] = round(float(vol_map.get(w['仓库'], w.get('7月日均操作量', w.get('操作单量', 0)))), 1)

with open(HTML, encoding='utf-8') as f:
    c = f.read()

# 替换 D 对象：从 "try{D={" 到 "};init();"
start = c.find('try{D={')
end = c.find('};init();', start)
if start < 0 or end < 0:
    raise SystemExit('未找到 D 对象边界!')

new_d = json.dumps(d, ensure_ascii=False, indent=2)
c2 = c[:start] + 'try{D=' + new_d + c[end:]

with open(HTML, 'w', encoding='utf-8') as f:
    f.write(c2)

print('注入完成。HTML字节数:', len(c2))
