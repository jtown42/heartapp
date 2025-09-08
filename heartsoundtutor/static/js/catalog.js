(async function () {
  const els = {
    random: document.getElementById('btn-random'),
    filter: document.getElementById('chk-filter'),
    lists: {
      systolic: document.getElementById('list-systolic'),
      diastolic: document.getElementById('list-diastolic'),
      congenital: document.getElementById('list-congenital'),
      extra: document.getElementById('list-extra')
    }
  };

  let items = [];
  try {
    const resp = await fetch('/static/data/murmurs.json?v=' + Date.now());
    const data = await resp.json();
    items = data.items || [];
  } catch (e) { console.error('Failed to load murmurs.json', e); }

  function ensureId(it, idx) {
    if (it.id) return it.id;
    return (it.title || ('item_'+idx)).toLowerCase().replace(/[^a-z0-9]+/g,'-');
  }

  function row(item, idx) {
    const id = ensureId(item, idx);
    const li = document.createElement('li');
    li.className = 'item';
    li.innerHTML = `
      <div class="meta">
        <div><strong>${item.title}</strong></div>
        <div class="buzz">${item.buzz.join(' • ')}</div>
      </div>
      <div class="btns">
        <a href="/case/${id}"><button class="btn-primary">Start</button></a>
      </div>`;
    return li;
  }

  items.forEach((it, i) => {
    const bucket = els.lists[it.cat];
    if (bucket) bucket.appendChild(row(it, i));
  });

  function getPool() {
    if (!els.filter?.checked) return items;
    const checks = Array.from(document.querySelectorAll('.cat-check'));
    const allow = new Set(checks.filter(c=>c.checked).map(c=>c.dataset.cat));
    return items.filter(x => allow.has(x.cat));
  }

  if (els.random) {
    els.random.onclick = (e) => {
      e.preventDefault();
      const pool = getPool();
      if (!pool.length) return;
      const item = pool[Math.floor(Math.random() * pool.length)];
      const id = item.id || item.title.toLowerCase().replace(/[^a-z0-9]+/g,'-');
      window.location.href = `/case/${id}?blind=1`;
    };
  }
})();
