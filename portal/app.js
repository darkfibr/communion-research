/* Phoenix Portal v2 — app.js
 * Pure ES6+. No frameworks. No build step.
 */

const API = {
  auth: 'Bearer Jay4480',
  base: '',

  headers() {
    return {
      'Authorization': this.auth,
      'Content-Type': 'application/json',
    };
  },

  async agents() {
    const r = await fetch(`${this.base}/chat/agents`, { headers: { Authorization: this.auth } });
    return r.json();
  },

  async dm(agent, message, history = [], client_msg_id = '') {
    const r = await fetch(`${this.base}/chat/dm`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ agent, message, history, client_msg_id }),
    });
    return r.json();
  },

  async group(agents, message, history = [], client_msg_id = '') {
    const r = await fetch(`${this.base}/chat/group`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ agents, message, history, client_msg_id }),
    });
    return r.json();
  },

  async broadcast(message, history = [], client_msg_id = '') {
    const r = await fetch(`${this.base}/chat/broadcast`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ message, history, client_msg_id }),
    });
    return r.json();
  },

  async roomMessages() {
    const r = await fetch(`${this.base}/room/messages`, { headers: { Authorization: this.auth } });
    return r.json();
  },

  async roomSay(text) {
    const r = await fetch(`${this.base}/room/say`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ content: text, author: 'mike', type: 'say' }),
    });
    return r.json();
  },

  async roomStatus() {
    const r = await fetch(`${this.base}/room/status`, { headers: { Authorization: this.auth } });
    return r.json();
  },

  async heartbeat(count = 20) {
    const r = await fetch(`${this.base}/chat/heartbeat?count=${count}`, { headers: { Authorization: this.auth } });
    return r.json();
  },

  ttsUrl(agent, text) {
    return `${this.base}/chat/tts?agent=${encodeURIComponent(agent)}&text=${encodeURIComponent(text)}`;
  },

  async status() {
    const r = await fetch(`${this.base}/chat/system/status`, { headers: { Authorization: this.auth } });
    return r.json();
  },
};

/* ── State ── */
const state = {
  mode: localStorage.getItem('phoenix_mode') || 'dm',
  agents: [],
  selected: new Set(),
  messages: [],
  roomMessages: [],
  roomState: null,
  muted: localStorage.getItem('phoenix_muted') === 'true',
  loading: false,
  lastAgent: localStorage.getItem('phoenix_last_agent') || null,
  agentHealth: {}, // agent_id -> {ok: bool, lastError: string, lastOk: timestamp}
  heartbeat: [],
};

/* ── DOM refs ── */
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const els = {
  sidebarAgents: $('#sidebarAgents'),
  mobileAgents: $('#mobileAgents'),
  sidebarModes: $('#sidebarModes'),
  mobileModes: $('#mobileModes'),
  messages: $('#messages'),
  msgInput: $('#msgInput'),
  sendBtn: $('#sendBtn'),
  chatTitle: $('#chatTitle'),
  voiceToggle: $('#voiceToggle'),
  mobileMenu: $('#mobileMenu'),
};

/* ── Markdown-lite ── */
function mdToHtml(text) {
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // code blocks
  html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  // inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/_(.+?)_/g, '<em>$1</em>');
  // links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // line breaks
  html = html.replace(/\n/g, '<br>');

  return html;
}

