// Weststar ONE — small helpers. No inline scripts anywhere (strict Content-Security-Policy).
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } } };

  // Ctrl/Cmd+K focuses the search; Escape closes pop-ups and the drawer.
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); $('#jump')?.focus(); }
    if (e.key === 'Escape') { closeModal(); closeFly(); $('#jump-results') && ($('#jump-results').innerHTML = ''); hide('#user-pop', '#user-btn'); hide('#new-pop', '#new-btn'); }
  });

  function closeModal() { const m = $('#modal'); if (m) m.innerHTML = ''; }
  document.addEventListener('click', (e) => {
    const t = e.target;
    if (t.closest('[data-close]') || (t.classList && t.classList.contains('shade'))) { e.preventDefault(); closeModal(); }
    if (!t.closest('#jump-box')) { const r = $('#jump-results'); if (r) r.innerHTML = ''; }
    if (!t.closest('#user-pop') && !t.closest('#user-btn')) hide('#user-pop', '#user-btn');
    if (!t.closest('#new-btn') || t.closest('#new-pop')) { if (!t.closest('#new-btn')) hide('#new-pop', '#new-btn'); }
  });

  function hide(popSel, btnSel) { const p = $(popSel); if (p) p.hidden = true; $(btnSel)?.setAttribute('aria-expanded', 'false'); }
  $('#user-btn')?.addEventListener('click', () => { const p = $('#user-pop'); p.hidden = !p.hidden; $('#user-btn').setAttribute('aria-expanded', String(!p.hidden)); hide('#new-pop', '#new-btn'); });
  $('#new-btn')?.addEventListener('click', () => { const p = $('#new-pop'); p.hidden = !p.hidden; $('#new-btn').setAttribute('aria-expanded', String(!p.hidden)); hide('#user-pop', '#user-btn'); });

  // Top bar clock, like the old app.
  const clk = $('[data-clock]'), dt = $('[data-date]');
  if (clk) {
    const tick = () => { const n = new Date(); clk.textContent = n.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' }); if (dt) dt.textContent = n.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }); };
    tick(); setInterval(tick, 1000);
  }

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
    const n = $$('[data-tick]:checked').length; f.hidden = false; f.classList.toggle('show', n > 0); $('[data-bulk-count]', f).textContent = n;
    $$('tr[data-open]').forEach((r) => r.classList.toggle('ticked', !!$('[data-tick]:checked', r)));
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

  // Line items: show each line's total and the document total as you type.
  const money = (n) => '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const recalcLines = () => {
    const body = $('#lines-body'); if (!body) return;
    let sub = 0, taxable = 0;
    $$('tr', body).forEach((tr) => {
      const q = parseFloat($('input[name$="-qty"]', tr)?.value || '0') || 0, r = parseFloat($('input[name$="-rate"]', tr)?.value || '0') || 0;
      const del = $('input[name$="-DELETE"]', tr)?.checked, tax = $('input[name$="-taxable"]', tr)?.checked;
      const total = Math.round(q * r * 100) / 100, cell = $('[data-line-total]', tr);
      if (cell && ($('input[name$="-description"]', tr)?.value || r)) cell.textContent = money(total);
      if (!del) { sub += total; if (tax) taxable += total; }
    });
    const rate = parseFloat($('#module-form [name="tax_rate"]')?.value || '0') || 0, t = Math.round(taxable * rate) / 100;
    const out = $('[data-doc-totals]'); if (out) out.innerHTML = `Subtotal ${money(sub)} · Tax ${money(t)} · <b>Total ${money(sub + t)}</b>`;
  };
  document.addEventListener('input', (e) => { if (e.target.closest('#lines-body') || e.target.name === 'tax_rate') recalcLines(); });
  document.addEventListener('change', (e) => { if (e.target.closest('#lines-body')) recalcLines(); });

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

  // A form opened from a link (?open_form=…): drop it from the address so a reload after saving doesn't open it again.
  { const u = new URL(window.location.href); if (u.searchParams.has('open_form')) { u.searchParams.delete('open_form'); window.history.replaceState(null, '', u); } }

  // Ticket panel: open on the newest message, like the old app.
  const panelToBottom = () => { const b = $('#panel [data-pbody="conv"]'); if (b) b.scrollTop = b.scrollHeight; };
  panelToBottom();
  document.body.addEventListener('htmx:afterSwap', (e) => { if (e.detail.target.id === 'panel' || (e.detail.elt && e.detail.elt.id === 'panel')) panelToBottom(); });
  document.body.addEventListener('htmx:afterSettle', () => { if ($('#panel [data-pbody="conv"]') && !$('#panel').dataset.scrolled) { panelToBottom(); $('#panel').dataset.scrolled = '1'; } });

  // Ticket panel (grid): tabs, CC row, and click-menus that close when you pick something or click elsewhere.
  document.addEventListener('click', (e) => {
    const tab = e.target.closest('[data-ptab]');
    if (tab) {
      const p = tab.closest('.tkg-panel');
      $$('[data-ptab]', p).forEach((b) => b.classList.toggle('on', b === tab));
      $$('[data-pbody]', p).forEach((b) => (b.hidden = b.dataset.pbody !== tab.dataset.ptab));
    }
    if (e.target.closest('[data-cc-toggle]')) { const r = e.target.closest('form').querySelector('[data-cc-row-panel]'); r.classList.toggle('show'); if (r.classList.contains('show')) $('input', r).focus(); }
    $$('details.tkg-pop[open]').forEach((d) => {
      const inside = d.contains(e.target);
      if (!inside || (e.target.closest('.tkg-menu button, .tkg-menu a'))) d.open = false;
    });
  });

  // Ticket grid: the automatic refresh waits while you have tickets ticked or a menu open, so it never undoes what you're doing.
  document.body.addEventListener('htmx:beforeRequest', (e) => {
    if (e.detail.elt.id !== 'grid-body' || e.detail.requestConfig.verb !== 'get') return;
    const busy = $$('[data-tick]:checked').length || (document.activeElement && document.activeElement.closest('#grid-body, .tkg-bar, #bulk') && document.activeElement.matches('select, input'));
    if (busy && !(e.detail.requestConfig.triggeringEvent && e.detail.requestConfig.triggeringEvent.type === 'ticketsChanged')) e.preventDefault();
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

// Settings home: filter the tiles as you type (like the old app); "/" jumps to the box.
(() => {
  const q = document.querySelector('[data-sx-search]');
  if (q) {
    const tiles = Array.from(document.querySelectorAll('.sx-tile'));
    const run = () => {
      const words = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
      let n = 0;
      tiles.forEach((t) => { const hit = words.every((w) => t.dataset.q.includes(w)); t.classList.toggle('sx-hidden', !hit); if (hit) n++; });
      document.querySelectorAll('.sx-grp').forEach((g) => g.classList.toggle('sx-hidden', !g.querySelector('.sx-tile:not(.sx-hidden)')));
      ['sx-jumps', 'sx-attn'].forEach((id) => document.getElementById(id)?.classList.toggle('sx-hidden', words.length > 0));
      const e = document.getElementById('sx-empty'); if (e) e.hidden = n > 0;
    };
    q.addEventListener('input', run);
    q.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { const f = document.querySelector('.sx-tile:not(.sx-hidden)'); if (f && q.value.trim()) { e.preventDefault(); location.href = f.href; } }
      if (e.key === 'Escape') { q.value = ''; run(); }
    });
    document.addEventListener('keydown', (e) => { if (e.key === '/' && document.activeElement !== q && !/input|textarea|select/i.test(document.activeElement.tagName)) { e.preventDefault(); q.focus(); } });
  }
  // Close the "Jump to…" menu when clicking elsewhere; focus its filter when it opens.
  const j = document.querySelector('.sx-jump');
  if (j) {
    j.addEventListener('toggle', () => { if (j.open) j.querySelector('[data-set-filter]')?.focus(); });
    document.addEventListener('click', (e) => { if (j.open && !j.contains(e.target)) j.open = false; });
  }
})();

