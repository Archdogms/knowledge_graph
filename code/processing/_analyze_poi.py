#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv('output/tables/poi_cleaned.csv')
print(f'总行数: {len(df)}')
print(f'\n列名: {list(df.columns)}')

print('\n=== category 分布 ===')
print(df['category'].value_counts().to_string())

print('\n=== query_type 分布 ===')
print(df['query_type'].value_counts().to_string())

print('\n=== town 分布 ===')
print(df['town'].value_counts().to_string())

print('\n=== category=自然景观 下的分类错误检测 ===')
mask = df['category'] == '自然景观'
for kw in ['祠堂','宗祠','公祠','寺','庙','教堂','清真','故居','纪念馆','红色','遗址','书院']:
    n = df[mask & df['name'].str.contains(kw, na=False)].shape[0]
    if n > 0:
        print(f'  category=自然景观 但名称含"{kw}": {n}条')

print('\n=== 各category的示例 ===')
for cat in df['category'].unique():
    names = df[df['category'] == cat]['name'].head(5).tolist()
    print(f'  [{cat}] 示例: {names}')

print('\n=== original_type unique 数量 ===')
print(f'  {df["original_type"].nunique()} 个')
print('\n=== original_type 前30 ===')
for v in df['original_type'].value_counts().head(30).items():
    print(f'  {v[0]}: {v[1]}')
