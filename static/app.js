const state = {
  market: null,
  watchlist: [],
  candidates: [],
  portfolio: null,
  sectors: [],
  funds: [],
  events: [],
  strategyScan: null,
  dataQuality: null,
  emotionVolume: null,
  breadth: null,
  coverage: null,
  movers: null,
  systemAudit: null,
  chokepointAtlas: null,
  breakthroughReview: null,
  agentDebate: null,
  serenityFramework: null,
  actionQueue: null,
  tradeLog: [],
  eaSimulation: null,
  hiddenFundProxy: null,
  dataSourcePlan: null,
  quantUpgradePlan: null,
  aiRecommendations: null,
  adminMembers: [],
  membershipPlans: null,
  mobileDashboard: null,
  aiStatus: null,
  lastAiResult: null,
  aiReports: [],
  aiConfigProfiles: [],
  dailyReview: null,
  dailyReviewHistory: [],
  screenerCatalog: null,
  screenerStrategies: [],
  currentScreenerDsl: null,
  lastScreenerResults: [],
  screenerLoaded: false,
  abnormalCatalog: null,
  abnormalLoaded: false,
  abnormalItems: [],
  industryChainReports: [],
  selectedSuggestion: null,
  currentUser: null,
  reviewTheme: localStorage.getItem('laoma-review-theme') || 'light',
  watchSort: {
    held: 'custom',
    observing: 'custom',
  },
};

