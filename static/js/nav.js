/* nav.js — mobile rail open/close, shared by every authenticated page. */
(function () {
  const toggle = document.querySelector('.rail-toggle');
  const rail = document.querySelector('.rail');
  if (!toggle || !rail) return;

  toggle.addEventListener('click', () => {
    const open = rail.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(open));
  });

  document.addEventListener('click', (e) => {
    if (rail.classList.contains('is-open') && !rail.contains(e.target) && e.target !== toggle) {
      rail.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });

  // Handle logout — styled confirm modal (templates/partials/nav_rail.html)
  // instead of the native browser confirm() popup.
  const logoutBtn = document.getElementById('logoutBtn');
  const logoutModal = document.getElementById('logoutModal');
  const logoutCancelBtn = document.getElementById('logoutCancelBtn');
  const logoutConfirmBtn = document.getElementById('logoutConfirmBtn');

  function openLogoutModal() {
    if (!logoutModal) return;
    logoutModal.hidden = false;
    logoutConfirmBtn?.focus();
    document.addEventListener('keydown', onLogoutModalKeydown);
  }

  function closeLogoutModal() {
    if (!logoutModal) return;
    logoutModal.hidden = true;
    document.removeEventListener('keydown', onLogoutModalKeydown);
    logoutBtn?.focus();
  }

  function onLogoutModalKeydown(e) {
    if (e.key === 'Escape') closeLogoutModal();
  }

  function performLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
  }

  if (logoutBtn && logoutModal) {
    logoutBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openLogoutModal();
    });
    logoutCancelBtn?.addEventListener('click', closeLogoutModal);
    logoutConfirmBtn?.addEventListener('click', performLogout);
    // Click on the dimmed backdrop (not the card itself) also cancels.
    logoutModal.addEventListener('click', (e) => {
      if (e.target === logoutModal) closeLogoutModal();
    });
  } else if (logoutBtn) {
    // Defensive fallback if the modal partial isn't present on some page.
    logoutBtn.addEventListener('click', (e) => {
      e.preventDefault();
      performLogout();
    });
  }
})();