# 老马股票助手 — 前端模块化重构方案

## 当前问题诊断

```
app.js          4,196 行  ← 185个函数、92个事件绑定，全部塞在一个文件
styles.css      2,872 行  ← 没有组件隔离，改一个地方可能崩另一个
index.html        793 行  ← 9个view全部内联，没有组件复用
```

**根因：代码是"堆积"出来的，不是"设计"出来的。**

每次加功能都在现有文件末尾 append，导致：
- 找一段逻辑要翻几千行
- 改一个 bug 可能意外影响三个模块
- 新功能加进去像往垃圾堆里扔东西
- 页面加载慢（4,200 行 JS 一次性解析）

---

## 重构目标

```
重构前（现在）                    重构后（目标）
┌─────────────────┐              ┌─────────────┐
│   app.js        │              │  main.js    │  ← 100行：入口+路由
│   4,196 行      │              │  (100行)    │
│                 │              ├─────────────┤
│  状态管理        │      →       │ state.js    │  ← 全局状态
│  API请求         │              │ api.js      │  ← 封装请求
│  UI渲染×9个view │              │ ui/         │  ← 9个模块文件
│  事件绑定×92个   │              │ components/ │  ← 可复用组件
│  工具函数×30个   │              │ utils.js    │  ← 工具函数
└─────────────────┘              └─────────────┘
```

---

## 文件结构

```
static/
├── index.html              ← 只留骨架，view 内容移入 JS
├── styles.css              ← 拆成 base.css + components.css + views.css
├── js/
│   ├── main.js             ← 入口：路由切换、初始化
│   ├── state.js            ← 全局状态（原来的 state 对象）
│   ├── api.js              ← API 封装（apiJson + 各模块请求）
│   ├── utils.js            ← 工具函数（fmtPct、trend、escapeHtml 等）
│   ├── components/
│   │   ├── modal.js        ← 弹窗组件
│   │   ├── table.js        ← 表格组件
│   │   ├── card.js         ← 卡片组件
│   │   └── chart.js        ← 图表组件
│   └── views/
│       ├── dashboard.js    ← 今日工作台（原 ~400 行）
│       ├── review.js       ← 复盘中心
│       ├── watchlist.js    ← 股票自选
│       ├── trading.js      ← 交易动作
│       ├── market.js       ← 市场行情
│       ├── abnormal.js     ← 异动监控
│       ├── screener.js     ← 智能选股
│       ├── ai-tools.js     ← AI 工具（问财+东财）
│       ├── research.js     ← 研究中心
│       └── admin.js        ← 会员管理
```

---

## 各模块拆分详情

### 1. utils.js（工具函数，~150 行）

从 app.js 提取所有纯工具函数：

```javascript
// utils.js
export const $ = (selector) => document.querySelector(selector);
export const $$ = (selector) => document.querySelectorAll(selector);
export const fmtPct = (value) => `${value >= 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
export const fmtPrice = (value) => Number(value).toFixed(2);
export const trend = (value) => value >= 0 ? 'up' : 'down';
export const escapeHtml = (text) => { /* ... */ };
export const debounce = (fn, delay) => { /* ... */ };
export const throttle = (fn, interval) => { /* ... */ };
// ... 共 20+ 个工具函数
```

### 2. state.js（全局状态，~100 行）

```javascript
// state.js
export const state = {
  market: null,
  watchlist: [],
  // ... 所有状态字段
};

export function setState(key, value) {
  state[key] = value;
  // 可扩展：触发订阅者更新
}
```

### 3. api.js（API 封装，~200 行）

```javascript
// api.js
import { state } from './state.js';

export async function apiJson(url, options = {}) {
  // 统一超时、错误处理、401 跳转
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(timeout);
    if (res.status === 401) { showLogin(); throw new Error('unauthorized'); }
    return await res.json();
  } catch (err) {
    clearTimeout(timeout);
    console.error(`API ${url} failed:`, err);
    throw err;
  }
}

// 各模块 API 封装
export const wencaiApi = {
  query: (payload) => apiJson('/api/wencai/query', { method: 'POST', body: JSON.stringify(payload) }),
};

export const eastmoneyApi = {
  hotspot: (payload) => apiJson('/api/eastmoney-ai/hotspot', { method: 'POST', body: JSON.stringify(payload) }),
  analysis: (payload) => apiJson('/api/eastmoney-ai/stock-analysis', { method: 'POST', body: JSON.stringify(payload) }),
  chat: (payload) => apiJson('/api/eastmoney-ai/chat', { method: 'POST', body: JSON.stringify(payload) }),
};
// ... 其他模块
```

### 4. views/*.js（各页面模块，每个 200-500 行）

以 `ai-tools.js` 为例：

```javascript
// views/ai-tools.js
import { $ } from '../utils.js';
import { wencaiApi, eastmoneyApi } from '../api.js';

export function initAITools() {
  // Tab 切换
  bindTabs();
  // 事件绑定
  $('#runWencaiQuery')?.addEventListener('click', runWencaiQuery);
  // ...
}

