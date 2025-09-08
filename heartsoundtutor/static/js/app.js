(async function () {
  const els = {
    chat: document.getElementById('chat'),
    title: document.getElementById('case-title'),
    form: document.getElementById('chat-form'),
    input: document.getElementById('chat-input'),
    random: document.getElementById('btn-random'),
    filter: document.getElementById('chk-filter'),
    lists: {
      systolic: document.getElementById('list-systolic'),
      diastolic: document.getElementById('list-diastolic'),
      congenital: document.getElementById('list-congenital'),
      extra: document.getElementById('list-extra')
    }
  };

  // Load catalog
  let items = [];
  try {
    const resp = await fetch('/static/data/murmurs.json?v=' + Date.now());
    const data = await resp.json();
    items = data.items || [];
  } catch (e) {
    console.error('Failed to load murmurs.json', e);
  }

  // Build a catalog row
  function row(item) {
    const li = document.createElement('li');
    li.className = 'item';
    li.innerHTML = `
      <div class="meta">
        <div><strong>${item.title}</strong></div>
        <div class="buzz">${item.buzz.join(' • ')}</div>
      </div>
      <div class="btns">
        <button data-act="start" title="Start guided case">Start</button>
      </div>`;
    li.querySelector('[data-act="start"]').onclick = () => startCase(item);
    return li;
  }
  items.forEach(it => { const b = els.lists[it.cat]; if (b) b.appendChild(row(it)); });

  // Helpers to render chat bubbles
  function bubble(role, html) {
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + role;
    wrap.innerHTML = html;
    els.chat.appendChild(wrap);
    els.chat.scrollTop = els.chat.scrollHeight;
  }
  function bubbleAudio(src) {
    const wrap = document.createElement('div');
    wrap.className = 'msg assistant';
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = src;
    wrap.appendChild(audio);
    els.chat.appendChild(wrap);
    els.chat.scrollTop = els.chat.scrollHeight;
    audio.play().catch(()=>{});
  }

  // State for the current session
  let current = null;          // selected item (title, buzz, teach, file)
  let state = null;            // 'intro' | 'probe' | 'maneuvers' | 'wrap'
  let thread = [];             // [{role:'user'|'assistant', content:'...'}]

  function getPool() {
    if (!els.filter?.checked) return items;
    const checks = Array.from(document.querySelectorAll('.cat-check'));
    const allow = new Set(checks.filter(c=>c.checked).map(c=>c.dataset.cat));
    return items.filter(x => allow.has(x.cat));
  }

  // Start a guided case for an item
  async function startCase(item) {
    current = item;
    state = 'intro';
    thread = [];
    els.chat.innerHTML = '';
    els.title.textContent = item.title;

    // Hit server to get the intro + audio
    const res = await fetch('/case', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ state, item })
    });
    const data = await res.json();
    if (data.error) {
      bubble('assistant', 'Tutor error: ' + data.error);
      return;
    }
    if (data.text) bubble('assistant', data.text);
    if (data.audio) bubbleAudio(data.audio);
    state = data.next_state || 'probe';
  }

  // Random case
  els.random.onclick = () => {
    const pool = getPool();
    if (!pool.length) return;
    const pick = pool[Math.floor(Math.random() * pool.length)];
    startCase(pick);
  };

  // User sends a message (their answer) → ask server for next turn
  if (els.form) {
    els.form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = (els.input.value || '').trim();
      if (!q || !current || !state) return;
      els.input.value = '';
      bubble('user', q);

      const res = await fetch('/case', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          state,
          item: current,
          user_msg: q,
          thread
        })
      });
      const data = await res.json();
      if (data.error) {
        bubble('assistant', 'Tutor error: ' + data.error);
        return;
      }
      if (data.text) bubble('assistant', data.text);
      if (data.audio) bubbleAudio(data.audio);
      state = data.next_state || state;

      // keep a tiny local transcript (for context continuity)
      thread.push({role:'user', content:q});
      if (data.text) thread.push({role:'assistant', content:data.text});
    });
  }
})();
