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
          <a href="/" data-nav>Home</a>
          <a href="/custom-label.html" data-nav>Custom Label</a>
          <a href="/recent.html" data-nav>Recent</a>
        </nav>
      </div>`;

  document.body.prepend(header);
  document.body.classList.add('has-site-header');

    // Set active link
    document.querySelectorAll('[data-nav]').forEach(a => {
      if (isActive(a.getAttribute('href'))) a.classList.add('active');
    });
  }

  window.renderSiteHeader = renderHeader;
})();
