(function(){
  // figure out initial theme
  const stored = localStorage.getItem('theme');
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = stored || (prefersDark ? 'dark' : 'light');

  setTheme(theme);

  // wire any button with id="btn-theme" (supports both pages)
  window.addEventListener('DOMContentLoaded', ()=>{
    const btns = document.querySelectorAll('#btn-theme');
    btns.forEach(btn=>{
      btn.addEventListener('click', ()=>{
        const next = (document.documentElement.dataset.theme === 'dark') ? 'light' : 'dark';
        setTheme(next);
      });
      refreshLabel(btn);
    });
  });

  function setTheme(t){
    document.documentElement.dataset.theme = t;
    localStorage.setItem('theme', t);
    document.querySelectorAll('#btn-theme').forEach(refreshLabel);
  }

  function refreshLabel(btn){
    const t = document.documentElement.dataset.theme;
    btn.setAttribute('aria-pressed', t === 'dark' ? 'true' : 'false');
    btn.textContent = (t === 'dark') ? '☀️ Light' : '🌙 Dark';
  }
})();