// New ticket: type to filter the client list (like the old app), and suggest that client's contacts as requesters.
document.body.addEventListener('input', (e) => {
  const q = e.target.closest('[data-filter-select]');
  if (!q) return;
  const sel = document.getElementById(q.dataset.filterSelect); if (!sel) return;
  const words = q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
  let first = null, shown = 0;
  Array.from(sel.options).forEach((o) => {
    if (!o.value) { o.hidden = words.length > 0; return; }
    const hit = words.every((w) => o.text.toLowerCase().includes(w));
    o.hidden = !hit; if (hit) { shown++; if (!first) first = o; }
  });
  sel.size = words.length && shown > 1 ? Math.min(shown, 8) : 1;
  if (first && words.length) { sel.value = first.value; sel.dispatchEvent(new Event('change', { bubbles: true })); }
});
document.body.addEventListener('keydown', (e) => {
  const q = e.target.closest('[data-filter-select]');
  if (q && (e.key === 'Enter' || e.key === 'ArrowDown')) { e.preventDefault(); const sel = document.getElementById(q.dataset.filterSelect); if (e.key === 'ArrowDown') sel?.focus(); else { if (sel) sel.size = 1; document.querySelector('[data-new-ticket] [name=subject]')?.focus(); } }
});
document.body.addEventListener('change', (e) => {
  const f = e.target.closest('[data-new-ticket]');
  if (!f) return;
  const data = JSON.parse(document.getElementById('nt-contact-data')?.textContent || '[]');
  if (e.target.name === 'client') {
    if (e.target.size > 1 && e.isTrusted) e.target.size = 1;
    const list = document.getElementById('nt-contacts'); if (!list) return;
    list.innerHTML = '';
    data.filter((c) => String(c.c) === e.target.value).forEach((c) => { const o = document.createElement('option'); o.value = c.n; o.label = c.e; list.appendChild(o); });
  }
  if (e.target.name === 'contact_name') {
    const cl = f.querySelector('[name=client]').value, m = data.find((c) => c.n === e.target.value && String(c.c) === cl);
    const em = f.querySelector('[name=contact_email]'); if (m && em && !em.value) em.value = m.e;
  }
});
document.body.addEventListener('click', (e) => {
  const sel = e.target.closest('[data-new-ticket] select[name=client]');
  if (sel && sel.size > 1 && e.target.tagName === 'OPTION') { sel.size = 1; }
});

// A thin "working…" bar under the top bar whenever something is saving or loading, so a click never looks ignored.
(() => {
  let n = 0, timer = null;
  const root = document.documentElement;
  const quiet = (e) => e.detail.elt && e.detail.elt.id === 'grid-body' && !(e.detail.requestConfig && e.detail.requestConfig.triggeringEvent && e.detail.requestConfig.triggeringEvent.type === 'ticketsChanged');
  document.body.addEventListener('htmx:beforeRequest', (e) => {
    if (e.defaultPrevented || quiet(e)) return;
    n++; e.detail.elt.dataset.wsBusy = '1';
    clearTimeout(timer); timer = setTimeout(() => { if (n > 0) root.classList.add('ws-busy'); }, 120);
  });
  document.body.addEventListener('htmx:afterRequest', (e) => {
    if (!e.detail.elt || e.detail.elt.dataset.wsBusy !== '1') return;
    delete e.detail.elt.dataset.wsBusy;
    n = Math.max(0, n - 1);
    if (!n) { clearTimeout(timer); root.classList.remove('ws-busy'); }
  });
})();
