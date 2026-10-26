// Customer sign-off page: live charges + statement, signature pad, override. Mirrors apps/helpdesk/signoff.py.
(() => {
  const page = document.getElementById('so-page'); if (!page) return;
  const TYPE = page.dataset.type, RATE = parseFloat(page.dataset.rate || '0'), TAX = parseFloat(page.dataset.tax || '0'), CO = page.dataset.company;
  const $ = (id) => document.getElementById(id);
  const money = (n) => '$' + (Math.round(n * 100) / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const trim = (n) => String(Math.round(n * 100) / 100);
  const num = (id) => { const e = $(id); const v = e ? parseFloat(e.value) : 0; return isNaN(v) || v < 0 ? 0 : v; };
  function recalc() {
    const st = $('stmt');
    if (TYPE === 'dropoff') { st.textContent = `I confirm that I received the items listed above from ${CO} in good condition.`; return; }
    const h = Math.round(num('so-h') * 100) / 100, p = Math.round(num('so-pa') * 100) / 100, pd = ($('so-pd').value || '').trim();
    const labC = Math.round(h * RATE * 100), subC = labC + Math.round(p * 100), taxC = Math.round(subC * Math.round(TAX * 100) / 10000);
    $('c-lab').textContent = `${money(labC / 100)} (${trim(h)} h × ${money(RATE)})`;
    $('c-parts-row').style.display = p > 0 ? '' : 'none'; $('c-parts').textContent = money(p);
    if ($('c-tax')) $('c-tax').textContent = money(taxC / 100);
    $('c-tot').textContent = money((subC + taxC) / 100);
    st.textContent = 'I confirm that the work described above has been completed, that my computers, systems and equipment are working the same as before or better, and I agree to the charges of '
      + money((subC + taxC) / 100) + ` (${trim(h)} hour${h === 1 ? '' : 's'} at ${money(RATE)}/hour` + (p > 0 ? `, plus ${money(p)} for ${pd || 'parts/materials'}` : '') + (TAX > 0 ? `, plus ${trim(TAX)}% tax` : '') + ').';
  }
  ['so-h', 'so-pa', 'so-pd'].forEach((i) => $(i)?.addEventListener('input', recalc));
  recalc();

  const canvas = $('sig-canvas'), ctx = canvas.getContext('2d'); let drawing = false, has = false;
  const size = () => { const r = canvas.getBoundingClientRect(); canvas.width = r.width * 2; canvas.height = r.height * 2; ctx.setTransform(2, 0, 0, 2, 0, 0); ctx.strokeStyle = '#1e293b'; ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; };
  size();
  const pos = (e) => { const r = canvas.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const mark = () => { has = true; $('sig-wrap').classList.add('on'); $('sign-btn').disabled = false; };
  canvas.addEventListener('pointerdown', (e) => { e.preventDefault(); drawing = true; canvas.setPointerCapture(e.pointerId); const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); });
  canvas.addEventListener('pointermove', (e) => { if (!drawing) return; e.preventDefault(); const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); mark(); });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach((ev) => canvas.addEventListener(ev, () => { drawing = false; }));
  $('sig-clear').addEventListener('click', () => { ctx.clearRect(0, 0, canvas.width, canvas.height); has = false; $('sig-wrap').classList.remove('on'); $('sign-btn').disabled = true; });

  const form = $('so-form');
  form.addEventListener('submit', (e) => {
    if ($('ov-flag').value === '1') return;
    if (!has) { e.preventDefault(); return; }
    const nm = $('so-n');
    if (!nm.value.trim()) { e.preventDefault(); nm.classList.add('bad'); nm.placeholder = 'Customer must type their name'; nm.focus(); return; }
    $('sig-data').value = canvas.toDataURL('image/png');
    $('sign-btn').disabled = true;
  });
  $('ov-btn').addEventListener('click', () => {
    const r = $('so-r');
    if (r.value.trim().length < 8) { r.classList.add('bad'); r.focus(); return; }
    const it = $('so-items'); if (it && !it.value.trim()) { it.focus(); return; }
    $('ov-flag').value = '1'; $('sig-data').value = '';
    form.requestSubmit ? form.requestSubmit() : form.submit();
  });
})();
