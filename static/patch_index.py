#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 index.html 中添加 AI 工具导航和页面"""

import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在导航栏添加 AI 工具按钮（在"智能选股"和"研究中心"之间）
old_nav = '    <button class="nav" data-view="screener">智能选股</button>\r\n    <button class="nav" data-view="research">研究中心</button>'
new_nav = '    <button class="nav" data-view="screener">智能选股</button>\r\n    <button class="nav" data-view="ai-tools">AI 工具</button>\r\n    <button class="nav" data-view="research">研究中心</button>'

if old_nav in content:
    content = content.replace(old_nav, new_nav)
    print("✓ 导航栏已添加 AI 工具按钮")
else:
    print("✗ 未找到导航栏目标位置，尝试备用匹配...")
    # 备用：用正则匹配
    nav_pattern = r'(<button class="nav" data-view="screener">智能选股</button>\r?\n)(\s*<button class="nav" data-view="research">研究中心</button>)'
    content = re.sub(nav_pattern, r'\1    <button class="nav" data-view="ai-tools">AI 工具</button>\n\2', content)
    print("✓ 导航栏已通过正则添加 AI 工具按钮")

# 2. 在 admin section 之前添加 AI 工具 section
ai_tools_section = '''    <section id="ai-tools" class="view">
      <div class="panel screener-shell">
        <div class="section-head screener-heading">
          <div>
            <span class="eyebrow">问财选股 × 东财 AI</span>
            <h2>AI 工具中心</h2>
            <p>接入同花顺问财自然语言选股和东方财富妙想 AI，辅助盘中决策与盘后研究。</p>
          </div>
          <div id="aiToolsSourceStatus" class="screener-source-status">等待读取</div>
        </div>

        <div class="screener-tabs" role="tablist">
          <button class="active" type="button" data-ai-tab="wencai">问财选股</button>
          <button type="button" data-ai-tab="eastmoney-hotspot">东财热点</button>
          <button type="button" data-ai-tab="eastmoney-analysis">东财分析</button>
          <button type="button" data-ai-tab="eastmoney-qa">东财问答</button>
        </div>

        <!-- 问财选股 -->
        <div class="screener-pane active" data-ai-pane="wencai">
          <div class="screener-filter-card">
            <div>
              <h3>同花顺问财 — 自然语言选股</h3>
              <p>输入自然语言描述选股条件，例如"近5日涨幅超过10%的科技股"。</p>
            </div>
            <div class="screener-search-bar">
              <input id="wencaiQueryInput" value="近5日涨幅超过10%，换手率大于3%，市值大于50亿" placeholder="输入问财选股条件">
              <button id="runWencaiQuery" class="primary" type="button">问财选股</button>
            </div>
            <div class="screener-inline-controls">
              <label>结果数量<input id="wencaiLimit" type="number" min="1" max="100" value="20"></label>
              <label>排序方式
                <select id="wencaiSort">
                  <option value="">默认</option>
                  <option value="price_change_rate:desc">涨幅从高到低</option>
                  <option value="turnover_rate:desc">换手率从高到低</option>
                  <option value="market_cap:desc">市值从大到小</option>
                </select>
              </label>
            </div>
          </div>
          <div id="wencaiResult" class="screener-result"><div class="empty">输入条件后点击"问财选股"。</div></div>
        </div>

        <!-- 东财热点 -->
        <div class="screener-pane" data-ai-pane="eastmoney-hotspot">
          <div class="screener-filter-card">
            <div>
              <h3>东方财富妙想 — 热点发现</h3>
              <p>获取市场最新热点板块和主题，捕捉资金流向。</p>
            </div>
            <div class="screener-search-bar">
              <input id="eastmoneyHotspotQuery" value="" placeholder="可选：输入主题关键词筛选">
              <button id="runEastMoneyHotspot" class="primary" type="button">获取热点</button>
            </div>
            <div class="screener-inline-controls">
              <label>热点类型
                <select id="eastmoneyHotspotType">
                  <option value="all">全部</option>
                  <option value="industry">行业板块</option>
                  <option value="concept">概念板块</option>
                  <option value="region">地域板块</option>
                </select>
              </label>
              <label>结果数量<input id="eastmoneyHotspotLimit" type="number" min="5" max="50" value="20"></label>
            </div>
          </div>
          <div id="eastmoneyHotspotResult" class="screener-result"><div class="empty">点击"获取热点"查看市场热点。</div></div>
        </div>

        <!-- 东财个股分析 -->
        <div class="screener-pane" data-ai-pane="eastmoney-analysis">
          <div class="screener-filter-card">
            <div>
              <h3>东方财富妙想 — 个股 AI 分析</h3>
              <p>输入股票代码，获取东方财富 AI 对个股的综合分析。</p>
            </div>
            <div class="screener-search-bar">
              <input id="eastmoneyAnalysisCode" placeholder="输入股票代码，例如 000001.SZ 或 600000.SH">
              <button id="runEastMoneyAnalysis" class="primary" type="button">AI 分析</button>
            </div>
            <div class="screener-inline-controls">
              <label>分析维度
                <select id="eastmoneyAnalysisType">
                  <option value="comprehensive">综合分析</option>
                  <option value="fund">资金流向</option>
                  <option value="technical">技术面</option>
                  <option value="fundamental">基本面</option>
                  <option value="news">舆情分析</option>
                </select>
              </label>
            </div>
          </div>
          <div id="eastmoneyAnalysisResult" class="screener-result"><div class="empty">输入股票代码后点击"AI 分析"。</div></div>
        </div>

        <!-- 东财问答 -->
        <div class="screener-pane" data-ai-pane="eastmoney-qa">
          <div class="screener-filter-card">
            <div>
              <h3>东方财富妙想 — 智能问答</h3>
              <p>向东方财富 AI 提问任何市场相关问题。</p>
            </div>
            <div class="screener-search-bar">
              <input id="eastmoneyQAQuestion" placeholder="输入你的问题，例如：最近有哪些利好政策？">
              <button id="runEastMoneyQA" class="primary" type="button">提问</button>
            </div>
          </div>
          <div id="eastmoneyQAResult" class="screener-result"><div class="empty">输入问题后点击"提问"。</div></div>
        </div>
      </div>
    </section>

'''

# 找到 admin section 的位置，在它前面插入
admin_marker = '    <section id="admin" class="view">'
if admin_marker in content:
    content = content.replace(admin_marker, ai_tools_section + admin_marker)
    print("✓ AI 工具 section 已添加")
else:
    print("✗ 未找到 admin section 标记")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nindex.html 修改完成！")
