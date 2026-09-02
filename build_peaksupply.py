"""
仓库旺季劳务缺口测算 + 供应商供给占比风险预警模型 - 7月数据版
======================================================
数据来源：《GUS_劳务供应商考核数据-7月.xlsx》
- Sheet《旺季预测人数-NEewr-1160未上设备》：550w/660w两档旺季需求
- Sheet《7月各大区仓库货量》：7月各仓库货量
- Sheet《7月各大区各仓库使用人数》：7月各供应商在岗人数

用户需求：
1. 人力缺口对比（550/660）仅呈现7月数据
2. 仓库劳务用工总览：6月+7月数据对比
3. 供应商配置标准框架：仅呈现7月数据
"""
import pandas as pd
import numpy as np
import json
import os
import re

INPUT_FILE = '/Users/mac/Desktop/GF_HR/01-劳务工:供应商管理/GUS_劳务供应商考核数据-7月.xlsx'
OUTPUT_JSON = '/Users/mac/CodeBuddy/20260618112854/model_data_7.json'

# ---- 配置 ----
SAFE_THRESHOLD = 0.40
WARNING_THRESHOLD = 0.55
MIN_SUPPLIER_COUNT = 2
GROUND_MULTIPLIER_550 = 2.0
GROUND_MULTIPLIER_660 = 2.4

REGION_MAP = {
    'WE': 'WE 美西大区', 'TX': 'TX 德州大区', 'NE': 'NE 东北大区',
    'MS': 'MS 中南大区', 'GL': 'GL 大湖大区', 'FL': 'FL 佛州大区',
    'Ground': 'Ground项目部',
}
WH_NAME_MAP = {'LAX.H': 'LAV.H', 'CNO.G': 'ONT.G', 'OG 美西区': 'ONT.G'}

# ---- 读取 ----
xls = pd.ExcelFile(INPUT_FILE)
df_peak = pd.read_excel(xls, '旺季预测人数-NEewr-1160未上设备', header=None)
df_jul_volume = pd.read_excel(xls, '7月各大区仓库货量')
df_jul_manpower = pd.read_excel(xls, '7月各大区各仓库使用人数')
# 月份兼容：'2026年 7月' 字符串 或 46204（Excel数值日期 2026-07-01）
df_jul_manpower['_is_jul'] = (df_jul_manpower['月份'] == '2026年 7月') | (df_jul_manpower['月份'] == 46204)
df_jul_manpower = df_jul_manpower[df_jul_manpower['_is_jul']].drop(columns=['_is_jul']).copy()

# ---- 解析550w/660w 两档 HUB需求 ----
def parse_peak():
    rows = []
    cur_region = None
    for i in range(2, df_peak.shape[0]):
        r = df_peak.iloc[i]
        region = r[0]
        hub = r[1]
        t550 = r[15]
        t660 = r[28]

        if pd.notna(region) and str(region).strip():
            raw = str(region).strip()
            cur_region = raw.split('（')[0].strip()

        if pd.isna(hub) or str(hub).strip() in ('', 'nan'):
            continue

        wh = str(hub).strip()
        if wh.endswith('.G'):
            continue
        if wh.startswith('EWR.H-'):
            wh = 'EWR.H'
        wh = WH_NAME_MAP.get(wh, wh)

        d550 = int(float(t550)) if pd.notna(t550) and str(t550).strip() not in ('-', '') else 0
        d660 = int(float(t660)) if pd.notna(t660) and str(t660).strip() not in ('-', '') else 0
        # 550w下单量日均总操作=col2, 660w下单量日均总操作=col16（两档单量不同）
        vol = int(float(r[2])) if pd.notna(r[2]) and str(r[2]).strip() not in ('-', '') else 0
        vol660 = int(float(r[16])) if pd.notna(r[16]) and str(r[16]).strip() not in ('-', '') else 0
        region_name = REGION_MAP.get(cur_region, cur_region)

        rows.append({
            '大区': region_name, '仓库': wh,
            '需求550w': d550, '需求660w': d660,
            '操作量': vol, '操作量660': vol660,
            '仓库类型': 'HUB',
        })
    return pd.DataFrame(rows)

