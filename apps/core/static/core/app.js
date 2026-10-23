// Weststar ONE — small helpers. No inline scripts anywhere (strict Content-Security-Policy).
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } } };

  // Ctrl/Cmd+K focuses the search; Escape closes pop-ups and the drawer.
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); $('#jump')?.focus(); }
    if (e.key === 'Escape') { closeModal(); closeFly(); $('#jump-results') && ($('#jump-results').innerHTML = ''); hide('#user-pop', '#user-btn'); }
  });

  function closeModal() { const m = $('#modal'); if (m) m.innerHTML = ''; }
  document.addEventListener('click', (e) => {
    const t = e.target;
    if (t.closest('[data-close]') || (t.classList && t.classList.contains('shade'))) { e.preventDefault(); closeModal(); }
    if (!t.closest('#jump-box')) { const r = $('#jump-results'); if (r) r.innerHTML = ''; }
    if (!t.closest('.user-menu')) hide('#user-pop', '#user-btn');
  });

  function hide(popSel, btnSel) { const p = $(popSel); if (p) p.hidden = true; $(btnSel)?.setAttribute('aria-expanded', 'false'); }
  $('#user-btn')?.addEventListener('click', () => { const p = $('#user-pop'); p.hidden = !p.hidden; $('#user-btn').setAttribute('aria-expanded', String(!p.hidden)); });

  // Look 1: collapsible sidebar sections, remembered per browser.
  const closed = store.get('ws.nav.closed', {});
  $$('.nav-group').forEach((g) => {
    const name = g.dataset.group, btn = $('.nav-section', g);
    const apply = () => { g.classList.toggle('closed', !!closed[name]); btn.setAttribute('aria-expanded', String(!closed[name])); };
    apply();
    btn.addEventListener('click', () => { closed[name] = !closed[name]; store.set('ws.nav.closed', closed); apply(); });
  });

  // Look 2: icon bar fly-outs.
  function closeFly() { $$('.fly').forEach((f) => (f.hidden = true)); $$('[data-fly]').forEach((b) => b.setAttribute('aria-expanded', 'false')); const s = $('#fly-shade'); if (s) s.hidden = true; }
  $$('[data-fly]').forEach((b) => b.addEventListener('click', () => {
    const f = document.getElementById(b.dataset.fly), open = f.hidden;
    closeFly();
    if (open) { f.hidden = false; b.setAttribute('aria-expanded', 'true'); $('#fly-shade').hidden = false; }
  }));
  $('#fly-shade')?.addEventListener('click', closeFly);

  // Phone: menu button shows the navigation.
  $('#menu-btn')?.addEventListener('click', () => {
    const n = $('#main-nav'), open = !n.classList.contains('open');
    n.classList.toggle('open', open); $('#menu-btn').setAttribute('aria-expanded', String(open)); $('#menu-btn').textContent = open ? 'Close menu' : 'Menu';
  });

  // Copy buttons (recovery codes).
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-copy]');
    if (!b) return;
    const text = document.getElementById(b.dataset.copy)?.innerText ?? '';
    navigator.clipboard?.writeText(text).then(() => { b.textContent = 'Copied'; }).catch(() => {});
  });

  // Reply box: Ctrl+Enter sends. Reply/Note toggle styles the box.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && e.target.matches('textarea[name="body"]')) { e.preventDefault(); e.target.form?.requestSubmit(); }
  });
  document.addEventListener('change', (e) => {
    if (e.target.matches('input[name="kind"]')) {
      const ta = e.target.form.querySelector('textarea[name="body"]');
      const note = e.target.value === 'note';
      ta.classList.toggle('note', note);
      ta.placeholder = note ? 'Only your team sees internal notes…' : ta.dataset.replyPlaceholder;
      const send = e.target.form.querySelector('[data-send]');
      if (send) send.textContent = note ? 'Add note' : 'Save reply';
    }
  });

  // Line items: add a row by cloning the empty form Django provides.
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-add-line]');
    if (!b) return;
    const tbody = $('#lines-body'), tmpl = $('#line-template'), total = $('#id_lines-TOTAL_FORMS');
    const n = Number(total.value);
    tbody.insertAdjacentHTML('beforeend', tmpl.innerHTML.replace(/__prefix__/g, String(n)));
    total.value = String(n + 1);
  });

  // Ticket list: highlight the row you picked.
  document.addEventListener('click', (e) => {
    const r = e.target.closest('.t-row');
    if (!r) return;
    $$('.t-row.on').forEach((x) => { x.classList.remove('on'); x.setAttribute('aria-pressed', 'false'); });
    r.classList.add('on'); r.setAttribute('aria-pressed', 'true');
  });

  // Big uploads (Settings › Import): send with a progress bar, then follow the redirect.
  document.addEventListener('submit', (e) => {
    const form = e.target.closest('form[data-upload-progress]');
    if (!form || !window.FormData) return;
    e.preventDefault();
    const data = new FormData(form);
    if (e.submitter && e.submitter.name) data.append(e.submitter.name, e.submitter.value);
    const bar = $('[data-progress-bar]', form), label = $('[data-progress]', form);
    bar.hidden = false; label.hidden = false;
    $$('button', form).forEach((b) => (b.disabled = true));
    const xhr = new XMLHttpRequest();
    xhr.open('POST', form.action || window.location.href);
    xhr.upload.addEventListener('progress', (ev) => {
      if (!ev.lengthComputable) return;
      const pct = Math.round((ev.loaded / ev.total) * 100);
      $('span', bar).style.width = pct + '%';
      label.textContent = pct < 100 ? `Uploading… ${pct}%` : 'Upload finished, starting…';
    });
    xhr.addEventListener('load', () => {
      if (xhr.status === 200 && xhr.responseURL) { window.location.href = xhr.responseURL; return; }
      document.open(); document.write(xhr.responseText); document.close();
    });
    xhr.addEventListener('error', () => { label.textContent = 'Upload failed: check your connection and try again.'; $$('button', form).forEach((b) => (b.disabled = false)); });
    xhr.send(data);
  });

  // After an htmx swap into the drawer, focus the first field.
  document.body.addEventListener('htmx:afterSwap', (e) => {
    if (e.detail.target.id === 'modal') e.detail.target.querySelector('input:not([type=hidden]),select,textarea')?.focus();
  });
  // Server returns 422 for forms with errors: still swap them in so the errors show.
  document.body.addEventListener('htmx:beforeSwap', (e) => { if (e.detail.xhr.status === 422) { e.detail.shouldSwap = true; e.detail.isError = false; } });
})();