async function runWencaiQuery() {
  const query = $('#wencaiQueryInput')?.value?.trim();
  if (!query) return;
  renderLoading('wencaiResult');
  try {
    const data = await wencaiApi.query({ query, limit: 20 });
    renderWencaiResult(data);
  } catch (err) {
    renderError('wencaiResult', err);
  }
}

function renderWencaiResult(data) {
  // 渲染逻辑...
}

// 内部辅助函数...
```

### 5. main.js（入口，~80 行）

```javascript
// main.js
import { initDashboard } from './views/dashboard.js';
import { initReview } from './views/review.js';
import { initWatchlist } from './views/watchlist.js';
import { initTrading } from './views/trading.js';
import { initMarket } from './views/market.js';
import { initAbnormalMonitor } from './views/abnormal.js';
import { initSmartScreener } from './views/screener.js';
import { initAITools } from './views/ai-tools.js';
import { initResearch } from './views/research.js';
import { loadAdminMembers } from './views/admin.js';

const VIEW_INIT_MAP = {
  dashboard: initDashboard,
  review: initReview,
  watchlist: initWatchlist,
  trading: initTrading,
  market: initMarket,
  abnormal: initAbnormalMonitor,
  screener: initSmartScreener,
  'ai-tools': initAITools,
  research: initResearch,
  admin: loadAdminMembers,
};

// 路由切换
document.querySelectorAll('.nav').forEach(button => {
  button.addEventListener('click', () => {
    const view = button.dataset.view;
    switchView(view);
    VIEW_INIT_MAP[view]?.();
  });
});

function switchView(viewName) {
  document.querySelectorAll('.nav').forEach(n => n.classList.remove('active'));
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelector(`.nav[data-view="${viewName}"]`)?.classList.add('active');
  document.querySelector(`#${viewName}`)?.classList.add('active');
  $('#pageTitle').textContent = document.querySelector(`.nav[data-view="${viewName}"]`)?.textContent || '';
}
```

---

## HTML 简化

重构后 `index.html` 只保留骨架：

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>老马智能股票盯盘助手</title>
  <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
  <!-- 登录页 -->
  <div id="loginGate">...</div>
  
  <!-- 侧边导航 -->
  <aside>...</aside>
  
  <!-- 主内容区：view 容器 -->
  <main>
    <section id="dashboard" class="view active"></section>
    <section id="review" class="view"></section>
    <section id="watchlist" class="view"></section>
    <section id="trading" class="view"></section>
    <section id="market" class="view"></section>
    <section id="abnormal" class="view"></section>
    <section id="screener" class="view"></section>
    <section id="ai-tools" class="view"></section>
    <section id="research" class="view"></section>
    <section id="admin" class="view"></section>
  </main>
  
  <!-- 弹窗容器 -->
  <div id="modalContainer"></div>
  
  <!-- 模块入口 -->
  <script type="module" src="/static/js/main.js"></script>
</body>
</html>
```

View 的内容由 JS 动态渲染，不再内联在 HTML 中。

---

## CSS 拆分

```
css/
├── base.css           ← 变量、重置、布局骨架
├── components.css     ← 按钮、卡片、表格、弹窗、标签
├── views/
│   ├── dashboard.css
│   ├── screener.css
│   ├── ai-tools.css
│   └── ...
└── styles.css         ← @import 汇总（构建时合并）
```

---

## 重构后收益

| 指标 | 重构前 | 重构后 | 变化 |
|------|--------|--------|------|
| 单文件最大行数 | 4,196 | ~500 | **↓ 88%** |
| 找一段逻辑时间 | 5-10 分钟 | 10 秒 | **↓ 90%** |
| 加一个新 view | 改 3 个文件、怕崩 | 新增 1 个文件、隔离 | **质变** |
| 首次加载 JS | 4,196 行全解析 | 按需加载 | **更快** |
| 代码复用 | innerHTML 复制粘贴 | 组件导入 | **可维护** |

---

## 执行步骤

### 阶段一：准备（1 天）
1. 创建 `js/`、`css/` 目录结构
2. 提取 `utils.js` 和 `state.js`
3. 提取 `api.js`

### 阶段二：逐个迁移 view（每天 2-3 个，3-4 天）
1. `dashboard.js` → `watchlist.js` → `market.js`
2. `screener.js` → `ai-tools.js` → `research.js`
3. `trading.js` → `abnormal.js` → `review.js` → `admin.js`

### 阶段三：清理上线（1 天）
1. 删除旧的 `app.js`
2. 验证所有功能
3. 更新版本号

**总计：5-7 个工作日。**

---

## GitHub 上传准备

重构完成后，仓库结构更适合开源：

```
LaomaStockAssistant/
├── .github/
│   └── workflows/           ← CI/CD 自动化
├── app/                     ← 后端（已模块化，OK）
├── static/
│   ├── css/                 ← 拆分后的样式
│   └── js/                  ← 模块化前端
├── tests/                   ← 测试用例
├── docs/
│   ├── README.md            ← 项目介绍
│   ├── CONTRIBUTING.md      ← 贡献指南
│   └── API.md               ← 接口文档
├── requirements.txt
├── docker-compose.yml
└── LICENSE                  ← 开源协议（建议 MIT）
```
