/* Site search. Plain JS, no tracking. Reads search-index.json built by scripts/build_search_index.py. */
(function () {
  var script = document.currentScript;
  var base = new URL('..', script.src);
  var nav = document.querySelector('.nav-inner');
  if (!nav) return;

  var wrap = document.createElement('div');
  wrap.className = 'site-search';
  wrap.setAttribute('role', 'search');
  wrap.innerHTML =
    '<label for="siteSearch" class="visually-hidden">Search the site</label>' +
    '<input id="siteSearch" type="search" placeholder="Search" autocomplete="off" spellcheck="false" ' +
    'role="combobox" aria-expanded="false" aria-controls="siteSearchResults" aria-autocomplete="list">' +
    '<kbd class="site-search-key" aria-hidden="true">/</kbd>' +
    '<ul id="siteSearchResults" class="site-search-results" role="listbox" aria-label="Search results" hidden></ul>' +
    '<p class="visually-hidden" aria-live="polite" id="siteSearchStatus"></p>';
  var toggle = nav.querySelector('.nav-toggle');
  nav.insertBefore(wrap, toggle || null);

  var input = wrap.querySelector('input');
  var list = wrap.querySelector('ul');
  var status = wrap.querySelector('#siteSearchStatus');
  var index = null, active = -1, items = [];

  function load() {
    if (index) return Promise.resolve(index);
    return fetch(new URL('search-index.json', base)).then(function (r) { return r.json(); })
      .then(function (d) { index = d; return d; }).catch(function () { index = []; return index; });
  }

  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function fold(s) { return (s || '').toLowerCase(); }

  function score(item, terms) {
    var t = fold(item.title), d = fold(item.description), b = fold(item.body), s = 0;
    for (var i = 0; i < terms.length; i++) {
      var w = terms[i], hit = 0;
      if (t.indexOf(w) > -1) hit += 10;
      if (d.indexOf(w) > -1) hit += 4;
      if (b.indexOf(w) > -1) hit += 1 + Math.min(4, b.split(w).length - 2);
      if (!hit) return 0;
      s += hit;
    }
    return s;
  }

  function snippet(item, terms) {
    var src = item.body || item.description || '';
    var low = fold(src), at = low.indexOf(terms[0]);
    var start = Math.max(0, at - 50), text = src.slice(start, start + 150);
    var html = esc((start ? '\u2026' : '') + text + (start + 150 < src.length ? '\u2026' : ''));
    terms.forEach(function (w) {
      html = html.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>');
    });
    return html;
  }

  function close() { list.hidden = true; input.setAttribute('aria-expanded', 'false'); active = -1; }

  function render(q) {
    var terms = fold(q).split(/\s+/).filter(Boolean);
    if (!terms.length) { close(); return; }
    items = index.map(function (it) { return { it: it, s: score(it, terms) }; })
      .filter(function (r) { return r.s; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 8);
    if (!items.length) {
      list.innerHTML = '<li class="site-search-empty">Nothing found for \u201c' + esc(q) + '\u201d</li>';
    } else {
      list.innerHTML = items.map(function (r, i) {
        var it = r.it, href = /^https?:/.test(it.url) ? it.url : new URL(it.url, base).href;
        var meta = it.type + (it.date ? ' \u00b7 ' + it.date : '');
        return '<li role="option" id="ss-opt-' + i + '"><a href="' + esc(href) + '"' +
          (/^https?:/.test(it.url) && it.url.indexOf(base.origin) !== 0 ? ' target="_blank" rel="noopener"' : '') + '>' +
          '<span class="ss-title">' + esc(it.title) + '</span><span class="ss-meta">' + esc(meta) + '</span>' +
          '<span class="ss-snip">' + snippet(it, terms) + '</span></a></li>';
      }).join('');
    }
    status.textContent = items.length + (items.length === 1 ? ' result' : ' results');
    list.hidden = false; input.setAttribute('aria-expanded', 'true'); active = -1;
  }

  function move(d) {
    var opts = list.querySelectorAll('[role=option]');
    if (!opts.length) return;
    if (active > -1) opts[active].classList.remove('active');
    active = (active + d + opts.length) % opts.length;
    opts[active].classList.add('active');
    input.setAttribute('aria-activedescendant', opts[active].id);
    opts[active].scrollIntoView({ block: 'nearest' });
  }

  input.addEventListener('focus', load);
  input.addEventListener('input', function () { var q = input.value; load().then(function () { render(q); }); });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Enter') {
      var a = list.querySelectorAll('[role=option] a')[active > -1 ? active : 0];
      if (a && !list.hidden) { e.preventDefault(); a.click(); }
    } else if (e.key === 'Escape') { if (!list.hidden) close(); else { input.value = ''; input.blur(); } }
  });
  document.addEventListener('keydown', function (e) {
    var tag = (e.target.tagName || '').toLowerCase();
    if (e.key === '/' && !e.metaKey && !e.ctrlKey && tag !== 'input' && tag !== 'textarea' && !e.target.isContentEditable) {
      e.preventDefault(); input.focus();
    }
  });
  document.addEventListener('click', function (e) { if (!wrap.contains(e.target)) close(); });
})();
