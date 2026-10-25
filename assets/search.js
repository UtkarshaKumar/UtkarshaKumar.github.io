/* Site search: a Cmd/Ctrl K dialog over search-index.json.
   Plain JS, no libraries, no tracking. Recent searches stay in this browser only (localStorage). */
(function () {
  var script = document.currentScript;
  var base = new URL('..', script.src);
  var nav = document.querySelector('.nav-inner');
  if (!nav) return;

  var isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  var GROUPS = [['Essay', 'Essays'], ['Guide', 'Guide'], ['Experience', 'Pages'], ['Project', 'Projects']];
  var RECENT_KEY = 'site-search-recent';
  var ICON = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/></svg>';

  /* ---------- trigger ---------- */
  var trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'ss-trigger';
  trigger.setAttribute('aria-haspopup', 'dialog');
  trigger.setAttribute('aria-keyshortcuts', isMac ? 'Meta+K /' : 'Control+K /');
  trigger.innerHTML = ICON + '<span class="ss-trigger-label">Search</span><kbd class="ss-kbd">' + (isMac ? '\u2318K' : 'Ctrl K') + '</kbd>';
  nav.insertBefore(trigger, nav.querySelector('.nav-toggle'));

  /* ---------- dialog ---------- */
  var dlg = document.createElement('dialog');
  dlg.className = 'ss-dialog';
  dlg.setAttribute('aria-labelledby', 'ssTitle');
  dlg.innerHTML =
    '<h2 id="ssTitle" class="visually-hidden">Search the site</h2>' +
    '<div class="ss-head">' + ICON +
      '<input id="ssInput" type="search" placeholder="Search essays, the guide, projects" autocomplete="off" spellcheck="false" enterkeyhint="go" ' +
      'role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="ssList" aria-labelledby="ssTitle">' +
      '<button type="button" class="ss-close" aria-label="Close search"><span class="ss-close-text">Cancel</span><kbd class="ss-kbd">Esc</kbd></button>' +
    '</div>' +
    '<div class="ss-body"><div id="ssList" role="listbox" aria-label="Search results"></div></div>' +
    '<div class="ss-foot" aria-hidden="true"><span><kbd class="ss-kbd">\u2191</kbd><kbd class="ss-kbd">\u2193</kbd> move</span><span><kbd class="ss-kbd">Enter</kbd> open</span><span><kbd class="ss-kbd">Esc</kbd> close</span></div>' +
    '<p class="visually-hidden" aria-live="polite" id="ssStatus"></p>';
  document.body.appendChild(dlg);

  var input = dlg.querySelector('#ssInput');
  var list = dlg.querySelector('#ssList');
  var status = dlg.querySelector('#ssStatus');
  var index = null, docs = [], options = [], active = -1, returnFocus = null;

  /* ---------- index ---------- */
  function tokens(s) { return (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').match(/[a-z0-9]+/g) || []; }
  function load() {
    if (index) return Promise.resolve();
    return fetch(new URL('search-index.json', base)).then(function (r) { return r.json(); })
      .then(function (d) {
        index = d;
        docs = d.map(function (it) {
          return { it: it, f: [[new Set(tokens(it.title)), 10], [new Set(tokens(it.description)), 4], [new Set(tokens(it.body)), 1]] };
        });
      }).catch(function () { index = []; docs = []; });
  }

  /* Edit distance with an early exit; small inputs only. */
  function within(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return false;
    var prev = [], i, j;
    for (j = 0; j <= b.length; j++) prev[j] = j;
    for (i = 1; i <= a.length; i++) {
      var cur = [i], rowMin = i;
      for (j = 1; j <= b.length; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        if (cur[j] < rowMin) rowMin = cur[j];
      }
      if (rowMin > max) return false;
      prev = cur;
    }
    return prev[b.length] <= max;
  }

  /* exact word 3, prefix 2, typo 1. Every query word must match somewhere. */
  function search(q) {
    var terms = tokens(q);
    if (!terms.length) return { terms: [], hits: [] };
    var hits = [];
    docs.forEach(function (d) {
      var total = 0, words = [];
      for (var t = 0; t < terms.length; t++) {
        var term = terms[t], best = 0, maxTypo = term.length >= 7 ? 2 : term.length >= 4 ? 1 : 0;
        d.f.forEach(function (pair) {
          pair[0].forEach(function (w) {
            var s = w === term ? 3 : (w.indexOf(term) === 0 ? 2 : (maxTypo && within(term, w, maxTypo) ? 1 : 0));
            if (s) { words.push(w); if (s * pair[1] > best) best = s * pair[1]; }
          });
        });
        if (!best) return;
        total += best;
      }
      hits.push({ it: d.it, score: total, words: words });
    });
    hits.sort(function (a, b) { return b.score - a.score; });
    return { terms: terms, hits: hits };
  }

  /* ---------- rendering ---------- */
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function mark(text, words) {
    var html = esc(text);
    if (!words || !words.length) return html;
    var uniq = Array.from(new Set(words)).sort(function (a, b) { return b.length - a.length; }).slice(0, 12);
    var re = new RegExp('\\b(' + uniq.map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }).join('|') + ')', 'gi');
    return html.replace(re, '<mark>$1</mark>');
  }
  function snippet(it, words) {
    var src = it.body || it.description || '', low = src.toLowerCase(), at = -1;
    for (var i = 0; i < words.length && at < 0; i++) at = low.indexOf(words[i]);
    if (at < 0) return mark(it.description || src.slice(0, 140), words);
    var start = Math.max(0, low.lastIndexOf(' ', Math.max(0, at - 60)) + 1);
    var text = src.slice(start, start + 160);
    return (start ? '\u2026' : '') + mark(text, words) + (start + 160 < src.length ? '\u2026' : '');
  }
  function href(it) { return /^https?:/.test(it.url) ? it.url : new URL(it.url, base).href; }
  function external(it) { return /^https?:/.test(it.url) && it.url.indexOf(location.origin) !== 0; }

  function option(it, words, n, extra) {
    var meta = it.type === 'Experience' ? 'Page' : it.type;
    if (it.date) meta += ' \u00b7 ' + it.date;
    if (external(it)) meta += ' \u00b7 GitHub';
    return '<a role="option" id="ssOpt' + n + '" aria-selected="false" tabindex="-1" class="ss-opt" href="' + esc(href(it)) + '"' +
      (external(it) ? ' target="_blank" rel="noopener"' : '') + (extra || '') + '>' +
      '<span class="ss-title">' + mark(it.title, words) + '</span>' +
      '<span class="ss-meta">' + esc(meta) + '</span>' +
      (words === null ? '' : '<span class="ss-snip">' + snippet(it, words) + '</span>') + '</a>';
  }
  function group(label, body, id) {
    return '<div role="group" aria-labelledby="' + id + '" class="ss-group"><div class="ss-group-label" id="' + id + '" role="presentation">' + label + '</div>' + body + '</div>';
  }

  function recent() { try { return JSON.parse(localStorage.getItem(RECENT_KEY)) || []; } catch (e) { return []; } }
  function remember(q) {
    q = q.trim(); if (!q) return;
    var r = recent().filter(function (x) { return x.toLowerCase() !== q.toLowerCase(); });
    r.unshift(q);
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(r.slice(0, 5))); } catch (e) {}
  }

  function suggested() {
    var pick = [], guide = index.filter(function (i) { return i.type === 'Guide'; })[0];
    if (guide) pick.push(guide);
    index.filter(function (i) { return i.type === 'Essay' && /^\d{4}-\d{2}-\d{2}$/.test(i.date); })
      .sort(function (a, b) { return a.date < b.date ? 1 : -1; }).slice(0, 3).forEach(function (i) { pick.push(i); });
    var exp = index.filter(function (i) { return i.type === 'Experience'; })[0];
    if (exp) pick.push(exp);
    return pick;
  }

  function renderEmpty(note) {
    var html = '', n = 0, r = recent();
    if (note) html += '<p class="ss-note">' + note + '</p>';
    if (r.length && !note) {
      html += group('Recent searches', r.map(function (q) {
        return '<button type="button" role="option" id="ssOpt' + (n++) + '" aria-selected="false" tabindex="-1" class="ss-opt ss-recent" data-q="' + esc(q) + '">' +
          '<span class="ss-title">' + esc(q) + '</span></button>';
      }).join(''), 'ssGRecent');
    }
    html += group(note ? 'Try one of these' : 'Suggested', suggested().map(function (it) { return option(it, null, n++); }).join(''), 'ssGSuggest');
    paint(html, note ? note.replace(/<[^>]+>/g, '') : 'Showing suggestions');
  }

  function render() {
    var q = input.value;
    if (!q.trim()) { renderEmpty(); return; }
    var res = search(q), n = 0, html = '';
    if (!res.hits.length) { renderEmpty('Nothing found for \u201c' + esc(q.trim()) + '\u201d.'); return; }
    GROUPS.forEach(function (g, gi) {
      var hits = res.hits.filter(function (h) { return h.it.type === g[0]; }).slice(0, 6);
      if (hits.length) html += group(g[1], hits.map(function (h) { return option(h.it, h.words, n++); }).join(''), 'ssG' + gi);
    });
    paint(html, res.hits.length + (res.hits.length === 1 ? ' result' : ' results'));
    setActive(0);
  }

  function paint(html, msg) {
    list.innerHTML = html;
    options = Array.prototype.slice.call(list.querySelectorAll('[role=option]'));
    active = -1;
    input.removeAttribute('aria-activedescendant');
    status.textContent = msg;
  }

  function setActive(i) {
    if (!options.length) return;
    if (active > -1 && options[active]) { options[active].classList.remove('active'); options[active].setAttribute('aria-selected', 'false'); }
    active = (i + options.length) % options.length;
    var o = options[active];
    o.classList.add('active'); o.setAttribute('aria-selected', 'true');
    input.setAttribute('aria-activedescendant', o.id);
    o.scrollIntoView({ block: 'nearest' });
  }

  function choose(o) {
    if (!o) return;
    if (o.dataset.q) { input.value = o.dataset.q; render(); input.focus(); return; }
    remember(input.value);
    if (o.target === '_blank') { window.open(o.href, '_blank', 'noopener'); close(); }
    else location.href = o.href;
  }

  /* ---------- open / close ---------- */
  function open() {
    if (dlg.open) { input.select(); return; }
    returnFocus = document.activeElement;
    dlg.showModal();
    document.documentElement.classList.add('ss-lock');
    input.focus(); input.select();
    load().then(render);
  }
  function close() { if (dlg.open) dlg.close(); }
  dlg.addEventListener('close', function () {
    document.documentElement.classList.remove('ss-lock');
    if (returnFocus && returnFocus.focus) returnFocus.focus();
  });

  trigger.addEventListener('click', open);
  dlg.querySelector('.ss-close').addEventListener('click', close);
  dlg.addEventListener('click', function (e) { if (e.target === dlg) close(); });   /* backdrop */
  list.addEventListener('click', function (e) {
    var o = e.target.closest('[role=option]');
    if (!o) return;
    if (o.dataset.q) { e.preventDefault(); choose(o); } else remember(input.value);
  });
  list.addEventListener('mousemove', function (e) {
    var o = e.target.closest('[role=option]'), i = options.indexOf(o);
    if (i > -1 && i !== active) setActive(i);
  });

  var timer;
  input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(function () { load().then(render); }, 60); });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active < 0 ? -1 : active - 1); }
    else if (e.key === 'Home' && e.ctrlKey) { e.preventDefault(); setActive(0); }
    else if (e.key === 'End' && e.ctrlKey) { e.preventDefault(); setActive(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); clearTimeout(timer); load().then(function () { if (active < 0 && input.value.trim()) render(); choose(options[active]); }); }
  });
  /* Keep Tab inside the dialog: input -> close button -> input. */
  dlg.addEventListener('keydown', function (e) {
    /* type=search swallows the first Esc to clear itself, so close explicitly. */
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key !== 'Tab') return;
    var f = [input, dlg.querySelector('.ss-close')], i = f.indexOf(document.activeElement);
    e.preventDefault(); f[(i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus();
  });

  document.addEventListener('keydown', function (e) {
    var k = (e.key || '').toLowerCase();
    if (k === 'k' && (e.metaKey || e.ctrlKey) && !e.altKey) { e.preventDefault(); dlg.open ? close() : open(); return; }
    if (e.key === '/' && !dlg.open && !e.metaKey && !e.ctrlKey) {
      var t = e.target, tag = (t.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || t.isContentEditable) return;
      e.preventDefault(); open();
    }
  });
})();
