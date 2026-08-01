#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正 app.js 中的 API 路径，匹配后端路由"""

with open('app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修正东财热点接口：GET -> POST，路径不变
old_hotspot = '''    const data = await apiJson(`/api/eastmoney-ai/hotspot?${params.toString()}`);'''
new_hotspot = '''    const data = await apiJson('/api/eastmoney-ai/hotspot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: query || '今日热点', type, limit }),
    });'''

if old_hotspot in content:
    content = content.replace(old_hotspot, new_hotspot)
    print("✓ 东财热点接口已修正为 POST")
else:
    print("✗ 未找到东财热点接口")

# 2. 修正东财个股分析接口路径
old_analysis = "    const data = await apiJson('/api/eastmoney-ai/analysis', {"
new_analysis = "    const data = await apiJson('/api/eastmoney-ai/stock-analysis', {"

if old_analysis in content:
    content = content.replace(old_analysis, new_analysis)
    print("✓ 东财个股分析接口路径已修正")
else:
    print("✗ 未找到东财个股分析接口")

# 3. 修正东财问答接口路径
old_qa = "    const data = await apiJson('/api/eastmoney-ai/qa', {"
new_qa = "    const data = await apiJson('/api/eastmoney-ai/chat', {"

if old_qa in content:
    content = content.replace(old_qa, new_qa)
    print("✓ 东财问答接口路径已修正")
else:
    print("✗ 未找到东财问答接口")

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("\napp.js API 路径修正完成！")