/* ── Time ── */
function timeAgo(ts) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 10) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtTime(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

/* ── Audio ── */
let currentAudio = null;

function playTTS(agent, text) {
  if (state.muted) return;
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  const a = new Audio(API.ttsUrl(agent, text));
  a.play();
  currentAudio = a;
  a.onended = () => { currentAudio = null; };
}

/* ── Agent health ── */
function setAgentHealth(agentId, ok, error) {
  state.agentHealth[agentId] = {
    ok,
    lastError: error || '',
    lastOk: ok ? Date.now() : (state.agentHealth[agentId]?.lastOk || 0),
  };
  renderAgents();
}

function agentHealthClass(agentId) {
  const h = state.agentHealth[agentId];
  if (!h) return '';
  if (!h.ok) return 'unhealthy';
  if (Date.now() - h.lastOk < 300000) return 'healthy'; // active in last 5 min
  return '';
}

/* ── Render agents ── */
function renderAgents() {
  const chips = state.agents.map((a) => {
    const active = state.selected.has(a.id) ? 'active' : '';
    const offline = a.soul_loaded ? '' : 'offline';
    const health = agentHealthClass(a.id);
    return `
      <div class="agent-chip ${active}" data-id="${a.id}">
        <span class="emoji">${a.emoji}</span>
        <span class="name">${a.display_name}</span>
        <span class="dot ${offline} ${health}"></span>
      </div>`;
  }).join('');

  els.sidebarAgents.innerHTML = chips;
  els.mobileAgents.innerHTML = chips;

  $$('.agent-chip').forEach((chip) => {
    chip.addEventListener('click', () => onAgentClick(chip.dataset.id));
  });
}

function onAgentClick(id) {
  if (state.mode === 'dm') {
    state.selected = new Set([id]);
    state.lastAgent = id;
    localStorage.setItem('phoenix_last_agent', id);
    updateChatTitle();
  } else if (state.mode === 'group') {
    if (state.selected.has(id)) state.selected.delete(id);
    else state.selected.add(id);
  }
  renderAgents();
}

/* ── Mode tabs ── */
function setMode(mode) {
  state.mode = mode;
  localStorage.setItem('phoenix_mode', mode);

  // update tabs
  [...els.sidebarModes.children, ...els.mobileModes.children].forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });

  // selection logic
  if (mode === 'dm') {
    if (!state.selected.size && state.lastAgent) {
      state.selected = new Set([state.lastAgent]);
    } else if (!state.selected.size && state.agents.length) {
      state.selected = new Set([state.agents[0].id]);
      state.lastAgent = state.agents[0].id;
      localStorage.setItem('phoenix_last_agent', state.agents[0].id);
    }
    renderMessages();
  } else if (mode === 'broadcast') {
    state.selected = new Set(state.agents.map((a) => a.id));
    renderMessages();
  } else if (mode === 'group') {
    renderMessages();
  } else if (mode === 'room') {
    state.selected = new Set();
    renderRoomMessages();
    pollRoom(); // immediate poll
  }

  renderAgents();
  updateChatTitle();
}

function updateChatTitle() {
  if (state.mode === 'dm') {
    const id = [...state.selected][0];
    const a = state.agents.find((x) => x.id === id);
    els.chatTitle.innerHTML = a
      ? `<span>${a.emoji}</span> ${a.display_name}`
      : '<span>🕯️</span> Phoenix';
  } else if (state.mode === 'group') {
    const n = state.selected.size;
    els.chatTitle.innerHTML = `<span>👥</span> Group (${n})`;
  } else if (state.mode === 'broadcast') {
    els.chatTitle.innerHTML = `<span>📡</span> Broadcast`;
  } else if (state.mode === 'room') {
    const block = state.roomState?.current_block || 'quiet';
    els.chatTitle.innerHTML = `<span>🏛️</span> Room — ${block}`;
  }
}

/* ── Messages ── */
function pushMessage(msg) {
  state.messages.push(msg);
  if (state.messages.length > 200) state.messages = state.messages.slice(-200);
  if (state.mode !== 'room') {
    renderMessages();
    scrollToBottom();
  }
}

function scrollToBottom() {
  els.messages.scrollTop = els.messages.scrollHeight;
}

function renderMessages() {
  if (state.mode === 'room') {
    renderRoomMessages();
    return;
  }
  if (!state.messages.length) {
    els.messages.innerHTML = '<div class="msg-system">No messages yet</div>';
    return;
  }

  els.messages.innerHTML = state.messages.map((m) => {
    if (m.type === 'system') {
      return `<div class="msg-system">${mdToHtml(m.text)}</div>`;
    }

    const isOwn = m.own;
    const agent = state.agents.find((a) => a.id === m.agent);
    const emoji = agent ? agent.emoji : '🕯️';
    const color = agent ? `style="border-color: var(--${m.agent})"` : '';

    return `
      <div class="msg ${isOwn ? 'own' : ''}" id="msg-${m.id}">
        <div class="avatar" ${color}>${emoji}</div>
        <div>
          <div class="bubble">${mdToHtml(m.text)}</div>
          <div class="meta">
            <span class="agent-name">${m.name}</span>
            <span>${timeAgo(m.time)}</span>
          </div>
          ${!isOwn ? `<div class="actions">
            <button onclick="playTTS('${m.agent}', \`${m.text.replace(/`/g, '\\`')}\`)" title="Speak">🔊</button>
          </div>` : ''}
        </div>
      </div>`;
  }).join('');
}

