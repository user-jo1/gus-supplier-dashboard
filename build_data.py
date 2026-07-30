import pandas as pd, json, numpy as np

jun_xlsx = '/Users/mac/Desktop/GF_HR/01-劳务工:供应商管理/GUS_劳务供应商考核数据-6月xlsx.xlsx'

# 读取现有JSON（保留所有5月数据）
with open('/Users/mac/CodeBuddy/20260618112854/dashboard_data.json', 'r', encoding='utf-8') as f:
    existing = json.load(f)

# 读取6月数据
df_jun = pd.read_excel(jun_xlsx, sheet_name='数据收集表')
df_jun = df_jun[df_jun['月份'] == '2026年 6月'].copy()

# 6月汇总
df_sum = pd.read_excel(jun_xlsx, sheet_name='汇总数据')
df_sum = df_sum[df_sum['三级组织'].notna() & (df_sum['三级组织'] != '总计') & (df_sum['三级组织'] != '计时+计件总人数')]
cost_col = '总成本（计时）-不含正工挂靠、司机'
if cost_col in df_sum.columns:
    df_sum.rename(columns={cost_col: '总成本（计时）'}, inplace=True)

def sf(v):
    if pd.isna(v): return 0.0
    return float(v)
def ss(v):
    return str(v).strip() if pd.notna(v) else ''
def get_grade(s):
    if pd.isna(s): return 'D'
    s = float(s)
    return 'A' if s >= 80 else 'B' if s >= 60 else 'C' if s >= 40 else 'D'
def parse_mgr(v):
    if pd.isna(v): return 0
    if isinstance(v, str) and ':' in v:
        try: return 1.0 / float(v.split(':')[0])
        except: return 0
    try: return float(v)
    except: return 0
def normalize_markup(v):
    if pd.isna(v): return 0.0
    s = str(v)
    if s.endswith('%'): return float(s.replace('%', '')) / 100.0
    return float(s)

deduction_cols = ['onsite manager扣分', '响应配合度扣分', '结账配合度扣分', '库内管理扣分', '商业道德扣分', '摸鱼扣分', '不按时发薪扣分']
deduction_labels = ['Onsite Mgr', '响应配合', '结账配合', '库内管理', '商业道德', '摸鱼', '不按时发薪']

df = df_jun.copy()
df['等级'] = df['总分'].apply(get_grade)
df['合规标签'] = df['COI合规'].apply(lambda x: '不合规' if pd.notna(x) and str(x).strip() != '' else '合规')
df['不合规原因'] = df['COI合规'].apply(lambda x: ss(x) if pd.notna(x) else '')

# 6月 KPI
jun_total_ppl = int(df['实际使用人数（日均）'].sum())
jun_total_supp = int(df['供应商'].nunique())
jun_total_records = len(df)
jun_grades = df.groupby('供应商')['总分'].max().apply(get_grade)
jun_a = int((jun_grades == 'A').sum())
jun_d = int((jun_grades == 'D').sum())
jun_a_rec = int((df['等级'] == 'A').sum())
jun_d_rec = int((df['等级'] == 'D').sum())
jun_ncomp = int(df[df['合规标签'] == '不合规']['供应商'].nunique())

# 6月汇总数据
jun_total_ppl_sum = round(sf(df_sum['计时人数（日均）'].sum()) + sf(df_sum['计件人数（日均）'].sum()))
jun_total_time_ppl = round(sf(df_sum['计时人数（日均）'].sum()))
jun_total_piece_ppl = round(sf(df_sum['计件人数（日均）'].sum()))
jun_total_hours_sum = round(sf(df_sum['总工时数'].sum()))
jun_total_cost_sum = round(sf(df_sum['总成本'].sum()))

# 6月 cost_chart
jun_cost_chart = []
for _, row in df_sum.iterrows():
    daily_ppl = round(sf(row['计时人数（日均）']) + sf(row['计件人数（日均）']))
    jun_cost_chart.append({
        'region': row['三级组织'], 'time_cost': sf(row['总成本（计时）']),
        'piece_cost': sf(row['总成本（计件）']), 'total_cost': sf(row['总成本']),
        'total_hours': sf(row['总工时数']), 'daily_people': daily_ppl,
    })

