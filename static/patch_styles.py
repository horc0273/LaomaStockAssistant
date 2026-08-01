#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 styles.css 末尾添加 AI 工具样式"""

with open('styles.css', 'r', encoding='utf-8') as f:
    content = f.read()

ai_styles = '''
/* ========== AI 工具中心样式 ========== */

/* 热点卡片 */
.hotspot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
  padding: 12px 0;
}
.hotspot-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px 16px;
  transition: box-shadow .15s;
}
.hotspot-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.hotspot-name {
  font-weight: 600;
  font-size: 15px;
  color: #111827;
  margin-bottom: 6px;
}
.hotspot-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}
.hotspot-desc {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
}

/* AI 分析结果 */
.ai-analysis-result {
  padding: 12px 0;
}
.ai-analysis-result h4 {
  font-size: 17px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}
.analysis-section {
  margin-bottom: 14px;
}
.analysis-section b {
  display: block;
  font-size: 14px;
  color: #374151;
  margin-bottom: 4px;
}
.analysis-section p {
  font-size: 14px;
  color: #4b5563;
  line-height: 1.6;
  margin: 0;
}
.analysis-section pre {
  background: #f3f4f6;
  border-radius: 6px;
  padding: 10px;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* AI 问答结果 */
.ai-qa-result {
  padding: 12px 0;
}
.qa-question {
  background: #f3f4f6;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  color: #374151;
  margin-bottom: 12px;
}
.qa-answer {
  font-size: 14px;
  color: #111827;
  line-height: 1.7;
  padding: 0 4px;
}

/* 元信息 */
.screener-meta {
  font-size: 12px;
  color: #9ca3af;
  padding: 8px 0 4px;
  text-align: right;
}

/* 问财结果表格 */
.screener-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.screener-table th,
.screener-table td {
  border-bottom: 1px solid #e5e7eb;
  padding: 8px 10px;
  text-align: left;
}
.screener-table th {
  background: #f9fafb;
  font-weight: 600;
  color: #374151;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .02em;
}
.screener-table tr:hover td {
  background: #f9fafb;
}
'''

content = content.rstrip() + '\n' + ai_styles + '\n'

with open('styles.css', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ AI 工具样式已添加到 styles.css")
