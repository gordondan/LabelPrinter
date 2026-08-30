(function(){
  // --- Data-driven label sizes ---
  const LABEL_SIZES = [
    { id: '1x3',       width: 3,    height: 1,    label: '3\u2033 \u00d7 1\u2033',       default: true },
    { id: '2.25x1',    width: 2.25, height: 1,    label: '2.25\u2033 \u00d7 1\u2033' },
    { id: '2.25x1.25', width: 2.25, height: 1.25, label: '2.25\u2033 \u00d7 1.25\u2033' },
    { id: '2x2',       width: 2,    height: 2,    label: '2\u2033 Circle',          shape: 'circle' },
    { id: '4x6',       width: 4,    height: 6,    label: '4\u2033 \u00d7 6\u2033' },
  ];
  window.LABEL_SIZES = LABEL_SIZES;

  function currentPath(){ return window.location.pathname || '/'; }
  function isActive(href){
    try {
      const targetPath = new URL(href, window.location.origin).pathname;
      const current = currentPath();
      if (href === '/' && (current === '/' || current === '/index.html')) return true;
      return targetPath === current;
    } catch { return false; }
  }

  function renderHeader(){
    // --- Top header ---
    const header = document.createElement('header');
    header.className = 'site-header';
    header.innerHTML = `
      <div class="inner">
        <button class="mobile-menu-toggle" aria-label="Toggle menu" aria-expanded="false">
          <span class="hamburger"></span>
        </button>
        <a class="site-brand" href="/">Label Pro <span id="jobsBadge" class="jobs-badge" style="display:none;"></span></a>
        <div class="header-right">
          <svg class="header-icon" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 00-16 0"/>
          </svg>
        </div>
      </div>`;
    document.body.prepend(header);
    document.body.classList.add('has-site-header');

    // Mobile menu (hidden by default, only for non-tab links)
    const menuToggle = header.querySelector('.mobile-menu-toggle');
    // No dropdown menu in new design — hamburger reserved for future use
    menuToggle.style.visibility = 'visible';

    // --- Bottom tab bar ---
    const tabs = document.createElement('nav');
    tabs.className = 'bottom-tabs';
    tabs.innerHTML = `
      <a href="/" class="tab" data-nav>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="4" y1="6" x2="16" y2="6"/><line x1="8" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="16" y2="18"/>
          <circle cx="19" cy="6" r="2" fill="currentColor"/><circle cx="5" cy="12" r="2" fill="currentColor"/><circle cx="19" cy="18" r="2" fill="currentColor"/>
        </svg>
        <span>Create</span>
      </a>
      <a href="/recent" class="tab" data-nav>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        <span>Recent</span>
      </a>
      <a href="/batch" class="tab" data-nav>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 3v18"/>
        </svg>
        <span>Batch</span>
      </a>`;
    document.body.appendChild(tabs);

    // Set active tab
    tabs.querySelectorAll('[data-nav]').forEach(a => {
      if (isActive(a.getAttribute('href'))) a.classList.add('active');
    });
    header.querySelectorAll('[data-nav]').forEach(a => {
      if (isActive(a.getAttribute('href'))) a.classList.add('active');
    });

    // --- Version badge ---
    const versionBadge = document.createElement('div');
    versionBadge.id = 'versionBadge';
    versionBadge.className = 'version-badge';
    versionBadge.textContent = 'v...';
    document.body.appendChild(versionBadge);

    fetch('/api/version', { cache: 'no-store' })
      .then(r => r.json())
      .then(data => {
        if (data && data.version) {
          versionBadge.textContent = `v${data.version}`;
          versionBadge.title = `Build: ${data.build_date || 'unknown'}`;
        }
      })
      .catch(() => { versionBadge.textContent = 'v?'; });

    // --- Global hotkeys ---
    const navMap = { 'c': '/', 'r': '/recent', 'b': '/batch' };
    document.addEventListener('keydown', (ev) => {
      const t = ev.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
      if (!ev.key || ev.key.length !== 1) return;
      const href = navMap[ev.key.toLowerCase()];
      if (!href) return;
      ev.preventDefault();
      window.location.href = href;
    }, { passive: false });

    // --- Job badge polling ---
    const badge = header.querySelector('#jobsBadge');
    let jobsTimer = null;
    async function refreshJobs(){
      try {
        const r = await fetch('/api/jobs/counts', { cache: 'no-store' });
        const j = await r.json();
        const queued = parseInt(j.queued, 10) || 0;
        const running = parseInt(j.running, 10) || 0;
        if (!queued && !running){
          badge.textContent = '';
          badge.style.display = 'none';
          if (jobsTimer){ clearInterval(jobsTimer); jobsTimer = null; }
          return;
        }
        let parts = [];
        if (queued > 0) parts.push(`${queued} queued`);
        if (running > 0) parts.push(`${running} running`);
        badge.textContent = parts.join(' ');
        badge.style.display = '';
        if (!jobsTimer) jobsTimer = setInterval(refreshJobs, 15000);
      } catch {}
    }
    refreshJobs();
    window.bumpJobsBadge = () => { try { refreshJobs(); } catch{} };
  }

  window.renderSiteHeader = renderHeader;
})();