df_hub_peak = parse_peak()
df_hub_peak = df_hub_peak.groupby(['大区', '仓库'], as_index=False).agg({
    '需求550w': 'sum', '需求660w': 'sum', '操作量': 'sum', '操作量660': 'sum', '仓库类型': 'first'
})

# ---- Ground 7月在岗 + 货量（先映射仓库名，含 OG 美西区→ONT.G 计件行） ----
df_jul_manpower['仓库'] = df_jul_manpower['仓库'].replace(WH_NAME_MAP)
df_g_mp = df_jul_manpower[df_jul_manpower['仓库'].str.endswith('.G', na=False)].copy()
g_total = df_g_mp.groupby(['大区', '仓库'])['实际使用人数（日均）'].sum().reset_index()
g_total.columns = ['大区', '仓库', '7月总人数']

df_g_vol = df_jul_volume[df_jul_volume['仓库'].str.endswith('.G', na=False)].copy()
df_g_vol['仓库'] = df_g_vol['仓库'].replace(WH_NAME_MAP)
g_vol_map = dict(zip(df_g_vol['仓库'], df_g_vol['日均操作量']))
df_g_peak = g_total.copy()
df_g_peak['需求550w'] = (df_g_peak['7月总人数'] * GROUND_MULTIPLIER_550).round().astype(int)
df_g_peak['需求660w'] = (df_g_peak['7月总人数'] * GROUND_MULTIPLIER_660).round().astype(int)
df_g_peak['操作量'] = (df_g_peak['仓库'].map(g_vol_map).fillna(0) * GROUND_MULTIPLIER_660).round().astype(int)
df_g_peak['仓库类型'] = 'Ground'
df_g_peak['操作量660'] = df_g_peak['操作量']  # Ground 无660拆分单量，沿用同一货量口径

# ---- 合并所有仓库需求 ----
df_all_demand = pd.concat([df_hub_peak, df_g_peak], ignore_index=True)
df_all_demand['单量550w'] = df_all_demand['操作量']
# 660w下单量日均总操作 = col16（若缺失如 Ground，用 550w 单量同源）
df_all_demand['单量660w'] = df_all_demand['操作量660'].fillna(df_all_demand['操作量'])

# ---- 7月在岗（含未开仓库=0） ----
df_mp_hub = df_jul_manpower[~df_jul_manpower['仓库'].str.endswith('.G', na=False)].copy()
df_mp_hub['仓库'] = df_mp_hub['仓库'].replace(WH_NAME_MAP)
mp_hub_sum = df_mp_hub.groupby(['大区', '仓库', '供应商'])['实际使用人数（日均）'].sum().reset_index()
mp_hub_sum.columns = ['大区', '仓库', '供应商', '7月在岗人数']

hub_total = mp_hub_sum.groupby(['大区', '仓库'])['7月在岗人数'].sum().reset_index()
hub_total_map = dict(zip(zip(hub_total['大区'], hub_total['仓库']), hub_total['7月在岗人数']))

def hub_total_for(wh):
    return hub_total_map.get(wh, 0)

def merge_supplier(mp_df):
    total_map = mp_df.groupby(['大区', '仓库'])['7月在岗人数'].sum().to_dict()
    out = mp_df.copy()
    out['7月总人数'] = out.apply(lambda s: total_map.get((s['大区'], s['仓库']), 0), axis=1)
    out['供给占比'] = np.where(out['7月总人数'] > 0, out['7月在岗人数'] / out['7月总人数'], 0)
    out['风险等级'] = out['供给占比'].apply(lambda x: '高风险' if x > WARNING_THRESHOLD else ('预警' if x > SAFE_THRESHOLD else '安全'))
    return out

supplier_hub = merge_supplier(mp_hub_sum)
supplier_g = merge_supplier(df_g_mp.groupby(['大区', '仓库', '供应商'])['实际使用人数（日均）'].sum().reset_index().rename(columns={'实际使用人数（日均）': '7月在岗人数'}))
supplier_all = pd.concat([supplier_hub, supplier_g], ignore_index=True)

