#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 app.js 中添加 AI 工具交互逻辑"""

import re

with open('app.js', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在导航切换逻辑中添加 ai-tools 初始化
old_nav_logic = '''    if (button.dataset.view === 'abnormal') initAbnormalMonitor();
    if (button.dataset.view === 'screener') initSmartScreener();
    if (button.dataset.view === 'admin') loadAdminMembers();'''

new_nav_logic = '''    if (button.dataset.view === 'abnormal') initAbnormalMonitor();
    if (button.dataset.view === 'screener') initSmartScreener();
    if (button.dataset.view === 'ai-tools') initAITools();
    if (button.dataset.view === 'admin') loadAdminMembers();'''

if old_nav_logic in content:
    content = content.replace(old_nav_logic, new_nav_logic)
    print("✓ 导航切换逻辑已添加 ai-tools 分支")
else:
    print("✗ 未找到导航切换目标位置")

# 2. 在文件末尾添加 AI 工具的全部交互代码
ai_tools_js = '''

/* ========== AI 工具中心（问财 + 东财） ========== */

function initAITools() {
  // AI 工具 Tab 切换
  document.querySelectorAll('[data-ai-tab]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-ai-tab]').forEach(item => item.classList.remove('active'));
      document.querySelectorAll('[data-ai-pane]').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      document.querySelector(`[data-ai-pane="${button.dataset.aiTab}"]`)?.classList.add('active');
    });
  });

  // 问财选股
  $('#runWencaiQuery')?.addEventListener('click', runWencaiQuery);
  $('#wencaiQueryInput')?.addEventListener('keydown', event => {
    if (event.key === 'Enter') runWencaiQuery();
  });

  // 东财热点
  $('#runEastMoneyHotspot')?.addEventListener('click', runEastMoneyHotspot);

  // 东财个股分析
  $('#runEastMoneyAnalysis')?.addEventListener('click', runEastMoneyAnalysis);
  $('#eastmoneyAnalysisCode')?.addEventListener('keydown', event => {
    if (event.key === 'Enter') runEastMoneyAnalysis();
  });

  // 东财问答
  $('#runEastMoneyQA')?.addEventListener('click', runEastMoneyQA);
  $('#eastmoneyQAQuestion')?.addEventListener('keydown', event => {
    if (event.key === 'Enter') runEastMoneyQA();
  });

  // 加载状态指示
  const statusNode = $('#aiToolsSourceStatus');
  if (statusNode) {
    statusNode.textContent = '已就绪';
    statusNode.style.color = '#16a34a';
  }
}

/* --- 问财选股 --- */
async function runWencaiQuery() {
  const query = $('#wencaiQueryInput')?.value?.trim();
  const resultNode = $('#wencaiResult');
  if (!query) {
    resultNode.innerHTML = '<div class="empty">请输入选股条件。</div>';
    return;
  }
  const limit = parseInt($('#wencaiLimit')?.value || '20', 10);
  const sort = $('#wencaiSort')?.value || '';

  resultNode.innerHTML = '<div class="empty">问财选股中，请稍候...</div>';
  try {
    const data = await apiJson('/api/wencai/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, limit, sort }),
    });
    renderWencaiResult(data, resultNode);
  } catch (error) {
    resultNode.innerHTML = `<div class="empty">问财选股失败：${escapeHtml(error.message || '未知错误')}</div>`;
  }
}

function renderWencaiResult(data, container) {
  if (!data || data.error) {
    container.innerHTML = `<div class="empty">${escapeHtml(data?.error || '未返回结果')}</div>`;
    return;
  }
  const stocks = data.stocks || [];
  if (stocks.length === 0) {
    container.innerHTML = '<div class="empty">未找到符合条件的股票。</div>';
    return;
  }

  const headers = data.headers || [];
  let html = '<table class="screener-table"><thead><tr>';
  headers.forEach(h => {
    html += `<th>${escapeHtml(h)}</th>`;
  });
  html += '</tr></thead><tbody>';

  stocks.forEach(stock => {
    html += '<tr>';
    headers.forEach(h => {
      const val = stock[h] !== undefined ? stock[h] : '';
      html += `<td>${escapeHtml(String(val))}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table>';
  html += `<p class="screener-meta">共 ${stocks.length} 条结果 · 来源：同花顺问财</p>`;
  container.innerHTML = html;
}

/* --- 东财热点 --- */
async function runEastMoneyHotspot() {
  const query = $('#eastmoneyHotspotQuery')?.value?.trim();
  const type = $('#eastmoneyHotspotType')?.value || 'all';
  const limit = parseInt($('#eastmoneyHotspotLimit')?.value || '20', 10);
  const resultNode = $('#eastmoneyHotspotResult');

  resultNode.innerHTML = '<div class="empty">正在获取热点数据...</div>';
  try {
    const params = new URLSearchParams({ type, limit: String(limit) });
    if (query) params.append('query', query);
    const data = await apiJson(`/api/eastmoney-ai/hotspot?${params.toString()}`);
    renderEastMoneyHotspotResult(data, resultNode);
  } catch (error) {
    resultNode.innerHTML = `<div class="empty">获取热点失败：${escapeHtml(error.message || '未知错误')}</div>`;
  }
}

function renderEastMoneyHotspotResult(data, container) {
  if (!data || data.error) {
    container.innerHTML = `<div class="empty">${escapeHtml(data?.error || '未返回结果')}</div>`;
    return;
  }
  const hotspots = data.hotspots || [];
  if (hotspots.length === 0) {
    container.innerHTML = '<div class="empty">暂无热点数据。</div>';
    return;
  }

  let html = '<div class="hotspot-grid">';
  hotspots.forEach(item => {
    html += `<div class="hotspot-card">
      <div class="hotspot-name">${escapeHtml(item.name || '')}</div>
      <div class="hotspot-meta">
        <span class="tag ${item.change >= 0 ? 'green' : 'red'}">${item.change >= 0 ? '+' : ''}${item.change?.toFixed(2) || '0.00'}%</span>
        <span>资金流入: ${escapeHtml(String(item.inflow || '--'))}</span>
      </div>
      <div class="hotspot-desc">${escapeHtml(item.description || '')}</div>
    </div>`;
  });
  html += '</div>';
  html += `<p class="screener-meta">共 ${hotspots.length} 条热点 · 来源：东方财富</p>`;
  container.innerHTML = html;
}

/* --- 东财个股分析 --- */
async function runEastMoneyAnalysis() {
  const code = $('#eastmoneyAnalysisCode')?.value?.trim();
  const analysisType = $('#eastmoneyAnalysisType')?.value || 'comprehensive';
  const resultNode = $('#eastmoneyAnalysisResult');
  if (!code) {
    resultNode.innerHTML = '<div class="empty">请输入股票代码。</div>';
    return;
  }

  resultNode.innerHTML = '<div class="empty">AI 分析中，请稍候...</div>';
  try {
    const data = await apiJson('/api/eastmoney-ai/analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, type: analysisType }),
    });
    renderEastMoneyAnalysisResult(data, resultNode);
  } catch (error) {
    resultNode.innerHTML = `<div class="empty">分析失败：${escapeHtml(error.message || '未知错误')}</div>`;
  }
}

function renderEastMoneyAnalysisResult(data, container) {
  if (!data || data.error) {
    container.innerHTML = `<div class="empty">${escapeHtml(data?.error || '未返回结果')}</div>`;
    return;
  }
  const analysis = data.analysis || data;
  let html = '<div class="ai-analysis-result">';
  html += `<h4>${escapeHtml(analysis.stock_name || data.code || '')} (${escapeHtml(data.code || '')})</h4>`;
  if (analysis.summary) {
    html += `<div class="analysis-section"><b>综合结论</b><p>${escapeHtml(analysis.summary)}</p></div>`;
  }
  if (analysis.fund_flow) {
    html += `<div class="analysis-section"><b>资金流向</b><p>${escapeHtml(analysis.fund_flow)}</p></div>`;
  }
  if (analysis.technical) {
    html += `<div class="analysis-section"><b>技术面</b><p>${escapeHtml(analysis.technical)}</p></div>`;
  }
  if (analysis.fundamental) {
    html += `<div class="analysis-section"><b>基本面</b><p>${escapeHtml(analysis.fundamental)}</p></div>`;
  }
  if (analysis.risk) {
    html += `<div class="analysis-section"><b>风险提示</b><p>${escapeHtml(analysis.risk)}</p></div>`;
  }
  if (analysis.raw) {
    html += `<div class="analysis-section"><b>原始分析</b><pre>${escapeHtml(JSON.stringify(analysis.raw, null, 2))}</pre></div>`;
  }
  html += '</div>';
  html += `<p class="screener-meta">来源：东方财富妙想 AI · 仅供参考</p>`;
  container.innerHTML = html;
}

/* --- 东财问答 --- */
async function runEastMoneyQA() {
  const question = $('#eastmoneyQAQuestion')?.value?.trim();
  const resultNode = $('#eastmoneyQAResult');
  if (!question) {
    resultNode.innerHTML = '<div class="empty">请输入问题。</div>';
    return;
  }

  resultNode.innerHTML = '<div class="empty">AI 思考中，请稍候...</div>';
  try {
    const data = await apiJson('/api/eastmoney-ai/qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    renderEastMoneyQAResult(data, resultNode);
  } catch (error) {
    resultNode.innerHTML = `<div class="empty">问答失败：${escapeHtml(error.message || '未知错误')}</div>`;
  }
}

function renderEastMoneyQAResult(data, container) {
  if (!data || data.error) {
    container.innerHTML = `<div class="empty">${escapeHtml(data?.error || '未返回结果')}</div>`;
    return;
  }
  const answer = data.answer || data.response || data.content || JSON.stringify(data, null, 2);
  let html = '<div class="ai-qa-result">';
  html += `<div class="qa-question"><b>Q:</b> ${escapeHtml($('#eastmoneyQAQuestion')?.value || '')}</div>`;
  html += `<div class="qa-answer"><b>A:</b> ${escapeHtml(String(answer)).replace(/\\n/g, '<br>')}</div>`;
  html += '</div>';
  html += `<p class="screener-meta">来源：东方财富妙想 AI · 仅供参考</p>`;
  container.innerHTML = html;
}

/* 辅助函数 */
function escapeHtml(text) {
  if (text == null) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}
'''

# 在文件末尾添加
content = content.rstrip() + '\n' + ai_tools_js + '\n'
print("✓ AI 工具交互代码已添加到文件末尾")

with open('app.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("\napp.js 修改完成！")
