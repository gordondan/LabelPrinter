(function(){
  // Light-weight link grid component
  // API:
  //   createLinkGrid({
  //     mount: HTMLElement,
  //     getItems: async () => Array<{ href?: string, image_url: string, title?: string, path?: string }>,
  //     cols: number, rows: number,
  //     onEnter?: (item) => void,
  //     onDelete?: async (item) => Promise<boolean>,
  //   })

  function createLinkGrid(opts){
    const COLS = Math.max(1, opts.cols || 4);
    const ROWS = Math.max(1, opts.rows || 2);
    const PAGE_SIZE = COLS * ROWS;

    const state = {
      items: [],
      buttons: [],
      page: 0,
      selectedIndex: 0,
    };

  // Hotkey -> local index map for current page
  let hotkeyMap = {};

    const wrapper = document.createElement('div');
    wrapper.className = 'lg-page';

    const grid = document.createElement('main');
    grid.className = 'lg-grid';
    grid.setAttribute('aria-label','Link grid');

    const controls = document.createElement('div');
    controls.className = 'lg-controls';

    const prevBtn = document.createElement('button');
    prevBtn.className = 'lg-nav-btn';
    prevBtn.textContent = '<-';

    const pageIndicator = document.createElement('div');
    pageIndicator.className = 'lg-page-indicator';

    const nextBtn = document.createElement('button');
    nextBtn.className = 'lg-nav-btn';
    nextBtn.textContent = '->';

    controls.appendChild(prevBtn);
    controls.appendChild(pageIndicator);
    controls.appendChild(nextBtn);

    const status = document.createElement('div');
    status.style.cssText = 'position:fixed;bottom:12px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.8);color:#fff;padding:8px 12px;border-radius:6px;font-size:14px;z-index:1000;display:none';

    function setStatus(msg){
      status.textContent = msg;
      status.style.display = 'block';
      clearTimeout(setStatus._t);
      setStatus._t = setTimeout(()=> status.style.display='none', 2500);
    }

    wrapper.appendChild(grid);
    wrapper.appendChild(controls);
    wrapper.appendChild(status);

    opts.mount.appendChild(wrapper);

    function pageCount(){
      return Math.max(1, Math.ceil(state.items.length / PAGE_SIZE));
    }

    function pageStartIndex(p){ return p * PAGE_SIZE; }
    function pageEndIndex(p){ return Math.min(state.items.length, pageStartIndex(p) + PAGE_SIZE); }

    function updateControls(){
      const pc = pageCount();
      prevBtn.style.display = state.page > 0 ? '' : 'none';
      nextBtn.style.display = state.page < pc - 1 ? '' : 'none';
      pageIndicator.textContent = pc > 1 ? `Page ${state.page+1} / ${pc}` : '';
    }

    function updateSelection(newIndex){
      state.buttons[state.selectedIndex]?.classList.remove('selected');
      state.selectedIndex = newIndex;
      const el = state.buttons[state.selectedIndex];
      if (el){ el.classList.add('selected'); el.focus(); }
    }

  function renderPage(){
      grid.innerHTML = '';
      state.buttons = [];
      hotkeyMap = {};

      const start = pageStartIndex(state.page);
      const end = pageEndIndex(state.page);
      const slice = state.items.slice(start, end);

      slice.forEach((it, localIndex) => {
        const globalIndex = start + localIndex;
        const a = document.createElement('a');
        a.href = it.href || '#';
        a.className = 'lg-button';
        a.dataset.index = String(globalIndex);
        a.tabIndex = 0;

        const img = document.createElement('img');
        img.src = it.image_url;
        img.alt = it.title || 'Link';
        a.appendChild(img);

        // Derive a hotkey: explicit it.hotKey/it.hotkey, else default to ordinal (1..9, 0 for 10)
        const explicitHK = (it.hotKey || it.hotkey || '').toString().trim();
        let hk = explicitHK ? explicitHK[0] : '';
        if (!hk){
          const ord = localIndex + 1;
          if (ord >= 1 && ord <= 9) hk = String(ord);
          else if (ord === 10) hk = '0';
        }
        if (hk){
          const hkLower = hk.toLowerCase();
          if (!(hkLower in hotkeyMap)) hotkeyMap[hkLower] = localIndex;
          const hkEl = document.createElement('div');
          hkEl.className = 'lg-hotkey';
          hkEl.textContent = hk.toUpperCase();
          a.appendChild(hkEl);
        }

  a.addEventListener('click', (e)=>{
          // If href provided, allow navigation; otherwise intercept and call onEnter
          if (!it.href){ e.preventDefault(); }
          if (typeof opts.onEnter === 'function') opts.onEnter(it);
        });

        a.addEventListener('focus', ()=>{
          const idx = Number(a.dataset.index);
          updateSelection(idx - start);
        });

        grid.appendChild(a);
  state.buttons.push(a);
      });

      // reset selection within page
      if (state.buttons.length) updateSelection(0);
      updateControls();
    }

    function gotoPage(p){
      const pc = pageCount();
      state.page = Math.min(Math.max(0, p), pc-1);
      renderPage();
    }

    // Keyboard navigation: Arrow keys page only; hotkeys trigger items
    document.addEventListener('keydown', async (event) => {
      const key = event.key;
      const start = pageStartIndex(state.page);
      const end = pageEndIndex(state.page);
      const localCount = end - start;
      if (!localCount) return;

      // Page with arrow keys
      if (["ArrowRight","ArrowDown"].includes(key)){
        event.preventDefault();
        gotoPage(state.page + 1);
        return;
      }
      if (["ArrowLeft","ArrowUp"].includes(key)){
        event.preventDefault();
        gotoPage(state.page - 1);
        return;
      }

      // Enter triggers the first item on the page
      if (key === 'Enter'){
        event.preventDefault();
        const item = state.items[start + 0];
        if (!item) return;
        if (typeof opts.onEnter === 'function') opts.onEnter(item);
        return;
      }

      // Delete/Backspace passes to onDelete for first item (optional behavior retained)
      if (key === 'Delete' || key === 'Backspace'){
        if (typeof opts.onDelete === 'function'){
          event.preventDefault();
          const item = state.items[start + 0];
          if (!item) return;
          const ok = await opts.onDelete(item);
          if (ok){
            state.items.splice(start + 0, 1);
            const pc = pageCount();
            if (state.page >= pc) state.page = Math.max(0, pc-1);
            renderPage();
          }
        }
        return;
      }

      // Hotkey: explicit per-item or default ordinal (1..9, 0 for 10)
      const k = key.length === 1 ? key.toLowerCase() : '';
      if (!k) return;

      let localIndex = undefined;
      if (k in hotkeyMap){
        localIndex = hotkeyMap[k];
      } else {
        const n = parseInt(k, 10);
        if (!Number.isNaN(n)){
          const target = n === 0 ? 9 : (n - 1); // 0 -> index 9 (10th)
          if (target >= 0 && target < localCount) localIndex = target;
        }
      }

      if (localIndex !== undefined){
        event.preventDefault();
        const item = state.items[start + localIndex];
        if (!item) return;
        if (typeof opts.onEnter === 'function') opts.onEnter(item);
      }
    });

    // Buttons
    nextBtn.addEventListener('click', ()=> gotoPage(state.page + 1));
    prevBtn.addEventListener('click', ()=> gotoPage(state.page - 1));

    // Public API
  return {
      async load(){
        state.items = await opts.getItems();
        gotoPage(0);
      },
      setItems(arr){ state.items = Array.isArray(arr) ? arr.slice() : []; gotoPage(0); },
      setPage(p){ gotoPage(p); },
      get page(){ return state.page; },
      get pageSize(){ return PAGE_SIZE; },
      get cols(){ return COLS; },
      get rows(){ return ROWS; },
      setStatus(msg){ setStatus(msg); },
      // Busy state toggling for a given item (by reference) if present on current page
      setBusy(item, busy){
        const idx = state.items.indexOf(item);
        if (idx === -1) return;
        const start = pageStartIndex(state.page);
        const end = pageEndIndex(state.page);
        if (idx < start || idx >= end) return;
        const local = idx - start;
        const btn = state.buttons[local];
        if (!btn) return;
        if (busy) btn.classList.add('is-busy'); else btn.classList.remove('is-busy');
      }
    };
  }

  window.createLinkGrid = createLinkGrid;
})();