# ---- 5档货量配置标准 ----
def volume_tier(vol):
    if vol > 1000000: return 'S级', '超大型', '>100万单/日'
    if vol > 500000:  return 'A级', '大型', '50~100万单/日'
    if vol > 250000:  return 'B级', '中型', '25~50万单/日'
    if vol > 100000:  return 'C级', '中小型', '10~25万单/日'
    return 'D级', '小型', '≤10万单/日'

def demand_to_volume_tier(demand):
    if demand > 800: return 'S级', '超大型', '>100万单/日'
    if demand > 400: return 'A级', '大型', '50~100万单/日'
    if demand > 250: return 'B级', '中型', '25~50万单/日'
    if demand > 100: return 'C级', '中小型', '10~25万单/日'
    return 'D级', '小型', '≤10万单/日'

# ---- 6月在岗对比数据（取自7月Excel《6月各大区各仓库使用人数》sheet，供应商级） ----
try:
    df_jun_mp = pd.read_excel(xls, '6月各大区各仓库使用人数')
    # 月份兼容：46174（2026-06-01）或 '2026年 6月'
    df_jun_mp['_is_jun'] = (df_jun_mp['月份'] == '2026年 6月') | (df_jun_mp['月份'] == 46174)
    df_jun_mp = df_jun_mp[df_jun_mp['_is_jun']].drop(columns=['_is_jun']).copy()
    df_jun_mp['仓库'] = df_jun_mp['仓库'].replace(WH_NAME_MAP)
    # 仓库级6月在岗
    JUNE_STAFF = df_jun_mp.groupby('仓库')['实际使用人数（日均）'].sum().round().astype(int).to_dict()
    # 供应商级6月在岗（按 大区+仓库+供应商）
    JUNE_SUPPLIER = {}
    for _, r in df_jun_mp.iterrows():
        key = (r['大区'], r['仓库'], str(r['供应商']).strip())
        JUNE_SUPPLIER[key] = JUNE_SUPPLIER.get(key, 0) + float(r['实际使用人数（日均）'])
    print(f'✅ 6月在岗数据已加载: {len(JUNE_STAFF)}个仓库, {len(JUNE_SUPPLIER)}条供应商记录')
except Exception as e:
    print('⚠ 6月数据读取失败，使用内置数据:', e)
    JUNE_STAFF = {
        'MCO.H':168,'MIA.H':330,'CLE.H':0,'CVG.H':105,'ORD.H':761,'ATL.H':36,'CLT.H':138,
        'PDK.H':446,'BWI.H':102,'EWR.H':970,'JFK.H':66,'PHL.H':0,'DFW.H':712,'IAH.H':249,
        'CNO.H':567,'DEN.H':50,'LAV.H':262,'PHX.H':0,'SEA.H':54,'SFO.H':112,'SLC.H':0,
        'ATL.G':1,'CNO.G':54,'EWR.G':27,'ORD.G':15,'SAV.G':1,'SFO.G':8,
    }
    JUNE_SUPPLIER = {}

