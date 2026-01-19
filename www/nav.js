(function(){
  function currentPath(){ return window.location.pathname || '/'; }
  function isActive(href){
    try {
      const targetPath = new URL(href, window.location.origin).pathname;
      const current = currentPath();
      // Handle root path matching for custom-label (now landing page)
      if (href === '/' && (current === '/' || current === '/custom-label.html' || current === '/index.html')) return true;
      return targetPath === current;
    }
    catch { return false; }
  }

  function renderHeader(){
    const header = document.createElement('header');
    header.className = 'site-header';
    header.innerHTML = `
      <div class="inner">
        <a class="site-brand" href="/">Label Printer <span id="jobsBadge" class="jobs-badge" style="display:none;"></span></a>
        <button class="mobile-menu-toggle" aria-label="Toggle menu" aria-expanded="false">
          <span class="hamburger"></span>
        </button>
        <nav class="site-nav">
          <a href="/" data-nav>Create <span class="nav-hotkey">(c)</span></a>
          <a href="/recent.html" data-nav>Recent <span class="nav-hotkey">(r)</span></a>
          <a href="/batch" data-nav class="desktop-only">Batch <span class="nav-hotkey">(b)</span></a>
        </nav>
        <div class="label-size-selector">
          <label for="label-size-select">Size:</label>
          <select id="label-size-select">
            <option value="1x3" data-width="3" data-height="1" selected>3" × 1"</option>
            <option value="2.25x1.25" data-width="2.25" data-height="1.25">2.25" × 1.25"</option>
            <option value="4x6" data-width="4" data-height="6">4" × 6"</option>
          </select>
        </div>
      </div>`;

    document.body.prepend(header);
    document.body.classList.add('has-site-header');

    // Mobile menu toggle
    const menuToggle = header.querySelector('.mobile-menu-toggle');
    const nav = header.querySelector('.site-nav');
    const labelSizeSelector = header.querySelector('.label-size-selector');

    menuToggle.addEventListener('click', () => {
      const isExpanded = menuToggle.getAttribute('aria-expanded') === 'true';
      menuToggle.setAttribute('aria-expanded', !isExpanded);
      nav.classList.toggle('open');
      labelSizeSelector.classList.toggle('open');
    });

    // Close menu when clicking a nav link (mobile)
    nav.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        nav.classList.remove('open');
        labelSizeSelector.classList.remove('open');
        menuToggle.setAttribute('aria-expanded', 'false');
      });
    });

    // Set active link
    document.querySelectorAll('[data-nav]').forEach(a => {
      if (isActive(a.getAttribute('href'))) a.classList.add('active');
    });

    // Global hotkeys for top nav (c = create/home, r = recent, b = batch)
    const navMap = {
      'c': '/',
      'r': '/recent.html',
      'b': '/batch',
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

    // Poll job counts and update header badge
    const badge = header.querySelector('#jobsBadge');
    let jobsTimer = null;
    async function refreshJobs(){
      try{
        const r = await fetch('/api/jobs/counts', { cache: 'no-store' });
        const j = await r.json();
        const queued = (j && typeof j.queued === 'number') ? j.queued : ((j && j.queued) ? parseInt(j.queued, 10) : 0);
        const running = (j && typeof j.running === 'number') ? j.running : ((j && j.running) ? parseInt(j.running, 10) : 0);
        const active = (queued||0) + (running||0);
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
        if (!jobsTimer){
          // Start a slow poll while there is active work
          jobsTimer = setInterval(refreshJobs, 15000);
        }
      }catch{}
    }
    // One immediate refresh on load; interval starts only when active
    refreshJobs();
    // Expose a manual bump so pages can trigger a one-shot refresh when they enqueue work
    window.bumpJobsBadge = () => { try { refreshJobs(); } catch{} };

    // Expose function to get selected label size
    window.getSelectedLabelSize = () => {
      const select = document.getElementById('label-size-select');
      return select ? select.value : '1x3';
    };

    // Expose function to get label dimensions (width, height in inches)
    window.getSelectedLabelDimensions = () => {
      const select = document.getElementById('label-size-select');
      if (!select) return { width: 3, height: 1 };
      const option = select.options[select.selectedIndex];
      return {
        width: parseFloat(option.dataset.width) || 3,
        height: parseFloat(option.dataset.height) || 1
      };
    };

    // Dispatch event when label size changes
    const labelSelect = document.getElementById('label-size-select');
    if (labelSelect) {
      labelSelect.addEventListener('change', () => {
        window.dispatchEvent(new CustomEvent('labelsizechange', {
          detail: window.getSelectedLabelDimensions()
        }));
      });
    }
  }

  window.renderSiteHeader = renderHeader;
})();
