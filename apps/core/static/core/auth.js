// Sign-in pages: show/hide password, and a "Signing in…" button state.
document.querySelectorAll('.wl-eye').forEach((b) => b.addEventListener('click', () => {
  const i = b.parentNode.querySelector('input'); const show = i.type === 'password';
  i.type = show ? 'text' : 'password'; b.querySelector('i').className = show ? 'bi bi-eye-slash' : 'bi bi-eye';
  b.setAttribute('aria-label', show ? 'Hide password' : 'Show password'); i.focus();
}));
document.querySelectorAll('form[data-wl]').forEach((f) => f.addEventListener('submit', (e) => {
  const b = e.submitter && e.submitter.classList.contains('wl-btn') ? e.submitter : null;
  if (b) setTimeout(() => { b.disabled = true; b.textContent = b.dataset.busy || 'Signing in…'; }, 0);
}));