def build_warehouse(demand_col, demand_label, vol_col):
    wh_rows = []
    for _, w in df_all_demand.iterrows():
        wh = w['仓库']
        region = w['大区']
        demand = int(w[demand_col])
        vol = int(w[vol_col])
        # 7月在岗=四舍五入（保证与汇总5491一致）
        current = int(round(hub_total_map.get((region, wh), 0))) if w['仓库类型'] == 'HUB' else int(round(w['7月总人数']))
        june_staff = int(round(JUNE_STAFF.get(wh, 0)))
        gap = demand - current
        tier_name, tier_desc, tier_range = volume_tier(vol) if vol > 0 else demand_to_volume_tier(demand)
        wh_rows.append({
            '大区': region, '仓库': wh, '仓库类型': w['仓库类型'],
            '需求人数': demand, '6月在岗人数': june_staff, '7月在岗人数': current, '人数变化': current - june_staff, '人力缺口': gap,
            '缺口率': round(gap / demand, 4) if demand > 0 else 0,
            '操作单量': vol, '档位': tier_name, '档位描述': tier_desc, '日均操作量区间': tier_range,
        })
    df_wh = pd.DataFrame(wh_rows)

    sup_rows = []
    for _, s in supplier_all.iterrows():
        wh = s['仓库']
        region = s['大区']
        wh_row = df_wh[(df_wh['仓库'] == wh) & (df_wh['大区'] == region)]
        if wh_row.empty:
            continue
        demand = int(wh_row['需求人数'].iloc[0])
        gap = int(wh_row['人力缺口'].iloc[0])
        sup_key = (region, wh, str(s['供应商']).strip())
        june_sup = int(round(JUNE_SUPPLIER.get(sup_key, 0))) if JUNE_SUPPLIER else None
        sup_rows.append({
            '大区': region, '仓库': wh, '供应商': s['供应商'],
            '6月在岗人数': june_sup,
            '7月在岗人数': int(round(s['7月在岗人数'])),
            '人数变化': (int(round(s['7月在岗人数'])) - june_sup) if june_sup is not None else None,
            '仓库总人数': int(round(s['7月总人数'])),
            '供给占比': round(s['供给占比'], 4),
            '风险等级': s['风险等级'],
            '需求人数': demand, '人力缺口': gap,
        })
    df_sup = pd.DataFrame(sup_rows)
    return df_wh, df_sup

df_wh_550, df_sup_550 = build_warehouse('需求550w', '550w', '操作量')
df_wh_660, df_sup_660 = build_warehouse('需求660w', '660w', '单量660w')

# ---- 5档货量供应商配置标准框架 ----
def build_standard():
    tiers = [
        {'档位': 'S级(超大型)', '日均操作量区间': '>100万单/日', '需求人数': '>800人', '供应商家数': '5家及以上', '占比上限': '≤20%', '上限值': 0.20, '说明': '超高货量，需至少5家分散，单家≤20%'},
        {'档位': 'A级(大型)', '日均操作量区间': '50~100万单/日', '需求人数': '400~800人', '供应商家数': '4家及以上', '占比上限': '≤25%', '上限值': 0.25, '说明': '大货量，至少4家，单家≤25%'},
        {'档位': 'B级(中型)', '日均操作量区间': '25~50万单/日', '需求人数': '250~400人', '供应商家数': '3家及以上', '占比上限': '≤30%', '上限值': 0.30, '说明': '中货量，至少3家，单家≤30%'},
        {'档位': 'C级(中小型)', '日均操作量区间': '10~25万单/日', '需求人数': '100~250人', '供应商家数': '3家及以上', '占比上限': '<40%', '上限值': 0.40, '说明': '中低货量，至少3家，单家<40%'},
        {'档位': 'D级(小型)', '日均操作量区间': '≤10万单/日', '需求人数': '≤100人', '供应商家数': '2家及以上', '占比上限': '<50%', '上限值': 0.50, '说明': '低货量，最少保证2家，单家<50%'},
    ]
    return tiers

standard = build_standard()

