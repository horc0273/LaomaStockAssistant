/* 盯盘智能体对话面板 v5（独立模块，依赖全局 $） */
(function () {
  const agentState = { busy: false, history: [], mode: 'single' };
  const QUICK = ['今天大盘怎么样？', '我的持仓要注意什么？', '今天有什么异动？', '帮我复盘今天'];

  const $ = (sel) => document.querySelector(sel);

  function esc(text) {
    return String(text == null ? '' : text)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmt(text) {
    return esc(text).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
  }

  function scrollBottom() {
    const box = $('#agentMessages');
    if (box) box.scrollTop = box.scrollHeight;
  }

  function addMsg(role, html) {
    const box = $('#agentMessages');
    if (!box) return null;
    const item = document.createElement('div');
    item.className = 'agent-msg agent-msg-' + role;
    item.innerHTML = html;
    box.appendChild(item);
    scrollBottom();
    return item;
  }

  function verdictClass(v) {
    if (v === '看多') return 'bull';
    if (v === '看空') return 'bear';
    return 'neutral';
  }

  function renderExpertCard(exp, beforeEl) {
    const box = $('#agentMessages');
    if (!box) return;
    const card = document.createElement('div');
    card.className = 'agent-expert agent-expert-' + verdictClass(exp.verdict);
    const badge = exp.ok
      ? '<span class="agent-expert-verdict">' + esc(exp.verdict) + ' ' + (exp.confidence || 0) + '</span>'
      : '<span class="agent-expert-verdict agent-expert-fail">分析失败</span>';
    const body = exp.opinion ? fmt(exp.opinion) : esc(exp.core || '');
    card.innerHTML =
      '<div class="agent-expert-head"><span class="agent-expert-emoji">' + esc(exp.emoji || '🔍') + '</span>' +
      '<span class="agent-expert-name">' + esc(exp.name) + '</span>' + badge + '</div>' +
      '<div class="agent-expert-body">' + body + '</div>';
    if (beforeEl && beforeEl.parentNode === box) box.insertBefore(card, beforeEl);
    else box.appendChild(card);
    scrollBottom();
  }

  function renderQuick() {
    const box = $('#agentQuick');
    if (!box) return;
    box.innerHTML = QUICK.map(function (q) {
      return '<button type="button" data-agent-quick="' + esc(q) + '">' + esc(q) + '</button>';
    }).join('');
  }

  function updateModeUI() {
    const btn = $('#agentDebateToggle');
    if (!btn) return;
    const on = agentState.mode === 'debate';
    btn.classList.toggle('active', on);
    btn.textContent = on ? '🎯 多专家博弈：开' : '🎯 多专家博弈';
    const input = $('#agentInput');
    if (input) input.placeholder = on
      ? '如：600519 现在还能拿吗？（4 位专家并行会诊）'
      : '问我任何盯盘问题，如：我的持仓要注意什么？';
  }

  async function send(text) {
    text = (text || '').trim();
    if (!text || agentState.busy) return;
    const input = $('#agentInput');
    if (input) input.value = '';
    addMsg('user', fmt(text));
    const bubble = addMsg('assistant', '<span class="agent-typing">思考中…</span>');
    agentState.busy = true;
    const sendBtn = $('#agentSend');
    if (sendBtn) sendBtn.disabled = true;
    let answer = '';
    let lastStatus = '思考中…';
    try {
      const resp = await fetch('/api/stock-agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: agentState.history, mode: agentState.mode }),
      });
      if (!resp.ok || !resp.body) throw new Error('HTTP ' + resp.status);
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buf += decoder.decode(chunk.value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        lines.forEach(function (line) {
          if (!line.trim()) return;
          let evt;
          try { evt = JSON.parse(line); } catch (e) { return; }
          if (evt.type === 'status') lastStatus = evt.text || lastStatus;
          else if (evt.type === 'expert_done') renderExpertCard(evt, bubble);
          else if (evt.type === 'answer') answer = evt.text || answer;
          else if (evt.type === 'error') answer = (answer ? answer + '\n' : '') + '⚠️ ' + (evt.text || '出错了');
        });
        if (bubble) {
          bubble.innerHTML = answer
            ? fmt(answer)
            : '<span class="agent-typing">' + esc(lastStatus) + '</span>';
          scrollBottom();
        }
      }
    } catch (err) {
      if (bubble) bubble.innerHTML = '⚠️ 连接失败：' + esc(err.message) + '<br>请稍后重试';
    } finally {
      agentState.busy = false;
      if (sendBtn) sendBtn.disabled = false;
      if (answer) {
        agentState.history.push({ role: 'user', content: text });
        agentState.history.push({ role: 'assistant', content: answer });
        if (agentState.history.length > 12) agentState.history.splice(0, agentState.history.length - 12);
      }
      const input2 = $('#agentInput');
      if (input2) input2.focus();
    }
  }

  function toggle(open) {
    const panel = $('#agentPanel');
    const fab = $('#agentFab');
    if (!panel || !fab) return;
    const willOpen = typeof open === 'boolean' ? open : panel.hidden;
    panel.hidden = !willOpen;
    fab.classList.toggle('active', willOpen);
    if (willOpen) {
      const box = $('#agentMessages');
      if (box && !box.querySelector('.agent-msg')) {
        addMsg('assistant', fmt('老马你好！我是盯盘智能体 🐎\n你直接问，我自己去查行情、持仓、异动这些真实数据再回答，绝不瞎编。\n想要更深度的分析，点右上角「🎯 多专家博弈」，我会召集舆情/技术/资金/风控 4 位专家并行会诊并多空辩论。\n试试下面的快捷问题 👇'));
      }
      renderQuick();
      updateModeUI();
      const input = $('#agentInput');
      if (input) input.focus();
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    const fab = $('#agentFab');
    if (!fab) return;
    fab.addEventListener('click', function () { toggle(); });
    $('#agentClose').addEventListener('click', function () { toggle(false); });
    $('#agentDebateToggle').addEventListener('click', function () {
      agentState.mode = agentState.mode === 'debate' ? 'single' : 'debate';
      updateModeUI();
    });
    $('#agentSend').addEventListener('click', function () { send($('#agentInput').value); });
    $('#agentInput').addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); send(event.target.value); }
    });
    $('#agentQuick').addEventListener('click', function (event) {
      const btn = event.target.closest('[data-agent-quick]');
      if (btn) send(btn.dataset.agentQuick);
    });
  });
})();
