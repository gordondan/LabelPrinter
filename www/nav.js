(function(){
  function currentPath(){ return window.location.pathname || '/'; }
  function isActive(href){
    try { return new URL(href, window.location.origin).pathname === currentPath(); }
    catch { return false; }
  }

  function renderHeader(){
    const header = document.createElement('header');
    header.className = 'site-header';
    header.innerHTML = `
      <div class="inner">
        <a class="site-brand" href="/">Label Printer</a>
        <nav class="site-nav">
          <a href="/" data-nav>Home <span class="nav-hotkey">(h)</span></a>
          <a href="/custom-label.html" data-nav>Custom Label <span class="nav-hotkey">(c)</span></a>
          <a href="/recent.html" data-nav>Recent <span class="nav-hotkey">(r)</span></a>
        </nav>
      </div>`;

  document.body.prepend(header);
  document.body.classList.add('has-site-header');

    // Set active link
    document.querySelectorAll('[data-nav]').forEach(a => {
      if (isActive(a.getAttribute('href'))) a.classList.add('active');
    });

    // Global hotkeys for top nav
    const navMap = {
      'h': '/',
      'c': '/custom-label.html',
      'r': '/recent.html',
    };
    document.addEventListener('keydown', (ev) => {
      // Ignore when typing in inputs or editable elements
      const t = ev.target;
      if (t && ((t.tagName === 'INPUT') || (t.tagName === 'TEXTAREA') || (t.isContentEditable))) return;
      if (!ev.key || ev.key.length !== 1) return;
      const k = ev.key.toLowerCase();
      const href = navMap[k];
      if (!href) return;
      ev.preventDefault();
      window.location.href = href;
    }, { passive: false });
  }

  window.renderSiteHeader = renderHeader;
})();