const $ = (selector) => document.querySelector(selector);
const fmtPct = (value) => `${value >= 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
const trend = (value) => value >= 0 ? 'up' : 'down';

function applyReviewTheme(theme = 'light') {
  state.reviewTheme = theme === 'dark' ? 'dark' : 'light';
  document.body.dataset.reviewTheme = state.reviewTheme;
  const button = $('#toggleReviewTheme');
  if (button) button.textContent = state.reviewTheme === 'dark' ? '浅色主题' : '深色主题';
  localStorage.setItem('laoma-review-theme', state.reviewTheme);
}

function sourceInfo(source = '') {
  const raw = String(source || '').trim();
  const lower = raw.toLowerCase();
  if (lower.includes('tushare')) return { label: raw.includes('daily') ? 'Tushare日K' : raw.includes('moneyflow') ? 'Tushare资金' : 'Tushare', level: 'real', note: raw };
  if (lower.includes('tencent')) return { label: '腾讯实时', level: 'real', note: raw };
  if (lower.includes('eastmoney')) return { label: '东方财富', level: raw.includes('fflow') ? 'fallback' : 'real', note: raw };
  if (lower.includes('sina')) return { label: '新浪备用', level: 'fallback', note: raw };
  if (lower.includes('broker')) return { label: '券商截图', level: 'manual', note: raw };
  if (lower.includes('manual')) return { label: '手工录入', level: 'manual', note: raw };
  if (lower.includes('pending') || lower.includes('demo') || lower.includes('fallback') || !raw) return { label: '待确认', level: 'pending', note: raw || '暂无数据源' };
  return { label: raw.split(/[ /]/)[0], level: 'fallback', note: raw };
}

function sourceTrafficLight(source = '', warnings = [], stale = false, fallbackUsed = false) {
  const raw = String(source || '').toLowerCase();
  const hasWarnings = Array.isArray(warnings) && warnings.length > 0;
  if (stale || raw.includes('missing') || raw.includes('not_configured') || raw.includes('unavailable') || raw.includes('disabled')) {
    return { level: 'red', label: '不可用/需确认' };
  }
  if (fallbackUsed || hasWarnings || raw.includes('fallback') || raw.includes('pending') || raw.includes('local') || raw.includes('manual')) {
    return { level: 'yellow', label: '降级/备用' };
  }
  return { level: 'green', label: '真实可用' };
}

function sourceBadge(source = '', extra = '') {
  const info = sourceInfo(source);
  return `<span class="source-badge ${info.level}" title="${info.note}">${info.label}</span>${extra ? `<small class="source-note">${extra}</small>` : ''}`;
}

function chartSourceBlock(chart) {
  const info = sourceInfo(chart?.source || '');
  const status = chart?.is_real ? '真实返回' : '不可用/降级';
  const message = chart?.message || (chart?.is_real ? '该图表使用接口返回的真实序列。' : '行情源没有返回有效序列。');
  return `<div class="source-panel ${info.level}">
    <div>${sourceBadge(chart?.source || '')}<b>${status}</b></div>
    <p>${message}</p>
  </div>`;
}

const WATCH_SORT_OPTIONS = [
  ['custom', '自定义排序'],
  ['change_desc', '涨幅从高到低'],
  ['change_asc', '跌幅从深到浅'],
  ['daily_pnl_desc', '今日盈亏从高到低'],
  ['daily_pnl_asc', '今日亏损从高到低'],
  ['pnl_desc', '持仓盈亏从高到低'],
  ['pnl_asc', '持仓亏损从高到低'],
  ['market_value_desc', '市值从高到低'],
  ['confidence_desc', 'AI置信度从高到低'],
  ['name_asc', '名称/代码排序'],
];

function candidateForItem(item) {
  return state.candidates.find(candidate => candidate.stock?.code === item.stock?.code) || {};
}

function sortWatchRows(rows, mode) {
  const list = [...rows];
  const get = (item) => {
    const stock = item.stock || {};
    const candidate = candidateForItem(item);
    return {
      custom: Number(stock.sort_order || 999),
      change: Number(stock.change_pct || 0),
      dailyPnl: Number(item.daily_pnl_amount || 0),
      pnl: Number(item.pnl_amount || 0),
      marketValue: Number(stock.price || 0) * Number(item.quantity || 0),
      confidence: Number(candidate.confidence || 0),
      name: `${stock.name || ''}${stock.code || ''}`,
      code: stock.code || '',
    };
  };
  list.sort((a, b) => {
    const av = get(a);
    const bv = get(b);
    let diff = 0;
    if (mode === 'change_desc') diff = bv.change - av.change;
    else if (mode === 'change_asc') diff = av.change - bv.change;
    else if (mode === 'daily_pnl_desc') diff = bv.dailyPnl - av.dailyPnl;
    else if (mode === 'daily_pnl_asc') diff = av.dailyPnl - bv.dailyPnl;
    else if (mode === 'pnl_desc') diff = bv.pnl - av.pnl;
    else if (mode === 'pnl_asc') diff = av.pnl - bv.pnl;
    else if (mode === 'market_value_desc') diff = bv.marketValue - av.marketValue;
    else if (mode === 'confidence_desc') diff = bv.confidence - av.confidence;
    else if (mode === 'name_asc') diff = av.name.localeCompare(bv.name, 'zh-CN');
    else diff = av.custom - bv.custom;
    return diff || av.code.localeCompare(bv.code);
  });
  return list;
}

function sortControl(kind) {
  return `<label class="sort-control">排序
    <select data-watch-sort="${kind}">
      ${WATCH_SORT_OPTIONS.map(([value, label]) => `<option value="${value}" ${state.watchSort[kind] === value ? 'selected' : ''}>${label}</option>`).join('')}
    </select>
  </label>`;
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  });
  if (response.status === 401) {
    showLogin();
    throw new Error('unauthorized');
  }
  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      const snippet = text.slice(0, 160);
      throw new Error(`HTTP ${response.status}: ${snippet || 'Internal Server Error'}`);
    }
  }
  if (!response.ok) {
    const message = payload?.message || payload?.error || text || 'Internal Server Error';
    throw new Error(`HTTP ${response.status}: ${message}`);
  }
  return payload ?? {};
}

// 页面初始化不能因为一个慢数据源而整页停在“准备中”。
// 保留原始 apiJson 供需要严格失败的操作使用；批量看板请求使用这个容错包装。
async function safeApiJson(url, fallback = {}) {
  try {
    return await apiJson(url);
  } catch (error) {
    pushEvent(`数据暂不可用：${url} · ${error.message || error}`);
    return typeof fallback === 'function' ? fallback(error) : fallback;
  }
}

function safeRender(renderer, payload, targetId = '') {
  try {
    renderer(payload);
  } catch (error) {
    const target = targetId ? document.getElementById(targetId) : null;
    if (target) target.innerHTML = `<div class="empty">该模块数据暂不可用，请稍后刷新。<br><small>${escapeHtml(error.message || error)}</small></div>`;
    pushEvent(`页面模块渲染失败：${targetId || renderer.name} · ${error.message || error}`);
  }
}

function showLogin(message = '') {
  const gate = $('#loginGate');
  if (gate) gate.classList.remove('hidden');
  if ($('#loginError')) $('#loginError').textContent = message;
}

function hideLogin() {
  const gate = $('#loginGate');
  if (gate) gate.classList.add('hidden');
}

function renderUserBadge(user) {
  const target = $('#userBadge');
  if (!target || !user) return;
  state.currentUser = user;
  document.body.classList.add('mobile-ready');
  document.querySelectorAll('.admin-only').forEach(item => item.classList.toggle('hidden', user.role !== 'admin'));
  target.innerHTML = `
    <div>
      <b>${user.display_name || user.username}</b>
      <span>${user.plan || 'member'} · ${user.role || 'member'}</span>
    </div>
    ${user.role === 'admin' ? '<button id="memberAdminJump" type="button">会员管理</button>' : ''}
    <button id="logoutButton">退出</button>
  `;
  $('#memberAdminJump')?.addEventListener('click', () => document.querySelector('.nav[data-view="admin"]')?.click());
  $('#logoutButton').addEventListener('click', logout);
}

const AI_PROVIDER_PRESETS = {
  deepseek: { baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  siliconflow: { baseUrl: 'https://api.siliconflow.cn/v1', model: 'deepseek-ai/DeepSeek-V3' },
  zhipu: { baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  doubao: { baseUrl: 'https://ark.cn-beijing.volces.com/api/v3', model: 'doubao-seed-1-6-flash-250615' },
  aliyun: { baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  moonshot: { baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  hunyuan: { baseUrl: 'https://api.hunyuan.cloud.tencent.com/v1', model: 'hunyuan-lite' },
  spark: { baseUrl: 'https://spark-api-open.xf-yun.com/v1', model: 'generalv3.5' },
  lingyi: { baseUrl: 'https://api.lingyiwanwu.com/v1', model: 'yi-lightning' },
  minimax: { baseUrl: 'https://api.minimax.chat/v1', model: 'abab6.5s-chat' },
  mimo_tokenplan: { baseUrl: 'https://token-plan-cn.xiaomimimo.com/v1', model: 'mimo-chat' },
  mimo: { baseUrl: 'https://api.xiaomimimo.com/v1', model: 'mimo-chat' },
  tencent_tokenhub: { baseUrl: 'https://tokenhub.tencentmaas.com/v1', model: 'deepseek-v3' },
  openai: { baseUrl: 'https://api.openai.com/v1', model: 'gpt-4.1-mini' },
  azure: { baseUrl: 'https://YOUR_RESOURCE.openai.azure.com/openai/deployments/YOUR_DEPLOYMENT', model: 'YOUR_DEPLOYMENT' },
  openrouter: { baseUrl: 'https://openrouter.ai/api/v1', model: 'deepseek/deepseek-chat-v3-0324' },
  ollama: { baseUrl: 'http://localhost:11434/v1', model: 'qwen2.5:7b' },
};

function renderAiGatewayStatus(status) {
  state.aiStatus = status;
  const button = $('#aiGatewayButton');
  if (!button) return;
  const label = status.enabled ? `${status.provider} · ${status.model}` : '本地规则引擎';
  button.textContent = `AI网关：${label}`;
  button.title = status.can_configure ? `点击配置 AI 模型（${status.scope_label || '个人模型配置'}）` : '当前账号不可修改 AI 模型配置';
  button.disabled = !status.can_configure;
}

async function refreshAiStatus() {
  try {
    renderAiGatewayStatus(await apiJson('/api/ai/status'));
  } catch (error) {
    const button = $('#aiGatewayButton');
    if (button) button.textContent = 'AI网关：状态读取失败';
  }
}

function setAiConfigFeedback(message = '', type = '') {
  const target = $('#aiConfigFeedback');
  target.textContent = message;
  target.className = `ai-config-feedback ${type}`.trim();
}

function aiConfigPayload() {
  return {
    enabled: $('#aiConfigEnabled').checked,
    provider: $('#aiConfigProvider').value,
    base_url: $('#aiConfigBaseUrl').value.trim(),
    model: $('#aiConfigModel').value.trim(),
    api_key: $('#aiConfigApiKey').value.trim(),
    profile_id: $('#aiConfigProfile').value,
    profile_name: $('#aiConfigProfileName').value.trim(),
  };
}

function fillAiConfigProfile(profile) {
  if (!profile) {
    $('#aiConfigProfileName').value = '';
    $('#aiConfigApiKey').value = '';
    $('#aiConfigApiKey').placeholder = '请输入 API Key';
    return;
  }
  const provider = Object.prototype.hasOwnProperty.call(AI_PROVIDER_PRESETS, profile.provider) ? profile.provider : 'custom';
  $('#aiConfigEnabled').checked = Boolean(profile.enabled || profile.has_api_key);
  $('#aiConfigProvider').value = provider;
  $('#aiConfigProfileName').value = profile.name || '';
  $('#aiConfigBaseUrl').value = profile.base_url || '';
  $('#aiConfigModel').value = profile.model || '';
  $('#aiConfigApiKey').value = '';
  $('#aiConfigApiKey').placeholder = profile.has_api_key ? `已保存 ${profile.masked_api_key}，留空则不修改` : '请输入 API Key';
  $('#aiConfigKeyHint').textContent = profile.has_api_key ? `当前已保存 ${profile.masked_api_key}；新 Key 只会覆盖本机旧配置。` : '密钥仅保存在这台电脑的本地配置中。';
}

function applyAiProviderPreset(provider, force = false) {
  const preset = AI_PROVIDER_PRESETS[provider];
  if (!preset) return;
  if (force || !$('#aiConfigBaseUrl').value.trim()) $('#aiConfigBaseUrl').value = preset.baseUrl;
  if (force || !$('#aiConfigModel').value.trim()) $('#aiConfigModel').value = preset.model;
}

async function openAiConfigModal() {
  if (!state.aiStatus?.can_configure) return;
  setAiConfigFeedback('正在读取当前配置...');
  $('#aiConfigModal').classList.add('open');
  try {
    const config = await apiJson('/api/ai/config');
    $('#aiConfigScopeLabel').textContent = config.scope_label || (config.config_scope === 'system' ? '系统默认配置' : '个人模型配置');
    state.aiConfigProfiles = config.profiles || [];
    const profileSelect = $('#aiConfigProfile');
    profileSelect.innerHTML = `<option value="">新增模型配置</option>${(config.profiles || []).map(profile => `<option value="${profile.id}">${profile.name}</option>`).join('')}`;
    profileSelect.value = config.active_profile_id || '';
    const provider = Object.prototype.hasOwnProperty.call(AI_PROVIDER_PRESETS, config.provider) ? config.provider : 'custom';
    $('#aiConfigEnabled').checked = Boolean(config.enabled);
    $('#aiConfigProvider').value = provider;
    $('#aiConfigBaseUrl').value = config.base_url || '';
    $('#aiConfigModel').value = config.model || '';
    $('#aiConfigApiKey').value = '';
    $('#aiConfigApiKey').placeholder = config.has_api_key ? `已保存 ${config.masked_api_key}，留空则不修改` : '请输入 API Key';
    $('#aiConfigKeyHint').textContent = config.has_api_key
      ? `当前已保存 ${config.masked_api_key}；新 Key 只会覆盖本机旧配置。`
      : '密钥仅保存在这台电脑的本地配置中。';
    const activeProfile = (config.profiles || []).find(profile => profile.id === config.active_profile_id);
    if (activeProfile) fillAiConfigProfile(activeProfile);
    setAiConfigFeedback(config.enabled ? `当前外部模型已启用（${config.scope_label || '个人模型配置'}）。` : `当前使用内置规则引擎（${config.scope_label || '个人模型配置'}）。`);
  } catch (error) {
    setAiConfigFeedback('配置读取失败，请重新登录后再试。', 'error');
  }
}

async function saveAiConfig(event) {
  event.preventDefault();
  const submit = event.currentTarget.querySelector('button[type="submit"]');
  submit.disabled = true;
  setAiConfigFeedback('正在保存配置...');
  try {
    const result = await apiJson('/api/ai/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(aiConfigPayload()),
    });
    if (!result.ok) throw new Error(result.message || '保存失败');
    setAiConfigFeedback('模型配置已保存；个股 AI 分析时可以直接选择。', 'success');
    await refreshAiStatus();
    await openAiConfigModal();
  } catch (error) {
    setAiConfigFeedback(error.message || '保存失败，请检查配置。', 'error');
  } finally {
    submit.disabled = false;
  }
}

async function testAiConfig() {
  const button = $('#testAiConfig');
  button.disabled = true;
  setAiConfigFeedback('正在连接模型，通常需要几秒钟...');
  try {
    const result = await apiJson('/api/ai/config/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(aiConfigPayload()),
    });
    if (!result.ok) throw new Error(result.message || '连接失败');
    setAiConfigFeedback(`连接成功：${result.model}${result.message ? ` · ${result.message}` : ''}`, 'success');
  } catch (error) {
    setAiConfigFeedback(error.message || '连接失败，请检查地址、模型名和 API Key。', 'error');
  } finally {
    button.disabled = false;
  }
}

function setClock() {
  const now = new Date();
  $('#clock').textContent = now.toLocaleString('zh-CN', { hour12: false });
}

function renderMarket(market) {
  state.market = market;
  $('#indexStrip').innerHTML = market.indices.map(index => (
    `<div class="ticker">${index.name} <b class="${trend(index.change_pct)}">${index.price.toFixed(2)} ${fmtPct(index.change_pct)}</b>${sourceBadge(index.source || '')}</div>`
  )).join('');

  $('#marketMetrics').innerHTML = [
    ['市场广度', `${market.up_count} / ${market.down_count}`, `红盘率 ${(market.up_count / (market.up_count + market.down_count) * 100).toFixed(1)}%`],
    ['短线情绪', market.mood, `涨停 ${market.limit_up} / 跌停 ${market.limit_down}`],
    ['成交额', `${market.turnover_billion.toFixed(1)}亿`, '正式版会接真实两市成交额'],
    ['今日风口', market.themes[0], market.themes.join('、')],
  ].map(([label, value, note]) => `<div class="metric"><label>${label}</label><strong>${value}</strong><p>${note}</p></div>`).join('');

  $('#marketQuant').innerHTML = [
    ['市场环境', market.mood, '决定进攻、防守、观察策略开关'],
    ['板块方向', market.themes.slice(0, 3).join(' / '), '用于筛选候选股票所在主线'],
    ['风险温度', market.limit_down > 20 ? '偏高' : '可控', '跌停数和全球风险共同判断'],
    ['数据源状态', market.source_mode, market.source_note],
  ].map(([label, value, note]) => `<div class="metric"><label>${label}</label><strong>${value}</strong><p>${note}</p></div>`).join('');

  $('#aiSummary').textContent = `市场处于${market.mood}阶段，红盘率接近中性，成交额演示值为${market.turnover_billion.toFixed(1)}亿。量化系统优先推荐“低位有模型信号 + 板块有资金”的股票，强趋势股只做风向标。`;
}

function renderQuantControl(radar) {
  const data = radar || {};
  const windowInfo = data.current_window || {};
  const policy = data.automation_policy || {};
  const linkage = data.global_linkage || {};
  const rules = (data.rules || []).slice(0, 6);
  const drivers = linkage.drivers || [];
  const riskScore = data.risk_score ?? '-';

  const mobileQuantControlContent = $('#mobileQuantControlContent');
  if (mobileQuantControlContent) {
    mobileQuantControlContent.innerHTML = `
      <b>${escapeHtml(windowInfo.name || '等待窗口识别')}</b>
      <span>${escapeHtml(windowInfo.action || '先观察市场，不做情绪化操作。')}</span>
      <small>风险 ${escapeHtml(riskScore)} / 100 · ${escapeHtml(policy.max_mode || 'confirm_before_order')}</small>
    `;
  }

  const panel = $('#quantControlPanel');
  if (!panel) return;
  panel.innerHTML = `
    <div class="quant-control-head">
      <div>
        <span class="eyebrow">反量化控盘雷达</span>
        <h2>${escapeHtml(windowInfo.name || '交易窗口纪律')}</h2>
        <p>${escapeHtml(windowInfo.action || '等待市场给出更清晰的确认信号。')}</p>
      </div>
      <div class="quant-risk-score"><span>风险</span><b>${escapeHtml(riskScore)}</b><small>/100</small></div>
    </div>
    <div class="quant-control-grid">
      <div class="quant-control-box">
        <b>当前纪律</b>
        <span>${escapeHtml(windowInfo.stance || '-')}</span>
        <small>${escapeHtml(windowInfo.start || '--')} - ${escapeHtml(windowInfo.end || '--')}</small>
      </div>
      <div class="quant-control-box">
        <b>自动化边界</b>
        <span>模拟：${escapeHtml(policy.paper_trade || '-')}</span>
        <small>真实下单：${escapeHtml(policy.real_order || '-')}</small>
      </div>
      <div class="quant-control-box">
        <b>全球联动观察</b>
        <span>${drivers.length ? drivers.map(item => escapeHtml(item)).join(' · ') : '-'}</span>
        <small>${escapeHtml(linkage.note || '')}</small>
      </div>
      <div class="quant-control-box">
        <b>反量化规则</b>
        <ul>${rules.map(item => `<li>${escapeHtml(item)}</li>`).join('') || '<li>暂无规则</li>'}</ul>
      </div>
    </div>
  `;
}

function renderDecisionFusion(data) {
  const panel = $('#decisionFusionPanel');
  if (!panel) return;
  const fusion = data || {};
  const tomorrow = fusion.tomorrow || {};
  const quant = fusion.quant || {};
  const matrix = fusion.data_matrix || {};
  const execution = fusion.execution || {};
  const nextActions = fusion.next_best_actions || [];
  const guardrails = fusion.guardrails || [];
  panel.innerHTML = `
    <div class="decision-fusion-head">
      <div>
        <span class="eyebrow">决策融合</span>
        <h2>明日预判 × 量化雷达 × 数据矩阵</h2>
        <p>把外部数据源、盘中量化扰动、自选股动作和回测验证合并成一个人工确认前的作战面板。</p>
      </div>
      <div class="quant-risk-score"><span>明日评分</span><b>${escapeHtml(tomorrow.score ?? '-')}</b><small>/100</small></div>
    </div>
    <div class="decision-fusion-grid">
      <div class="quant-control-box">
        <b>明日阶段</b>
        <span>${escapeHtml(tomorrow.stage || '-')}</span>
        <small>${escapeHtml(tomorrow.stance || '')}</small>
      </div>
      <div class="quant-control-box">
        <b>量化雷达</b>
        <span>最高嫌疑 ${escapeHtml(quant.top_score ?? '-')} / 100</span>
        <small>高风险 ${escapeHtml(quant.high_count ?? 0)} 只 · 尾盘压力 ${escapeHtml(quant.tail_pressure || '-')}</small>
      </div>
      <div class="quant-control-box">
        <b>数据矩阵</b>
        <span>${escapeHtml(matrix.gate || '-')}</span>
        <small>V${escapeHtml(matrix.toolkit_version || '-')} · 已接 ${escapeHtml(matrix.connected_count ?? 0)} / ${escapeHtml(matrix.endpoint_count ?? 0)} 个端点</small>
      </div>
      <div class="quant-control-box">
        <b>执行队列</b>
        <span>高优先级 ${escapeHtml(execution.high_priority_count ?? 0)} 个</span>
        <small>${escapeHtml(fusion.mode || 'human_confirmed_decision')}</small>
      </div>
    </div>
    <div class="decision-fusion-body">
      <div class="analysis-block">
        <h3>下一步动作</h3>
        ${listHtml(nextActions)}
      </div>
      <div class="analysis-block">
        <h3>风控边界</h3>
        ${listHtml(guardrails)}
      </div>
    </div>
  `;
}

function renderAiRecommendations(data) {
  state.aiRecommendations = data;
  const target = $('#aiRecommendations');
  if (!target) return;
  const items = (data.items || []).slice(0, 10);
  const gate = data.market_gate || state.unifiedGate || {};
  if (!items.length) {
    target.innerHTML = '<div class="empty">暂时没有满足条件的AI推荐股。市场闸门不打开时，宁可少推。</div>';
    return;
  }
  target.innerHTML = `
    <div class="ai-rec-head">
      <div>
        <b>AI 推荐盯盘池</b>
        <span>${data.principle || '最多10只，只做盯盘验证。'}</span>
      </div>
      <small>闸门 ${gate.state || '-'} · ${gate.score || '-'}分 · ${data.updated_at || '-'}</small>
    </div>
    <div class="ai-rec-list">
      ${items.map(item => `
        <div class="ai-rec-item">
          <div class="ai-rec-main">
            <strong>${item.name} <small>${item.code}</small></strong>
            <span class="${trend(item.change_pct)}">${Number(item.price || 0).toFixed(2)} ${fmtPct(item.change_pct || 0)}</span>
            <em>${item.reason || ''}</em>
          </div>
          <div class="ai-rec-meta">
            <span class="score-pill">AI ${item.score}</span>
            <span class="tag ${item.action === 'PRIORITY_TRACK' ? 'green' : 'amber'}">${item.action}</span>
            <small>成交额 ${Number(item.amount || 0).toFixed(2)}亿 · 主力 ${Number(item.main_net || 0).toFixed(2)}亿</small>
          </div>
          <div class="ai-rec-evidence">${(item.evidence || []).slice(0, 3).map(text => `<span>${text}</span>`).join('')}</div>
          <button ${item.in_watchlist ? 'disabled' : ''} data-track-reco="${item.code}">
            ${item.in_watchlist ? '已在盯盘' : '纳入盯盘'}
          </button>
        </div>
      `).join('')}
    </div>
  `;
}

function renderAiRecommendations(data) {
  state.aiRecommendations = data;
  const target = $('#aiRecommendations');
  if (!target) return;
  const items = (data.items || []).slice(0, 10);
  const gate = data.market_gate || state.unifiedGate || {};
  if (!items.length) {
    target.innerHTML = '<div class="empty">暂时没有满足条件的AI推荐股。市场闸门不打开时，宁可少推。</div>';
    return;
  }
  target.innerHTML = `
    <div class="ai-rec-head clean">
      <div>
        <b>AI 推荐盯盘池</b>
        <span>最多10只，只纳入盯盘验证，不直接等同于买入。</span>
      </div>
      <small>市场闸门 ${gate.state || '-'} · ${gate.score || '-'}分</small>
    </div>
    <div class="ai-rec-list compact">
      ${items.map((item, index) => {
        const evidence = item.evidence || [];
        const firstEvidence = evidence[0] || '量价和资金综合排序靠前';
        const secondEvidence = evidence.slice(1, 3).join(' / ') || item.reason || '等待回踩确认和后续盯盘验证';
        const isStrong = Number(item.score || 0) >= 82;
        return `
          <div class="ai-rec-item compact">
            <div class="ai-rec-rank">${index + 1}</div>
            <div class="ai-rec-main">
              <strong>${item.name}</strong>
              <small>${item.code}</small>
              <span class="ai-rec-category ${escapeHtml(item.signal_category || 'observe')}">${escapeHtml(item.signal_label || '仅观察')}</span>
            </div>
            <div class="ai-rec-price">
              <b class="${trend(item.change_pct)}">${Number(item.price || 0).toFixed(2)}</b>
              <span class="${trend(item.change_pct)}">${fmtPct(item.change_pct || 0)}</span>
            </div>
            <div class="ai-rec-reason">
              <b>${firstEvidence}</b>
              <span>${secondEvidence}</span>
            </div>
            <div class="ai-rec-score ${isStrong ? 'strong' : ''}">
              <b>${item.score}</b>
              <span>AI分</span>
            </div>
            <button ${item.in_watchlist ? 'disabled' : ''} data-track-reco="${item.code}">
              ${item.in_watchlist ? '已在盯盘' : '纳入盯盘'}
            </button>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderEmotionVolume(data) {
  state.emotionVolume = data;
  const rows = [
    ['情绪分', data.emotion_score, `${data.state}：${data.gate}`],
    ['量能分', data.volume_score, `${data.volume_state}，成交额 ${Number(data.turnover_billion || 0).toFixed(1)} 亿`],
    ['综合闸门', data.composite_score, `红盘率 ${Number(data.red_ratio || 0).toFixed(1)}%`],
    ['执行模式', data.risk_mode, (data.evidence || []).join(' / ')],
  ];
  const html = rows.map(([label, value, note]) => `<div class="metric"><label>${label}</label><strong>${value}</strong><p>${note}</p></div>`).join('');
  const target = $('#emotionVolumePanel');
  if (target) target.innerHTML = html;
}

function renderHiddenFundProxy(data) {
  state.hiddenFundProxy = data;
  const rows = (data.rows || []).slice(0, 8);
  $('#hiddenFundProxy').innerHTML = `
    <div class="warning">
      <b>说明：</b>${data.disclaimer || ''}
      <p>真正暗盘/席位/逐笔需要第三方 Level-2 或券商授权数据；当前为公开行情代理指标。</p>
    </div>
    <table>
      <thead><tr><th>股票</th><th>评分</th><th>状态</th><th>涨跌</th><th>成交额/主力净额</th><th>代理证据</th></tr></thead>
      <tbody>${rows.map(item => `<tr>
        <td>${item.name}<br><small>${item.code}</small></td>
        <td>${item.score}</td>
        <td><span class="tag ${item.score >= 72 ? 'green' : item.score >= 58 ? 'amber' : ''}">${item.status}</span></td>
        <td class="${trend(item.change_pct)}">${fmtPct(item.change_pct)}</td>
        <td>${Number(item.amount || 0) ? (Number(item.amount) / 100000000).toFixed(2) + '亿' : '-'}<br><small>${Number(item.main_net || 0) ? (Number(item.main_net) / 100000000).toFixed(2) + '亿' : '-'}</small></td>
        <td>${(item.notes || []).join(' / ')}</td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

function renderDataQuality(quality) {
  state.dataQuality = quality;
  const warnings = quality.warnings && quality.warnings.length
    ? quality.warnings.join('；')
    : '腾讯实时源工作正常，指数与个股正在按 2-10 秒节奏刷新。';
  $('#dataQualityBanner').innerHTML = `
    <b>行情源：</b>
    指数 ${sourceBadge(quality.index_source || '')}
    个股 ${sourceBadge(quality.quote_source || '')}
    全A ${sourceBadge(quality.market_source || '')}
    <span>刷新：指数 ${quality.index_age_sec ?? '-'} 秒，个股 ${quality.quote_age_sec ?? '-'} 秒，全A ${quality.market_age_sec ?? '-'} 秒</span>
    <p>${warnings}</p>
  `;
  $('#dataQualityBanner').classList.toggle('danger', Boolean(quality.warnings && quality.warnings.length));
}

function renderWatchlist(items) {
  state.watchlist = items;
  const candidateMap = new Map(state.candidates.map(item => [item.stock.code, item]));
  $('#watchCards').innerHTML = `<div class="holdings-board"><table class="holdings-table">
    <thead>
      <tr>
        <th>名称/代码</th>
        <th>数据源</th>
        <th>现价/涨跌</th>
        <th>动作</th>
        <th>市值</th>
        <th>持仓/成本</th>
        <th>持仓盈亏</th>
        <th>今日盈亏</th>
        <th>模型信号</th>
        <th>操作</th>
      </tr>
    </thead>
    <tbody>
    ${items.map(item => {
    const stock = item.stock;
    const candidate = candidateMap.get(stock.code) || {};
    const action = candidate.action || 'WATCH';
    const tags = item.signals.map(signal => `<span class="tag ${signal.score >= 70 ? 'green' : signal.score < 50 ? 'red' : 'amber'}">${signal.name}:${signal.status}</span>`).join('');
    return `<tr>
      <td><b>${stock.name}</b><br><small>${stock.code}</small></td>
      <td>${sourceBadge(stock.source || 'fallback', '报价/持仓计算口径')}</td>
      <td><strong class="${trend(stock.change_pct)}">${stock.price.toFixed(2)}</strong><br><span class="${trend(stock.change_pct)}">${fmtPct(stock.change_pct)}</span></td>
      <td><span class="action-label ${action.toLowerCase()}">${action}</span><br><small>置信度 ${candidate.confidence || '-'}</small></td>
      <td>${(stock.price * item.quantity).toFixed(2)}</td>
      <td>${item.quantity}<br><small>成本 ${stock.cost.toFixed(3)}</small></td>
      <td><span class="${trend(item.pnl_pct)}">${item.pnl_amount.toFixed(2)}</span><br><small class="${trend(item.pnl_pct)}">${fmtPct(item.pnl_pct)}</small></td>
      <td><span class="${trend(item.daily_pnl_amount)}">${item.daily_pnl_amount.toFixed(2)}</span><br><small class="${trend(item.daily_pnl_amount)}">${fmtPct(item.daily_pnl_pct)}</small></td>
      <td><div class="tags compact">${tags}</div><small>${stock.ai}</small></td>
      <td><div class="card-actions"><button class="ai" data-ai="${stock.code}" data-name="${stock.name}">AI分析</button><button data-remove="${stock.code}">取消</button></div></td>
    </tr>`;
    }).join('')}
    </tbody>
  </table></div>`;
}

function renderWatchlistV2(items) {
  state.watchlist = items;
  const candidateMap = new Map(state.candidates.map(item => [item.stock.code, item]));
  const sorted = [...items].sort((a, b) => {
    const ao = a.stock.sort_order || 999;
    const bo = b.stock.sort_order || 999;
    return ao - bo || a.stock.code.localeCompare(b.stock.code);
  });
  const held = sortWatchRows(sorted.filter(item => item.quantity > 0), state.watchSort.held);
  const observing = sortWatchRows(sorted.filter(item => item.quantity <= 0), state.watchSort.observing);

  function table(title, rows, emptyText, kind) {
    return `
      <div class="watch-section">
        <div class="section-head compact-head">
          <div>
            <h2>${title}</h2>
            <p>${rows.length} 只股票</p>
          </div>
          ${sortControl(kind)}
        </div>
        ${rows.length ? `<div class="holdings-board"><table class="holdings-table">
          <thead>
            <tr>
              <th>名称/代码</th>
              <th>数据源</th>
              <th>现价/涨跌</th>
              <th>动作</th>
              <th>市值</th>
              <th>持仓/成本</th>
              <th>持仓盈亏</th>
              <th>今日盈亏</th>
              <th>提醒/风控</th>
              <th>模型信号</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
          ${rows.map(item => {
            const stock = item.stock;
            const candidate = candidateMap.get(stock.code) || {};
            const action = candidate.action || 'WATCH';
            const tags = item.signals.map(signal => `<span class="tag ${signal.score >= 70 ? 'green' : signal.score < 50 ? 'red' : 'amber'}">${signal.name}:${signal.status}</span>`).join('');
            return `<tr>
              <td><b>${stock.name}</b><br><small>${stock.code}</small></td>
              <td>${sourceBadge(stock.source || 'fallback', item.quantity > 0 ? '现价用于盈亏计算' : '观察报价')}</td>
              <td><strong class="${trend(stock.change_pct)}">${stock.price.toFixed(2)}</strong><br><span class="${trend(stock.change_pct)}">${fmtPct(stock.change_pct)}</span></td>
              <td><span class="action-label ${action.toLowerCase()}">${action}</span><br><small>置信度 ${candidate.confidence || '-'}</small></td>
              <td>${item.quantity > 0 ? (stock.price * item.quantity).toFixed(2) : '-'}</td>
              <td>${item.quantity || 0}<br><small>成本 ${Number(stock.cost || 0).toFixed(3)}</small>${item.cost_valid === false ? '<br><span class="tag red">成本待确认</span>' : ''}</td>
              <td><span class="${trend(item.pnl_amount)}">${item.quantity > 0 ? item.pnl_amount.toFixed(2) : '-'}</span><br><small class="${trend(item.pnl_pct)}">${item.quantity > 0 ? fmtPct(item.pnl_pct) : '非持仓'}</small></td>
              <td><span class="${trend(item.daily_pnl_amount)}">${item.quantity > 0 ? item.daily_pnl_amount.toFixed(2) : '-'}</span><br><small class="${trend(item.daily_pnl_amount)}">${item.quantity > 0 ? fmtPct(item.daily_pnl_pct) : '-'}</small></td>
              <td>
                <small>涨跌 ${Number(stock.alert_pct || 0).toFixed(2)}%</small><br>
                <small>价格 ${Number(stock.alert_price || 0).toFixed(2)}</small><br>
                <small>止盈 ${Number(stock.take_profit || 0).toFixed(2)} / 止损 ${Number(stock.stop_loss || 0).toFixed(2)}</small>
              </td>
              <td><div class="tags compact">${tags}</div><small>${stock.ai}</small></td>
              <td><div class="card-actions">
                <button class="ai" data-ai="${stock.code}" data-name="${stock.name}">AI分析</button>
                <button data-stock-view="sources" data-code="${stock.code}">三源数据</button>
                <button data-stock-view="capital" data-code="${stock.code}">资金事件</button>
                <button data-stock-view="analysis" data-code="${stock.code}">K线资金分析</button>
                <button data-stock-view="minute" data-code="${stock.code}">分时</button>
                <button data-stock-view="kline" data-code="${stock.code}">日K</button>
                <button data-stock-view="fund" data-code="${stock.code}">资金</button>
                <button data-stock-view="detail" data-code="${stock.code}">详情</button>
                <button data-stock-view="announcements" data-code="${stock.code}">公告</button>
                <button data-stock-view="research" data-code="${stock.code}">研报</button>
                <button data-stock-view="backtest" data-code="${stock.code}">回测</button>
                <button class="position" data-position="${stock.code}">持仓设置</button>
                <button data-remove="${stock.code}">取消</button>
              </div></td>
            </tr>`;
          }).join('')}
          </tbody>
        </table></div>` : `<div class="empty-log">${emptyText}</div>`}
      </div>
    `;
  }

  $('#watchCards').innerHTML = [
    table('自持仓', held, '还没有持仓股票。点观察池里的“持仓设置”，录入数量和成本后会自动归入这里。', 'held'),
    table('观察池 / 非自持', observing, '观察池为空，可以用顶部搜索添加股票。', 'observing'),
  ].join('');
}

function renderPortfolio(summary) {
  state.portfolio = summary;
  const riskText = summary.risk_positions
    .map(item => `${item.name} ${fmtPct(item.pnl_pct)}`)
    .join(' / ');
  const topText = summary.top_positions
    .map(item => `${item.name} ${item.market_value.toFixed(0)}`)
    .join(' / ');
  const cashEditor = `
    <div class="cash-editor">
      <input id="portfolioCashInput" type="number" min="0" step="0.01" value="${Number(summary.cash_available || 0).toFixed(2)}">
      <button id="portfolioCashSave" class="confirm" type="button">确认</button>
    </div>
  `;
  const rows = [
    ['总资产', Number(summary.total_assets || 0).toFixed(2), `实时持仓市值 + 可用资金 · ${summary.account || '当前账户'}`, ''],
    ['总市值', summary.total_market_value.toFixed(2), `${summary.position_count} 只持仓 · 按现价*数量计算`, ''],
    ['可用资金', `${Number(summary.cash_available || 0).toFixed(2)}${cashEditor}`, `来源 ${summary.cash_source || 'not_configured'} · 输入后点击确认更新`, ''],
    ['总浮盈亏', summary.total_pnl.toFixed(2), `按现价/成本/数量计算 · 盈利 ${summary.profitable_count} / 亏损 ${summary.losing_count}`, trend(summary.total_pnl)],
    ['今日盈亏', summary.total_daily_pnl.toFixed(2), '按实时现价、涨跌幅和实际持股数量计算', trend(summary.total_daily_pnl)],
    ['重仓', topText || '暂无', '按当前市值排序', ''],
    ['风险持仓', riskText || '暂无', '按浮亏比例排序', ''],
  ];
  $('#portfolioSummary').innerHTML = rows.map(([label, value, note, cls]) => `<div class="metric"><label>${label}</label><strong class="${cls}">${value}</strong><p>${note}</p></div>`).join('');
}

async function savePortfolioCash() {
  const input = $('#portfolioCashInput');
  const button = $('#portfolioCashSave');
  if (!input || !button) return;
  const cashAvailable = Number(input.value || 0);
  button.disabled = true;
  try {
    await apiJson('/api/portfolio/cash', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cash_available: cashAvailable }),
    });
    pushEvent(`可用资金已更新为 ${cashAvailable.toFixed(2)}。`);
    renderPortfolio(await apiJson('/api/portfolio/summary'));
  } catch (error) {
    pushEvent(`可用资金保存失败：${error.message || error}`);
  } finally {
    button.disabled = false;
  }
}

function renderQuantFundRadar(radar) {
  const data = radar || {};
  $('#actionGate').insertAdjacentHTML('afterbegin', `<div class="warning ${unifiedGate.allowed ? '' : 'danger'}"><b>统一闸门：${unifiedGate.allowed ? '可进入人工确认' : '仅观察/减仓'}</b> ${escapeHtml((unifiedGate.reasons || []).join('；'))}</div>`);
  if (gateHistory.length) $('#actionGate').insertAdjacentHTML('beforeend', `<small>闸门最近记录：${escapeHtml(gateHistory.length)} 条，最近一次 ${escapeHtml(gateHistory[0].created_at || '-')}（${gateHistory[0].allowed ? '通过' : '拦截'}）</small>`);
  const summary = data.summary || {};
  const tail = data.tail_session || {};
  const linkage = data.linkage || {};
  const dominantTags = linkage.dominant_tags || [];
  const drivers = linkage.global_drivers || [];
  const alerts = data.top_alerts || [];
  if (!alerts.length) {
    return `<div class="quant-fund-radar"><b>量化资金雷达 3.0</b><p>已扫描 ${escapeHtml(summary.scanned ?? 0)} 只自选股，暂未发现高强度尾盘/资金异动。</p></div>`;
  }
  return `
    <div class="quant-fund-radar">
      <div class="quant-control-head">
        <div>
          <span class="eyebrow">量化资金雷达 ${escapeHtml(data.version || '3.0')}</span>
          <h3>高风险 ${escapeHtml(summary.high_count ?? 0)} 只 · 最高嫌疑 ${escapeHtml(summary.top_score ?? '-')} / 100</h3>
          <p>${escapeHtml(data.policy || '只做盯盘、复盘和人工确认，不自动下单。')}</p>
        </div>
      </div>
      <div class="grid two">
        <div class="health-card">
          <h4>尾盘监控</h4>
          <p><b>${escapeHtml(tail.level || '-')}</b> · ${escapeHtml(tail.window || '14:00-15:00')} · 压力 ${escapeHtml(tail.pressure_score ?? '-')} / 100</p>
          <small>${escapeHtml(tail.action || '等待尾盘资金证据。')}</small>
        </div>
        <div class="health-card">
          <h4>板块联动 / 全球驱动</h4>
          <p>${dominantTags.map(item => `${escapeHtml(item.name)}×${escapeHtml(item.count)}`).join(' · ') || '暂无明显同主题聚集'}</p>
          <small>${escapeHtml(linkage.interpretation || '')}${drivers.length ? `｜${drivers.map(escapeHtml).join('、')}` : ''}</small>
        </div>
      </div>
      <div class="grid three">
        ${alerts.map(item => `<div class="health-card">
          <h4>${escapeHtml(item.name)} <small>${escapeHtml(item.code)}</small></h4>
          <p><b>量化嫌疑 ${escapeHtml(item.suspicion_score)} / 100</b> · ${escapeHtml(item.level)} · ${escapeHtml(item.fund_direction || '-')}</p>
          <small>${escapeHtml(item.reason || item.stance || '-')}</small>
        </div>`).join('')}
      </div>
    </div>
  `;
}

function renderActionQueue(data) {
  state.actionQueue = data;
  const ev = data.emotion_volume || {};
  const pitfallChecks = [
    { question: '计划是否只针对本人持仓和自选？', verdict: '已隔离', note: '动作队列只服务当前登录会员，不读取其他会员股票池。' },
    { question: '关键数据源是否清楚？', verdict: '可追溯', note: '每条建议都保留 data source，便于回头核对截图或接口来源。' },
    { question: '触发条件是否明确？', verdict: '明确', note: '重点核对触发价、失效价和仓位上限，避免模糊执行。' },
    { question: '是否需要人工确认？', verdict: '需要', note: '这里生成的是执行清单，不是自动下单指令。' },
  ];
  $('#actionMode').textContent = data.mode || 'decision queue';
  const unifiedGate = data.unified_gate || state.unifiedGate || {};
  const gateHistory = data.gate_history || [];
  $('#actionGate').innerHTML = `
    <b>交易闸门：${data.gate || '-'}</b>
    <span>${data.updated_at || ''}</span>
    <p>${data.gate_reason || data.principle || ''}</p>
    <p><b>情绪量能：</b>${ev.state || '-'}，综合 ${ev.composite_score ?? '-'} / 情绪 ${ev.emotion_score ?? '-'} / 量能 ${ev.volume_score ?? '-'}；${ev.gate || ''}</p>
  ` + pitfallChecksHtml(pitfallChecks, '交易前四问');
  const summary = data.summary || {};
  const summaryRows = [
    ['减仓/风控', (summary.REDUCE_RISK || 0) + (summary.STOP_REVIEW || 0), '弱市深亏或破位复核'],
    ['量化盯防', summary.QUANT_WATCH || 0, '尾盘/资金异动，需要人工盯防'],
    ['盈利保护', summary.PROTECT || 0, '利润垫较厚，优先守收益'],
    ['加仓候选', summary.ADD_ON_PULLBACK || 0, '只看回踩确认，不追高'],
    ['持有/观察', (summary.HOLD || 0) + (summary.HOLD_CONFIRM || 0) + (summary.WATCH || 0), '等待触发价和证据共振'],
  ];
  $('#actionSummary').innerHTML = summaryRows.map(([label, value, note]) => `
    <div class="metric">
      <label>${label}</label>
      <strong>${value}</strong>
      <p>${note}</p>
    </div>
  `).join('');

  const rows = data.actions || [];
  const controls = data.execution_controls || {};
  const controlItems = controls.items || [];
  $('#actionQueue').innerHTML = `
    <div class="execution-controls">
      <div>
        <span class="eyebrow">交易安全控制</span>
        <h3>自动操作先过四道闸门</h3>
        <p>当前为“确认清单”模式：订单预检通过后仍需人工确认，实盘自动下单保持关闭。</p>
      </div>
      <div class="execution-control-grid">
        ${controlItems.map(item => `<div class="execution-control-card ${escapeHtml(item.status || '')}">
          <b>${escapeHtml(item.name || '')}</b>
          <span>${escapeHtml(item.status || '')}</span>
          <small>${escapeHtml(item.detail || '')}</small>
        </div>`).join('')}
      </div>
    </div>
    ${renderQuantFundRadar(data.quant_fund_radar)}
    <table class="action-table">
      <thead>
        <tr>
          <th>优先级</th>
          <th>股票</th>
          <th>动作</th>
          <th>现价/涨跌</th>
          <th>持仓盈亏</th>
          <th>触发价</th>
          <th>失效价</th>
          <th>仓位规则</th>
          <th>理由与证据</th>
          <th>记录</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(item => {
          const actionKey = String(item.action || '').toLowerCase();
          const evidence = (item.evidence || []).map(text => `<span class="tag">${text}</span>`).join('');
          return `<tr>
            <td><b>${item.priority}</b></td>
            <td><b>${item.name}</b><br><small>${item.code}<br>${item.data_source || '-'}</small></td>
            <td><span class="action-pill ${actionKey}">${item.label || item.action}</span><br><small>${item.action}</small></td>
            <td><strong class="${trend(item.change_pct)}">${Number(item.price).toFixed(2)}</strong><br><span class="${trend(item.change_pct)}">${fmtPct(item.change_pct)}</span></td>
            <td><span class="${trend(item.pnl_amount)}">${Number(item.pnl_amount).toFixed(2)}</span><br><small class="${trend(item.pnl_pct)}">${fmtPct(item.pnl_pct)}</small><br><small>今日 ${Number(item.daily_pnl).toFixed(2)}</small></td>
            <td>${Number(item.trigger_price).toFixed(2)}</td>
            <td>${Number(item.invalidation_price).toFixed(2)}</td>
            <td>${item.position_advice}<br><small>单票上限 ${item.max_position_pct}%</small></td>
            <td><p>${item.reason}</p><div class="tags compact">${evidence}</div><small>${item.next_step}</small></td>
            <td><div class="card-actions log-actions">
              <button data-log-code="${item.code}" data-log-mode="paper">模拟执行</button>
              <button class="confirm" data-log-code="${item.code}" data-log-mode="manual">人工确认</button>
            </div></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;
}

function renderTradeLog(data) {
  const items = data.items || data || [];
  state.tradeLog = items;
  if (!items.length) {
    $('#tradeLog').innerHTML = '<div class="empty-log">还没有执行记录。先在动作队列里点“模拟执行”，系统会把当时的价格、理由和闸门都保存下来。</div>';
    return;
  }
  $('#tradeLog').innerHTML = `
    <table class="action-table">
      <thead><tr><th>时间</th><th>模式</th><th>股票</th><th>动作</th><th>价格</th><th>触发/失效</th><th>当时闸门</th><th>理由</th></tr></thead>
      <tbody>${items.slice(0, 40).map(item => `<tr>
        <td>${item.created_at}</td>
        <td><span class="tag ${item.mode === 'paper' ? 'amber' : 'green'}">${item.status}</span></td>
        <td>${item.name}<br><small>${item.code}</small></td>
        <td><span class="action-pill ${String(item.action).toLowerCase()}">${item.label || item.action}</span></td>
        <td>${Number(item.price).toFixed(2)}<br><small class="${trend(item.daily_pnl)}">今日 ${Number(item.daily_pnl).toFixed(2)}</small></td>
        <td>${Number(item.trigger_price).toFixed(2)} / ${Number(item.invalidation_price).toFixed(2)}</td>
        <td>${item.market_gate || '-'}<br><small>${item.emotion_volume?.state || '-'} ${item.emotion_volume?.composite_score ?? '-'}</small></td>
        <td>${item.reason}</td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

function renderEaSimulation(data) {
  state.eaSimulation = data;
  const target = $('#eaSimulationBody');
  if (!target) return;
  const strategies = data.strategies || [];
  const selected = $('#eaStrategySelect')?.value || strategies[0]?.id || 'anti_quant_tail';
  const strategy = strategies.find(item => item.id === selected) || strategies[0] || {};
  const lastOrders = data.last_orders || data.orders || [];
  target.innerHTML = `
    <div class="ea-simulation-summary">
      <div><b>${escapeHtml(data.title || 'EA模拟盘')}</b><span>${escapeHtml(data.safety_policy || '只模拟，不实盘')}</span></div>
      <div><b>${Number(data.stats?.total_orders || lastOrders.length)}</b><span>累计模拟订单</span></div>
      <div><b>${data.stats?.manual_required ? '需要' : '不需要'}</b><span>人工确认</span></div>
      <div><b>${escapeHtml(data.stats?.last_run_at || '-')}</b><span>最近运行</span></div>
    </div>
    <div class="analysis-block">
      <h3>${escapeHtml(strategy.name || '策略机器人')}</h3>
      <p>${escapeHtml(strategy.description || 'EA式策略只在模拟盘运行，用于验证信号，不直接触达券商。')}</p>
      <small>安全边界：只模拟，不实盘；后续真实下单必须走人工确认或官方券商接口。</small>
    </div>
    ${lastOrders.length ? `<table><thead><tr><th>时间</th><th>策略</th><th>股票</th><th>动作</th><th>价格</th><th>风控窗口</th></tr></thead><tbody>${lastOrders.slice(0, 10).map(item => `<tr>
      <td>${escapeHtml(item.created_at || '-')}</td>
      <td>${escapeHtml(item.strategy_id || '-')}</td>
      <td>${escapeHtml(item.name || '-')}<br><small>${escapeHtml(item.code || '')}</small></td>
      <td><span class="tag amber">${escapeHtml(item.status || 'ea_simulated')}</span><br>${escapeHtml(item.label || item.action || '-')}</td>
      <td>${screenerNumber(item.price)}</td>
      <td>${escapeHtml(item.risk_gate?.name || '-')}<br><small>${escapeHtml(item.risk_gate?.action || '')}</small></td>
    </tr>`).join('')}</tbody></table>` : '<div class="empty-log">还没有 EA 模拟订单，点击“运行一轮模拟”。</div>'}
  `;
}

async function refreshEaSimulation() {
  try {
    const data = await apiJson('/api/trading/ea-simulation');
    renderEaSimulation(data);
    const code = (data.last_orders || [])[0]?.code;
    if (code) {
      loadDynamicRisk(code);
      loadFactorAnalysis(code);
    }
  } catch (error) {
    $('#eaSimulationBody').innerHTML = `<div class="warning">EA模拟盘读取失败：${escapeHtml(error.message || error)}</div>`;
  }
}

async function runEaSimulation() {
  const button = $('#runEaSimulation');
  if (button) button.disabled = true;
  try {
    const result = await apiJson('/api/trading/ea-simulation/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        strategy_id: $('#eaStrategySelect')?.value || 'anti_quant_tail',
        max_orders: Number($('#eaMaxOrders')?.value || 5),
      }),
    });
    renderEaSimulation(result);
    const log = await apiJson('/api/trading/log');
    renderTradeLog(log);
    pushEvent(`EA模拟盘已生成 ${result.count || 0} 条模拟订单；只模拟，不实盘。`);
  } catch (error) {
    pushEvent(`EA模拟盘运行失败：${error.message || error}`);
  } finally {
    if (button) button.disabled = false;
  }
}

function pitfallChecksHtml(items = [], title = '避坑4问') {
  if (!items.length) return '';
  return `<div class="analysis-block pitfall-board">
    <h3>${escapeHtml(title)}</h3>
    <div class="grid two">
      ${items.map(item => `<div class="health-card"><b>${escapeHtml(item.question || '-')}</b><p>${escapeHtml(item.verdict || '-')}</p><small>${escapeHtml(item.note || '')}</small></div>`).join('')}
    </div>
  </div>`;
}

function renderCandidates(items) {
  state.candidates = items;
  $('#candidateTable').innerHTML = `<table>
    <thead><tr><th>股票</th><th>推荐</th><th>评分</th><th>模型信号</th><th>AI解释</th></tr></thead>
    <tbody>${items.map(item => `<tr>
      <td>${item.stock.name} ${item.stock.code}</td>
      <td><span class="tag green">${item.recommendation}</span></td>
      <td>${item.total_score}</td>
      <td>${item.signals.map(signal => `${signal.name}:${signal.status}`).join(' / ')}</td>
      <td>${item.reason}</td>
    </tr>`).join('')}</tbody>
  </table>`;
}

function renderSectors(items) {
  state.sectors = items;
  $('#sectorTable').innerHTML = `<table><thead><tr><th>板块</th><th>涨跌幅</th><th>强度</th><th>原因</th></tr></thead><tbody>
    ${items.map(item => `<tr><td>${item.name}</td><td class="${trend(item.change_pct)}">${fmtPct(item.change_pct)}</td><td>${item.strength}</td><td>${item.reason}</td></tr>`).join('')}
  </tbody></table>`;
}

function renderFunds(items) {
  state.funds = items;
  $('#fundTable').innerHTML = `<table><thead><tr><th>股票</th><th>涨跌幅</th><th>资金估算</th><th>状态</th></tr></thead><tbody>
    ${items.map(item => `<tr><td>${item.name}</td><td class="${trend(item.change_pct)}">${fmtPct(item.change_pct)}</td><td>${item.estimated_flow_wan}万</td><td>${item.status}</td></tr>`).join('')}
  </tbody></table>`;
}

function renderEvents(items) {
  state.events = items;
  $('#eventTable').innerHTML = `<table><thead><tr><th>时间</th><th>类型</th><th>事件</th><th>影响</th></tr></thead><tbody>
    ${items.map(item => `<tr><td>${item.time.replace('T', ' ')}</td><td>${item.type}</td><td>${item.title}</td><td>${item.impact}</td></tr>`).join('')}
  </tbody></table>`;
}

function heatColor(value) {
  if (value >= 72) return 'heat hot';
  if (value >= 46) return 'heat warm';
  if (value >= 24) return 'heat mild';
  return 'heat cold';
}

function renderBreadth(data) {
  state.breadth = data;
  $('#breadthSummary').innerHTML = `
    <b>${data.signal}</b>
    <span>${data.source}</span>
    <p>${data.advice}</p>
  `;
  const columns = data.columns || [];
  const rows = data.rows || [];
  $('#breadthHeatmap').innerHTML = `
    <table class="heatmap">
      <thead>
        <tr>
          <th class="date-cell">日期</th>
          ${columns.map(col => `<th><span>${col}</span></th>`).join('')}
          <th class="total-cell">总计</th>
        </tr>
      </thead>
      <tbody>
        ${rows.map(row => `<tr>
          <td class="date-cell">${row.date}</td>
          ${row.values.map(cell => `<td class="${heatColor(cell.value)}" title="${row.date} ${cell.sector}: ${cell.value}">${cell.value}</td>`).join('')}
          <td class="total-cell">${row.total}</td>
        </tr>`).join('')}
      </tbody>
    </table>
  `;
}

function renderCoverage(data) {
  state.coverage = data;
  $('#coverageTable').innerHTML = `
    <div class="analysis-block"><h3>数据原则</h3><p>${data.principle}</p></div>
    <table>
      <thead><tr><th>模块</th><th>状态</th><th>来源</th><th>用途</th></tr></thead>
      <tbody>${data.modules.map(item => `<tr>
        <td>${item.name}</td>
        <td><span class="tag ${item.status.includes('已') ? 'green' : item.status.includes('待') ? 'amber' : ''}">${item.status}</span></td>
        <td>${item.source}</td>
        <td>${item.use}</td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

function renderMoverList(title, items, field) {
  const rows = (items || []).slice(0, 8).map(item => {
    const value = field === 'amount'
      ? `${(Number(item.amount || 0) / 100000000).toFixed(2)}亿`
      : field === 'main_net'
        ? `${(Number(item.main_net || 0) / 100000000).toFixed(2)}亿`
        : fmtPct(Number(item.change_pct || 0));
    const cls = field === 'main_net' ? trend(Number(item.main_net || 0)) : trend(Number(item.change_pct || 0));
    return `<tr><td>${item.name}<br><small>${item.code}</small></td><td class="${cls}">${value}</td><td>${Number(item.price || 0).toFixed(2)}</td></tr>`;
  }).join('');
  return `<div class="panel mini-table"><h3>${title}</h3><table><thead><tr><th>股票</th><th>指标</th><th>现价</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderMovers(data) {
  state.movers = data;
  $('#moversGrid').innerHTML = [
    renderMoverList('涨幅榜', data.top_gainers, 'change_pct'),
    renderMoverList('跌幅榜', data.top_losers, 'change_pct'),
    renderMoverList('成交额榜', data.top_amount, 'amount'),
    renderMoverList('主力净额榜', data.top_main_net, 'main_net'),
  ].join('');
}

function auditTag(status) {
  if (status === '已定义') return 'green';
  if (status === '部分定义') return 'amber';
  return 'red';
}

function renderSystemAudit(data) {
  state.systemAudit = data;
  $('#systemAudit').innerHTML = `
    <div class="grid four audit-summary">
      <div class="metric"><label>系统完整度</label><strong>${data.score}</strong><p>已定义 ${data.solved} / 部分 ${data.partial} / 待补 ${data.pending}</p></div>
      <div class="metric"><label>交易闸门</label><strong>${data.gate}</strong><p>${data.gate_reason}</p></div>
      <div class="metric"><label>规则来源</label><strong>12问</strong><p>${data.source}</p></div>
      <div class="metric"><label>执行纪律</label><strong>先系统</strong><p>${data.rule}</p></div>
    </div>
    <table>
      <thead><tr><th>问题</th><th>分组</th><th>回答</th><th>状态</th></tr></thead>
      <tbody>${data.questions.map(item => `<tr>
        <td>${item.id}. ${item.question}</td>
        <td>${item.group}</td>
        <td>${item.answer}</td>
        <td><span class="tag ${auditTag(item.status)}">${item.status}</span></td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

function renderChokepointAtlas(data) {
  state.chokepointAtlas = data;
  $('#chokepointAtlas').innerHTML = `
    <div class="analysis-block"><h3>研究原则</h3><p>${data.principle}</p><p>${data.source}</p></div>
    <div class="atlas-grid">
      ${data.lanes.map(lane => `<div class="analysis-block">
        <h3>${lane.name} <span class="tag ${lane.score >= 80 ? 'green' : 'amber'}">${lane.status}</span></h3>
        <p>${lane.system}</p>
        <p><b>产业层级：</b>${lane.layers.join(' / ')}</p>
        <p><b>潜在卡点：</b>${lane.chokepoints.join(' / ')}</p>
        <p><b>验证证据：</b>${lane.verification.join(' / ')}</p>
        <table>
          <thead><tr><th>持仓/候选</th><th>角色</th><th>受益逻辑</th></tr></thead>
          <tbody>${lane.mapped_positions.map(item => `<tr><td>${item.name}<br><small>${item.code}</small></td><td>${item.role}</td><td>${item.benefit}</td></tr>`).join('')}</tbody>
        </table>
      </div>`).join('')}
    </div>
  `;
}

function renderBreakthroughReview(data) {
  state.breakthroughReview = data;
  $('#breakthroughReview').innerHTML = `
    <div class="analysis-block"><h3>识别标准</h3><p>${data.source}</p><ul>${data.rules.map(rule => `<li>${rule}</li>`).join('')}</ul></div>
    <table>
      <thead><tr><th>股票</th><th>涨跌</th><th>评分</th><th>状态</th><th>证据</th><th>下一步</th></tr></thead>
      <tbody>${data.rows.map(item => `<tr>
        <td>${item.name}<br><small>${item.code}</small></td>
        <td class="${trend(item.change_pct)}">${fmtPct(item.change_pct)}</td>
        <td>${item.score}</td>
        <td><span class="tag ${item.score >= 72 ? 'green' : item.score >= 55 ? 'amber' : 'red'}">${item.status}</span></td>
        <td>${item.evidence.join(' / ')}</td>
        <td>${item.next_check}</td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

function renderAgentDebate(data) {
  state.agentDebate = data;
  $('#agentDebate').innerHTML = `
    <div class="analysis-block"><h3>分工原则</h3><p>${data.principle}</p><p>${data.source}</p><p>${data.integration_status || ''}</p></div>
    <table>
      <thead><tr><th>层级</th><th>角色</th><th>职责</th></tr></thead>
      <tbody>${(data.layers || []).map(item => `<tr><td>${item.layer}</td><td>${item.roles}</td><td>${item.job}</td></tr>`).join('')}</tbody>
    </table>
    <div class="analysis-block"><h3>交易记忆机制</h3><ul>${(data.memory_plan || []).map(item => `<li>${item}</li>`).join('')}</ul></div>
    <div class="grid two">
      ${data.agents.map(agent => `<div class="analysis-block">
        <h3>${agent.name} <span class="tag amber">${agent.verdict}</span></h3>
        <p><b>边界：</b>${agent.scope}</p>
        <p>${agent.view}</p>
      </div>`).join('')}
    </div>
  `;
}

function renderSerenityFramework(data) {
  state.serenityFramework = data;
  const dimensions = data.dimensions || [];
  const cards = data.framework_cards || [];
  const rows = data.rows || [];
  $('#serenityFramework').innerHTML = `
    <div class="analysis-block serenity-lead">
      <h3>研究原则</h3>
      <p>${data.principle || ''}</p>
      <p class="danger-text">${data.warning || ''}</p>
      <small>${data.source || ''} · ${data.updated_at || ''}</small>
    </div>
    <div class="serenity-dimensions">
      ${dimensions.map((item, index) => `<div>
        <b>${index + 1}｜${item.name}</b>
        <span>${item.job}</span>
      </div>`).join('')}
    </div>
    <div class="grid four serenity-cards">
      ${cards.map(item => `<div class="analysis-block">
        <h3>${item.name}</h3>
        <p>${item.detail}</p>
      </div>`).join('')}
    </div>
    <table>
      <thead><tr><th>股票</th><th>框架分</th><th>优先级</th><th>产业链位置</th><th>瓶颈假设</th><th>验证证据</th><th>下一步</th></tr></thead>
      <tbody>${rows.map(item => `<tr>
        <td>${item.name}<br><small>${item.code} · ${item.tag}</small></td>
        <td><strong>${item.serenity_score}</strong></td>
        <td><span class="tag ${item.serenity_score >= 78 ? 'green' : item.serenity_score >= 65 ? 'amber' : 'red'}">${item.priority}</span></td>
        <td>${item.lanes}<br><small>${item.supply_chain_role}</small></td>
        <td>${item.bottleneck_hypothesis}</td>
        <td>${(item.verification || []).join(' / ')}</td>
        <td>${item.next_research}</td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

function renderDataSourcePlan(data) {
  state.dataSourcePlan = data;
  $('#dataSourcePlan').innerHTML = `
    <div class="analysis-block">
      <h3>建议</h3>
      <p>${data.recommendation}</p>
      <p>${data.principle}</p>
      <div class="tags">${(data.must_have || []).map(item => `<span class="tag green">${item}</span>`).join('')}</div>
    </div>
    <table>
      <thead><tr><th>数据源</th><th>定位</th><th>适合内容</th><th>成本判断</th><th>优点</th><th>限制</th><th>结论</th></tr></thead>
      <tbody>${data.vendors.map(item => `<tr>
        <td><b>${item.name}</b></td>
        <td>${item.tier}</td>
        <td>${item.fit}</td>
        <td>${item.cost}</td>
        <td>${item.strength}</td>
        <td>${item.weakness}</td>
        <td><span class="tag ${item.decision.includes('第一') ? 'green' : item.decision.includes('暂不') ? 'red' : 'amber'}">${item.decision}</span></td>
      </tr>`).join('')}</tbody>
    </table>
    <div class="analysis-block">
      <h3>路线图</h3>
      <ul>${data.roadmap.map(item => `<li>${item}</li>`).join('')}</ul>
    </div>
  `;
}

function renderQuantUpgradePlan(data) {
  state.quantUpgradePlan = data;
  $('#quantUpgradePlan').innerHTML = `
    <div class="analysis-block quant-upgrade-lead">
      <h3>结论</h3>
      <p>${escapeHtml(data.judgement || '')}</p>
      <p><b>当前阶段：</b>${escapeHtml(data.current_stage || '')}</p>
    </div>
    <div class="grid two">
      ${(data.priority_gaps || []).map(item => `<div class="analysis-block">
        <h3>${escapeHtml(item.name)}</h3>
        <p>${escapeHtml(item.why)}</p>
        <small>${escapeHtml(item.status)}</small>
      </div>`).join('')}
    </div>
    <table>
      <thead><tr><th>阶段</th><th>目标</th><th>周期</th><th>交付物</th></tr></thead>
      <tbody>${(data.phases || []).map(item => `<tr>
        <td>${escapeHtml(item.phase)}</td>
        <td>${escapeHtml(item.title)}</td>
        <td>${escapeHtml(item.time)}</td>
        <td>${escapeHtml(item.deliverable)}</td>
      </tr>`).join('')}</tbody>
    </table>
    <div class="warning"><b>自动交易红线：</b>${(data.red_lines || []).map(item => `<span>${escapeHtml(item)}</span>`).join('')}</div>
  `;
}

function setAdminMemberFeedback(message = '', type = '') {
  const target = $('#adminMemberFeedback');
  if (!target) return;
  target.textContent = message;
  target.className = `ai-config-feedback ${type}`.trim();
}

function membershipTierOptions(selected = 'trial') {
  const tiers = state.membershipPlans?.tiers || [
    { id: 'trial', name: '试用会员' },
    { id: 'supporter', name: '赞助会员' },
    { id: 'pro', name: '进阶赞助会员' },
    { id: 'sponsor', name: '共建赞助会员' },
    { id: 'founder', name: '创始管理员' },
  ];
  return tiers.map(tier => `<option value="${escapeHtml(tier.id)}" ${selected === tier.id ? 'selected' : ''}>${escapeHtml(tier.name)}</option>`).join('');
}

function membershipFeatureGate(planId = 'trial', featureKey = '') {
  const tier = (state.membershipPlans?.tiers || []).find(item => item.id === planId);
  if (!tier) return false;
  const value = tier.features?.[featureKey];
  return value === true || value === 'limited';
}

function renderMembershipPlans(data) {
  state.membershipPlans = data;
  const adminPlanSelect = $('#adminNewPlan');
  if (adminPlanSelect) adminPlanSelect.innerHTML = membershipTierOptions(adminPlanSelect.value || 'trial');
  const target = $('#membershipPlanPanel');
  if (!target || !data) return;
  const current = data.current || state.currentUser?.membership || {};
  const currentTier = current.tier_id || state.currentUser?.plan || 'trial';
  target.innerHTML = `
    <div class="section-head">
      <div>
        <span class="eyebrow">会员/赞助计划</span>
        <h2>低门槛赞助制，不消耗管理员 AI 额度</h2>
        <p>${escapeHtml(data.philosophy || '收费只对应软件服务、数据能力和功能权限，不承诺收益。')}</p>
      </div>
      <span class="tag green">当前：${escapeHtml(current.tier_name || currentTier)}</span>
    </div>
    <div class="membership-tier-grid">
      ${(data.tiers || []).map(tier => `
        <div class="membership-tier-card ${tier.id === currentTier ? 'active' : ''}">
          <div class="membership-tier-head">
            <span class="tag ${tier.id === 'trial' ? 'amber' : tier.id === 'founder' ? 'red' : 'green'}">${escapeHtml(tier.badge || tier.name)}</span>
            <h3>${escapeHtml(tier.name)}</h3>
          </div>
          <div class="membership-price">${Number(tier.price_month || 0) > 0 ? `¥${tier.price_month}/月` : '¥0'}<small>${Number(tier.price_year || 0) > 0 ? ` / ¥${tier.price_year}/年` : tier.id === 'founder' ? ' / 管理员' : ' / 试用'}</small></div>
          <p>${escapeHtml(tier.description || '')}</p>
          <ul class="membership-benefits">${(tier.benefits || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
        </div>
      `).join('')}
    </div>
    <div class="membership-private-contact">
      <div class="membership-private-copy">
        <span class="eyebrow">首批私域开通</span>
        <h3>${escapeHtml(data.private_contact?.title || '扫码联系管理员开通')}</h3>
        <p>${escapeHtml(data.private_contact?.description || '首批名额采用人工审核，确认套餐后由管理员开通。')}</p>
        <strong>${escapeHtml(data.private_contact?.name || '管理员')} · ${escapeHtml(data.private_contact?.location || '')}</strong>
      </div>
      <img class="membership-private-qr" src="${escapeHtml(data.private_contact?.qr_path || '/static/private-contact-qr.png')}" alt="添加微信联系管理员">
    </div>
    <div class="membership-rule-strip">${(data.rules || []).map(item => `<span>${escapeHtml(item)}</span>`).join('')}</div>
  `;
}

function renderAdminMembers(data) {
  const items = data.items || data || [];
  state.adminMembers = items;
  const target = $('#adminMemberTable');
  if (!target) return;
  if (!items.length) {
    target.innerHTML = '<div class="empty">暂无会员。</div>';
    return;
  }
  target.innerHTML = `
    <table>
      <thead><tr><th>ID</th><th>账号/手机号</th><th>昵称</th><th>角色</th><th>套餐</th><th>到期</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>${items.map(user => `<tr data-admin-user-row="${user.id}">
        <td>${user.id}</td>
        <td><b>${escapeHtml(user.username)}</b><br><input data-admin-field="phone" value="${escapeHtml(user.phone || '')}" placeholder="手机号"></td>
        <td><input data-admin-field="display_name" value="${escapeHtml(user.display_name || '')}"></td>
        <td><select data-admin-field="role">${['admin', 'analyst', 'member', 'viewer'].map(role => `<option value="${role}" ${user.role === role ? 'selected' : ''}>${role}</option>`).join('')}</select></td>
        <td><select data-admin-field="plan">${membershipTierOptions(user.plan || 'trial')}</select><br><small>${escapeHtml(user.membership?.tier_name || '')}</small></td>
        <td><input data-admin-field="days" type="number" min="0" placeholder="续期天数"><br><small>${escapeHtml(user.expires_at || '长期')}</small></td>
        <td><label class="mini-check"><input data-admin-field="is_active" type="checkbox" ${user.is_active !== false ? 'checked' : ''}>启用</label></td>
        <td><input data-admin-field="password" type="password" placeholder="留空不改密码"><button data-admin-save="${user.id}" type="button">保存</button></td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

async function loadAdminMembers() {
  if (state.currentUser?.role !== 'admin') return;
  setAdminMemberFeedback('正在读取会员列表...');
  try {
    renderAdminMembers(await apiJson('/api/admin/users'));
    setAdminMemberFeedback(`已加载 ${state.adminMembers.length} 个会员。`, 'success');
  } catch (error) {
    setAdminMemberFeedback(error.message || '会员列表读取失败。', 'error');
  }
}

async function createAdminMember(event) {
  event.preventDefault();
  const payload = {
    username: $('#adminNewUsername').value.trim(),
    phone: $('#adminNewPhone').value.trim(),
    display_name: $('#adminNewDisplayName').value.trim(),
    password: $('#adminNewPassword').value,
    role: $('#adminNewRole').value,
    plan: $('#adminNewPlan').value.trim() || 'trial',
    days: Number($('#adminNewDays').value || 30),
  };
  setAdminMemberFeedback('正在新增会员...');
  try {
    const result = await apiJson('/api/admin/users', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    if (result.error) throw new Error(result.message || result.error);
    setAdminMemberFeedback(`会员 ${result.user.display_name || result.user.username} 已新增。`, 'success');
    $('#adminCreateMemberForm').reset();
    $('#adminNewPassword').value = '123456';
    $('#adminNewRole').value = 'member';
    $('#adminNewPlan').value = 'trial';
    $('#adminNewDays').value = '30';
    await loadAdminMembers();
  } catch (error) {
    setAdminMemberFeedback(error.message || '新增会员失败。', 'error');
  }
}

async function saveAdminMember(userId) {
  const row = document.querySelector(`[data-admin-user-row="${userId}"]`);
  if (!row) return;
  const payload = {};
  row.querySelectorAll('[data-admin-field]').forEach(input => {
    const key = input.dataset.adminField;
    if (key === 'is_active') payload[key] = input.checked;
    else if (key === 'days') {
      if (input.value !== '') payload[key] = Number(input.value);
    } else if (key === 'password') {
      if (input.value) payload[key] = input.value;
    } else payload[key] = input.value;
  });
  setAdminMemberFeedback('正在保存会员...');
  try {
    const result = await apiJson(`/api/admin/users/${userId}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    if (result.error) throw new Error(result.message || result.error);
    setAdminMemberFeedback(`会员 ${result.user.display_name || result.user.username} 已更新。`, 'success');
    await loadAdminMembers();
  } catch (error) {
    setAdminMemberFeedback(error.message || '保存会员失败。', 'error');
  }
}

function reviewWatchlistTable(items) {
  if (!items.length) return '<div class="empty">当前账号还没有自选股，先从顶部搜索里加几只重点标的。</div>';
  return `<table><thead><tr><th>股票</th><th>动作</th><th>现价/涨跌</th><th>策略点位</th><th>持仓表现</th><th>AI摘要</th><th>操作</th></tr></thead><tbody>${items.map(item => `<tr>
    <td><b>${escapeHtml(item.name)}</b><br><small>${escapeHtml(item.code)}</small></td>
    <td><span class="tag ${Number(item.priority || 0) >= 70 ? 'red' : Number(item.priority || 0) >= 50 ? 'amber' : 'green'}">${escapeHtml(item.action || '盯盘观察')}</span></td>
    <td><strong class="${trend(item.change_pct)}">${screenerNumber(item.price)}</strong><br><span class="${trend(item.change_pct)}">${fmtPct(Number(item.change_pct || 0))}</span></td>
    <td>支撑 ${screenerNumber(item.support)}<br>压力 ${screenerNumber(item.resistance)}<br><small>止损 ${screenerNumber(item.stop_loss)} / 止盈 ${screenerNumber(item.take_profit)}</small></td>
    <td>${item.position ? `${item.position} 股` : '观察股'}<br><small class="${trend(item.pnl_pct || 0)}">${item.pnl_pct === null || item.pnl_pct === undefined ? '-' : fmtPct(item.pnl_pct)}</small></td>
    <td>${escapeHtml(item.ai_summary || '-')}</td>
    <td><div class="screener-action-cell"><button data-review-watch="${escapeHtml(item.code)}">加自选</button><button data-review-ai="${escapeHtml(item.code)}" data-review-name="${escapeHtml(item.name)}">AI复核</button></div></td>
  </tr>`).join('')}</tbody></table>`;
}

function reviewObservationTable(items) {
  if (!items.length) return '<div class="empty">当前没有新的观察池候选，先等下一轮行情刷新。</div>';
  return `<table><thead><tr><th>股票</th><th>评分</th><th>资金/成交</th><th>证据</th><th>操作</th></tr></thead><tbody>${items.map(item => `<tr>
    <td><b>${escapeHtml(item.name)}</b><br><small>${escapeHtml(item.code)}</small></td>
    <td><strong>${escapeHtml(item.score)}</strong><br><small>${escapeHtml(item.action || 'TRACK')}</small></td>
    <td>${screenerNumber(item.amount, '亿')}<br><small>主力 ${screenerNumber(item.main_net, '亿')}</small></td>
    <td>${escapeHtml((item.evidence || []).join('；'))}</td>
    <td><div class="screener-action-cell"><button data-review-score="${escapeHtml(item.code)}">中枢评分</button><button data-review-track="${escapeHtml(item.code)}">纳入盯盘</button></div></td>
  </tr>`).join('')}</tbody></table>`;
}

function reviewHistoryList(items) {
  if (!items.length) return '<div class="empty">还没有保存过复盘，点“保存今日复盘”后会出现在这里。</div>';
  return `<div class="ai-history-list">${items.map(item => `<div class="ai-history-item" data-review-history="${item.id}"><b>${escapeHtml(item.title || item.review_date || '复盘')}</b><span>${escapeHtml(item.created_at)} · ${escapeHtml(item.summary || '')}</span></div>`).join('')}</div>`;
}

function sentimentTone(score) {
  const value = Number(score || 0);
  if (value >= 75) return 'hot';
  if (value >= 58) return 'warm';
  if (value >= 42) return 'calm';
  return 'cold';
}

function reviewSignalCards(items) {
  return (items || []).map(item => `<div class="review-signal-card ${escapeHtml(item.tone || 'amber')}">
    <span>${escapeHtml(item.label)}</span>
    <strong>${escapeHtml(item.value)}</strong>
    <p>${escapeHtml(item.note || '')}</p>
  </div>`).join('');
}

function reviewNewsFeed(items) {
  if (!items.length) return '<div class="empty">当前没有新的事件流。</div>';
  return `<div class="review-news-list">${items.map(item => `<article class="review-news-item">
    <div><span class="tag ${item.impact?.includes('风险') || item.impact?.includes('谨慎') ? 'red' : item.impact?.includes('多') || item.impact?.includes('观察') ? 'green' : 'amber'}">${escapeHtml(item.type || '事件')}</span><small>${escapeHtml(item.time || '')}</small></div>
    <b>${escapeHtml(item.title || '')}</b>
    <p>${escapeHtml(item.impact || '')}</p>
  </article>`).join('')}</div>`;
}

function reviewHistorySummary(summary) {
  const tradeLogs = summary.trade_logs || [];
  const savedReviews = summary.saved_reviews || [];
  return `<div class="review-mini-columns">
    <div class="analysis-block review-mini-panel">
      <h4>最近动作记录</h4>
      ${tradeLogs.length ? `<ul>${tradeLogs.map(item => `<li>${escapeHtml(item.created_at || '')} · ${escapeHtml(item.name || item.code || '')} · ${escapeHtml(item.label || item.status || '')}</li>`).join('')}</ul>` : '<p>当前没有新的交易记录。</p>'}
    </div>
    <div class="analysis-block review-mini-panel">
      <h4>最近保存复盘</h4>
      ${savedReviews.length ? `<ul>${savedReviews.map(item => `<li>${escapeHtml(item.created_at || '')} · ${escapeHtml(item.title || '')}</li>`).join('')}</ul>` : '<p>当前没有已保存复盘。</p>'}
    </div>
  </div>`;
}

function reviewPlanBadges(plan) {
  const bias = plan.market_bias || {};
  return `
    <div class="review-plan-badges">
      <span class="tag ${escapeHtml(plan.color || 'amber')}">${escapeHtml(plan.stage || '待判断')}</span>
      <span>情绪 ${escapeHtml(bias.emotion_score ?? '-')}</span>
      <span>宽度 ${escapeHtml(bias.breadth_signal || '-')}</span>
      <span>量化风险 ${escapeHtml(bias.quant_risk_score ?? '-')}</span>
      <span>成交额 ${escapeHtml(bias.turnover_billion ?? '-')} 亿</span>
    </div>
  `;
}

function reviewPlanActionTable(items) {
  if (!items.length) return '<div class="empty">当前没有需要加入明日作战卡的自选股动作。</div>';
  return `<table><thead><tr><th>股票</th><th>动作</th><th>触发/支撑</th><th>理由</th></tr></thead><tbody>${items.map(item => `<tr>
    <td><b>${escapeHtml(item.name || '')}</b><br><small>${escapeHtml(item.code || '')}</small></td>
    <td><span class="tag ${Number(item.priority || 0) >= 80 ? 'red' : Number(item.priority || 0) >= 60 ? 'amber' : 'green'}">${escapeHtml(item.action || '观察')}</span></td>
    <td>触发 ${escapeHtml(item.trigger_price ?? '-')}<br><small>支撑 ${escapeHtml(item.support ?? '-')}</small></td>
    <td>${escapeHtml(item.reason || '-')}<br><small>${escapeHtml((item.evidence || []).join('；'))}</small></td>
  </tr>`).join('')}</tbody></table>`;
}

function reviewPlanCandidateTable(items) {
  if (!items.length) return '<div class="empty">当前没有值得纳入明日观察池的新增候选。</div>';
  return `<table><thead><tr><th>候选</th><th>评分</th><th>资金</th><th>证据</th></tr></thead><tbody>${items.map(item => `<tr>
    <td><b>${escapeHtml(item.name || '')}</b><br><small>${escapeHtml(item.code || '')}</small></td>
    <td><strong>${escapeHtml(item.score ?? '-')}</strong><br><small>${escapeHtml(item.action || 'TRACK')}</small></td>
    <td>${screenerNumber(item.amount, '亿')}<br><small>主力 ${screenerNumber(item.main_net, '亿')}</small></td>
    <td>${escapeHtml((item.evidence || []).join('；') || '-')}</td>
  </tr>`).join('')}</tbody></table>`;
}

function reviewCatalystFeed(items) {
  if (!items.length) return '<div class="empty">当前没有新增催化，明早重点看板块与资金承接。</div>';
  return `<div class="review-news-list">${items.map(item => `<article class="review-news-item">
    <div><span class="tag ${item.type === '公告' ? 'amber' : item.type === '研报' ? 'green' : 'blue'}">${escapeHtml(item.type || '事件')}</span><small>${escapeHtml(item.date || '')}</small></div>
    <b>${escapeHtml(item.name || '')}</b>
    <p>${escapeHtml(item.title || '')}</p>
    <small>${escapeHtml(item.impact || '')}</small>
  </article>`).join('')}</div>`;
}

function reviewIntradayWindows(items) {
  if (!items.length) return '<div class="empty">当前没有盘中窗口提示。</div>';
  return `<div class="review-window-grid">${items.map(item => `<article class="review-window-card">
    <strong>${escapeHtml(item.time || '')}</strong>
    <b>${escapeHtml(item.title || '')}</b>
    <p>${escapeHtml(item.action || '')}</p>
  </article>`).join('')}</div>`;
}

function reviewIntelList(items, type) {
  if (!items.length) return '<div class="empty">当前没有新的情报更新。</div>';
  return `<div class="review-news-list">${items.map(item => `<article class="review-news-item">
    <div><span class="tag ${type === 'announcement' ? 'amber' : 'green'}">${type === 'announcement' ? '公告' : '研报'}</span><small>${escapeHtml(item.date || '')}</small></div>
    <b>${escapeHtml(item.name || item.code || '')}</b>
    <p>${escapeHtml(item.title || '')}</p>
    <small>${escapeHtml(type === 'announcement' ? (item.source || '公告') : `${item.institution || '-'} / ${item.rating || '-'}`)}</small>
  </article>`).join('')}</div>`;
}

function reviewIntelBoard(items) {
  if (!items.length) return '<div class="empty">当前没有可展开的个股情报。</div>';
  return `<div class="review-intel-board">${items.map((item, index) => `<details class="review-intel-card" ${index === 0 ? 'open' : ''}>
    <summary>
      <div class="review-intel-trigger" data-review-intel="${escapeHtml(item.code || '')}">
        <b>${escapeHtml(item.name || item.code || '')}</b>
        <small>${escapeHtml(item.code || '')} · 最近更新 ${escapeHtml(item.latest_date || '-')}</small>
      </div>
      <div class="review-intel-metrics">
        <span>${escapeHtml(item.announcement_count ?? 0)} 公告</span>
        <span>${escapeHtml(item.research_count ?? 0)} 研报</span>
      </div>
    </summary>
    <div class="review-intel-detail">
      <section>
        <h4>公告催化</h4>
        ${reviewIntelList(item.announcements || [], 'announcement')}
      </section>
      <section>
        <h4>研报跟踪</h4>
        ${reviewIntelList(item.research_reports || [], 'research')}
      </section>
    </div>
  </details>`).join('')}</div>`;
}

function openReviewIntelDrawer(code) {
  const groups = state.dailyReview?.market_review?.intelligence?.by_stock || [];
  const item = groups.find(entry => entry.code === code);
  if (!item) return;
  $('#reviewIntelDrawerTitle').textContent = `${item.name || item.code} 情报雷达`;
  $('#reviewIntelDrawerMeta').textContent = `${item.code || ''} · 公告 ${item.announcement_count ?? 0} 条 · 研报 ${item.research_count ?? 0} 条 · 最近更新 ${item.latest_date || '-'}`;
  $('#reviewIntelDrawerBody').innerHTML = `
    <div class="review-intel-drawer-actions">
      <button type="button" class="primary" data-review-drawer-ai="${escapeHtml(item.code || '')}" data-review-drawer-name="${escapeHtml(item.name || '')}">AI 分析</button>
      <button type="button" data-review-watch="${escapeHtml(item.code || '')}">加入自选</button>
    </div>
    <div class="review-intel-drawer-grid">
      <section class="analysis-block review-section-card">
        <h3>公告催化</h3>
        ${reviewIntelList(item.announcements || [], 'announcement')}
      </section>
      <section class="analysis-block review-section-card">
        <h3>研报跟踪</h3>
        ${reviewIntelList(item.research_reports || [], 'research')}
      </section>
    </div>
  `;
  $('#reviewIntelDrawer').classList.add('open');
}

function closeReviewIntelDrawer() {
  $('#reviewIntelDrawer')?.classList.remove('open');
}

function renderDailyReview(data) {
  state.dailyReview = data;
  const market = data.market_review || {};
  const watchlist = data.watchlist_review || {};
  const observation = data.observation_pool || {};
  const nextDay = data.next_day_plan || {};
  const history = data.history || {};
  const intelligence = market.intelligence || {};
  const sentimentScore = Number(market.emotion_score || 0);
  const sentimentStyle = `--review-score:${Math.max(0, Math.min(100, sentimentScore))};`;
  $('#reviewCenterBody').innerHTML = `
    <section class="review-hero tone-${sentimentTone(sentimentScore)}">
      <div class="review-hero-copy">
        <span class="eyebrow">Daily Review Center</span>
        <h3>${escapeHtml(data.title || '今日复盘')}</h3>
        <p>${escapeHtml(data.summary || '')}</p>
        <small>${escapeHtml(data.generated_at || '')}</small>
        <div class="review-signal-grid">${reviewSignalCards(market.key_signals || [])}</div>
      </div>
      <div class="review-sentiment-panel">
        <div class="review-ring ${sentimentTone(sentimentScore)}" style="${sentimentStyle}">
          <div>
            <span>Market Sentiment</span>
            <strong>${escapeHtml(market.emotion_score ?? '-')}</strong>
            <small>${escapeHtml(market.mood || '')}</small>
          </div>
        </div>
        <div class="review-hero-meta">
          <div><label>宽度信号</label><b>${escapeHtml(market.breadth_signal || '-')}</b></div>
          <div><label>上涨 / 下跌</label><b>${escapeHtml(market.up_count ?? '-')} / ${escapeHtml(market.down_count ?? '-')}</b></div>
          <div><label>成交额</label><b>${escapeHtml(market.turnover_billion ?? '-')} 亿</b></div>
          <div><label>已存档复盘</label><b>${escapeHtml(history.count ?? 0)}</b></div>
        </div>
      </div>
    </section>
    <div class="review-layout">
      <div class="review-main">
        <div class="analysis-block review-section-card"><h3>自选股复盘</h3><p>范围：${escapeHtml(watchlist.scope || 'current_user_watchlist')} · ${escapeHtml(watchlist.count || 0)} 只</p>${reviewWatchlistTable(watchlist.items || [])}</div>
        <div class="analysis-block review-section-card"><h3>明日观察池</h3><p>市场闸门：${escapeHtml(observation.market_gate?.state || '-')} / ${escapeHtml(observation.market_gate?.score ?? '-')} 分</p>${reviewObservationTable(observation.items || [])}</div>
        <div class="analysis-block review-section-card review-plan-card">
          <h3>明日预判作战卡</h3>
          <p>${escapeHtml(nextDay.headline || '把复盘收束成明天可执行动作，先看环境，再看板块和个股。')}</p>
          ${reviewPlanBadges(nextDay)}
          <div class="review-plan-slab">
            <div>
              <label>核心立场</label>
              <strong>${escapeHtml(nextDay.stage || '-')}</strong>
              <span>${escapeHtml(nextDay.stance || '')}</span>
            </div>
            <div>
              <label>市场闸门</label>
              <strong>${escapeHtml(nextDay.market_bias?.gate || '-')}</strong>
              <span>不追情绪，优先等板块和个股共振。</span>
            </div>
          </div>
          <div class="review-mini-columns">
            <div class="analysis-block review-mini-panel"><h4>明日主线</h4>${listHtml((nextDay.focus_sectors || []).map(item => `${item.name} / 强度 ${item.strength} / ${item.reason}`))}</div>
            <div class="analysis-block review-mini-panel"><h4>禁止动作</h4>${listHtml(nextDay.forbidden_actions || [])}</div>
          </div>
          <div class="analysis-block review-section-card embedded-card"><h3>自选股动作清单</h3>${reviewPlanActionTable(nextDay.watch_actions || [])}</div>
          <div class="analysis-block review-section-card embedded-card"><h3>新增候选与资金证据</h3>${reviewPlanCandidateTable(nextDay.candidate_actions || [])}</div>
        </div>
      </div>
      <aside class="review-side">
        <div class="analysis-block review-section-card"><h3>主线与风险</h3>${listHtml([...(market.next_focus || []), ...(market.risk_alerts || [])])}</div>
        <div class="analysis-block review-section-card"><h3>强势板块</h3>${listHtml((market.strong_sectors || []).map(item => `${item.name} ${item.change_pct > 0 ? '+' : ''}${Number(item.change_pct || 0).toFixed(2)}% / 强度 ${item.strength}`))}</div>
        <div class="analysis-block review-section-card"><h3>事件流</h3>${reviewNewsFeed(market.news_feed || [])}</div>
        <div class="analysis-block review-section-card"><h3>明早催化与验证</h3>${reviewCatalystFeed(nextDay.catalysts || [])}</div>
        <div class="analysis-block review-section-card"><h3>盘中关键窗口</h3>${reviewIntradayWindows(nextDay.intraday_windows || [])}</div>
        <div class="analysis-block review-section-card"><h3>开盘前检查表</h3>${listHtml(nextDay.prep_checklist || [])}</div>
      </aside>
    </div>
    <div class="analysis-block review-section-card"><h3>个股情报雷达</h3><p>按自选股归组查看公告催化与研报变化，优先盯有新增信息的标的。</p>${reviewIntelBoard(intelligence.by_stock || [])}</div>
    <div class="review-mini-columns">
      <div class="analysis-block review-section-card">
        <h3>公告催化</h3>
        ${reviewIntelList(intelligence.announcements || [], 'announcement')}
      </div>
      <div class="analysis-block review-section-card">
        <h3>研报跟踪</h3>
        ${reviewIntelList(intelligence.research_reports || [], 'research')}
      </div>
    </div>
    ${reviewHistorySummary(watchlist.history_summary || {})}
    <div class="analysis-block review-section-card"><h3>最近复盘</h3>${reviewHistoryList(history.latest || [])}</div>
  `;
}

async function loadDailyReview() {
  const body = $('#reviewCenterBody');
  if (body) body.innerHTML = '<div class="empty">正在读取复盘数据…</div>';
  try {
    const data = await apiJson('/api/review/daily');
    renderDailyReview(data);
  } catch (error) {
    if (body) body.innerHTML = `<div class="warning"><b>今日复盘暂时不可用</b><p>${escapeHtml(error.message || error)}</p><button type="button" data-retry-daily-review>重新加载</button></div>`;
    pushEvent(`复盘加载失败：${error.message || error}`);
  }
}

async function saveDailyReview() {
  const result = await apiJson('/api/review/daily/save', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})});
  pushEvent(result.ok ? `今日复盘已保存：${result.title}` : `复盘保存失败：${result.message || result.error}`);
  await loadDailyReviewHistory();
}

async function loadDailyReviewHistory() {
  const data = await apiJson('/api/review/history?limit=20');
  state.dailyReviewHistory = data.items || [];
  if (state.dailyReview) {
    renderDailyReview({...state.dailyReview, history: {count: state.dailyReviewHistory.length, latest: state.dailyReviewHistory.slice(0, 6)}});
    return;
  }
  $('#reviewCenterBody').innerHTML = `<div class="analysis-block"><h3>最近复盘</h3>${reviewHistoryList(state.dailyReviewHistory)}</div>`;
}

async function exportDailyReviewMarkdown() {
  const response = await fetch('/api/review/daily/export.md', { headers: authHeaders() });
  if (!response.ok) {
    pushEvent(`复盘导出失败：HTTP ${response.status}`);
    return;
  }
  const text = await response.text();
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${new Date().toISOString().slice(0, 10)}-复盘中心.md`;
  link.click();
  URL.revokeObjectURL(link.href);
  pushEvent('复盘 Markdown 已导出。');
}

function renderStrategyScan(data) {
  state.strategyScan = data;
  $('#strategyScan').innerHTML = `
    <div class="analysis-block">
      <h3>${data.engine}</h3>
      <p>${data.source_reference}</p>
      <p>计划任务：${data.schedule}</p>
      <p>数据计划：${data.data_plan.join(' / ')}</p>
    </div>
    <table>
      <thead><tr><th>股票</th><th>策略</th><th>动量</th><th>资金</th><th>均线</th><th>板块</th><th>总分</th><th>动作</th></tr></thead>
      <tbody>${data.rows.map(item => `<tr>
        <td>${item.name} ${item.code}</td>
        <td>${item.strategy}</td>
        <td>${item.momentum}</td>
        <td>${item.fund_score}</td>
        <td>${item.ma_score}</td>
        <td>${item.sector_strength}</td>
        <td>${item.total_score}</td>
        <td>${item.action}</td>
      </tr>`).join('')}</tbody>
    </table>
  `;
}

function pushEvent(text) {
  const line = document.createElement('div');
  line.className = 'event';
  line.textContent = `${new Date().toLocaleTimeString('zh-CN', { hour12: false })} · ${text}`;
  $('#eventStream').prepend(line);
  while ($('#eventStream').children.length > 8) $('#eventStream').lastElementChild.remove();
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
}

function listHtml(items) {
  if (!items || !items.length) return '<p>暂无</p>';
  return `<ul>${items.map(item => `<li>${escapeHtml(typeof item === 'string' ? item : JSON.stringify(item))}</li>`).join('')}</ul>`;
}

const AI_FIELD_LABELS = {
  metric: '指标', current: '本期', previous: '上期', change: '变化', period: '报告期', source: '来源', interpretation: '解读',
  name: '数据工具', status: '状态', freshness: '时点', note: '说明', title: '项目', value: '内容', conclusion: '结论', basis: '依据',
};

function structuredContentHtml(content) {
  if (content === null || content === undefined || content === '') return '<p class="data-missing">数据未返回/需核实</p>';
  if (!Array.isArray(content)) return `<p>${escapeHtml(typeof content === 'object' ? JSON.stringify(content) : content)}</p>`;
  if (!content.length) return '<p class="data-missing">数据未返回/需核实</p>';
  if (content.every(item => typeof item === 'string' || typeof item === 'number')) return listHtml(content);
  const rows = content.filter(item => item && typeof item === 'object');
  if (!rows.length) return listHtml(content);
  const preferred = ['metric', 'name', 'title', 'current', 'previous', 'change', 'value', 'period', 'status', 'source', 'freshness', 'interpretation', 'note', 'conclusion', 'basis'];
  const found = new Set(rows.flatMap(row => Object.keys(row)));
  const columns = preferred.filter(key => found.has(key)).slice(0, 8);
  if (!columns.length) return listHtml(content);
  return `<div class="ai-table-wrap"><table class="ai-report-table"><thead><tr>${columns.map(key => `<th>${escapeHtml(AI_FIELD_LABELS[key] || key)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${columns.map(key => `<td>${escapeHtml(Array.isArray(row[key]) ? row[key].join('；') : (row[key] ?? '-'))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function analysisSection(title, content, className = '') {
  return `<section class="analysis-block ${className}"><h3>${escapeHtml(title)}</h3>${structuredContentHtml(content)}</section>`;
}

async function copyAccessText(text, successLabel = '访问地址已复制到剪贴板。') {
  try {
    await navigator.clipboard.writeText(text);
    pushEvent(successLabel);
  } catch (error) {
    pushEvent('访问地址复制失败，请手动长按或复制。');
  }
}

function renderMobileDashboard(data) {
  state.mobileDashboard = data;
  $('#mobileDashboardUpdatedAt').textContent = `更新 ${data.updated_at || '-'}`;
  const status = data.data_state || {};
  const statusNode = $('#mobileDataState');
  statusNode.className = `mobile-data-state ${status.status === 'degraded' || status.stale ? 'warning' : ''}`.trim();
  statusNode.textContent = `${status.status === 'degraded' ? '数据已降级' : '数据正常'} · ${status.source || '未知来源'} · ${status.updated_at || data.updated_at || '-'}`;

  const access = data.access || {};
  $('#mobileAccessContent').innerHTML = `
    <div class="mobile-access-line">
      <span>同 Wi‑Fi 手机</span>
      <code>${escapeHtml(access.lan_url || '暂未识别局域网地址')}</code>
      ${access.lan_url ? `<button type="button" data-copy-access="${escapeHtml(access.lan_url)}">复制</button>` : ''}
    </div>
    <div class="mobile-access-line">
      <span>本机浏览器</span>
      <code>${escapeHtml(access.local_url || `${location.origin}/?v=desktop`)}</code>
      <button type="button" data-copy-access="${escapeHtml(access.local_url || `${location.origin}/?v=desktop`)}">复制</button>
    </div>
    <small>${escapeHtml(access.hint || '建议手机和电脑接入同一局域网。')}</small>
  `;

  const mood = data.market_mood || {};
  $('#mobileMarketMoodContent').innerHTML = `
    <b>${escapeHtml(mood.state || '-')}</b>
    <span>${escapeHtml(mood.summary || '-')}</span>
    <small>上涨 ${escapeHtml(mood.up_count ?? '-')} / 下跌 ${escapeHtml(mood.down_count ?? '-')} · 成交额 ${escapeHtml(mood.turnover_billion ?? '-')} 亿</small>
  `;

  const portfolio = data.portfolio_summary || {};
  $('#mobilePortfolioContent').innerHTML = `
    <b>${Number(portfolio.total_daily_pnl || 0).toFixed(2)}</b>
    <span>今日盈亏 · 总资产 ${Number(portfolio.total_assets || 0).toFixed(2)}</span>
    <small>持仓 ${escapeHtml(portfolio.position_count ?? 0)} 只 · 可用资金 ${Number(portfolio.cash_available || 0).toFixed(2)}</small>
  `;

  const watchlist = data.watchlist_summary || {};
  $('#mobileWatchlistContent').innerHTML = `
    <b>${escapeHtml(watchlist.total ?? 0)} 只</b>
    <span>上涨 ${escapeHtml(watchlist.up_count ?? 0)} / 下跌 ${escapeHtml(watchlist.down_count ?? 0)}</span>
    <small>${(watchlist.leaders || []).slice(0, 2).map(item => `${item.name} ${fmtPct(item.change_pct || 0)}`).join(' · ') || '暂无领涨自选'}</small>
  `;

  const reco = (data.ai_recommendations || []).slice(0, 2);
  $('#mobileAiRecoContent').innerHTML = reco.length
    ? `${reco.map(item => `<div><span class="mobile-card-pill">${escapeHtml(item.action || '观察')}</span><small>${escapeHtml(item.name || item.code || '')} · ${escapeHtml(item.reason || '')}</small></div>`).join('')}`
    : '<p>暂无 AI 推荐摘要</p>';

  const actions = (data.trade_actions || []).slice(0, 2);
  $('#mobileTradeActionContent').innerHTML = actions.length
    ? `${actions.map(item => `<div><span class="mobile-card-pill">${escapeHtml(item.label || item.action || '动作')}</span><small>${escapeHtml(item.name || item.code || '')} · ${escapeHtml(item.reason || '')}</small></div>`).join('')}`
    : '<p>暂无待确认动作</p>';

  const risks = (data.risk_alerts || []).slice(0, 3);
  $('#mobileRiskAlertContent').innerHTML = risks.length
    ? `<ul>${risks.map(item => `<li>${escapeHtml(item.title || '')} · ${escapeHtml(item.detail || '')}</li>`).join('')}</ul>`
    : '<p>暂无新增风险提示</p>';

  const sourceCard = data.data_source_card || {};
  const sourceLight = sourceCard.level ? { level: sourceCard.level, label: sourceCard.label || '' } : sourceTrafficLight(sourceCard.source || status.source || '', [], status.stale, status.fallback_used);
  const sourceTarget = $('#mobileDataSourceContent');
  if (sourceTarget) {
    sourceTarget.innerHTML = `
      <b><span class="source-dot ${escapeHtml(sourceLight.level)}"></span>${escapeHtml(sourceLight.label || '数据源')}</b>
      <span>${escapeHtml(sourceCard.source || status.source || '-')}</span>
      <small>${escapeHtml(sourceCard.detail || '关键模块会继续标注真实/降级/不可用状态。')}</small>
    `;
  }

  renderQuantControl(data.quant_control || {});

  $('#mobileQuickLinks').innerHTML = (data.quick_links || []).map(item => `
    <button type="button" data-mobile-jump="${escapeHtml(item.key)}">${escapeHtml(item.label)}</button>
  `).join('');
}

function renderMorningBriefing(data = {}) {
  const target = $('#morningBriefing');
  if (!target) return;
  const tone = data.level === 'warning' ? 'warning' : data.level === 'watch' ? 'watch' : 'neutral';
  const indices = (data.external_indices || []).map(item => `${escapeHtml(item.name)} ${fmtPct(item.change_pct || 0)}`).join(' · ') || '暂无外盘指数数据';
  target.innerHTML = `<div class="morning-briefing-card ${tone}">
    <div><span class="eyebrow">早盘风险简报</span><strong>${escapeHtml(data.stance || '等待数据')}</strong><small>${escapeHtml(data.auction_window || '')}</small></div>
    <div class="morning-briefing-indices">${indices}<br><small>外盘综合 ${escapeHtml(data.external_score ?? '-')} · A股情绪 ${escapeHtml(data.a_share_mood || '-')}</small></div>
    <p>${escapeHtml(data.source_note || '')}</p>
  </div>`;
}

async function loadMobileDashboard() {
  const data = await apiJson('/api/mobile/dashboard');
  renderMobileDashboard(data);
  return data;
}

function renderDashboardBootstrap(data) {
  if (!data) return;
  if (data.unified_gate) state.unifiedGate = data.unified_gate;
  if (data.market) renderMarket(data.market);
  if (data.morning_briefing) renderMorningBriefing(data.morning_briefing);
  if (data.portfolio) renderPortfolio(data.portfolio);
  if (data.watchlist) renderWatchlistV2(data.watchlist);
  if (data.ai_recommendations) renderAiRecommendations(data.ai_recommendations);
  if (data.data_sources) {
    const light = sourceTrafficLight(data.data_sources.source || '', data.data_sources.warnings || [], false, data.data_sources.level === 'yellow');
    const banner = $('#dataQualityBanner');
    if (banner) {
      const gate = data.unified_gate || {};
      banner.dataset.unifiedGate = gate.allowed ? 'ready' : 'blocked';
      delete banner.dataset.unifiedGateBadge;
      setTimeout(() => {
        if (banner.dataset.unifiedGateBadge === '1') return;
        banner.insertAdjacentHTML('beforeend', ` <span class="source-badge ${gate.allowed ? 'green' : 'red'}">统一闸门：${gate.allowed ? '人工确认' : '仅观察/减仓'}</span>`);
        banner.dataset.unifiedGateBadge = '1';
      }, 0);
      banner.className = `warning source-health-${data.data_sources.level || light.level}`;
      banner.innerHTML = `<b>数据源：</b><span class="source-badge ${escapeHtml(data.data_sources.level || light.level)}">${escapeHtml(data.data_sources.label || light.label)}</span> ${escapeHtml(data.data_sources.source || '-')}`;
    }
  }
  if (data.membership && state.membershipPlans) {
    renderMembershipPlans({ ...state.membershipPlans, current: data.membership });
  }
}

async function loadDashboardBootstrap() {
  const data = await apiJson('/api/dashboard/bootstrap');
  renderDashboardBootstrap(data);
  return data;
}

async function loadDeferredDashboardData() {
  return loadAll();
}

const STRATEGY_WORKFLOW_STAGES = [
  {
    key: 'translate',
    title: '1. 想法翻译',
    summary: '把模糊盘感改写成可回测、可执行的客观规则。',
    bullets: ['先定大盘环境', '再定选股条件', '明确买卖点', '补齐止损和仓位'],
    prompt: `你是一名严谨的A股量化研究助手。请把下面的主观交易想法，翻译成可以编程和回测的客观规则。

请分别给出：
1. 大盘环境过滤条件；
2. 股票筛选条件；
3. 买入条件；
4. 卖出条件；
5. 止损规则；
6. 仓位管理规则；
7. 最大持仓数量；
8. 需要避免的未来函数和数据偏差；
9. 适合验证策略的回测周期；
10. 建议测试的参数区间，而不是单一最优参数。

要求所有条件尽量使用明确数字表达，不要使用“明显上涨”“适当回调”这种模糊描述。`,
  },
  {
    key: 'audit',
    title: '2. 漏洞审计',
    summary: '先挑毛病再回测，优先处理未来函数、过拟合和成交可实现性。',
    bullets: ['检查未来数据', '检查幸存者偏差', '补手续费滑点', '评估极端行情失效点'],
    prompt: `请站在风险控制和量化研究的角度，审计下面这套策略，不要追求更高收益率，优先找出它为什么可能在实盘失效。

请重点检查：
1. 是否使用了未来数据；
2. 是否存在幸存者偏差；
3. 是否忽略停牌、涨跌停和无法成交的问题；
4. 是否考虑手续费、印花税和滑点；
5. 是否只适合某一种市场环境；
6. 是否参数过多、存在过度拟合；
7. 是否交易过于频繁；
8. 极端行情下最大风险是什么；
9. 哪些回测结果可能很好看，但不具备可复制性；
10. 如何用最少修改提高稳健性。`,
  },
  {
    key: 'review',
    title: '3. 回测复盘',
    summary: '别只盯收益率，要看回撤、夏普、盈亏比、交易样本和年份分布。',
    bullets: ['收益不是唯一目标', '先看最大回撤', '胜率要配合盈亏比', '拆开不同年份看表现'],
    prompt: `下面是我的量化策略回测结果，请从稳健性角度分析，不要帮我追求更高收益率。

请重点判断：
1. 收益是否过度依赖少数几笔交易；
2. 最大回撤是否超出普通投资者可承受范围；
3. 胜率与盈亏比是否匹配；
4. 交易次数是否具有统计意义；
5. 不同年份和不同市场环境下是否稳定；
6. 是否存在参数敏感问题；
7. 加入更高的手续费和滑点后是否仍然有效；
8. 如果收益率下降30%，这套策略是否仍值得继续研究；
9. 哪些修改可以降低回撤，但不会明显增加复杂度；
10. 下一步应该如何做样本外测试、滚动测试和模拟盘验证。`,
  },
  {
    key: 'live',
    title: '4. 实盘前四关',
    summary: '回测漂亮也不能直接上实盘，必须过样本外、滚动、模拟盘、小资金验证。',
    bullets: ['样本外测试', '滚动测试', '模拟盘检查成交与异常', '小资金先验证执行纪律'],
    prompt: `请把下面这套已完成回测的策略，拆成“实盘前四关”的验证清单：

第一关：样本外测试；
第二关：滚动测试；
第三关：模拟盘；
第四关：小资金验证。

请逐关给出：
1. 要验证的目标；
2. 关键观察指标；
3. 常见失败信号；
4. 通过标准；
5. 进入下一关前必须补齐的动作。

要求强调执行纪律、成交偏差、滑点、流动性和异常行情处理，不要直接给出‘可以重仓实盘’结论。`,
  },
];

const STRATEGY_FRAMEWORK_TEMPLATE = {
  title: '新手研究模板：趋势过滤 + 回调买入 + 固定风控',
  cards: [
    { label: '市场环境', items: ['指数收盘价位于120日均线之上才允许开仓', '指数跌破120日均线时降低仓位或暂停新增'] },
    { label: '股票筛选', items: ['股价位于60日均线之上', '20日均线高于60日均线', '近20日成交额满足流动性要求'] },
    { label: '买入条件', items: ['从20日高点回撤5%至10%', '回调期间缩量', '重新站上5日均线后次日执行'] },
    { label: '卖出条件', items: ['跌破10日均线', '触发预设止损', '持有若干天仍未继续上涨'] },
    { label: '仓位控制', items: ['单只股票不超过总资金10%至20%', '同时持有5至10只', '单笔亏损占总资金比例固定'] },
  ],
};

function strategyStageCardsHtml() {
  return `<div class="grid two">${STRATEGY_WORKFLOW_STAGES.map(stage => `
    <div class="health-card strategy-stage-card">
      <h3>${stage.title}</h3>
      <p>${stage.summary}</p>
      <ul>${stage.bullets.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
      <div class="screener-action-cell">
        <button type="button" data-strategy-prompt="${stage.key}">复制提示词</button>
      </div>
    </div>
  `).join('')}</div>`;
}

function strategyFrameworkHtml() {
  return `
    <div class="analysis-block">
      <h3>${STRATEGY_FRAMEWORK_TEMPLATE.title}</h3>
      <div class="grid two">
        ${STRATEGY_FRAMEWORK_TEMPLATE.cards.map(card => `
          <div class="health-card">
            <b>${card.label}</b>
            <ul>${card.items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function strategyWorkflowCenterHtml() {
  return `
    <div class="section-head">
      <div>
        <h2>策略落地中心</h2>
        <p>把文章里的思路拆成 4 个固定阶段，减少拍脑袋、方便你每天照着执行。</p>
      </div>
    </div>
    ${strategyStageCardsHtml()}
    <div class="grid two">
      <div class="analysis-block">
        <h3>回测时先盯这 5 个指标</h3>
        <ul>
          <li>最大回撤：先确认心理和资金能不能扛住。</li>
          <li>夏普比率：比较单位风险下的收益效率。</li>
          <li>盈亏比：不能只看胜率。</li>
          <li>交易次数：样本太少时结果不可靠。</li>
          <li>分年份表现：确认上涨、震荡、下跌阶段是否都能解释。</li>
        </ul>
      </div>
      <div class="analysis-block">
        <h3>别直接上实盘</h3>
        <ul>
          <li>先做样本外测试，别拿全历史数据调参。</li>
          <li>再做滚动测试，确认不是只适合某一段行情。</li>
          <li>再跑模拟盘，检查信号、成交价和异常行情处理。</li>
          <li>最后用小资金验证执行纪律，再考虑放大。</li>
        </ul>
      </div>
    </div>
    ${strategyFrameworkHtml()}
  `;
}

function ensureStrategyWorkflowCenter() {
  if (document.getElementById('strategyWorkflowCenter')) return;
  const systemAudit = document.getElementById('systemAudit');
  if (!systemAudit) return;
  const wrapper = document.createElement('div');
  wrapper.id = 'strategyWorkflowCenter';
  wrapper.className = 'strategy-workflow-center';
  wrapper.innerHTML = strategyWorkflowCenterHtml();
  const heading = Array.from(document.querySelectorAll('#research h2')).find(node => node.textContent.includes('交易系统'));
  if (heading) heading.parentNode.insertBefore(wrapper, heading);
  else systemAudit.parentNode.insertBefore(wrapper, systemAudit);
}

function copyStrategyPrompt(stageKey) {
  const stage = STRATEGY_WORKFLOW_STAGES.find(item => item.key === stageKey);
  if (!stage) return;
  navigator.clipboard.writeText(stage.prompt).then(() => {
    pushEvent(`${stage.title} 提示词已复制，可直接拿去喂给 AI。`);
  }).catch(() => {
    pushEvent('提示词复制失败，请手动重试。');
  });
}

function aiWorkflowFollowupHtml() {
  return `
    <div class="analysis-block">
      <h3>分析之后怎么落地</h3>
      <div class="grid two">
        ${STRATEGY_WORKFLOW_STAGES.map(stage => `
          <div class="health-card">
            <b>${stage.title}</b>
            <p>${stage.summary}</p>
            <ul>${stage.bullets.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>
            <div class="screener-action-cell">
              <button type="button" data-strategy-prompt="${stage.key}">复制这一步提示词</button>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderAiAnalysis(title, result, targetSelector = '#aiModalBody', openDefaultModal = true) {
  const rec = result.action_recommendation || {};
  const actionKey = ['BUY', 'HOLD', 'REDUCE', 'SELL', 'WATCH'].includes(String(rec.action || '').toUpperCase()) ? String(rec.action).toLowerCase() : 'watch';
  const actionClass = `action-${actionKey}`;
  const modeLabel = AI_ANALYSIS_MODE_LABELS[result.analysis_mode] || result.analysis_mode || '机构决策报告';
  const score = result.decision_score || {};
  const trendView = result.trend_view || {};
  const reportSections = (result.report_sections || []).map(section => `
    <div class="analysis-block">
      <h3>${escapeHtml(section.title)}</h3>
      ${listHtml(section.items)}
    </div>
  `).join('');
  const assistantRole = result.assistant_role || {};
  const pitfallChecks = result.pitfall_checks || [];
  const roleBoard = assistantRole.title ? `
    <div class="analysis-block ai-role-board">
      <h3>${escapeHtml(assistantRole.title)}</h3>
      <p>${escapeHtml(assistantRole.summary || '')}</p>
      <p><small>${escapeHtml(assistantRole.boundary || '')}</small></p>
    </div>
  ` : '';
  const pitfallBoard = pitfallChecks.length ? `
    <div class="analysis-block pitfall-board">
      <h3>??4?</h3>
      <div class="grid two">
        ${pitfallChecks.map(item => `<div class="health-card"><b>${escapeHtml(item.question || '-')}</b><p>${escapeHtml(item.verdict || '-')}</p><small>${escapeHtml(item.note || '')}</small></div>`).join('')}
      </div>
    </div>
  ` : '';
  const decisionBoard = Object.keys(score).length ? `
    <div class="ai-decision-grid">
      <div class="ai-score-card"><span>总分</span><b>${escapeHtml(score.overall ?? '-')}</b></div>
      <div class="ai-score-card"><span>基本面</span><b>${escapeHtml(score.fundamentals ?? '-')}</b></div>
      <div class="ai-score-card"><span>技术面</span><b>${escapeHtml(score.technicals ?? '-')}</b></div>
      <div class="ai-score-card"><span>资金面</span><b>${escapeHtml(score.flow ?? '-')}</b></div>
      <div class="ai-score-card risk"><span>风险暴露</span><b>${escapeHtml(score.risk_exposure ?? '-')}</b></div>
    </div>
  ` : '';
  const trendBoard = Object.keys(trendView).length ? `
    <div class="analysis-block">
      <h3>趋势视图</h3>
      <div class="ai-trend-grid">
        <div><span>方向</span><b>${escapeHtml(trendView.bias || '-')}</b></div>
        <div><span>阶段</span><b>${escapeHtml(trendView.stage || '-')}</b></div>
        <div><span>支撑</span><b>${escapeHtml(trendView.support || '-')}</b></div>
        <div><span>压力</span><b>${escapeHtml(trendView.resistance || '-')}</b></div>
      </div>
    </div>
  ` : '';
  const comprehensiveSections = [
    ['🏢 公司概况', result.company_overview],
    ['📊 核心财务数据与质量', result.financial_analysis],
    ['🧭 业务结构与增长逻辑', result.business_analysis],
    ['🧪 技术优势与产能进展', result.technology_capacity],
    ['📈 股价趋势与估值', result.valuation_price],
    ['👥 股东户数与筹码结构', result.holder_chips],
    ['📝 研报共识与盈利预期', result.research_consensus],
  ].filter(([, content]) => Array.isArray(content) ? content.length : Boolean(content)).map(([sectionTitle, content]) => analysisSection(sectionTitle, content)).join('');
  const audit = result.data_audit ? analysisSection('🔎 本次数据调用与完整性', result.data_audit, 'data-audit-block') : '';
  if (openDefaultModal) $('#aiModalTitle').textContent = title;
  $(targetSelector).innerHTML = result.error
    ? `<div class="analysis-block"><h3>AI 分析未完成</h3><p>${escapeHtml(result.message || result.error)}</p></div>`
    : `
      <div class="ai-report-meta"><span>${escapeHtml(result.provider || '-')}</span><span>${escapeHtml(result.model || '-')}</span><span>报告 #${escapeHtml(result.report_id || '未保存')}</span></div>
      <div class="ai-report-meta"><span>策略模式：${escapeHtml(modeLabel)}</span><span>动作：${escapeHtml(rec.action || result.action_level || '-')}</span></div>
      ${audit}
      <div class="analysis-block report-summary"><h3>${escapeHtml(result.report_title || 'AI 综合分析结论')}</h3><p>${escapeHtml(result.summary || '')}</p></div>
      ${decisionBoard}
      ${trendBoard}
      ${comprehensiveSections}
      ${analysisSection('✅ 核心优势', result.core_strengths || [])}
      ${analysisSection('⚠️ 需要关注', result.watch_items || [])}
      ${result.catalyst_watch ? analysisSection('🚀 催化观察', result.catalyst_watch) : ''}
      <div class="action-box">
        <h3>📌 操作建议</h3>
        <p><strong class="${actionClass}">${escapeHtml(rec.action || result.action_level || '-')}</strong> 置信度：${escapeHtml(rec.confidence || '-')} / 100</p>
        <p>仓位建议：${escapeHtml(rec.position_advice || '-')}</p>
        <p>买入区：${escapeHtml(rec.buy_zone || '-')}</p>
        <p>减仓/卖出区：${escapeHtml(rec.reduce_zone || '-')}</p>
        <p>止损/失效：${escapeHtml(rec.stop_loss || result.invalidation || '-')}</p>
        <p>下一触发：${escapeHtml(rec.next_trigger || '-')}</p>
        ${rec.rationale ? `<p>建议依据：${escapeHtml(rec.rationale)}</p>` : ''}
      </div>
      ${reportSections}
      <div class="analysis-block"><h3>证据</h3>${listHtml(result.evidence)}</div>
      <div class="analysis-block"><h3>风险</h3>${listHtml(result.risks)}</div>
      <div class="analysis-block"><h3>观察条件</h3>${listHtml(result.watch_conditions)}</div>
      ${result.execution_checklist ? analysisSection('🧭 执行清单', result.execution_checklist) : ''}
      ${aiWorkflowFollowupHtml()}
      <div class="analysis-block"><h3>失效条件</h3><p>${escapeHtml(result.invalidation || '')}</p></div>
      ${result.source_notes ? analysisSection('数据来源与口径', result.source_notes) : ''}
      <div class="analysis-block"><h3>提示</h3><p>${escapeHtml(rec.disclaimer || '以上为系统辅助建议，请人工确认后再行动。')}</p></div>
    `;
  if (openDefaultModal) $('#aiModal').classList.add('open');
}

function seededValue(seed, index) {
  let value = 0;
  const text = `${seed}-${index}`;
  for (let i = 0; i < text.length; i += 1) value = (value * 31 + text.charCodeAt(i)) % 9973;
  return (value % 1000) / 1000;
}

function buildChartSeries(item, mode) {
  const stock = item.stock;
  const count = mode === 'minute' ? 120 : 70;
  const current = Number(stock.price || 1);
  const prev = current / (1 + Number(stock.change_pct || 0) / 100);
  const volatility = mode === 'minute' ? Math.max(0.006, Math.abs(stock.change_pct) / 100 / 2) : 0.035;
  const rows = [];
  for (let i = 0; i < count; i += 1) {
    const progress = i / Math.max(1, count - 1);
    const noise = (seededValue(stock.code, i) - 0.5) * volatility * prev;
    const wave = Math.sin(progress * Math.PI * (mode === 'minute' ? 2.6 : 5.2)) * volatility * prev * 0.45;
    const base = prev + (current - prev) * progress + noise + wave;
    const price = i === count - 1 ? current : Math.max(0.01, base);
    const volume = Math.max(1, Math.round((seededValue(stock.code, i + 300) * 0.8 + 0.25) * (item.quantity > 0 ? item.quantity * 35 : 1200)));
    const main = (seededValue(stock.code, i + 700) - 0.47) * volume * price * 0.8;
    rows.push({ price, volume, main });
  }
  return rows;
}

function drawLineChart(canvas, series, options = {}) {
  const ctx = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 760;
  const height = canvas.clientHeight || 320;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const pad = { left: 46, right: 18, top: 18, bottom: 44 };
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;
  const prices = series.map(row => row.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = Math.max(0.01, max - min);
  ctx.strokeStyle = '#e7ebf0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = pad.top + (chartH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = '#667085';
    ctx.font = '12px sans-serif';
    ctx.fillText((max - span * i / 4).toFixed(2), 6, y + 4);
  }
  ctx.strokeStyle = options.color || '#2563eb';
  ctx.lineWidth = 2;
  ctx.beginPath();
  series.forEach((row, index) => {
    const x = pad.left + chartW * index / Math.max(1, series.length - 1);
    const y = pad.top + chartH - (row.price - min) / span * chartH;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  if (options.volume) {
    const maxVol = Math.max(...series.map(row => row.volume), 1);
    series.forEach((row, index) => {
      const x = pad.left + chartW * index / Math.max(1, series.length - 1);
      const h = Math.max(2, row.volume / maxVol * 42);
      ctx.fillStyle = row.price >= series[Math.max(0, index - 1)].price ? 'rgba(220,38,38,.35)' : 'rgba(5,150,105,.35)';
      ctx.fillRect(x, height - pad.bottom + 6 + (42 - h), Math.max(2, chartW / series.length - 1), h);
    });
  }
  ctx.fillStyle = '#667085';
  ctx.font = '12px sans-serif';
  ctx.fillText(options.leftLabel || '', pad.left, height - 8);
  ctx.fillText(options.rightLabel || '', width - pad.right - 96, height - 8);
}

function drawFundChart(canvas, series) {
  const ctx = canvas.getContext('2d');
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 760;
  const height = canvas.clientHeight || 320;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const pad = { left: 46, right: 18, top: 18, bottom: 34 };
  const values = series.map(row => row.main);
  const maxAbs = Math.max(...values.map(value => Math.abs(value)), 1);
  const zeroY = pad.top + (height - pad.top - pad.bottom) / 2;
  ctx.strokeStyle = '#e7ebf0';
  ctx.beginPath();
  ctx.moveTo(pad.left, zeroY);
  ctx.lineTo(width - pad.right, zeroY);
  ctx.stroke();
  const barW = (width - pad.left - pad.right) / series.length;
  values.forEach((value, index) => {
    const h = Math.abs(value) / maxAbs * ((height - pad.top - pad.bottom) / 2 - 8);
    const x = pad.left + index * barW;
    ctx.fillStyle = value >= 0 ? 'rgba(220,38,38,.6)' : 'rgba(5,150,105,.62)';
    ctx.fillRect(x, value >= 0 ? zeroY - h : zeroY, Math.max(2, barW - 1), h);
  });
  ctx.fillStyle = '#667085';
  ctx.font = '12px sans-serif';
  ctx.fillText('主力净流入估算', pad.left, 14);
  ctx.fillText('公开行情代理指标，非真实Level-2暗盘数据', pad.left, height - 8);
}

function renderTechnicalFundAnalysis(data) {
  const periods = data.multi_periods || {};
  const quant = data.quant_watch || {};
  const fund = data.fund_trend || {};
  const sources = data.data_sources || [];
  return `
    <div class="analysis-block technical-fund-report">
      <div class="technical-fund-head">
        <div>
          <span class="eyebrow">K线资金分析</span>
          <h3>${escapeHtml(data.name || data.code || '')} · ${escapeHtml(data.stance || '分歧观察')}</h3>
          <p>${escapeHtml(data.disclaimer || '仅作盯盘参考，不构成投资建议。')}</p>
        </div>
        <div class="quant-risk-score"><span>量化嫌疑</span><b>${escapeHtml(quant.suspicion_score ?? '-')}</b><small>/100</small></div>
      </div>
      <div class="grid three">
        <div class="health-card">
          <h4>日K结构</h4>
          <p>${escapeHtml(periods['日K']?.interpretation || '-')}</p>
          <small>MA5 ${escapeHtml(periods['日K']?.ma5 ?? '-')} · MA20 ${escapeHtml(periods['日K']?.ma20 ?? '-')} · 趋势 ${escapeHtml(periods['日K']?.trend_score ?? '-')}</small>
        </div>
        <div class="health-card">
          <h4>资金趋势</h4>
          <p>${escapeHtml(fund.direction || periods['资金']?.interpretation || '-')}</p>
          <small>最新 ${escapeHtml(fund.latest_main ?? '-')} · 3日 ${escapeHtml(fund.recent_3_sum ?? '-')} · 10日 ${escapeHtml(fund.recent_10_sum ?? '-')}</small>
        </div>
        <div class="health-card">
          <h4>尾盘扰动</h4>
          <p>${quant.tail_dump_detected ? '检测到尾盘放量急跌' : '暂未检测到强尾盘砸盘'}</p>
          <small>尾盘跌幅 ${escapeHtml(quant.tail_drop_pct ?? '-')}% · 样本 ${escapeHtml(periods['分时']?.samples ?? '-')}</small>
        </div>
      </div>
      <div class="grid two">
        <div class="health-card">
          <h4>量化嫌疑证据</h4>
          ${listHtml(quant.evidence || [])}
        </div>
        <div class="health-card">
          <h4>操作纪律</h4>
          ${listHtml(data.action_points || [])}
        </div>
      </div>
      <div class="source-row">
        ${sources.map(item => `<span>${escapeHtml(item.name)}：${item.ok ? '可用' : '不可用'} · ${escapeHtml(item.source || '-')} · ${escapeHtml(item.count ?? 0)}条</span>`).join('')}
      </div>
    </div>
  `;
}

function renderThreeSourceProfile(data) {
  const east = data.eastmoney || {};
  const xueqiu = data.xueqiu || {};
  const tdx = data.tongdaxin || {};
  const indicators = tdx.indicators || {};
  const sourceCards = (data.sources || []).map(item => `
    <div class="health-card">
      <h4>${escapeHtml(item.name)} <small>${escapeHtml(item.status)}</small></h4>
      <p>${escapeHtml(item.role || '')}</p>
      <small>${(item.used_for || []).map(escapeHtml).join(' / ')}</small>
    </div>
  `).join('');
  return `
    <div class="analysis-block">
      <div class="quant-control-head">
        <div>
          <span class="eyebrow">三源数据融合</span>
          <h3>${escapeHtml(data.name)} ${escapeHtml(data.code)}</h3>
          <p>${escapeHtml(data.fusion?.usage || '东方财富定事实，通达信定技术，雪球定情绪。')}</p>
        </div>
      </div>
      <div class="grid three">${sourceCards}</div>
      <div class="grid three">
        <div class="health-card">
          <h4>东方财富：行情/资金</h4>
          <p><b>${escapeHtml(east.quote?.price ?? '-')}</b> · ${escapeHtml(east.quote?.change_pct ?? '-')}%</p>
          <small>资金流：${escapeHtml(east.fund_flow?.latest_main_net_wan ?? '-')} 万｜${escapeHtml(east.quote?.source || '-')}</small>
        </div>
        <div class="health-card">
          <h4>雪球：社区情绪</h4>
          <p>${escapeHtml(xueqiu.status || '-')} · ${escapeHtml(xueqiu.symbol || '-')}</p>
          <small>${escapeHtml(xueqiu.note || '')}</small>
          ${xueqiu.deep_link ? `<p><a href="${escapeHtml(xueqiu.deep_link)}" target="_blank" rel="noopener">打开雪球个股页</a></p>` : ''}
        </div>
        <div class="health-card">
          <h4>通达信：技术/公式</h4>
          <p>MA5 ${escapeHtml(indicators.ma5 ?? '-')} · MA20 ${escapeHtml(indicators.ma20 ?? '-')} · 量比 ${escapeHtml(indicators.volume_ratio ?? '-')}</p>
          <small>${(tdx.formula_signals || []).map(escapeHtml).join(' / ')}</small>
        </div>
      </div>
      <div class="analysis-block note">
        <b>融合原则</b>
        <p>${escapeHtml(data.fusion?.risk_note || '社区观点只做交叉验证，不直接作为买卖依据。')}</p>
      </div>
    </div>
  `;
}

function renderCapitalEvents(data) {
  const sectionOrder = ['dragon_tiger', 'restricted_release', 'margin_trading', 'block_trade', 'holder_change'];
  const sections = data.sections || {};
  const cards = sectionOrder.map(key => sections[key]).filter(Boolean).map(section => {
    const items = (section.items || []).slice(0, 6);
    return `
      <div class="health-card">
        <h4>${escapeHtml(section.name || section.key)} <small>${section.ok ? '已接入' : '暂无返回'}</small></h4>
        <p>${escapeHtml(section.source || '-')} · ${escapeHtml(section.count ?? items.length)} 条</p>
        ${items.length ? `<div class="intel-list compact">${items.map(entry => {
          const raw = entry.raw || {};
          const highlights = Object.entries(raw)
            .filter(([field, value]) => value !== null && value !== undefined && value !== '' && !String(field).includes('CODE'))
            .slice(0, 4)
            .map(([field, value]) => `${field}:${value}`)
            .join(' ｜ ');
          return `<div class="intel-row"><b>${escapeHtml(entry.title || section.name || '-')}</b><span>${escapeHtml(entry.date || '')} ${escapeHtml(highlights)}</span></div>`;
        }).join('')}</div>` : `<small>${escapeHtml(section.error || '接口暂无数据，后续可用公告、资金流和K线交叉验证。')}</small>`}
      </div>
    `;
  }).join('');
  return `
    <div class="analysis-block">
      <div class="quant-control-head">
        <div>
          <span class="eyebrow">资金事件雷达</span>
          <h3>${escapeHtml(data.name || '')} ${escapeHtml(data.code || '')}</h3>
          <p>聚合龙虎榜席位、限售解禁、融资融券、大宗交易、股东户数变化；用于识别机构席位、杠杆变化、筹码变化和潜在量化扰动。</p>
        </div>
        <span class="tag ${data.ok ? 'green' : 'amber'}">${data.ok ? '有数据' : '待刷新'}</span>
      </div>
      <div class="grid two">${cards || `<div class="empty">${escapeHtml(data.message || '暂未返回资金事件数据。')}</div>`}</div>
      <div class="analysis-block note">
        <b>使用原则</b>
        <p>资金事件只做交易前复核和风险提示，不直接自动下单；龙虎榜和大宗交易看机构行为，解禁和股东户数看筹码压力，融资融券看杠杆情绪。</p>
      </div>
    </div>
  `;
}

function renderResonancePanel(data, code) {
  const categories = data.categories || {};
  const labels = { trend: '趋势', momentum: '动量', oscillation: '震荡', strength: '强度' };
  const signals = data.signals || [];
  const enabledCount = Object.values(data.config?.enabled || {}).filter(Boolean).length;
  return `
    <div class="analysis-block resonance-panel" data-resonance-code="${escapeHtml(code)}">
      <div class="quant-control-head">
        <div>
          <span class="eyebrow">指标共振 · 量化雷达</span>
          <h3>${escapeHtml(data.stance || 'mixed')} · ${escapeHtml(data.overall_score ?? '-')} / 100</h3>
          <p>${escapeHtml(data.risk_gate?.reason || '趋势、动量、震荡与强度综合评分')}</p>
        </div>
        <button type="button" class="secondary" data-resonance-refresh="${escapeHtml(code)}">刷新</button>
      </div>
      <div class="grid four resonance-categories">
        ${Object.entries(labels).map(([key, label]) => {
          const item = categories[key] || {};
          return `<div class="health-card resonance-category"><h4>${label}</h4><strong>${escapeHtml(item.score ?? '-')}</strong><small>启用 ${escapeHtml(item.enabled ?? 0)} / ${escapeHtml(item.total ?? 0)}</small></div>`;
        }).join('')}
      </div>
      <div class="resonance-indicators">
        ${signals.map(item => `<button type="button" class="tag ${item.enabled ? 'green active' : 'muted'}" data-resonance-indicator="${escapeHtml(item.key)}" title="${escapeHtml(item.reason || '')}">${escapeHtml(item.label || item.key)} ${escapeHtml(item.score ?? '-')}</button>`).join('')}
      </div>
      <small class="muted">已启用 ${enabledCount} 项 · 资金流与量化风险仅作为门控条件 · 仅作研究和模拟复核</small>
    </div>`;
}

async function loadResonancePanel(code, disabled = '') {
  const query = disabled ? `?disabled=${encodeURIComponent(disabled)}` : '';
  const data = await apiJson(`/api/stocks/${encodeURIComponent(code)}/resonance${query}`);
  const host = $('#resonancePanelHost');
  if (host) host.innerHTML = renderResonancePanel(data, code);
  return data;
}

function renderTStrategyPanel(data) {
  const levels = data.levels || {};
  const gate = data.enterprise_gate || {};
  const suitability = data.suitability || '观察';
  const tone = suitability === '适合做T' ? 'green' : suitability === '不适合做T' ? 'red' : 'amber';
  return `
    <div class="analysis-block t-strategy-panel">
      <div class="quant-control-head">
        <div><span class="eyebrow">做T模型 · 企业先行</span><h3>${escapeHtml(data.name || '')} · ${escapeHtml(suitability)}</h3><p>机会评分 ${escapeHtml(data.opportunity_score ?? '-')} / 100 · ${escapeHtml(data.metrics?.spread_pct ?? 0)}% 日内振幅区间</p></div>
        <span class="tag ${tone}">${gate.passed ? '企业门槛通过' : '企业门槛未通过'}</span>
      </div>
      <div class="t-strategy-levels"><span>当前 ${escapeHtml(levels.current ?? '-')}</span><span>支撑 ${escapeHtml(levels.support ?? '-')}</span><span>压力 ${escapeHtml(levels.resistance ?? '-')}</span><span>高点 ${escapeHtml(levels.high ?? '-')}</span><span>低点 ${escapeHtml(levels.low ?? '-')}</span></div>
      <div class="t-strategy-timeline">${(data.intraday_plan || []).map(item => `<div class="t-strategy-step"><b>${escapeHtml(item.time)}</b><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.action)}</span></div>`).join('')}</div>
      <div class="grid two"><div><h4>企业与风险判断</h4><ul>${(gate.reasons || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div><div><h4>模型原则</h4><ul>${(data.rationale || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div></div>
      <small class="muted">${escapeHtml(data.disclaimer || '')}</small>
    </div>`;
}

async function loadTStrategyPanel(code) {
  const data = await apiJson(`/api/stocks/${encodeURIComponent(code)}/t-strategy`);
  const host = $('#tStrategyPanelHost');
  if (host) host.innerHTML = renderTStrategyPanel(data);
  return data;
}

async function openStockTool(code, mode) {
  const item = findWatchItem(code);
  if (!item) return;
  const stock = item.stock;
  const titles = { minute: '分时走势', sources: '三源数据', capital: '资金事件', analysis: 'K线资金分析', kline: '日K结构', fund: '真实资金流', detail: '个股详情', announcements: '公司公告', research: '机构研报', backtest: '策略回测实验室' };
  $('#aiModalTitle').textContent = `${stock.name} ${titles[mode] || '详情'}`;
  $('#aiModal').classList.add('open');
  const held = item.quantity > 0;
  const summary = `
    <div class="stock-tool-summary">
      <div><label>现价</label><strong class="${trend(stock.change_pct)}">${stock.price.toFixed(2)}</strong><span class="${trend(stock.change_pct)}">${fmtPct(stock.change_pct)}</span></div>
      <div><label>${held ? '持仓/成本' : '状态'}</label><strong>${held ? `${item.quantity} 股` : '观察池'}</strong><span>${held ? `成本 ${Number(stock.cost || 0).toFixed(3)}` : '未录入持仓'}</span></div>
      <div><label>浮盈亏</label><strong class="${trend(item.pnl_amount)}">${held ? item.pnl_amount.toFixed(2) : '-'}</strong><span>${held ? fmtPct(item.pnl_pct) : '非自持'}</span></div>
      <div><label>报价源</label><strong>${sourceInfo(stock.source || '').label}</strong><span>${stock.code}</span></div>
    </div>
  `;
  if (mode === 'detail') {
    $('#aiModalBody').innerHTML = `
      ${summary}
      <div class="analysis-block">
        <h3>核心观察</h3>
        <p>${stock.ai || '等待模型计算。'}</p>
        <ul>
          <li>主题标签：${stock.tag || '-'}</li>
          <li>提醒价：${Number(stock.alert_price || 0).toFixed(2)}，涨跌提醒：${Number(stock.alert_pct || 0).toFixed(2)}%</li>
          <li>止盈：${Number(stock.take_profit || 0).toFixed(2)}，止损：${Number(stock.stop_loss || 0).toFixed(2)}</li>
        </ul>
      </div>
      <div class="tags compact">${(item.signals || []).map(signal => `<span class="tag ${signal.score >= 70 ? 'green' : signal.score < 50 ? 'red' : 'amber'}">${signal.name}:${signal.status}</span>`).join('')}</div>
    `;
    return;
  }
  if (mode === 'analysis') {
    $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>正在分析多周期K线、资金趋势和尾盘量化扰动...</h3></div>`;
    try {
      const data = await apiJson(`/api/stocks/${encodeURIComponent(code)}/technical-fund-analysis`);
      $('#aiModalBody').innerHTML = `${summary}${renderTechnicalFundAnalysis(data)}<div id="tStrategyPanelHost"><div class="empty">正在评估企业底线与做T机会…</div></div><div id="resonancePanelHost"><div class="empty">正在计算指标共振…</div></div>`;
      loadTStrategyPanel(code).catch(error => pushEvent(`做T策略读取失败：${error.message || error}`, 'warn'));
      loadResonancePanel(code).catch(error => pushEvent(`指标共振读取失败：${error.message || error}`, 'warn'));
    } catch (error) {
      $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>K线资金分析失败</h3><p>${escapeHtml(error.message || error)}</p></div>`;
    }
    return;
  }
  if (mode === 'sources') {
    $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>正在读取东方财富、雪球、通达信三源数据...</h3></div>`;
    try {
      const data = await apiJson(`/api/stocks/${encodeURIComponent(code)}/three-source-profile`);
      $('#aiModalBody').innerHTML = `${summary}${renderThreeSourceProfile(data)}`;
    } catch (error) {
      $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>三源数据读取失败</h3><p>${escapeHtml(error.message || error)}</p></div>`;
    }
    return;
  }
  if (mode === 'capital') {
    $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>正在读取龙虎榜、解禁、融资融券、大宗交易、股东户数...</h3></div>`;
    try {
      const data = await apiJson(`/api/stocks/${encodeURIComponent(code)}/capital-events?limit=12&window=today`);
      $('#aiModalBody').innerHTML = `${summary}${renderCapitalEvents(data)}`;
    } catch (error) {
      $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>资金事件读取失败</h3><p>${escapeHtml(error.message || error)}</p></div>`;
    }
    return;
  }
  if (mode === 'announcements' || mode === 'research') {
    $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>正在读取${titles[mode]}...</h3></div>`;
    const endpoint = mode === 'announcements' ? 'announcements' : 'research-reports';
    const data = await apiJson(`/api/stocks/${encodeURIComponent(code)}/${endpoint}?limit=20`);
    $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>${titles[mode]} · ${escapeHtml(data.source || '-')}</h3>${(data.items || []).length ? `<div class="intel-list">${data.items.map(entry => `<a href="${escapeHtml(entry.url || '#')}" target="_blank" rel="noopener"><b>${escapeHtml(entry.title)}</b><span>${escapeHtml(entry.date || '')} ${escapeHtml(entry.institution || entry.type || '')} ${escapeHtml(entry.rating || '')}</span></a>`).join('')}</div>` : `<p>${escapeHtml(data.error || '暂未返回数据')}</p>`}</div>`;
    return;
  }
  if (mode === 'backtest') {
    $('#aiModalBody').innerHTML = `${summary}
      <form class="backtest-form" data-backtest-form data-code="${escapeHtml(code)}">
        <label><span>策略</span><select name="strategy"><option value="sma_cross">双均线交叉</option><option value="2060_recovery">2060 趋势修复</option></select></label>
        <label><span>短周期</span><input name="short_period" type="number" min="2" value="20"></label>
        <label><span>长周期</span><input name="long_period" type="number" min="3" value="60"></label>
        <label><span>初始资金</span><input name="initial_cash" type="number" min="1000" step="1000" value="100000"></label>
        <label><span>双边费用(bps)</span><input name="fee_bps" type="number" min="0" step="1" value="10"></label>
        <label><span>滑点(bps)</span><input name="slippage_bps" type="number" min="0" step="1" value="5"></label>
        <label class="backtest-check"><input name="parameter_scan" type="checkbox"><span>参数扫描（检查过拟合）</span></label>
        <button class="primary" type="submit">用真实历史行情开始回测</button>
      </form>
      <div class="backtest-warning">信号在收盘后确认，统一按下一交易日开盘成交；包含费用和滑点。回测仅用于证伪策略，不预测未来。</div>
      <div id="backtestResult"></div>`;
    return;
  }
  $('#aiModalBody').innerHTML = `${summary}<div class="chart-shell"><canvas id="stockToolCanvas"></canvas></div><div class="chart-note">正在读取真实行情数据...</div>`;
  let chart;
  try {
    chart = mode === 'fund'
      ? await apiJson(`/api/stocks/${encodeURIComponent(code)}/fund-flow?limit=40`).then(data => ({ ...data, is_real: data.ok, message: data.ok ? '真实个股资金流' : data.error, items: (data.items || []).map(row => ({ ...row, main: Number(row.main_net_wan || 0), price: Number(row.main_net_wan || 0), volume: Math.abs(Number(row.large_net_wan || 0)) })) }))
      : await fetch(`/api/stocks/${encodeURIComponent(code)}/chart?type=${encodeURIComponent(mode)}`).then(res => res.json());
  } catch (error) {
    $('#aiModalBody').innerHTML = `${summary}<div class="analysis-block"><h3>真实数据读取失败</h3><p>${error.message || error}</p></div>`;
    return;
  }
  if (!chart.is_real || !chart.items || !chart.items.length) {
    $('#aiModalBody').innerHTML = `${summary}${chartSourceBlock(chart)}<div class="analysis-block"><h3>真实数据暂不可用</h3><p>${chart.message || '行情源没有返回有效序列。'}</p><p>建议：确认该接口权限，或暂时只把该图作为观察，不参与买卖动作评分。</p></div>`;
    return;
  }
  $('.chart-note').innerHTML = `${chartSourceBlock(chart)}<span>更新时间：${chart.updated_at || '-'}</span>`;
  const canvas = $('#stockToolCanvas');
  if (mode === 'fund') drawFundChart(canvas, chart.items);
  else drawLineChart(canvas, chart.items, {
    volume: true,
    color: mode === 'kline' ? '#dc2626' : '#2563eb',
    leftLabel: chart.items[0]?.time || chart.items[0]?.date || '',
    rightLabel: chart.items[chart.items.length - 1]?.time || chart.items[chart.items.length - 1]?.date || '',
  });
}

function renderBacktestResult(result) {
  const target = $('#backtestResult');
  if (!target) return;
  if (result.error) {
    target.innerHTML = `<div class="analysis-block"><h3>回测未执行</h3><p>${escapeHtml(result.message || result.error)}</p></div>`;
    return;
  }
  if (result.results) {
    target.innerHTML = `<div class="analysis-block"><h3>参数扫描排名</h3><p>${escapeHtml(result.warning || '')}</p><table><thead><tr><th>短/长周期</th><th>收益</th><th>超额</th><th>回撤</th><th>夏普</th><th>交易数</th></tr></thead><tbody>${result.results.map(row => `<tr><td>${row.short_period}/${row.long_period}</td><td>${row.total_return_pct}%</td><td>${row.excess_return_pct}%</td><td>${row.max_drawdown_pct}%</td><td>${row.sharpe}</td><td>${row.trade_count}</td></tr>`).join('')}</tbody></table></div>`;
    return;
  }
  const m = result.metrics || {};
  const metricChecklist = [
    `最大回撤 ${m.max_drawdown_pct ?? '-'}%：先确认最差阶段你能不能扛住。`,
    `夏普比率 ${m.sharpe ?? '-'}：看承担单位风险后换来的收益效率。`,
    `胜率/交易次数 ${m.win_rate_pct ?? '-'}% / ${m.trade_count ?? '-'}：确认不是靠少数交易撑出来。`,
    `超额收益 ${m.excess_return_pct ?? '-'}%：和同期持有基准对比，不只看总收益。`,
    '继续把结果拆到不同年份和不同市场环境里复核。',
  ];
  const liveGates = [
    '样本外测试：留一段未参与调参的数据重新验证。',
    '滚动测试：窗口前移，确认不是只适合某一段历史行情。',
    '模拟盘：检查信号、成交价偏差、异常行情处理是否正常。',
    '小资金验证：先验证执行纪律，再决定是否放大仓位。',
  ];
  const robustnessChecks = [
    '不要只追求历史收益更高，先看回撤、样本量和可实现性。',
    '把手续费、滑点、涨跌停和流动性问题都算进去。',
    '优先测试参数区间稳定性，不要迷信某一个最优参数点。',
    '如果市场环境一变就失效，这套策略还不能直接上实盘。',
  ];
  target.innerHTML = `
    <div class="backtest-source">真实数据源：${escapeHtml(result.data_source || '-')} · ${escapeHtml(result.period?.start || '')} 至 ${escapeHtml(result.period?.end || '')} · ${result.period?.bars || 0} 根日K</div>
    <div class="backtest-metrics">
      <div><span>策略收益</span><b class="${trend(m.total_return_pct || 0)}">${m.total_return_pct}%</b></div>
      <div><span>同期持有</span><b>${m.benchmark_return_pct}%</b></div>
      <div><span>超额收益</span><b>${m.excess_return_pct}%</b></div>
      <div><span>最大回撤</span><b class="down">${m.max_drawdown_pct}%</b></div>
      <div><span>夏普</span><b>${m.sharpe}</b></div>
      <div><span>胜率 / 交易</span><b>${m.win_rate_pct}% / ${m.trade_count}</b></div>
    </div>
    <div class="grid two">
      <div class="analysis-block"><h3>稳健性先看什么</h3>${listHtml(metricChecklist)}</div>
      <div class="analysis-block"><h3>实盘前四关</h3>${listHtml(liveGates)}</div>
    </div>
    <div class="analysis-block"><h3>回测复盘提醒</h3>${listHtml(robustnessChecks)}</div>
    <div class="analysis-block"><h3>审计说明</h3>${listHtml([result.audit?.execution, result.audit?.cost_model, ...(result.audit?.known_limits || [])])}</div>
    <div class="analysis-block"><h3>交易记录</h3>${(result.trades || []).length ? `<table><thead><tr><th>买入</th><th>卖出</th><th>买入价</th><th>卖出价</th><th>收益</th></tr></thead><tbody>${result.trades.map(item => `<tr><td>${escapeHtml(item.entry_date)}</td><td>${escapeHtml(item.exit_date)}</td><td>${item.entry_price}</td><td>${item.exit_price}</td><td class="${trend(item.pnl)}">${item.return_pct}%</td></tr>`).join('')}</tbody></table>` : '<p>该参数在样本期内没有产生完整交易。</p>'}</div>`;
}

async function runBacktestForm(form) {
  const target = $('#backtestResult');
  target.innerHTML = '<div class="analysis-block"><h3>回测计算中</h3><p>正在读取真实历史日K并执行无未来函数的模拟撮合...</p></div>';
  const values = Object.fromEntries(new FormData(form).entries());
  const payload = {
    strategy: values.strategy,
    short_period: Number(values.short_period),
    long_period: Number(values.long_period),
    initial_cash: Number(values.initial_cash),
    fee_bps: Number(values.fee_bps),
    slippage_bps: Number(values.slippage_bps),
    parameter_scan: form.elements.parameter_scan.checked,
  };
  const result = await apiJson(`/api/research/backtest/${encodeURIComponent(form.dataset.code)}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  renderBacktestResult(result);
}

async function analyzeStock(code, name) {
  $('#aiWorkbenchTitle').textContent = `【${name}】AI 分析`;
  $('#aiWorkbenchCode').value = code;
  $('#aiAnalysisMode').value = 'decision_report';
  $('#aiWorkbenchResult').innerHTML = '<div class="ai-workbench-empty"><b>选择模型后开始分析</b><p>不会使用本地规则结果冒充 AI；未配置外部模型时会明确提示你先配置。</p></div>';
  $('#aiWorkbenchQuestion').value = `请结合${name}（${code}）的实时行情、公告、研报、资金流、持仓成本和量化信号，输出可执行的机构决策报告，给出评分、关键催化、主要风险、执行清单和后续操作计划。`;
  $('#aiQuestionCount').textContent = $('#aiWorkbenchQuestion').value.length;
  const models = await apiJson('/api/ai/models');
  const select = $('#aiWorkbenchModel');
  select.innerHTML = (models.items || []).length
    ? models.items.map(model => `<option value="${model.id}" ${model.id === models.active_profile_id ? 'selected' : ''}>${escapeHtml(model.name)} · ${escapeHtml(model.model)}</option>`).join('')
    : '<option value="">尚未配置外部 AI 模型</option>';
  $('#startAiAnalysis').disabled = !(models.items || []).length;
  $('#aiWorkbenchModal').classList.add('open');
}

const AI_SYSTEM_PROMPTS = {
  professional: '采用完整投研报告风格，均衡覆盖公司、财务、业务、技术与产能、估值、股东筹码、研报共识、资金公告、风险和操作建议。',
  risk: '采用风险控制风格，完整分析不减项，但优先识别回撤、流动性、公告、估值、业绩兑现和技术破位风险。',
  short: '采用交易复盘风格，完整分析不减项，但重点解释量价、主力资金、板块强度、关键价位和下一交易日触发条件。',
};

const AI_ANALYSIS_MODE_LABELS = {
  decision_report: '机构决策报告',
  trend_following: '趋势跟随',
  breakout_hunter: '突破捕手',
  rebound_repair: '超跌修复',
  risk_guard: '风险守门',
};

function selectedSystemPrompt() {
  const preset = $('#aiSystemPromptPreset').value;
  return preset === 'custom' ? $('#aiCustomSystemPrompt').value.trim() : AI_SYSTEM_PROMPTS[preset];
}

async function runAiWorkbench(event) {
  event.preventDefault();
  const code = $('#aiWorkbenchCode').value;
  const modelId = $('#aiWorkbenchModel').value;
  const analysisMode = $('#aiAnalysisMode').value || 'decision_report';
  const analysisModeLabel = AI_ANALYSIS_MODE_LABELS[analysisMode] || analysisMode;
  if (!modelId) return;
  const question = `${$('#aiWorkbenchQuestion').value.trim()}\n策略模式：${analysisModeLabel}\n分析重点：${$('#aiAnalysisFocus').selectedOptions[0].textContent}`;
  const button = $('#startAiAnalysis');
  button.disabled = true;
  button.textContent = '正在调用 AI...';
  $('#aiWorkbenchResult').innerHTML = '<div class="ai-workbench-empty"><b>AI 正在分析</b><p>正在汇总真实行情、公告、研报、资金流和量化证据，请稍候...</p></div>';
  try {
    const result = await apiJson(`/api/ai/analyze/${encodeURIComponent(code)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId, system_prompt: selectedSystemPrompt(), question, tools_enabled: $('#aiToolsEnabled').checked, analysis_mode: analysisMode }),
    });
    state.lastAiResult = result;
    renderAiAnalysis($('#aiWorkbenchTitle').textContent, result, '#aiWorkbenchResult', false);
    pushEvent(`${$('#aiWorkbenchTitle').textContent}已由 ${result.model || '外部模型'} 生成。`);
  } catch (error) {
    $('#aiWorkbenchResult').innerHTML = `<div class="analysis-block"><h3>分析失败</h3><p>${escapeHtml(error.message || '请检查模型配置和网络连接。')}</p></div>`;
  } finally {
    button.disabled = false;
    button.textContent = '开始 AI 分析';
  }
}

function aiResultMarkdown(result = state.lastAiResult) {
  if (!result || result.error) return '';
  const rec = result.action_recommendation || {};
  const mdContent = content => {
    if (!Array.isArray(content) || !content.length) return '- 数据未返回/需核实';
    if (content.every(item => typeof item !== 'object')) return content.map(item => `- ${item}`).join('\n');
    const rows = content.filter(item => item && typeof item === 'object');
    const columns = [...new Set(rows.flatMap(row => Object.keys(row)))].slice(0, 8);
    if (!columns.length) return '- 数据未返回/需核实';
    const clean = value => String(Array.isArray(value) ? value.join('；') : (value ?? '-')).replace(/\|/g, '\\|').replace(/\n/g, ' ');
    return `| ${columns.map(key => AI_FIELD_LABELS[key] || key).join(' | ')} |\n| ${columns.map(() => '---').join(' | ')} |\n${rows.map(row => `| ${columns.map(key => clean(row[key])).join(' | ')} |`).join('\n')}`;
  };
  const namedSections = [
    ['数据调用与完整性', result.data_audit], ['公司概况', result.company_overview], ['核心财务数据与质量', result.financial_analysis],
    ['业务结构与增长逻辑', result.business_analysis], ['技术优势与产能进展', result.technology_capacity], ['股价趋势与估值', result.valuation_price],
    ['股东户数与筹码结构', result.holder_chips], ['研报共识与盈利预期', result.research_consensus], ['核心优势', result.core_strengths],
    ['需要关注', result.watch_items], ['证据', result.evidence], ['风险', result.risks], ['观察条件', result.watch_conditions], ['数据来源与口径', result.source_notes],
  ].map(([heading, content]) => `## ${heading}\n\n${mdContent(content)}`).join('\n\n');
  const legacySections = (result.report_sections || []).map(section => `## ${section.title}\n\n${mdContent(section.items)}`).join('\n\n');
  return `# ${result.report_title || $('#aiWorkbenchTitle').textContent}\n\n- 模型：${result.provider || '-'} / ${result.model || '-'}\n- 动作：${rec.action || result.action_level || '-'}\n- 置信度：${rec.confidence || '-'}\n\n## 综合结论\n\n${result.summary || ''}\n\n${namedSections}\n\n${legacySections}\n\n## 操作建议\n\n- 仓位建议：${rec.position_advice || '-'}\n- 买入区：${rec.buy_zone || '-'}\n- 减仓/卖出区：${rec.reduce_zone || '-'}\n- 止损：${rec.stop_loss || '-'}\n- 下一触发：${rec.next_trigger || '-'}\n- 建议依据：${rec.rationale || '-'}\n\n## 失效条件\n\n${result.invalidation || ''}\n\n> ${rec.disclaimer || 'AI分析结果仅供参考，请以实际行情和正式披露为准。投资需谨慎，风险自担。'}\n`;
}

async function copyAiResult() {
  const text = aiResultMarkdown();
  if (!text) return;
  await navigator.clipboard.writeText(text);
  pushEvent('AI 分析结果已复制到剪贴板。');
}

function saveAiMarkdown() {
  const text = aiResultMarkdown();
  if (!text) return;
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${$('#aiWorkbenchCode').value}-AI分析.md`;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function showAiHistory() {
  const code = $('#aiWorkbenchCode').value;
  const data = await apiJson(`/api/ai/reports?code=${encodeURIComponent(code)}&limit=20`);
  state.aiReports = data.items || [];
  $('#aiWorkbenchResult').innerHTML = state.aiReports.length ? `<div class="ai-history-list">${state.aiReports.map(report => `<div class="ai-history-item" data-ai-report-id="${report.id}"><b>${escapeHtml(report.stock_name)} · ${escapeHtml(report.model)}</b><span>${escapeHtml(report.created_at)} · ${escapeHtml(report.question || '完整分析')}</span></div>`).join('')}</div>` : '<div class="ai-workbench-empty"><b>暂无历史报告</b><p>完成一次外部 AI 分析后，报告会自动保存。</p></div>';
}

function renderScreenerSource(data) {
  const target = $('#screenerSourceStatus');
  if (!target) return;
  const fallback = data.fallback_used || data.is_stale;
  target.className = `screener-source-status ${fallback ? 'fallback' : 'real'}`;
  target.textContent = `${data.source || '未知来源'} · ${data.fetched_at || '无时点'}${data.latency_ms !== null && data.latency_ms !== undefined ? ` · ${data.latency_ms}ms` : ''}${fallback ? ' · 已降级' : ''}`;
}

function screenerNumber(value, unit = '') {
  if (value === null || value === undefined || value === '') return '-';
  return `${Number(value).toFixed(2)}${unit}`;
}

function renderScreenerTable(data, targetSelector, strategyName = '条件扫描') {
  const target = $(targetSelector);
  state.lastScreenerResults = data.items || [];
  renderScreenerSource(data);
  if (!state.lastScreenerResults.length) {
    target.innerHTML = '<div class="empty">真实数据中没有股票同时满足当前条件。</div>';
    return;
  }
  target.innerHTML = `<div class="warning">本次批量扫描 ${data.scanned_count || '-'} 只，命中 ${data.total} 只，当前展示 ${state.lastScreenerResults.length} 只。筛选结果不等同于买入建议。</div><table>
    <thead><tr><th>股票</th><th>最新价</th><th>涨跌幅</th><th>换手/量比</th><th>成交额</th><th>估值</th><th>主力净额</th><th>命中条件</th><th>操作</th></tr></thead>
    <tbody>${state.lastScreenerResults.map(item => `<tr>
      <td><b>${escapeHtml(item.name)}</b><br><small>${escapeHtml(item.code)}</small></td>
      <td>${screenerNumber(item.price)}</td><td class="${Number(item.change_pct) >= 0 ? 'up' : 'down'}">${fmtPct(Number(item.change_pct || 0))}</td>
      <td>${screenerNumber(item.turnover_rate, '%')} / ${screenerNumber(item.volume_ratio)}</td>
      <td>${screenerNumber(Number(item.amount || 0) / 100000000, '亿')}</td>
      <td>PE ${screenerNumber(item.pe_ttm)}<br><small>PB ${screenerNumber(item.pb)}</small></td>
      <td>${screenerNumber(Number(item.main_net || 0) / 100000000, '亿')}</td>
      <td>${escapeHtml((item.matched_conditions || item.signals || []).join('；') || '基础条件')}</td>
      <td><div class="screener-action-cell"><button data-screen-watch="${escapeHtml(item.code)}">加自选</button><button data-screen-score="${escapeHtml(item.code)}">中枢评分</button><button data-screen-recommend="${escapeHtml(item.code)}" data-screen-strategy="${escapeHtml(strategyName)}">记录推荐</button><button data-screen-ai="${escapeHtml(item.code)}" data-screen-name="${escapeHtml(item.name)}">AI复核</button></div></td>
    </tr>`).join('')}</tbody></table>`;
}

function setCurrentScreenerDsl(dsl) {
  state.currentScreenerDsl = dsl;
  $('#strategyDslPreview').textContent = JSON.stringify(dsl, null, 2);
}

function renderScreenerStrategies() {
  const hot = state.screenerCatalog?.hot_strategies || [];
  $('#hotStrategyList').innerHTML = hot.map(item => `<button class="strategy-item" type="button" data-hot-strategy="${escapeHtml(item.id)}"><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.description)}</small></button>`).join('') || '<div class="empty">暂无热门策略</div>';
  $('#myStrategyList').innerHTML = state.screenerStrategies.map(item => `<div class="strategy-item" data-my-strategy="${item.id}"><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.description || JSON.stringify(item.dsl))}</small><button class="strategy-delete" type="button" data-delete-strategy="${item.id}">删除</button></div>`).join('') || '<div class="empty">尚未保存策略</div>';
}

async function loadScreenerStrategies() {
  const data = await apiJson('/api/screener/strategies');
  state.screenerStrategies = data.items || [];
  renderScreenerStrategies();
}

async function initSmartScreener() {
  if (state.screenerLoaded) return;
  const [catalog] = await Promise.all([apiJson('/api/screener/catalog'), loadScreenerStrategies()]);
  state.screenerCatalog = catalog;
  const supported = new Set(['volume_breakout', 'low_fund_inflow', 'gap_up', 'bullish_engulfing']);
  $('#shapeSignalOptions').innerHTML = (catalog.signals || []).filter(item => supported.has(item.key)).map((item, index) => `<label><input type="checkbox" value="${escapeHtml(item.key)}" ${index === 0 ? 'checked' : ''}>${escapeHtml(item.label)}</label>`).join('');
  renderScreenerStrategies();
  state.screenerLoaded = true;
}

async function runScreener(dsl, targetSelector, strategyName) {
  const target = $(targetSelector);
  target.innerHTML = '<div class="empty">正在读取全A批量快照并执行确定性筛选...</div>';
  const data = await apiJson('/api/screener/run', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({dsl})});
  if (data.error) {
    target.innerHTML = `<div class="warning">${escapeHtml(data.message || data.error)}</div>`;
    if (data.source) renderScreenerSource(data);
    return;
  }
  renderScreenerTable(data, targetSelector, strategyName);
}

async function runShapeScreener() {
  const signals = [...document.querySelectorAll('#shapeSignalOptions input:checked')].map(input => ({signal: input.value, within_days: 1}));
  const turnover = Number($('#shapeMinTurnover').value || 0);
  const amount = Number($('#shapeMinAmount').value || 0) * 100000000;
  const dsl = {all: [...signals, {field: 'turnover_rate', op: '>=', value: turnover}, {field: 'amount', op: '>=', value: amount}], sort: [{field: 'main_net', direction: 'desc'}], limit: Number($('#shapeLimit').value || 50)};
  await runScreener(dsl, '#shapeScreenerResult', '形态选股');
}

async function parseNaturalStrategy() {
  const text = $('#naturalStrategyInput').value.trim();
  const data = await apiJson('/api/screener/parse', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
  if (data.error) {
    $('#strategyDslPreview').textContent = data.message || data.error;
    return;
  }
  setCurrentScreenerDsl(data.dsl);
}

async function saveCurrentStrategy() {
  if (!state.currentScreenerDsl) await parseNaturalStrategy();
  if (!state.currentScreenerDsl) return;
  const name = window.prompt('策略名称', '我的选股策略');
  if (!name) return;
  const result = await apiJson('/api/screener/strategies', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name, description: $('#naturalStrategyInput').value.trim(), dsl: state.currentScreenerDsl, enabled: true})});
  if (result.error) return pushEvent(`策略保存失败：${result.message || result.error}`);
  await loadScreenerStrategies();
  pushEvent(`选股策略“${name}”已保存。`);
}

async function createScreenerRecommendation(code, strategyName) {
  const item = state.lastScreenerResults.find(row => row.code === code) || {};
  const result = await apiJson('/api/recommendations', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code, strategy_name: strategyName, reason: (item.matched_conditions || item.signals || []).join('；'), risk_note: '候选推荐用于跟踪验证，需结合失效条件人工决策。'})});
  pushEvent(result.error ? `推荐记录失败：${result.message || result.error}` : `${item.name || code} 已按当前真实价格进入推荐验证台。`);
}

async function loadRecommendationValidation() {
  const data = await apiJson('/api/recommendations/validation?limit=100');
  renderScreenerSource(data);
  const rows = data.items || [];
  const pitfallChecks = [
    { question: '推荐逻辑是否一致？', verdict: '要核对', note: '先看推荐理由、快照价格和当时策略标签是否一致。' },
    { question: '数据口径是否一致？', verdict: '要核对', note: '收益、回撤和持有天数必须用同一口径复盘。' },
    { question: '风险提示是否充分？', verdict: '必要', note: '不能只看涨幅，要同时看 risk note 和回撤区间。' },
    { question: '是否形成复盘结论？', verdict: '输出', note: '复盘结果最终要沉淀成策略保留、降权或停用。' },
  ];
  $('#recommendationValidation').innerHTML = rows.length ? `<table><thead><tr><th>股票</th><th>策略</th><th>推荐时间</th><th>推荐价/现价</th><th>当前收益</th><th>1/3/5/10日</th><th>最大回撤</th><th>推荐理由</th><th>风险</th></tr></thead><tbody>${rows.map(item => `<tr>
    <td><b>${escapeHtml(item.stock_name)}</b><br><small>${escapeHtml(item.code)}</small></td><td>${escapeHtml(item.strategy_name)}</td><td>${escapeHtml(item.created_at)}</td>
    <td>${screenerNumber(item.entry_price)} / ${screenerNumber(item.current_price)}</td><td class="${Number(item.current_return_pct || 0) >= 0 ? 'up' : 'down'}">${item.current_return_pct === null ? '-' : fmtPct(item.current_return_pct)}</td>
    <td>${['return_1d_pct','return_3d_pct','return_5d_pct','return_10d_pct'].map(key => item.metrics?.[key] === null ? '-' : fmtPct(item.metrics?.[key])).join(' / ')}</td><td>${item.metrics?.max_drawdown_pct === null ? '-' : fmtPct(item.metrics?.max_drawdown_pct)}</td>
    <td>${escapeHtml(item.reason)}</td><td>${escapeHtml(item.risk_note)}</td></tr>`).join('')}</tbody></table>` : '<div class="empty">暂无推荐记录。请先从形态或指标扫描结果中选择“记录推荐”。</div>';
}

async function loadScreenerDataHealth() {
  const data = await apiJson('/api/data-sources/health');
  const gateway = data.gateway || [];
  const infra = data.infrastructure || {};
  const quality = data.quality || {};
  const preheat = data.preheat || {};
  const tradingTools = data.trading_tools || [];
  const fullstack_toolkit = data.fullstack_toolkit || {};
  const toolkitLayers = fullstack_toolkit.layers || [];
  $('#screenerDataHealth').innerHTML = `
    <div class="health-card"><h4>行情质量与预热</h4><div class="health-row"><span>指数数据年龄</span><b>${escapeHtml(quality.index_age_sec ?? '-')} 秒</b></div><div class="health-row"><span>个股数据年龄</span><b>${escapeHtml(quality.quote_age_sec ?? '-')} 秒</b></div><div class="health-row"><span>全市场数据年龄</span><b>${escapeHtml(quality.market_age_sec ?? '-')} 秒</b></div><div class="health-row"><span>最近预热</span><b class="${preheat.ok === false ? 'health-bad' : 'health-ok'}">${escapeHtml(preheat.last_run_at || '尚未执行')}</b></div><small>${preheat.snapshot ? `快照 ${escapeHtml(preheat.snapshot.count ?? 0)} 条 · ${escapeHtml(preheat.snapshot.latency_ms ?? '-')}ms · ${preheat.snapshot.fallback_used ? '已降级' : '主源'}` : '登录后自动预热，服务端每 5 分钟最多执行一次'}</small></div>
    <div class="health-card"><h4>全市场数据网关</h4>${gateway.map(item => `<div class="health-row"><span><b>${escapeHtml(item.name)}</b><br><small>${escapeHtml(item.last_error || item.last_success_at || '等待调用')}</small></span><span class="${item.ok === false ? 'health-bad' : 'health-ok'}">${item.ok === null ? '待检测' : item.ok ? `${item.latency_ms}ms` : '不可用'}<br><small>失败率 ${item.error_rate_pct}%</small></span></div>`).join('')}</div>
    <div class="health-card"><h4>A股全栈数据工具包 ${escapeHtml(fullstack_toolkit.version || 'V3.1')}</h4><div class="health-row"><span>分层架构</span><b>${escapeHtml(fullstack_toolkit.layer_count ?? '-')} 层</b></div><div class="health-row"><span>端点/能力组</span><b>${escapeHtml(fullstack_toolkit.endpoint_count ?? '-')}</b></div><div class="health-row"><span>已接入</span><b>${escapeHtml(fullstack_toolkit.connected_count ?? '-')}</b></div><small>${(fullstack_toolkit.principles || []).map(escapeHtml).join('；')}</small></div>
    <div class="health-card"><h4>V3.1 分层矩阵</h4>${toolkitLayers.map(layer => `<div class="health-row"><span><b>${escapeHtml(layer.name)}</b><br><small>${escapeHtml(layer.purpose || '')}</small></span><span>${escapeHtml((layer.endpoints || []).length)}项<br><small>${(layer.endpoints || []).slice(0, 2).map(item => escapeHtml(item.name)).join(' / ')}</small></span></div>`).join('')}</div>
    <div class="health-card"><h4>炒股三件套数据</h4>${tradingTools.map(item => `<div class="health-row"><span><b>${escapeHtml(item.name)}</b><br><small>${escapeHtml(item.role || '')}</small></span><span>${escapeHtml(item.status || '-')}<br><small>${escapeHtml(item.mode || '-')}</small></span></div>`).join('')}</div>
    <div class="health-card"><h4>缓存与持久化</h4><div class="health-row"><span>缓存</span><b>${escapeHtml(infra.cache?.backend || '-')}</b></div><div class="health-row"><span>业务数据库</span><b>${escapeHtml(infra.persistence?.backend || '-')}</b></div><div class="health-row"><span>Tushare</span><b class="${infra.tushare?.ok ? 'health-ok' : 'health-bad'}">${escapeHtml(infra.tushare?.message || '未配置')}</b></div><div class="health-row"><span>AKShare</span><b>${escapeHtml(infra.akshare?.message || (infra.akshare?.ok ? '可用' : '未启用'))}</b></div></div>
    <div class="health-card tushare-config-card">
      <h4>Tushare 数据源配置</h4>
      <p>管理员保存一次 Token 后，会写入服务器数据目录，网站重启也不用重复输入。</p>
      <div class="tushare-config-row">
        <input id="tushareTokenInput" type="password" placeholder="输入你的 Tushare Token">
        <button id="saveTushareToken" type="button">保存 Token</button>
      </div>
      <small id="tushareConfigStatus">当前状态：${escapeHtml(infra.tushare?.message || '未配置')}</small>
    </div>`;
}

async function saveTushareToken() {
  const input = $('#tushareTokenInput');
  const status = $('#tushareConfigStatus');
  const token = input?.value.trim() || '';
  if (!token) {
    if (status) status.textContent = '请先输入 Tushare Token。';
    return;
  }
  if (status) status.textContent = '正在保存并检测 Tushare...';
  try {
    const result = await apiJson('/api/tushare/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({token}),
    });
    if (input) input.value = '';
    if (status) status.textContent = `已保存：${result.masked_token || ''}；${result.status?.message || 'Tushare 已配置'}`;
    pushEvent('Tushare Token 已保存到服务器，日K/资金/分钟线会优先尝试 Tushare。');
    await loadScreenerDataHealth();
  } catch (error) {
    if (status) status.textContent = `保存失败：${error.message || error}`;
  }
}

function renderAbnormalSource(data) {
  const target = $('#abnormalSourceStatus');
  if (!target) return;
  const fallback = data.fallback_used || data.is_stale;
  target.className = `screener-source-status ${fallback ? 'fallback' : 'real'}`;
  target.textContent = `${data.source || '未知来源'} · ${data.fetched_at || data.created_at || '无时点'}${data.latency_ms !== null && data.latency_ms !== undefined ? ` · ${data.latency_ms}ms` : ''}${fallback ? ' · 已降级' : ''}`;
}

function selectedAbnormalTypes() {
  return [...document.querySelectorAll('#abnormalTypeOptions input:checked')].map(input => input.value);
}

function renderAbnormalTypeOptions(catalog) {
  const groups = [
    ['利好异动', catalog.positive || []],
    ['利空异动', catalog.negative || []],
  ];
  $('#abnormalTypeOptions').innerHTML = groups.map(([title, items]) => `<div class="abnormal-type-group"><b>${escapeHtml(title)}</b><div>${items.map(item => `<label><input type="checkbox" value="${escapeHtml(item.key)}" checked>${escapeHtml(item.label)}</label>`).join('')}</div></div>`).join('');
}

function renderAbnormalEvents(data, historical = false) {
  renderAbnormalSource(data);
  const rows = data.items || [];
  state.abnormalItems = rows;
  if (!rows.length) {
    $('#abnormalEventsResult').innerHTML = `<div class="empty">${historical ? '当前账号暂无历史异动快照。' : '当前条件没有识别到异动。'}</div>`;
    return;
  }
  $('#abnormalEventsResult').innerHTML = `<div class="warning">本次${historical ? '历史' : '实时'}共展示 ${rows.length} 条异动。利好/利空是信号分类，不等同交易建议。</div><table>
    <thead><tr><th>时间</th><th>股票</th><th>异动类型</th><th>价格/涨跌幅</th><th>量能/金额</th><th>行业概念</th><th>说明</th><th>操作</th></tr></thead>
    <tbody>${rows.map(item => `<tr>
      <td>${escapeHtml(item.time || item.created_at || data.fetched_at || '-')}</td>
      <td><b>${escapeHtml(item.name || item.stock_name || '')}</b><br><small>${escapeHtml(item.code || '')}</small></td>
      <td><span class="tag ${item.side === 'negative' ? 'red' : 'green'}">${escapeHtml(item.type_label || item.type_key || '-')}</span></td>
      <td>${screenerNumber(item.price)}<br><span class="${Number(item.change_pct || 0) >= 0 ? 'up' : 'down'}">${fmtPct(Number(item.change_pct || 0))}</span></td>
      <td>量比 ${screenerNumber(item.volume_ratio)}<br><small>${screenerNumber(Number(item.amount || 0) / 100000000, '亿')}</small></td>
      <td>${escapeHtml(item.industry || '-')}<br><small>${escapeHtml((item.concepts || []).slice(0, 3).join('、'))}</small></td>
      <td>${escapeHtml(item.reason || item.description || '')}</td>
      <td><div class="screener-action-cell"><button data-abnormal-watch="${escapeHtml(item.code || '')}">加自选</button><button data-abnormal-score="${escapeHtml(item.code || '')}">中枢评分</button><button data-abnormal-ai="${escapeHtml(item.code || '')}" data-abnormal-name="${escapeHtml(item.name || '')}">AI复核</button></div></td>
    </tr>`).join('')}</tbody></table>`;
}

async function initAbnormalMonitor() {
  if (state.abnormalLoaded) return;
  state.abnormalCatalog = await apiJson('/api/abnormal/catalog');
  renderAbnormalTypeOptions(state.abnormalCatalog);
  state.abnormalLoaded = true;
}

async function loadAbnormalEvents(mode = 'realtime') {
  await initAbnormalMonitor();
  $('#abnormalEventsResult').innerHTML = '<div class="empty">正在扫描全A异动信号...</div>';
  const types = selectedAbnormalTypes().join(',');
  const url = mode === 'history' ? '/api/abnormal/events?mode=history&limit=300' : `/api/abnormal/events?limit=300&types=${encodeURIComponent(types)}`;
  const data = await apiJson(url);
  renderAbnormalEvents(data, mode === 'history');
}

async function saveAbnormalSnapshot() {
  await initAbnormalMonitor();
  const data = await apiJson('/api/abnormal/snapshot', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({selected_types: selectedAbnormalTypes()})});
  renderAbnormalEvents(data);
  pushEvent(`异动快照已保存：${data.id}，共 ${data.items?.length || 0} 条。`);
}

function industryCandidateHtml(candidate) {
  return `<tr>
    <td><b>${escapeHtml(candidate.name || '')}</b><br><small>${escapeHtml(candidate.code || '')}</small></td>
    <td>${escapeHtml(candidate.role || candidate.industry || '-')}</td>
    <td>${screenerNumber(candidate.score || candidate.price || 0)}</td>
    <td>${escapeHtml((candidate.evidence || candidate.matched_conditions || candidate.signals || []).join('；'))}</td>
    <td><div class="screener-action-cell"><button data-chain-score="${escapeHtml(candidate.code || '')}">中枢评分</button><button data-chain-watch="${escapeHtml(candidate.code || '')}">加自选</button><button data-chain-ai="${escapeHtml(candidate.code || '')}" data-chain-name="${escapeHtml(candidate.name || '')}">AI复核</button></div></td>
  </tr>`;
}

function renderIndustryChainReport(report) {
  const candidates = report.candidates || [];
  $('#industryChainResult').innerHTML = `<div class="industry-chain-report">
    <div class="warning"><b>${escapeHtml(report.topic || '产业链分析')}</b> · ${escapeHtml(report.summary || '按产业链卡点和候选证据排序。')}<br><small>来源：${escapeHtml(report.source || '本地快照')} · ${escapeHtml(report.fetched_at || report.created_at || '')}</small></div>
    <div class="grid two">
      <div class="health-card"><h4>核心环节</h4>${listHtml(report.chain_nodes || report.nodes || [])}</div>
      <div class="health-card"><h4>卡点与催化</h4>${listHtml(report.bottlenecks || report.catalysts || [])}</div>
    </div>
    <h4>候选公司</h4>
    ${candidates.length ? `<table><thead><tr><th>股票</th><th>链条角色</th><th>强度</th><th>证据</th><th>操作</th></tr></thead><tbody>${candidates.map(industryCandidateHtml).join('')}</tbody></table>` : '<div class="empty">当前快照没有匹配出候选公司，可换一个主题或接入更完整产业链数据源。</div>'}
    <div class="warning danger">仅作研究线索与候选池管理，不构成投资建议；请结合公告、财报、研报和交易计划复核。</div>
  </div>`;
}

async function runIndustryChain() {
  const query = $('#industryChainQuery').value.trim();
  if (!query) return;
  $('#industryChainResult').innerHTML = '<div class="empty">正在拆解产业链并匹配候选...</div>';
  const data = await apiJson('/api/research/industry-chain/analyze', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({query, mode: 'quick'})});
  if (data.error) {
    $('#industryChainResult').innerHTML = `<div class="warning">${escapeHtml(data.message || data.error)}</div>`;
    return;
  }
  renderIndustryChainReport(data.report || data);
  pushEvent(`产业链报告已保存：${query}`);
}

async function loadIndustryChainHistory() {
  const data = await apiJson('/api/research/industry-chain/history?limit=20');
  state.industryChainReports = data.items || [];
  $('#industryChainResult').innerHTML = state.industryChainReports.length ? `<div class="ai-history-list">${state.industryChainReports.map(item => `<div class="ai-history-item" data-chain-history="${item.id}"><b>${escapeHtml(item.topic)}</b><span>${escapeHtml(item.created_at)} · ${escapeHtml(item.payload?.summary || '产业链报告')}</span></div>`).join('')}</div>` : '<div class="empty">暂无产业链历史报告。</div>';
}

async function scoreHubCandidate(code, persist = false) {
  const result = await apiJson('/api/recommendations/score', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code, persist})});
  if (result.error) return pushEvent(`中枢评分失败：${result.message || result.error}`);
  const score = result.score || {};
  const title = `${result.stock?.name || code} · 选股中枢评分 ${score.total_score || '-'} (${score.level || '-'})`;
  $('#aiModalTitle').textContent = title;
  $('#aiModalBody').innerHTML = `<div class="warning">${escapeHtml(score.risk_note || '候选推荐仅用于后续验证，不构成交易建议。')}</div>
    <div class="grid two">
      <div class="health-card"><h4>评分构成</h4>${Object.entries(score.components || {}).map(([key, value]) => `<div class="health-row"><span>${escapeHtml(key)}</span><b>${screenerNumber(value)}</b></div>`).join('')}</div>
      <div class="health-card"><h4>证据</h4>${listHtml(score.evidence || [])}</div>
    </div>
    <h4>产业链依据</h4><p>${escapeHtml(result.industry_chain?.summary || '-')}</p>
    <div class="screener-action-cell"><button id="persistHubRecommendation" type="button">写入推荐验证台</button><button data-modal-ai="${escapeHtml(code)}" data-modal-name="${escapeHtml(result.stock?.name || code)}" type="button">外部AI复核</button></div>`;
  $('#aiModal').classList.add('open');
  $('#persistHubRecommendation')?.addEventListener('click', async () => {
    const saved = await apiJson('/api/recommendations/score', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code, persist: true})});
    pushEvent(saved.recommendation_id ? `${result.stock?.name || code} 已写入推荐验证台。` : '写入推荐验证台失败。');
  }, {once: true});
}

async function loadAll() {
  const [mobileDashboard, market, watchlist, candidates, portfolio, actionQueue, tradeLog, eaSimulation, emotionVolume, hiddenFundProxy, sectors, funds, events, strategyScan, dataQuality, breadth, coverage, movers, systemAudit, chokepointAtlas, breakthroughReview, agentDebate, serenityFramework, dataSourcePlan, quantUpgradePlan, aiRecommendations, dailyReview, decisionFusion, membershipPlans] = await Promise.all([
    safeApiJson('/api/mobile/dashboard'),
    safeApiJson('/api/market/overview'),
    safeApiJson('/api/watchlist', []),
    safeApiJson('/api/research/candidates', []),
    safeApiJson('/api/portfolio/summary'),
    safeApiJson('/api/trading/action-queue'),
    safeApiJson('/api/trading/log', []),
    safeApiJson('/api/trading/ea-simulation'),
    safeApiJson('/api/market/emotion-volume'),
    safeApiJson('/api/market/hidden-fund-proxy'),
    safeApiJson('/api/market/sectors', []),
    safeApiJson('/api/market/fund-flow', []),
    safeApiJson('/api/research/events', []),
    safeApiJson('/api/research/strategy-scan'),
    safeApiJson('/api/market/data-quality'),
    safeApiJson('/api/market/breadth'),
    safeApiJson('/api/market/data-coverage'),
    safeApiJson('/api/market/movers'),
    safeApiJson('/api/research/system-audit'),
    safeApiJson('/api/research/chokepoint-atlas'),
    safeApiJson('/api/research/breakthrough-review'),
    safeApiJson('/api/research/agent-debate'),
    safeApiJson('/api/research/serenity-framework'),
    safeApiJson('/api/research/data-source-plan'),
    safeApiJson('/api/research/quant-upgrade-plan'),
    safeApiJson('/api/recommendations/ai?limit=10'),
    safeApiJson('/api/review/daily', () => ({title: '今日复盘', summary: '复盘数据源暂时不可用，请稍后重试。', market_review: {}, watchlist_review: {items: []}, observation_pool: {items: []}, next_day_plan: {}, history: {latest: []}})),
    safeApiJson('/api/decision/fusion'),
    safeApiJson('/api/membership/plans'),
  ]);
  safeRender(renderMobileDashboard, mobileDashboard, 'mobileDashboard');
  safeRender(renderMarket, market, 'market');
  safeRender(renderEmotionVolume, emotionVolume, 'emotionVolume');
  safeRender(renderDataQuality, dataQuality, 'dataQuality');
  safeRender(renderCandidates, candidates, 'candidates');
  safeRender(renderWatchlistV2, watchlist, 'watchlist');
  safeRender(renderPortfolio, portfolio, 'portfolio');
  safeRender(renderActionQueue, actionQueue, 'actionQueue');
  safeRender(renderTradeLog, tradeLog, 'tradeLog');
  safeRender(renderEaSimulation, eaSimulation, 'eaSimulation');
  safeRender(renderSectors, sectors, 'sectors');
  safeRender(renderFunds, funds, 'funds');
  safeRender(renderEvents, events, 'events');
  safeRender(renderStrategyScan, strategyScan, 'strategyScan');
  safeRender(renderBreadth, breadth, 'breadth');
  safeRender(renderCoverage, coverage, 'coverage');
  safeRender(renderMovers, movers, 'movers');
  safeRender(renderSystemAudit, systemAudit, 'systemAudit');
  safeRender(renderChokepointAtlas, chokepointAtlas, 'chokepointAtlas');
  safeRender(renderBreakthroughReview, breakthroughReview, 'breakthroughReview');
  safeRender(renderAgentDebate, agentDebate, 'agentDebate');
  safeRender(renderSerenityFramework, serenityFramework, 'serenityFramework');
  safeRender(renderDataSourcePlan, dataSourcePlan, 'dataSourcePlan');
  safeRender(renderQuantUpgradePlan, quantUpgradePlan, 'quantUpgradePlan');
  safeRender(renderHiddenFundProxy, hiddenFundProxy, 'hiddenFundProxy');
  safeRender(renderAiRecommendations, aiRecommendations, 'aiRecommendations');
  safeRender(renderDailyReview, dailyReview, 'reviewCenterBody');
  safeRender(renderDecisionFusion, decisionFusion, 'decisionFusion');
  safeRender(renderMembershipPlans, membershipPlans, 'membershipPlans');
  ensureStrategyWorkflowCenter();
  // 登录/刷新后低频预热行情源；服务端自带 5 分钟幂等节流，不会重复请求上游。
  apiJson('/api/data-sources/preheat').catch(error => pushEvent(`数据预热暂不可用：${error.message || error}`));
}

function syncMobileNavigation(activeView) {
  document.querySelectorAll('#mobileBottomTabs [data-mobile-view]').forEach(button => {
    button.classList.toggle('active', button.dataset.mobileView === activeView);
  });
}

async function login(event) {
  event.preventDefault();
  const username = $('#loginUsername').value.trim();
  const password = $('#loginPassword').value;
  $('#loginError').textContent = '';
  let result;
  try {
    result = await apiJson('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
  } catch (error) {
    showLogin('登录失败：账号、密码错误，或会员已到期。');
    return;
  }
  state.currentUser = result.user;
  hideLogin();
  renderUserBadge(result.user);
  try {
    await Promise.all([loadDashboardBootstrap(), loadMobileDashboard()]);
    await refreshAiStatus();
    loadDeferredDashboardData().catch(error => pushEvent(`后台数据补全失败：${error.message || error}`));
    connectWs();
  } catch (error) {
    pushEvent(`登录成功，但行情初始化暂时失败：${error.message || error}`);
    connectWs();
  }
}

async function registerByPhone(event) {
  event.preventDefault();
  const phone = $('#registerPhone').value.trim();
  const displayName = $('#registerDisplayName').value.trim();
  const password = $('#registerPassword').value;
  $('#registerError').textContent = '';
  try {
    const result = await apiJson('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, display_name: displayName, password }),
    });
    $('#loginUsername').value = result.user?.phone || phone;
    $('#loginPassword').value = password;
    $('#registerForm').classList.add('hidden');
    $('#loginForm').classList.remove('hidden');
    $('#loginError').textContent = '注册成功，已为你填入手机号，可以直接登录。';
  } catch (error) {
    $('#registerError').textContent = error.message || '注册失败，请检查手机号或稍后再试。';
  }
}

async function logout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
  state.currentUser = null;
  showLogin('已退出，请重新登录。');
}

async function initAuth() {
  try {
    const result = await apiJson('/api/auth/me');
    state.currentUser = result.user;
    hideLogin();
    renderUserBadge(result.user);
  } catch (error) {
    showLogin();
    return;
  }
  try {
    await Promise.all([loadDashboardBootstrap(), loadMobileDashboard()]);
    await refreshAiStatus();
    loadDeferredDashboardData().catch(error => pushEvent(`后台数据补全失败：${error.message || error}`));
    connectWs();
  } catch (error) {
    pushEvent(`已登录，但行情初始化暂时失败：${error.message || error}`);
    connectWs();
  }
}

async function searchStocks(query) {
  const data = await apiJson(`/api/stocks/search?q=${encodeURIComponent(query)}`);
  const box = $('#suggestions');
  box.style.display = 'block';
  box.innerHTML = data.items.map(stock => `<div class="suggestion" data-code="${stock.code}">
    <span>${stock.name} - ${stock.code}<br><small>${stock.market} · ${stock.tag} · ${fmtPct(stock.change_pct)}</small></span>
    <small>推荐</small>
  </div>`).join('');
  state.selectedSuggestion = data.items[0] || null;
}

async function addStock(code) {
  if (!code) return;
  const button = $('#addFirst');
  if (button) button.disabled = true;
  try {
    await apiJson('/api/watchlist', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    pushEvent(`${code} 已加入自选，开始进入模型监控。`);
    $('#stockSearch').value = '';
    $('#suggestions').style.display = 'none';
    await loadAll();
  } catch (error) {
    pushEvent(`${code} 加入自选失败，请稍后再试。`);
  } finally {
    if (button) button.disabled = false;
  }
  return;
  await fetch('/api/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  pushEvent(`${code} 已加入自选，开始进入模型监控。`);
  await loadAll();
}

async function trackRecommendation(code) {
  if (!code) return;
  try {
    await apiJson('/api/recommendations/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    pushEvent(`${code} 已按AI推荐纳入盯盘。`);
    await loadAll();
  } catch (error) {
    pushEvent(`${code} 推荐加入失败，请稍后再试。`);
  }
  return;
  await fetch('/api/recommendations/track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  pushEvent(`${code} 已按AI推荐纳入盯盘，并记录推荐基准价。`);
  await loadAll();
}

async function removeStock(code) {
  await fetch(`/api/watchlist/${encodeURIComponent(code)}`, { method: 'DELETE' });
  pushEvent(`${code} 已取消关注。`);
  await loadAll();
}

function findWatchItem(code) {
  return state.watchlist.find(item => item.stock.code === code);
}

function openPositionModal(code) {
  const item = findWatchItem(code);
  if (!item) return;
  const stock = item.stock;
  $('#positionModalTitle').textContent = `${stock.name} 持仓设置`;
  $('#positionCode').value = stock.code;
  $('#positionCost').value = Number(stock.cost || 0).toFixed(3);
  $('#positionQuantity').value = item.quantity || 0;
  $('#positionAlertPct').value = Number(stock.alert_pct || 3).toFixed(2);
  $('#positionAlertPrice').value = Number(stock.alert_price || stock.price || 0).toFixed(2);
  $('#positionOpenPrice').value = Number(stock.open_price_target || 0).toFixed(2);
  $('#positionSort').value = stock.sort_order || 0;
  $('#positionTakeProfit').value = Number(stock.take_profit || 0).toFixed(2);
  $('#positionStopLoss').value = Number(stock.stop_loss || 0).toFixed(2);
  $('#positionModal').classList.add('open');
}

async function savePosition(quantityOverride = null) {
  const payload = {
    code: $('#positionCode').value,
    cost: Number($('#positionCost').value || 0),
    quantity: quantityOverride === null ? Number($('#positionQuantity').value || 0) : quantityOverride,
    alert_pct: Number($('#positionAlertPct').value || 3),
    alert_price: Number($('#positionAlertPrice').value || 0),
    sort_order: Number($('#positionSort').value || 0),
    open_price_target: Number($('#positionOpenPrice').value || 0),
    take_profit: Number($('#positionTakeProfit').value || 0),
    stop_loss: Number($('#positionStopLoss').value || 0),
  };
  await fetch('/api/watchlist/position', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  $('#positionModal').classList.remove('open');
  pushEvent(`${payload.code} 持仓设置已保存。`);
  await loadAll();
}

async function recordTradeAction(code, mode) {
  const note = mode === 'manual' ? '人工确认执行，真实下单需在券商端完成' : '模拟执行，用于策略复盘';
  const result = await fetch('/api/trading/log', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, mode, note }),
  }).then(res => res.json());
  if (result.error) {
    pushEvent(`${code} 记录失败：${result.error}`);
    return;
  }
  pushEvent(`${result.entry.name} ${result.entry.label} 已记录为${mode === 'paper' ? '模拟执行' : '人工确认'}。`);
  const log = await fetch('/api/trading/log').then(res => res.json());
  renderTradeLog(log);
}

function connectWs() {
  connectSse();
  const ws = new WebSocket(`ws://${location.host}/ws/market`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type !== 'tick') return;
    if (state.market) {
      renderMarket({ ...state.market, indices: data.indices, updated_at: data.updated_at });
    }
    pushEvent('行情推送更新，模型等待下一次评分刷新。');
  };
  ws.onclose = () => setTimeout(connectWs, 2000);
}

let marketEventSource = null;
function connectSse() {
  if (!window.EventSource || !state.currentUser) return;
  if (marketEventSource) marketEventSource.close();
  marketEventSource = new EventSource('/api/events/stream');
  marketEventSource.addEventListener('market', event => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'tick') pushEvent('SSE 实时行情推送已更新。');
    } catch (_) { /* ignore malformed push */ }
  });
  marketEventSource.onerror = () => {
    marketEventSource?.close();
    setTimeout(() => { if (state.currentUser) connectSse(); }, 5000);
  };
}

async function loadDynamicRisk(code) {
  if (!code) return null;
  try {
    const data = await apiJson(`/api/risk/dynamic?code=${encodeURIComponent(code)}`);
    const node = $('#eaWorkflow');
    if (node && data.thresholds) {
      node.textContent = `波动率 ${data.thresholds.volatility_pct}% · 止损 ${data.thresholds.stop_loss_pct}% · 最大仓位 ${data.thresholds.max_position_pct}% · 仅供模拟复核`;
    }
    return data;
  } catch (_) {
    return null;
  }
}

async function loadFactorAnalysis(code) {
  if (!code) return null;
  try {
    const data = await apiJson(`/api/research/factors/${encodeURIComponent(code)}`);
    const node = $('#eaWorkflow');
    if (node && data.momentum_regime && data.factor_snapshot) {
      node.dataset.momentumRegime = 'momentum-regime';
      node.dataset.factorScore = 'factor-score';
      node.textContent = `${data.momentum_regime.label} · 因子综合 ${data.factor_snapshot.total_score} · ${data.momentum_regime.reason}`;
    }
    return data;
  } catch (_) {
    return null;
  }
}

document.querySelectorAll('.nav').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.nav').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.view').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
    $(`#${button.dataset.view}`).classList.add('active');
    $('#pageTitle').textContent = button.textContent;
    const mobileView = ['dashboard', 'watchlist', 'trading', 'screener', 'admin'].includes(button.dataset.view) ? button.dataset.view : 'screener';
    syncMobileNavigation(mobileView);
    if (button.dataset.view === 'abnormal') initAbnormalMonitor();
    if (button.dataset.view === 'screener') initSmartScreener();
    if (button.dataset.view === 'ai-tools') initAITools();
    if (button.dataset.view === 'admin') loadAdminMembers();
  });
});

document.querySelectorAll('[data-view-jump]').forEach(button => {
  button.addEventListener('click', () => {
    const target = button.dataset.viewJump;
    document.querySelector(`.nav[data-view="${target}"]`)?.click();
  });
});
document.querySelectorAll('[data-mobile-view]').forEach(button => {
  button.addEventListener('click', () => {
    const target = button.dataset.mobileView === 'screener' ? 'screener' : button.dataset.mobileView;
    document.querySelector(`.nav[data-view="${target}"]`)?.click();
  });
});
$('#mobileDashboard')?.addEventListener('click', event => {
  const copyButton = event.target.closest('[data-copy-access]');
  if (copyButton) {
    copyAccessText(copyButton.dataset.copyAccess, '手机访问地址已复制。');
    return;
  }
  const button = event.target.closest('[data-mobile-jump]');
  if (!button) return;
  document.querySelector(`.nav[data-view="${button.dataset.mobileJump}"]`)?.click();
});
$('#mobileQuickLinks')?.addEventListener('click', event => {
  const button = event.target.closest('[data-mobile-jump]');
  if (!button) return;
  document.querySelector(`.nav[data-view="${button.dataset.mobileJump}"]`)?.click();
});
$('#mobileDashboardRefresh')?.addEventListener('click', async () => {
  const button = $('#mobileDashboardRefresh');
  if (!button) return;
  button.disabled = true;
  try {
    await loadMobileDashboard();
    pushEvent('手机首页已刷新。');
  } catch (error) {
    pushEvent(`手机首页刷新失败：${error.message || error}`);
  } finally {
    button.disabled = false;
  }
});

$('#stockSearch').addEventListener('input', event => searchStocks(event.target.value));
$('#stockSearch').addEventListener('focus', event => searchStocks(event.target.value));
$('#suggestions').addEventListener('click', event => {
  const item = event.target.closest('.suggestion');
  if (!item) return;
  addStock(item.dataset.code);
  $('#suggestions').style.display = 'none';
});
$('#addFirst').addEventListener('click', () => {
  if (state.selectedSuggestion) addStock(state.selectedSuggestion.code);
});
$('#watchCards').addEventListener('click', event => {
  const stockViewButton = event.target.closest('[data-stock-view]');
  if (stockViewButton) {
    openStockTool(stockViewButton.dataset.code, stockViewButton.dataset.stockView);
    return;
  }
  const aiButton = event.target.closest('[data-ai]');
  if (aiButton) {
    analyzeStock(aiButton.dataset.ai, aiButton.dataset.name);
    return;
  }
  const positionButton = event.target.closest('[data-position]');
  if (positionButton) {
    openPositionModal(positionButton.dataset.position);
    return;
  }
  const button = event.target.closest('[data-remove]');
  if (button) removeStock(button.dataset.remove);
});
$('#watchCards').addEventListener('change', event => {
  const select = event.target.closest('[data-watch-sort]');
  if (!select) return;
  const kind = select.dataset.watchSort;
  state.watchSort[kind] = select.value;
  renderWatchlistV2(state.watchlist);
});
$('#portfolioSummary')?.addEventListener('click', event => {
  const button = event.target.closest('#portfolioCashSave');
  if (button) savePortfolioCash();
});
$('#positionForm').addEventListener('submit', event => {
  event.preventDefault();
  savePosition();
});
$('#clearPosition').addEventListener('click', () => savePosition(0));
$('#positionModalClose').addEventListener('click', () => $('#positionModal').classList.remove('open'));
$('#positionModal').addEventListener('click', event => {
  if (event.target.id === 'positionModal') $('#positionModal').classList.remove('open');
});
$('#actionQueue').addEventListener('click', event => {
  const button = event.target.closest('[data-log-code]');
  if (!button) return;
  recordTradeAction(button.dataset.logCode, button.dataset.logMode);
});
$('#runEaSimulation')?.addEventListener('click', runEaSimulation);
$('#eaStrategySelect')?.addEventListener('change', refreshEaSimulation);
$('#aiRecommendations')?.addEventListener('click', event => {
  const button = event.target.closest('[data-track-reco]');
  if (!button || button.disabled) return;
  trackRecommendation(button.dataset.trackReco);
});
$('#aiModalClose').addEventListener('click', () => $('#aiModal').classList.remove('open'));
$('#aiModal').addEventListener('click', event => {
  if (event.target.id === 'aiModal') $('#aiModal').classList.remove('open');
});
$('#aiModalBody')?.addEventListener('submit', event => {
  const form = event.target.closest('[data-backtest-form]');
  if (!form) return;
  event.preventDefault();
  runBacktestForm(form);
});
$('#aiGatewayButton')?.addEventListener('click', openAiConfigModal);
$('#refreshAdminMembers')?.addEventListener('click', loadAdminMembers);
$('#adminCreateMemberForm')?.addEventListener('submit', createAdminMember);
$('#adminMemberTable')?.addEventListener('click', event => {
  const button = event.target.closest('[data-admin-save]');
  if (!button) return;
  saveAdminMember(button.dataset.adminSave);
});
$('#aiConfigForm')?.addEventListener('submit', saveAiConfig);
$('#testAiConfig')?.addEventListener('click', testAiConfig);
$('#aiConfigProvider')?.addEventListener('change', event => applyAiProviderPreset(event.target.value, true));
$('#aiConfigProfile')?.addEventListener('change', event => {
  const profile = (state.aiConfigProfiles || []).find(item => item.id === event.target.value);
  fillAiConfigProfile(profile);
});
$('#toggleAiApiKey')?.addEventListener('click', () => {
  const input = $('#aiConfigApiKey');
  const reveal = input.type === 'password';
  input.type = reveal ? 'text' : 'password';
  $('#toggleAiApiKey').textContent = reveal ? '隐藏' : '显示';
});
$('#aiConfigModalClose')?.addEventListener('click', () => $('#aiConfigModal').classList.remove('open'));
$('#aiConfigModal')?.addEventListener('click', event => {
  if (event.target.id === 'aiConfigModal') $('#aiConfigModal').classList.remove('open');
});
$('#aiWorkbenchForm')?.addEventListener('submit', runAiWorkbench);
$('#aiWorkbenchClose')?.addEventListener('click', () => $('#aiWorkbenchModal').classList.remove('open'));
$('#aiWorkbenchModal')?.addEventListener('click', event => {
  if (event.target.id === 'aiWorkbenchModal') $('#aiWorkbenchModal').classList.remove('open');
});
$('#aiSystemPromptPreset')?.addEventListener('change', event => {
  $('#aiCustomSystemPrompt').classList.toggle('hidden', event.target.value !== 'custom');
});
$('#aiWorkbenchQuestion')?.addEventListener('input', event => { $('#aiQuestionCount').textContent = event.target.value.length; });
$('#copyAiAnalysis')?.addEventListener('click', copyAiResult);
$('#saveAiMarkdown')?.addEventListener('click', saveAiMarkdown);
$('#showAiHistory')?.addEventListener('click', showAiHistory);
document.querySelectorAll('[data-screener-tab]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-screener-tab]').forEach(item => item.classList.remove('active'));
  document.querySelectorAll('[data-screener-pane]').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  document.querySelector(`[data-screener-pane="${button.dataset.screenerTab}"]`)?.classList.add('active');
  if (button.dataset.screenerTab === 'recommendation') loadRecommendationValidation();
  if (button.dataset.screenerTab === 'health') loadScreenerDataHealth();
}));
document.querySelectorAll('[data-strategy-list]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-strategy-list]').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  $('#hotStrategyList').classList.toggle('hidden', button.dataset.strategyList !== 'hot');
  $('#myStrategyList').classList.toggle('hidden', button.dataset.strategyList !== 'mine');
}));
$('#runShapeScreener')?.addEventListener('click', runShapeScreener);
$('#parseStrategy')?.addEventListener('click', parseNaturalStrategy);
$('#runIndicatorScreener')?.addEventListener('click', async () => {
  if (!state.currentScreenerDsl) await parseNaturalStrategy();
  if (state.currentScreenerDsl) await runScreener(state.currentScreenerDsl, '#indicatorScreenerResult', '指标选股');
});
$('#saveScreenerStrategy')?.addEventListener('click', saveCurrentStrategy);
$('#refreshRecommendationValidation')?.addEventListener('click', loadRecommendationValidation);
$('#refreshDataHealth')?.addEventListener('click', loadScreenerDataHealth);
$('#refreshAbnormalEvents')?.addEventListener('click', () => loadAbnormalEvents('realtime'));
$('#saveAbnormalSnapshot')?.addEventListener('click', saveAbnormalSnapshot);
$('#loadAbnormalHistory')?.addEventListener('click', () => loadAbnormalEvents('history'));
$('#refreshDailyReview')?.addEventListener('click', loadDailyReview);
$('#saveDailyReview')?.addEventListener('click', saveDailyReview);
$('#exportDailyReviewMarkdown')?.addEventListener('click', exportDailyReviewMarkdown);
$('#loadDailyReviewHistory')?.addEventListener('click', loadDailyReviewHistory);
$('#toggleReviewTheme')?.addEventListener('click', () => applyReviewTheme(state.reviewTheme === 'dark' ? 'light' : 'dark'));
$('#closeReviewIntelDrawer')?.addEventListener('click', closeReviewIntelDrawer);
$('#reviewIntelDrawer')?.addEventListener('click', event => {
  if (event.target.dataset.reviewDrawerClose === '1') closeReviewIntelDrawer();
});
$('#runIndustryChain')?.addEventListener('click', runIndustryChain);
$('#loadIndustryChainHistory')?.addEventListener('click', loadIndustryChainHistory);
$('#industryChainQuery')?.addEventListener('keydown', event => {
  if (event.key === 'Enter') runIndustryChain();
});
$('#hotStrategyList')?.addEventListener('click', event => {
  const button = event.target.closest('[data-hot-strategy]');
  if (!button) return;
  const strategy = (state.screenerCatalog?.hot_strategies || []).find(item => item.id === button.dataset.hotStrategy);
  if (!strategy) return;
  $('#naturalStrategyInput').value = strategy.description;
  setCurrentScreenerDsl(strategy.dsl);
});
$('#myStrategyList')?.addEventListener('click', async event => {
  const deleteButton = event.target.closest('[data-delete-strategy]');
  if (deleteButton) {
    await apiJson(`/api/screener/strategies/${deleteButton.dataset.deleteStrategy}`, {method: 'DELETE'});
    await loadScreenerStrategies();
    return;
  }
  const item = event.target.closest('[data-my-strategy]');
  const strategy = state.screenerStrategies.find(entry => String(entry.id) === item?.dataset.myStrategy);
  if (strategy) {
    $('#naturalStrategyInput').value = strategy.description || strategy.name;
    setCurrentScreenerDsl(strategy.dsl);
  }
});
$('#screener')?.addEventListener('click', event => {
  const tushareButton = event.target.closest('#saveTushareToken');
  if (tushareButton) return saveTushareToken();
  const watchButton = event.target.closest('[data-screen-watch]');
  if (watchButton) return addStock(watchButton.dataset.screenWatch);
  const scoreButton = event.target.closest('[data-screen-score]');
  if (scoreButton) return scoreHubCandidate(scoreButton.dataset.screenScore);
  const recommendButton = event.target.closest('[data-screen-recommend]');
  if (recommendButton) return createScreenerRecommendation(recommendButton.dataset.screenRecommend, recommendButton.dataset.screenStrategy);
  const aiButton = event.target.closest('[data-screen-ai]');
  if (aiButton) analyzeStock(aiButton.dataset.screenAi, aiButton.dataset.screenName);
});
$('#abnormal')?.addEventListener('click', event => {
  const watchButton = event.target.closest('[data-abnormal-watch]');
  if (watchButton) return addStock(watchButton.dataset.abnormalWatch);
  const scoreButton = event.target.closest('[data-abnormal-score]');
  if (scoreButton) return scoreHubCandidate(scoreButton.dataset.abnormalScore);
  const aiButton = event.target.closest('[data-abnormal-ai]');
  if (aiButton) analyzeStock(aiButton.dataset.abnormalAi, aiButton.dataset.abnormalName);
});
$('#review')?.addEventListener('click', event => {
  if (event.target.closest('[data-retry-daily-review]')) return loadDailyReview();
  const historyItem = event.target.closest('[data-review-history]');
  if (historyItem) {
    const item = state.dailyReviewHistory.find(entry => String(entry.id) === historyItem.dataset.reviewHistory);
    if (item?.payload) renderDailyReview({...item.payload, history: {count: state.dailyReviewHistory.length, latest: state.dailyReviewHistory.slice(0, 6)}});
    return;
  }
  const intelButton = event.target.closest('[data-review-intel]');
  if (intelButton) return openReviewIntelDrawer(intelButton.dataset.reviewIntel);
  const aiButton = event.target.closest('[data-review-ai]');
  if (aiButton) return analyzeStock(aiButton.dataset.reviewAi, aiButton.dataset.reviewName);
  const watchButton = event.target.closest('[data-review-watch]');
  if (watchButton) return addStock(watchButton.dataset.reviewWatch);
  const scoreButton = event.target.closest('[data-review-score]');
  if (scoreButton) return scoreHubCandidate(scoreButton.dataset.reviewScore);
  const trackButton = event.target.closest('[data-review-track]');
  if (trackButton) return trackRecommendation(trackButton.dataset.reviewTrack);
});
$('#reviewIntelDrawerBody')?.addEventListener('click', event => {
  const aiButton = event.target.closest('[data-review-drawer-ai]');
  if (aiButton) return analyzeStock(aiButton.dataset.reviewDrawerAi, aiButton.dataset.reviewDrawerName);
  const watchButton = event.target.closest('[data-review-watch]');
  if (watchButton) return addStock(watchButton.dataset.reviewWatch);
});
$('#industryChainResult')?.addEventListener('click', event => {
  const historyItem = event.target.closest('[data-chain-history]');
  if (historyItem) {
    const item = state.industryChainReports.find(entry => String(entry.id) === historyItem.dataset.chainHistory);
    if (item) renderIndustryChainReport({...item.payload, created_at: item.created_at});
    return;
  }
  const scoreButton = event.target.closest('[data-chain-score]');
  if (scoreButton) return scoreHubCandidate(scoreButton.dataset.chainScore);
  const watchButton = event.target.closest('[data-chain-watch]');
  if (watchButton) return addStock(watchButton.dataset.chainWatch);
  const aiButton = event.target.closest('[data-chain-ai]');
  if (aiButton) analyzeStock(aiButton.dataset.chainAi, aiButton.dataset.chainName);
});
$('#aiModalBody')?.addEventListener('click', event => {
  const button = event.target.closest('[data-modal-ai]');
  if (button) analyzeStock(button.dataset.modalAi, button.dataset.modalName);
  const refresh = event.target.closest('[data-resonance-refresh]');
  if (refresh) return loadResonancePanel(refresh.dataset.resonanceRefresh);
  const indicator = event.target.closest('[data-resonance-indicator]');
  if (indicator) {
    indicator.classList.toggle('active');
    indicator.classList.toggle('muted');
    const panel = indicator.closest('[data-resonance-code]');
    if (!panel) return;
    const disabled = [...panel.querySelectorAll('[data-resonance-indicator].muted')].map(item => item.dataset.resonanceIndicator).join(',');
    loadResonancePanel(panel.dataset.resonanceCode, disabled).catch(error => pushEvent(`指标共振刷新失败：${error.message || error}`, 'warn'));
  }
});
$('#aiWorkbenchResult')?.addEventListener('click', event => {
  const item = event.target.closest('[data-ai-report-id]');
  if (!item) return;
  const report = state.aiReports.find(entry => String(entry.id) === item.dataset.aiReportId);
  if (report) {
    state.lastAiResult = report.result;
    renderAiAnalysis(`${report.stock_name} 历史 AI 分析`, report.result, '#aiWorkbenchResult', false);
  }
});
$('#research')?.addEventListener('click', event => {
  const button = event.target.closest('[data-strategy-prompt]');
  if (button) copyStrategyPrompt(button.dataset.strategyPrompt);
});
document.addEventListener('click', event => {
  if (!event.target.closest('.search')) $('#suggestions').style.display = 'none';
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden || !state.currentUser) return;
  const lastUpdated = Date.parse(state.mobileDashboard?.updated_at || '');
  if (!lastUpdated || Date.now() - lastUpdated > 90_000) {
    loadMobileDashboard().catch(() => {});
  }
});
$('#loginForm')?.addEventListener('submit', login);
$('#registerForm')?.addEventListener('submit', registerByPhone);
$('#showRegisterForm')?.addEventListener('click', () => {
  $('#loginForm')?.classList.add('hidden');
  $('#registerForm')?.classList.remove('hidden');
  $('#registerError').textContent = '';
});
$('#backToLogin')?.addEventListener('click', () => {
  $('#registerForm')?.classList.add('hidden');
  $('#loginForm')?.classList.remove('hidden');
  $('#loginError').textContent = '';
});

setInterval(setClock, 1000);
setInterval(() => {
  if (state.currentUser && !window.matchMedia('(max-width: 820px)').matches) loadAll();
}, 10000);
setClock();
applyReviewTheme(state.reviewTheme);
syncMobileNavigation('dashboard');
initAuth();


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
    const data = await apiJson('/api/eastmoney-ai/hotspot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: query || '今日热点', type, limit }),
    });
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
    const data = await apiJson('/api/eastmoney-ai/stock-analysis', {
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
    const data = await apiJson('/api/eastmoney-ai/chat', {
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
  html += `<div class="qa-answer"><b>A:</b> ${escapeHtml(String(answer)).replace(/\n/g, '<br>')}</div>`;
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

