// docs/static/js/case.js
(async function () {
  // URL bits
  const parts = location.pathname.split('/');
  const itemId = parts[parts.length - 1];
  const params = new URLSearchParams(location.search);
  const blind = params.get('blind') === '1';  // quiz mode only when coming from Random

  // DOM
  const chat = document.getElementById('chat');
  const titleEl = document.getElementById('case-title');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const hintBtnTop = document.getElementById('btn-hint');   // top bar
  const revealBtnTop = document.getElementById('btn-reveal');
  const nextBtnTop = document.getElementById('btn-next');

  // helpers
  function bubble(role, html) {
    const wrap = document.createElement('div');
    wrap.className = 'msg ' + role;
    wrap.innerHTML = html;
    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
    return wrap;
  }
  function bubbleAudio(src) {
    const wrap = document.createElement('div');
    wrap.className = 'msg assistant';
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = src;
    wrap.appendChild(audio);
    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
    audio.play().catch(()=>{});
    return wrap;
  }
  function slug(s){return (s||'').toLowerCase().replace(/[^a-z0-9]+/g,'-')}

  // Detect server mode
  let isMock = false;
  try {
    const h = await fetch('/health').then(r=>r.json());
    isMock = (h && h.ai_mode === 'mock');
  } catch (_) {}

  // load item + all items (for next random)
  let item = null, allItems = [];
  try {
    const resp = await fetch('/static/data/murmurs.json?v=' + Date.now());
    const data = await resp.json();
    allItems = (data.items || []);
    item = allItems.find(it => (it.id || '').toLowerCase() === itemId.toLowerCase())
        || allItems.find(it => (it.title||'').toLowerCase().replace(/[^a-z0-9]+/g,'-') === itemId.toLowerCase());
  } catch (e) { console.error(e); }

  if (!item) {
    bubble('assistant', 'Could not find that case. <a href="/">Go back to catalog</a>.');
    if (titleEl) titleEl.textContent = 'Case not found';
    form?.remove();
    return;
  }

  const trueTitle = item.title || 'Unknown murmur';

  // choose audio variant (if provided)
  const variants = Array.isArray(item.files) && item.files.length
    ? item.files.slice()
    : (item.file ? [item.file] : []);
  let chosenIdx = variants.length ? Math.floor(Math.random() * variants.length) : 0;
  let chosenFile = variants.length ? variants[chosenIdx] : null;

  // Title behavior
  titleEl.textContent = blind ? 'Identify the murmur' : trueTitle;

  // flow state + MCQ counters
  let state = 'intro';
  let attempts = 0;
  let hintLevel = 0;

  // In MOCK mode we hide the chat input; live mode may still use it
  if (isMock && form) form.style.display = 'none';

  // Choices currently on screen
  let currentChoices = null;

  // ---- local controls row (for quiz mode) ----
  function makeInlineControls(){
    const row = document.createElement('div');
    row.style.marginTop = '.5rem';
    row.style.display = 'flex';
    row.style.flexWrap = 'wrap';
    row.style.gap = '.5rem';

    const hint = document.createElement('button');
    hint.className = 'ghost';
    hint.textContent = 'Hint';

    const reveal = document.createElement('button');
    reveal.className = 'btn-primary';
    reveal.textContent = 'Reveal answer';

    const next = document.createElement('button');
    next.className = 'ghost';
    next.textContent = 'Next random';

    row.appendChild(hint);
    row.appendChild(reveal);
    row.appendChild(next);
    return {row, hint, reveal, next};
  }

  // Render MCQ buttons bubble (replaces previous choices bubble)
  function renderChoices(choices) {
    currentChoices = choices;
    if (!choices || !choices.length) return;

    // Remove any previous choices bubble to avoid stacking
    const old = chat.querySelector('.msg.assistant[data-choices="1"]');
    if (old) old.remove();

    const wrap = document.createElement('div');
    wrap.className = 'msg assistant';
    wrap.dataset.choices = '1';

    const box = document.createElement('div');
    box.style.display = 'grid';
    box.style.gridTemplateColumns = '1fr 1fr';
    box.style.gap = '.5rem';

    // Buttons A–D
    choices.forEach(opt => {
      const btn = document.createElement('button');
      btn.className = 'btn-primary';
      btn.textContent = `${opt.key}. ${opt.label}`;
      btn.style.textAlign = 'left';
      btn.onclick = async (e) => {
        e.preventDefault();
        const next = await turn({ state, user_msg: `choice ${opt.key}`, choice_key: opt.key });
        afterTurn(next);
      };
      box.appendChild(btn);
    });

    wrap.appendChild(box);

    // Inline controls (Hint / Reveal / Next) right under choices
    const controls = makeInlineControls();
    wrap.appendChild(controls.row);

    // Wire inline Hint
    controls.hint.onclick = async (e)=>{
      e.preventDefault();
      const next = await turn({ state, user_msg: 'hint' });
      afterTurn(next);
    };

    // Wire inline Reveal
    controls.reveal.onclick = async (e)=>{
      e.preventDefault();
      const next = await turn({ state, user_msg: 'reveal' });
      afterTurn(next);
    };

    // Wire inline Next random
    controls.next.onclick = (e)=>{
      e.preventDefault();
      if (!allItems.length) return;
      const rand = allItems[Math.floor(Math.random() * allItems.length)];
      const id = (rand.id || slug(rand.title));
      location.href = `/case/${id}?blind=1`;
    };

    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
  }

  // server turn helper (allows overriding first audio variant)
  async function turn(payload, opts = {}) {
    const res = await fetch('/case_api', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        ...payload,
        item: opts.overrideFile ? { ...item, file: opts.overrideFile } : item,
        attempts,
        hint_level: hintLevel
      })
    });
    const data = await res.json();
    if (data.error) { bubble('assistant', 'Tutor error: ' + data.error); return null; }

    // Non-random mode: ignore any MCQ the server might send
    if (!blind && Array.isArray(data.choices)) {
      delete data.choices;
    }

    if (data.text) bubble('assistant', data.text);
    if (data.audio) bubbleAudio(data.audio);
    if (blind && Array.isArray(data.choices)) renderChoices(data.choices);

    // sync counters/state if server returned them
    if (Number.isInteger(data.attempts)) attempts = data.attempts;
    if (Number.isInteger(data.hint_level)) hintLevel = data.hint_level;
    return data;
  }

  // Process a server response uniformly
  function afterTurn(next) {
    if (!next) return;
    if (next.next_state) state = next.next_state;

    // If we were blind and we reached wrap (correct or reveal), show title + more examples
    if (state === 'wrap' && blind) {
      titleEl.textContent = trueTitle;
      showMoreExamples();
      const old = chat.querySelector('.msg.assistant[data-choices="1"]');
      if (old) old.remove();
    }
  }

  // -------- First turn: play audio (always), then mode-specific behavior --------
  const first = await turn({ state }, { overrideFile: chosenFile });
  afterTurn(first);

  if (!blind) {
    // Non-random mode: hide top Hint & Reveal (no quiz), and automatically reveal teaching
    if (hintBtnTop) hintBtnTop.style.display = 'none';
    if (revealBtnTop) revealBtnTop.style.display = 'none';

    // Immediately fetch the explanation card so it appears right under the audio
    const revealed = await turn({ state, user_msg: 'reveal' });
    afterTurn(revealed);

    // Optionally show more audio examples if present
    showMoreExamples();
  } else {
    // Quiz mode: move buttons near choices; hide top versions
    if (hintBtnTop) hintBtnTop.style.display = 'none';
    if (revealBtnTop) revealBtnTop.style.display = 'none';
    if (nextBtnTop) nextBtnTop.style.display = 'none';
  }

  // show more examples (other variants) — used on wrap in quiz mode or immediately in non-random
  function showMoreExamples() {
    if (!variants.length) return;
    const rest = variants.filter((_, idx) => idx !== chosenIdx);
    if (!rest.length) return;

    const wrap = document.createElement('div');
    wrap.className = 'msg assistant';
    const h = document.createElement('div');
    h.innerHTML = '<strong>More examples of the same murmur</strong>';
    wrap.appendChild(h);

    rest.forEach(src => {
      const row = document.createElement('div');
      row.style.marginTop = '6px';
      const audio = document.createElement('audio');
      audio.controls = true;
      audio.src = src;
      row.appendChild(audio);
      wrap.appendChild(row);
    });

    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
  }

  // Top bar Next random (kept visible in non-random mode)
  if (!blind && nextBtnTop) {
    nextBtnTop.onclick = (e)=>{
      e.preventDefault();
      if (!allItems.length) return;
      const rand = allItems[Math.floor(Math.random() * allItems.length)];
      const id = (rand.id || slug(rand.title));
      location.href = `/case/${id}?blind=1`;
    };
  }

  // Text input submit (live mode only; mock hides the form)
  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const q = (input.value || '').trim();
    if (!q) return;
    input.value = '';
    bubble('user', q);
    const next = await turn({ state, user_msg: q });
    afterTurn(next);
  });

  // MOCK badge if applicable
  if (isMock) {
    const tag = document.createElement('div');
    tag.textContent = 'MOCK MODE — no API used';
    tag.style = 'position:fixed;top:8px;right:8px;background:#fde68a;border:1px solid #f59e0b;color:#78350f;padding:6px 10px;border-radius:8px;font:12px system-ui;z-index:9999';
    document.body.appendChild(tag);
  }
})();
