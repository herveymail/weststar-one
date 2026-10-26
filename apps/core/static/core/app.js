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

  // Look 2: icon bar fly-outs.
  function closeFly() { $$('.fly').forEach((f) => (f.hidden = true)); $$('[data-fly]').forEach((b) => b.setAttribute('aria-expanded', 'false')); const s = $('#fly-shade'); if (s) s.hidden = true; }
  $$('[data-fly]').forEach((b) => b.addEventListener('click', () => {
    const f = document.getElementById(b.dataset.fly), open = f.hidden;
    closeFly();
    if (open) { f.hidden = false; b.setAttribute('aria-expanded', 'true'); $('#fly-shade').hidden = false; }
  }));
  $('#fly-shade')?.addEventListener('click', closeFly);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeFly(); });
  $$('.fly a').forEach((a) => a.addEventListener('click', closeFly));

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
  // Ticket composer: Reply / Private note / Work log change the hint, placeholder, button and colors.
  const KIND = {
    reply: { ph: 'Write your reply to the client… Ctrl+Enter to send.', btn: 'Send reply' },
    note: { ph: 'Only your team sees private notes…', btn: 'Add note' },
    work: { ph: 'What did you do? Only your team sees work logs…', btn: 'Log work' },
  };
  function setKind(form, kind) {
    const k = KIND[kind] || KIND.reply, ta = form.querySelector('textarea[name="body"]');
    const radio = form.querySelector(`input[name="kind"][value="${kind}"]`); if (radio) radio.checked = true;
    if (ta) { ta.placeholder = kind === 'reply' ? (ta.dataset.replyPlaceholder || k.ph) : k.ph; ta.classList.toggle('note', kind !== 'reply'); }
    const send = form.querySelector('[data-send]'); if (send) send.textContent = k.btn;
    const hint = form.querySelector('[data-hint]'); if (hint) hint.textContent = hint.dataset[kind] || '';
    const cc = form.querySelector('[data-cc-row]'); if (cc) cc.hidden = kind !== 'reply';
    form.classList.toggle('is-note', kind !== 'reply');
  }
  document.addEventListener('change', (e) => {
    if (e.target.matches('input[name="kind"]')) setKind(e.target.form, e.target.value);
    if (e.target.matches('[data-saved-reply]') && e.target.value) {
      const ta = e.target.form.querySelector('textarea[name="body"]');
      ta.value = (ta.value ? ta.value + '\n\n' : '') + e.target.value; e.target.value = ''; ta.focus();
    }
    if (e.target.matches('[data-files]')) showFiles(e.target);
    if (e.target.matches('select[data-autosubmit]') || e.target.closest('form[data-autosubmit-form]')) (e.target.form || e.target.closest('form')).requestSubmit();
    if (e.target.matches('[data-tick], [data-tick-all]')) {
      if (e.target.matches('[data-tick-all]')) $$('[data-tick]').forEach((c) => (c.checked = e.target.checked));
      updateBulk();
    }
    if (e.target.matches('select[data-bulk]') && e.target.value !== '-') {
      const f = $('#bulk'); $('[data-bulk-action]', f).value = e.target.dataset.bulk; $('[data-bulk-value]', f).value = e.target.value; f.requestSubmit();
    }
  });
  document.addEventListener('click', (e) => {
    const m = e.target.closest('[data-compose]');
    if (m) { const f = $('form[data-composer]'); if (f) { setKind(f, m.dataset.compose); setTimeout(() => f.querySelector('textarea').focus(), 0); } }
    if (e.target.closest('[data-bulk-close]')) {
      const f = $('#bulk'); const n = $$('[data-tick]:checked').length;
      if (n && window.confirm(`Close ${n} ticket(s)?`)) { $('[data-bulk-action]', f).value = 'close'; f.requestSubmit(); }
    }
    if (e.target.closest('[data-bulk-clear]')) { $$('[data-tick], [data-tick-all]').forEach((c) => (c.checked = false)); updateBulk(); }
    // Grid: click a row (not its checkbox) to open the ticket beside the list.
    const row = e.target.closest('tr[data-open]');
    if (row && !e.target.closest('input, select, button') && !(e.ctrlKey || e.metaKey)) { e.preventDefault(); openPanel(row.dataset.open); }
    if (e.target.closest('[data-close-panel]')) closePanel();
  });
  function updateBulk() {
    const f = $('#bulk'); if (!f) return;
    const n = $$('[data-tick]:checked').length; f.hidden = n === 0; $('[data-bulk-count]', f).textContent = n;
  }
  function showFiles(input) {
    const out = input.form && input.form.querySelector('[data-file-names]');
    if (out) out.textContent = Array.from(input.files).map((f) => f.name).join(', ');
  }
  function addFiles(input, files) {
    const dt = new DataTransfer(); Array.from(input.files).forEach((f) => dt.items.add(f)); Array.from(files).forEach((f) => dt.items.add(f));
    input.files = dt.files; showFiles(input);
  }
  document.addEventListener('dragover', (e) => { const d = e.target.closest('[data-drop]'); if (d) { e.preventDefault(); d.classList.add('over'); } });
  document.addEventListener('dragleave', (e) => { const d = e.target.closest('[data-drop]'); if (d) d.classList.remove('over'); });
  document.addEventListener('drop', (e) => {
    const d = e.target.closest('[data-drop]'); if (!d) return;
    e.preventDefault(); d.classList.remove('over'); addFiles($('[data-files]', d), e.dataTransfer.files);
  });
  document.addEventListener('paste', (e) => {
    const f = e.target.closest && e.target.closest('form[data-composer]'); if (!f || !e.clipboardData) return;
    const imgs = Array.from(e.clipboardData.files || []).filter((x) => x.type.startsWith('image/'));
    if (imgs.length) { e.preventDefault(); addFiles($('[data-files]', f), imgs.map((x, i) => new File([x], `screenshot-${Date.now()}-${i}.png`, { type: x.type }))); }
  });
  function openPanel(id) {
    if (!window.htmx) { window.location.href = `/tickets/${id}/`; return; }
    $$('tr[data-open]').forEach((r) => r.classList.toggle('sel', r.dataset.open === String(id)));
    window.htmx.ajax('GET', `/tickets/${id}/panel/`, { target: '#panel', swap: 'outerHTML' }).then(() => $('#split')?.classList.add('has-panel'));
    const u = new URL(window.location.href); u.searchParams.set('open', id); window.history.replaceState(null, '', u);
  }
  function closePanel() {
    const p = $('#panel'); if (p) { p.outerHTML = '<div id="panel" hidden></div>'; }
    $('#split')?.classList.remove('has-panel'); $$('tr.sel').forEach((r) => r.classList.remove('sel'));
    const u = new URL(window.location.href); u.searchParams.delete('open'); window.history.replaceState(null, '', u);
  }
  // Running timers tick every second.
  setInterval(() => $$('[data-since]').forEach((el) => {
    const s = Math.max(0, Math.floor(Date.now() / 1000) - Number(el.dataset.since));
    el.textContent = `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
  }), 1000);
  // Keyboard, like the old app. Classic page: R reply, N note. Grid: j/k move, Enter open, x tick, / search, n new, Esc close.
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || e.target.closest('input, textarea, select, [contenteditable]')) return;
    const f = $('form[data-composer]');
    if (f && (e.key === 'r' || e.key === 'n') && !$('[data-grid]')) { e.preventDefault(); setKind(f, e.key === 'r' ? 'reply' : 'note'); f.querySelector('textarea').focus(); return; }
    if (!$('[data-grid]')) return;
    const rows = $$('tr[data-open]'); let i = rows.findIndex((r) => r.classList.contains('kb'));
    if (e.key === 'j' || e.key === 'k') { e.preventDefault(); rows[i]?.classList.remove('kb'); i = Math.min(rows.length - 1, Math.max(0, i + (e.key === 'j' ? 1 : -1))); rows[i]?.classList.add('kb'); rows[i]?.scrollIntoView({ block: 'nearest' }); }
    else if ((e.key === 'Enter' || e.key === 'o') && rows[i]) { e.preventDefault(); openPanel(rows[i].dataset.open); }
    else if (e.key === 'x' && rows[i]) { const c = $('[data-tick]', rows[i]); c.checked = !c.checked; updateBulk(); }
    else if (e.key === '/') { e.preventDefault(); $('[data-slash]')?.focus(); }
    else if (e.key === 'n') { $('button[hx-get="/tickets/new/"]')?.click(); }
    else if (e.key === 'r' && f) { e.preventDefault(); setKind(f, 'reply'); f.querySelector('textarea').focus(); }
    else if (e.key === 'Escape') closePanel();
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

// Settings: filter the left menu; highlight the chosen radio card.
(() => {
  const box = document.querySelector('[data-set-filter]');
  if (box) {
    box.addEventListener('input', () => {
      const q = box.value.trim().toLowerCase();
      let any = false;
      document.querySelectorAll('[data-set-group]').forEach((g) => {
        let shown = 0;
        g.querySelectorAll('.set-link').forEach((a) => { const ok = !q || a.dataset.words.includes(q); a.hidden = !ok; if (ok) shown++; });
        g.hidden = shown === 0; if (shown) any = true;
        g.classList.toggle('searching', !!q);
      });
      const none = document.querySelector('.set-none'); if (none) none.hidden = any;
    });
    box.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const a = document.querySelector('.set-link:not([hidden])'); if (a) { e.preventDefault(); location.href = a.href; } } });
  }
  document.querySelectorAll('[data-set-group] .set-group-title').forEach((b) => b.addEventListener('click', () => {
    const g = b.closest('[data-set-group]'); const closed = g.classList.toggle('closed'); b.setAttribute('aria-expanded', String(!closed));
  }));
  document.querySelectorAll('.set-cards').forEach((c) => c.addEventListener('change', () => {
    c.querySelectorAll('.set-card').forEach((l) => l.classList.toggle('on', l.querySelector('input').checked));
  }));
})();

// AI: "Draft reply" fills the reply box with a suggestion to edit before sending.
document.addEventListener('click', async (e) => {
  const b = e.target.closest('[data-ai-draft]');
  if (!b) return;
  const box = document.getElementById(b.dataset.target);
  if (!box) return;
  let token = '';
  try { token = JSON.parse(document.body.getAttribute('hx-headers') || '{}')['X-CSRFToken'] || ''; } catch (_) { /* no token */ }
  const label = b.textContent;
  b.disabled = true; b.textContent = 'Writing…';
  try {
    const r = await fetch(b.dataset.aiDraft, { method: 'POST', headers: { 'X-CSRFToken': token, 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'action=draft', credentials: 'same-origin' });
    const text = await r.text();
    if (r.ok) {
      const reply = box.form && box.form.querySelector('input[name=kind][value=reply]');
      if (reply && !reply.checked) reply.click();
      box.value = (box.value.trim() ? box.value.trim() + '\n\n' : '') + text;
      box.focus();
    } else {
      const d = document.createElement('div'); d.innerHTML = text; alertBox(box, d.textContent || 'The AI assistant could not write a draft.');
    }
  } catch (_) { alertBox(box, 'Could not reach the AI assistant.'); }
  b.disabled = false; b.textContent = label;
});
function alertBox(near, msg) {
  const p = document.createElement('p'); p.className = 'small'; p.style.color = 'var(--crit)'; p.style.margin = '4px 0'; p.textContent = msg;
  near.insertAdjacentElement('beforebegin', p); setTimeout(() => p.remove(), 8000);
}
document.addEventListener('click', (e) => { if (e.target.closest('[data-print]')) window.print(); });