/* ── Room Messages ── */
function renderRoomMessages() {
  if (!state.roomMessages.length) {
    els.messages.innerHTML = '<div class="msg-system">The room is quiet. Be the first to speak.</div>';
    return;
  }

  const agentMap = {};
  state.agents.forEach((a) => { agentMap[a.id] = a; });

  els.messages.innerHTML = state.roomMessages.map((m) => {
    const agent = agentMap[m.agent];
    const emoji = agent ? agent.emoji : '🕯️';
    const color = agent ? `style="border-color: var(--${m.agent})"` : '';
    const name = agent ? agent.display_name : (m.agent || 'System');
    const ts = m.ts ? fmtTime(m.ts) : '';

    if (m.agent === 'system') {
      return `<div class="msg-system">${mdToHtml(m.text)} <span class="room-time">${ts}</span></div>`;
    }

    return `
      <div class="msg room-msg" id="room-${m.ts}">
        <div class="avatar" ${color}>${emoji}</div>
        <div>
          <div class="bubble">${mdToHtml(m.text)}</div>
          <div class="meta">
            <span class="agent-name">${name}</span>
            <span class="room-time">${ts}</span>
          </div>
        </div>
      </div>`;
  }).join('');
  scrollToBottom();
}

/* ── Typing indicator ── */
function showTyping() {
  const id = 'typing-' + Date.now();
  const el = document.createElement('div');
  el.className = 'typing';
  el.id = id;
  el.innerHTML = '<span></span><span></span><span></span>';
  els.messages.appendChild(el);
  scrollToBottom();
  return id;
}

function hideTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/* ── Send ── */
async function sendMessage() {
  const text = els.msgInput.value.trim();
  if (!text || state.loading) return;

  if (state.mode === 'room') {
    els.msgInput.value = '';
    els.msgInput.style.height = 'auto';
    els.sendBtn.disabled = true;
    state.loading = true;

    const typingId = showTyping();
    try {
      const data = await API.roomSay(text);
      hideTyping(typingId);
      if (data.error) {
        pushMessage({ id: 'm' + Date.now(), agent: 'system', name: 'System', text: `Room error: ${data.error}`, time: Date.now(), own: false, type: 'system' });
      } else {
        await pollRoom();
      }
    } catch (err) {
      hideTyping(typingId);
      pushMessage({ id: 'm' + Date.now(), agent: 'system', name: 'System', text: `Network error: ${err.message}`, time: Date.now(), own: false, type: 'system' });
    }
    state.loading = false;
    els.sendBtn.disabled = false;
    return;
  }

  // Push own message
  pushMessage({
    id: 'm' + Date.now(),
    agent: 'mike',
    name: 'Mike',
    text,
    time: Date.now(),
    own: true,
    type: 'chat',
  });

  els.msgInput.value = '';
  els.msgInput.style.height = 'auto';
  els.sendBtn.disabled = true;
  state.loading = true;

  const history = state.messages.slice(-20).map((m) => ({
    role: m.own ? 'user' : 'assistant',
    content: m.text,
    agent: m.agent,
  }));

  const typingId = showTyping();

  try {
    if (state.mode === 'dm') {
      const agent = [...state.selected][0];
      if (!agent) throw new Error('No agent selected');
      const data = await API.dm(agent, text, history, 'm' + Date.now());
      hideTyping(typingId);

      if (data.error) {
        setAgentHealth(agent, false, data.error);
        pushMessage({ id: 'm' + Date.now(), agent: 'system', name: 'System', text: `${data.display_name || agent} error: ${data.error}`, time: Date.now(), own: false, type: 'system' });
      } else {
        setAgentHealth(agent, true, '');
        pushMessage({
          id: 'm' + Date.now(),
          agent: data.agent,
          name: data.display_name,
          text: data.response,
          time: Date.now(),
          own: false,
          type: 'chat',
        });
      }
    } else if (state.mode === 'group') {
      const agents = [...state.selected];
      if (!agents.length) throw new Error('No agents selected');
      const data = await API.group(agents, text, history, 'm' + Date.now());
      hideTyping(typingId);

      for (const r of data.responses || []) {
        if (r.error) setAgentHealth(r.agent, false, r.error);
        else setAgentHealth(r.agent, true, '');
        pushMessage({
          id: 'm' + Date.now() + '_' + r.agent,
          agent: r.agent,
          name: r.display_name,
          text: r.error ? `${r.display_name} error: ${r.error}` : r.response,
          time: Date.now(),
          own: false,
          type: 'chat',
        });
      }
    } else if (state.mode === 'broadcast') {
      const data = await API.broadcast(text, history, 'm' + Date.now());
      hideTyping(typingId);

      for (const id of Object.keys(data.results || {})) {
        const r = data.results[id];
        if (r.error) setAgentHealth(r.agent, false, r.error);
        else setAgentHealth(r.agent, true, '');
        pushMessage({
          id: 'm' + Date.now() + '_' + r.agent,
          agent: r.agent,
          name: r.display_name,
          text: r.error ? `${r.display_name} error: ${r.error}` : r.response,
          time: Date.now(),
          own: false,
          type: 'chat',
        });
      }
    }
  } catch (err) {
    hideTyping(typingId);
    pushMessage({ id: 'm' + Date.now(), agent: 'system', name: 'System', text: `Network error: ${err.message}`, time: Date.now(), own: false, type: 'system' });
  }

  state.loading = false;
  els.sendBtn.disabled = false;
}