# 6月 people_supplier_chart
regions = ['FL 佛州大区', 'GL 大湖大区', 'MS 中南大区', 'NE 东北大区', 'TX 德州大区', 'WE 美西大区', 'Ground项目部']
region_supplier_jun = []
for region in regions:
    rdf = df[df['大区'] == region]
    region_supplier_jun.append({
        'region': region, 'daily_people': int(rdf['实际使用人数（日均）'].sum()),
        'total_suppliers': int(rdf['供应商'].nunique()),
        'compliant': int((rdf['合规标签'] == '合规').sum()),
        'noncompliant': int((rdf['合规标签'] == '不合规').sum()),
        'a_count': int((rdf['等级'] == 'A').sum()), 'b_count': int((rdf['等级'] == 'B').sum()),
        'c_count': int((rdf['等级'] == 'C').sum()), 'd_count': int((rdf['等级'] == 'D').sum()),
    })

# 6月 detail_by_region
detail_jun = []
for _, row in df.iterrows():
    ded_list = []
    ded_total = 0
    for col, label in zip(deduction_cols, deduction_labels):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0:
            val = int(float(v))
            ded_total += val
            ded_list.append({'项目': label, '扣分': val})
    remark = ss(row.get('备注', ''))
    coi_remark = ss(row.get('COI合规', ''))
    detail_jun.append({
        '大区': row['大区'], '仓库': row['仓库'], '供应商': row['供应商'],
        '等级': row['等级'], '合规标签': row['合规标签'], '不合规原因': row['不合规原因'],
        '使用状态': ss(row.get('使用状态', '')),
        '日均使用人数': round(sf(row['实际使用人数（日均）'])),
        '分拣工时薪': sf(row.get('分拣工时薪', 0)),
        'markup': round(normalize_markup(row.get('分拣工markup', 0)) * 100),
        '分拣工结算价': sf(row.get('分拣工结算价', 0)),
        '报价竞争力得分': round(sf(row['报价竞争力得分'])),
        '派遣满足率得分': round(sf(row['派遣满足率得分'])),
        '考勤准确率得分': round(sf(row['考勤准确率得分'])),
        '人员稳定率得分': round(sf(row['人员稳定率得分'])),
        '定量考核总分': round(sf(row['定量考核总分'])),
        '总分': round(sf(row['总分'])),
        '报价竞争力': round(sf(row['报价竞争力']), 4),
        '派遣满足率': round(sf(row['派遣满足率']), 4),
        '考勤准确率': round(sf(row['考勤准确率']), 4),
        '人员稳定率': round(sf(row['人员稳定率']), 4),
        'onsite_manager_管理幅宽': parse_mgr(row.get('Onsite-manager管理幅宽', 0)),
        '扣分明细列表': ded_list,
        '扣分总计': ded_total,
        '备注': remark,
        'coi备注': coi_remark,
        '报价竞争力_pct': round(sf(row['报价竞争力']) * 100, 1),
        '派遣满足率_pct': round(sf(row['派遣满足率']) * 100, 1),
        '考勤准确率_pct': round(sf(row['考勤准确率']) * 100, 1),
        '人员稳定率_pct': round(sf(row['人员稳定率']) * 100, 1),
    })

detail_by_region_jun = {}
for region in regions:
    detail_by_region_jun[region] = [d for d in detail_jun if d['大区'] == region]

# 更新到现有JSON
kpi = existing['kpi']
kpi.update({
    'jun_daily_avg_people': jun_total_ppl_sum,
    'jun_daily_avg_people_time': jun_total_time_ppl,
    'jun_daily_avg_people_piece': jun_total_piece_ppl,
    'jun_daily_avg_trips': round(jun_total_hours_sum / 22.0 / 8.0),
    'jun_total_hours': jun_total_hours_sum,
    'jun_total_cost': jun_total_cost_sum,
    'jun_total_supplier_count': jun_total_supp,
    'jun_total_records': jun_total_records,
    'jun_a_suppliers': jun_a,
    'jun_a_pct': f'{jun_a_rec}/{jun_total_records}',
    'jun_d_suppliers': jun_d,
    'jun_d_pct': f'{jun_d_rec}/{jun_total_records}',
    'jun_coi_noncompliant': jun_ncomp,
    'jun_coi_pct': f'{jun_ncomp}/{jun_total_supp}',
})

existing['cost_chart_jun'] = jun_cost_chart
existing['people_supplier_chart_jun'] = region_supplier_jun
existing['detail_by_region_jun'] = detail_by_region_jun
existing['months'] = ['2026年5月', '2026年6月']

with open('/Users/mac/CodeBuddy/20260618112854/dashboard_data.json', 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print(f'Done! 6月: 总人数={jun_total_ppl_sum} 工时={jun_total_hours_sum:,} 成本=${jun_total_cost_sum:,}')
print(f'供应商={jun_total_supp}家 记录={jun_total_records}条')