# ---- 计算每档「现状」：匹配各仓库7月实际供应商数据 ----
def compute_tier_status():
    tier_key_map = {
        'S级(超大型)': 'S级', 'A级(大型)': 'A级', 'B级(中型)': 'B级',
        'C级(中小型)': 'C级', 'D级(小型)': 'D级',
    }
    jul_vol = df_jul_volume[['仓库', '日均操作量']].copy()
    jul_vol['仓库'] = jul_vol['仓库'].replace(WH_NAME_MAP)
    jul_vol_map = dict(zip(jul_vol['仓库'], jul_vol['日均操作量']))
    jul_mp = df_jul_manpower.groupby('仓库')['实际使用人数（日均）'].sum().reset_index()
    jul_mp['仓库'] = jul_mp['仓库'].replace(WH_NAME_MAP)
    jul_mp_map = dict(zip(jul_mp['仓库'], jul_mp['实际使用人数（日均）']))

    wh_by_tier = {}
    for _, w in df_wh_660.iterrows():
        t = tier_key_map.get(w['档位'], w['档位'])
        wh_by_tier.setdefault(t, []).append(w)

    tier_status = []
    for t in standard:
        key = tier_key_map.get(t['档位'], t['档位'])
        whs = wh_by_tier.get(key, [])
        min_n = int(re.sub(r'\D', '', t['供应商家数'])) if re.sub(r'\D', '', t['供应商家数']) else 0
        max_ratio = t['上限值']

        wh_details = []
        ok_count = 0
        warn_count = 0
        sup_660_records = df_sup_660.to_dict(orient='records')
        for w in whs:
            jul_vol = jul_vol_map.get(w['仓库'], 0)
            if not jul_vol or jul_vol <= 0:
                continue
            wh_sup = [s for s in sup_660_records if s['仓库'] == w['仓库'] and s['7月在岗人数'] > 0]
            n = len(wh_sup)
            max_r = max([s['供给占比'] for s in wh_sup], default=0)
            jul_mp = jul_mp_map.get(w['仓库'], 0)
            if n >= min_n and max_r <= max_ratio:
                status = '达标'
                ok_count += 1
            else:
                status = '预警'
                warn_count += 1
            wh_details.append({
                '仓库': w['仓库'],
                '现有家数': n,
                '要求家数': min_n,
                '最高占比': round(max_r, 4),
                '占比上限': max_ratio,
                '7月日均操作量': round(jul_vol, 0),
                '7月实际使用人数': round(jul_mp, 0),
                '状态': status,
            })

        tier_status.append({
            '档位': t['档位'],
            '仓库数': len(wh_details),
            '达标数': ok_count,
            '预警数': warn_count,
            '现状': wh_details,
        })
    return tier_status

standard_status = compute_tier_status()

# ---- 输出 ----
def clean(v):
    if isinstance(v, dict): return {k: clean(vv) for k, vv in v.items()}
    if isinstance(v, list): return [clean(vv) for vv in v]
    if isinstance(v, float):
        if np.isnan(v) or np.isinf(v): return None
        return round(v, 4)
    return v

output = clean({
    'meta': {
        'title': '仓库旺季劳务缺口测算+供应商供给占比风险预警模型（7月数据）',
        'time': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'GUS_劳务供应商考核数据-7月.xlsx',
        'thresholds': {'safe': f'≤{SAFE_THRESHOLD*100:.0f}%', 'warning': f'{SAFE_THRESHOLD*100:.0f}%~{WARNING_THRESHOLD*100:.0f}%', 'danger': f'>{WARNING_THRESHOLD*100:.0f}%'},
        'min_suppliers': MIN_SUPPLIER_COUNT,
        'ground_multiplier': f'550w:{GROUND_MULTIPLIER_550}x | 660w:{GROUND_MULTIPLIER_660}x',
        'demand_source': 'HUB仓库取自《旺季预测人数-NEewr-1160未上设备》550w/660w两档；Ground仓库=7月在岗×倍数',
    },
    'warehouse_550': df_wh_550.to_dict(orient='records'),
    'supplier_550': df_sup_550.to_dict(orient='records'),
    'warehouse_660': df_wh_660.to_dict(orient='records'),
    'supplier_660': df_sup_660.to_dict(orient='records'),
    'standard': standard,
    'standard_status': standard_status,
})

with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'✅ 7月模型数据已生成: {OUTPUT_JSON}')
print(f'   550w: 仓库{len(df_wh_550)} | 供应商{len(df_sup_550)}')
print(f'   660w: 仓库{len(df_wh_660)} | 供应商{len(df_sup_660)}')
print()
print('=== 550w 仓库需求总览 ===')
for _, w in df_wh_550.iterrows():
    status = '未开' if w['7月在岗人数'] == 0 and w['仓库类型'] == 'HUB' else ''
    print(f'  {w["仓库"]:8s} 需求{w["需求人数"]:4d} 在岗{w["7月在岗人数"]:4d} 缺口{w["人力缺口"]:4d} {status}')