/* ── Polling ── */
async function pollRoom() {
  if (state.mode !== 'room') return;
  try {
    const [msgData, statusData] = await Promise.all([API.roomMessages(), API.roomStatus()]);
    if (msgData.messages) {
      state.roomMessages = msgData.messages;
      renderRoomMessages();
    }
    if (statusData.state) {
      state.roomState = statusData;
      updateChatTitle();
    }
  } catch (err) {
    console.error('Room poll error:', err);
  }
}

async function pollHeartbeat() {
  try {
    const data = await API.heartbeat(20);
    if (data.heartbeat) {
      state.heartbeat = data.heartbeat;
      // Mark agents as healthy if they appear in heartbeat
      data.heartbeat.forEach((h) => {
        const agentId = h.agent;
        if (agentId && state.agentHealth[agentId]?.ok !== false) {
          state.agentHealth[agentId] = { ok: true, lastError: '', lastOk: Date.now() };
        }
      });
      renderAgents();
    }
  } catch (err) {
    console.error('Heartbeat poll error:', err);
  }
}

/* ── Event bindings ── */
els.sendBtn.addEventListener('click', sendMessage);

els.msgInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

els.msgInput.addEventListener('input', () => {
  els.msgInput.style.height = 'auto';
  els.msgInput.style.height = Math.min(els.msgInput.scrollHeight, 120) + 'px';
});

els.voiceToggle.addEventListener('click', () => {
  state.muted = !state.muted;
  localStorage.setItem('phoenix_muted', state.muted);
  els.voiceToggle.classList.toggle('active', !state.muted);
  els.voiceToggle.title = state.muted ? 'Voice muted' : 'Voice on';
});

els.mobileMenu.addEventListener('click', () => {
  document.querySelector('.sidebar').classList.toggle('open');
});

[...els.sidebarModes.children, ...els.mobileModes.children].forEach((btn) => {
  btn.addEventListener('click', () => setMode(btn.dataset.mode));
});

/* ── Init ── */
async function init() {
  els.voiceToggle.classList.toggle('active', !state.muted);

  try {
    const data = await API.agents();
    state.agents = data.agents || [];
    renderAgents();

    // Restore last mode + selection
    setMode(state.mode);

    pushMessage({
      id: 'm0',
      agent: 'system',
      name: 'System',
      text: `Connected. ${state.agents.length} agents online.`,
      time: Date.now(),
      own: false,
      type: 'system',
    });
  } catch (err) {
    pushMessage({
      id: 'm0',
      agent: 'system',
      name: 'System',
      text: `Failed to load agents: ${err.message}`,
      time: Date.now(),
      own: false,
      type: 'system',
    });
  }

  // Start polling loops
  setInterval(() => {
    if (state.mode === 'room') pollRoom();
  }, 5000);

  setInterval(pollHeartbeat, 30000); // every 30s
}

init();
