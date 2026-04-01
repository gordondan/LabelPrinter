(function(){
  // --- Data-driven label sizes ---
  // To add a new size: append an entry here and it appears in the dropdown automatically.
  // The 'id' is sent to the backend as the label_size parameter.
  // For circle labels, set shape:'circle' to get a round preview.
  const LABEL_SIZES = [
    { id: '1x3',       width: 3,    height: 1,    label: '3" \u00d7 1"',       default: true },
    { id: '2.25x1',    width: 2.25, height: 1,    label: '2.25" \u00d7 1"' },
    { id: '2.25x1.25', width: 2.25, height: 1.25, label: '2.25" \u00d7 1.25"' },
    { id: '2x2',       width: 2,    height: 2,    label: '2" Circle',          shape: 'circle' },
    { id: '4x6',       width: 4,    height: 6,    label: '4" \u00d7 6"' },
  ];

  function currentPath(){ return window.location.pathname || '/'; }
  function isActive(href){
    try {
      const targetPath = new URL(href, window.location.origin).pathname;
      const current = currentPath();
      if (href === '/' && (current === '/' || current === '/custom-label.html' || current === '/index.html')) return true;
      return targetPath === current;
    }
    catch { return false; }
  }

  function buildSizeOptions() {
    let html = '';
    for (const s of LABEL_SIZES) {
      const sel = s.default ? ' selected' : '';
      const shape = s.shape ? ` data-shape="${s.shape}"` : '';
      html += `<option value="${s.id}" data-width="${s.width}" data-height="${s.height}"${shape}${sel}>${s.label}</option>`;
    }
    html += '<option value="custom">Custom\u2026</option>';
    return html;
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
          <select id="label-size-select">${buildSizeOptions()}</select>
          <div id="custom-size-inputs" class="custom-size-inputs" style="display:none;">
            <input type="number" id="custom-width" min="0.5" max="12" step="0.25" value="3" aria-label="Width (inches)">
            <span>\u00d7</span>
            <input type="number" id="custom-height" min="0.5" max="12" step="0.25" value="1" aria-label="Height (inches)">
            <span>"</span>
          </div>
        </div>
      </div>`;

    document.body.prepend(header);
    document.body.classList.add('has-site-header');

    // Add version badge (fixed position bottom-right)
    const versionBadge = document.createElement('div');
    versionBadge.id = 'versionBadge';
    versionBadge.className = 'version-badge';
    versionBadge.textContent = 'v...';
    document.body.appendChild(versionBadge);

    // Fetch and display version
    fetch('/api/version', { cache: 'no-store' })
      .then(r => r.json())
      .then(data => {
        if (data && data.version) {
          versionBadge.textContent = `v${data.version}`;
          versionBadge.title = `Build: ${data.build_date || 'unknown'}`;
        }
      })
      .catch(() => {
        versionBadge.textContent = 'v?';
      });

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
          jobsTimer = setInterval(refreshJobs, 15000);
        }
      }catch{}
    }
    refreshJobs();
    window.bumpJobsBadge = () => { try { refreshJobs(); } catch{} };

    // --- Label size selector logic ---
    const labelSelect = document.getElementById('label-size-select');
    const customInputs = document.getElementById('custom-size-inputs');
    const customW = document.getElementById('custom-width');
    const customH = document.getElementById('custom-height');

    function showHideCustomInputs() {
      customInputs.style.display = labelSelect.value === 'custom' ? 'flex' : 'none';
    }

    // Expose function to get selected label size (returns id string or custom WxH)
    window.getSelectedLabelSize = () => {
      if (labelSelect.value === 'custom') {
        const w = parseFloat(customW.value) || 3;
        const h = parseFloat(customH.value) || 1;
        return `${w}x${h}`;
      }
      return labelSelect.value || '1x3';
    };

    // Expose function to get label dimensions (width, height in inches)
    window.getSelectedLabelDimensions = () => {
      if (labelSelect.value === 'custom') {
        return {
          width: parseFloat(customW.value) || 3,
          height: parseFloat(customH.value) || 1,
          shape: null
        };
      }
      const option = labelSelect.options[labelSelect.selectedIndex];
      return {
        width: parseFloat(option.dataset.width) || 3,
        height: parseFloat(option.dataset.height) || 1,
        shape: option.dataset.shape || null
      };
    };

    // Expose the sizes list for external consumers
    window.LABEL_SIZES = LABEL_SIZES;

    // Set label size programmatically (used by query param handling)
    window.setLabelSize = (sizeId) => {
      // Check if it's a known preset
      const presetOption = labelSelect.querySelector(`option[value="${sizeId}"]`);
      if (presetOption && sizeId !== 'custom') {
        labelSelect.value = sizeId;
      } else {
        // Try parsing as custom WxH
        const parts = sizeId.split('x');
        if (parts.length === 2) {
          const w = parseFloat(parts[0]);
          const h = parseFloat(parts[1]);
          if (!isNaN(w) && !isNaN(h)) {
            labelSelect.value = 'custom';
            customW.value = w;
            customH.value = h;
          }
        }
      }
      showHideCustomInputs();
      fireChange();
    };

    function fireChange() {
      window.dispatchEvent(new CustomEvent('labelsizechange', {
        detail: window.getSelectedLabelDimensions()
      }));
    }

    labelSelect.addEventListener('change', () => {
      showHideCustomInputs();
      fireChange();
    });

    // Fire change when custom dimensions change
    customW.addEventListener('input', fireChange);
    customH.addEventListener('input', fireChange);

    showHideCustomInputs();
  }

  window.renderSiteHeader = renderHeader;
})();
