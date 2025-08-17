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

    // Keyboard navigation
    document.addEventListener('keydown', async (event) => {
      const key = event.key;
      if (["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(key)) event.preventDefault();

      const start = pageStartIndex(state.page);
      const end = pageEndIndex(state.page);
      const localCount = end - start;

      if (!localCount) return;

      let newLocal = state.selectedIndex;
      switch(key){
        case 'ArrowRight': if ((newLocal + 1) % COLS !== 0) newLocal++; break;
        case 'ArrowLeft': if (newLocal % COLS !== 0) newLocal--; break;
        case 'ArrowDown': newLocal += COLS; break;
        case 'ArrowUp': newLocal -= COLS; break;
        case 'Enter': {
          const item = state.items[start + state.selectedIndex];
          if (item) {
            if (!item.href) event.preventDefault();
            if (typeof opts.onEnter === 'function') opts.onEnter(item);
          }
          return;
        }
        case 'Delete':
        case 'Backspace': {
          if (typeof opts.onDelete === 'function'){
            const item = state.items[start + state.selectedIndex];
            if (!item) return;
            event.preventDefault();
            const ok = await opts.onDelete(item);
            if (ok){
              state.items.splice(start + state.selectedIndex, 1);
              // Re-render page; handle if page becomes out of bounds
              const pc = pageCount();
              if (state.page >= pc) state.page = Math.max(0, pc-1);
              renderPage();
            }
          }
          return;
        }
        default: {
          const n = parseInt(key, 10);
          if (!Number.isNaN(n)){
            const target = n - 1;
            if (target >= 0 && target < localCount){ updateSelection(target); }
          }
          return;
        }
      }

      if (newLocal >= 0 && newLocal < localCount){ updateSelection(newLocal); }
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
      get rows(){ return ROWS; }
    };
  }

  window.createLinkGrid = createLinkGrid;
})();
