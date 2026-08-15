(function () {
  const form = document.getElementById('loginForm');
  const emailEl = document.getElementById('email');
  const passEl = document.getElementById('password');
  const emailErr = document.getElementById('emailError');
  const passErr = document.getElementById('passwordError');

  // Google OAuth redirects failures back here as ?oauth_error=... (see
  // app/routers/oauth_google.py) since the failure happens server-side,
  // outside the normal form-submit flow this page otherwise handles.
  const OAUTH_ERRORS = {
    google_denied: 'Google sign-in was cancelled.',
    google_failed: 'Something went wrong with Google sign-in. Please try again.',
    google_unverified: "That Google account's email isn't verified. Please use a different sign-in method.",
  };
  const oauthError = new URLSearchParams(window.location.search).get('oauth_error');
  if (oauthError && OAUTH_ERRORS[oauthError]) {
    const globalError = document.getElementById('globalError');
    globalError.textContent = OAUTH_ERRORS[oauthError];
    globalError.style.display = 'block';
    window.history.replaceState({}, '', '/login');
  }

  function showError(input, errEl) { input.classList.add('is-error'); errEl.style.display = 'block'; }
  function clearError(input, errEl) { input.classList.remove('is-error'); errEl.style.display = 'none'; }

  emailEl.addEventListener('input', () => clearError(emailEl, emailErr));
  passEl.addEventListener('input', () => clearError(passEl, passErr));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let valid = true;

    if (!emailEl.value || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailEl.value)) {
      showError(emailEl, emailErr); valid = false;
    } else { clearError(emailEl, emailErr); }

    if (!passEl.value) { showError(passEl, passErr); valid = false; }
    else { clearError(passEl, passErr); }

    if (!valid) return;

    const globalError = document.getElementById('globalError');
    globalError.style.display = 'none';
    globalError.textContent = '';

    const loginBtn = document.getElementById('loginBtn');
    const originalBtnText = loginBtn.textContent;
    loginBtn.disabled = true;
    loginBtn.textContent = 'Signing In...';

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailEl.value.trim(), password: passEl.value }),
      });
      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        loginBtn.textContent = 'Success!';
        loginBtn.style.background = 'var(--good)';
        setTimeout(() => { window.location.href = '/dashboard'; }, 800);
      } else {
        loginBtn.disabled = false;
        loginBtn.textContent = originalBtnText;
        globalError.textContent = data.detail || 'Invalid email or password.';
        globalError.style.display = 'block';
      }
    } catch (err) {
      loginBtn.disabled = false;
      loginBtn.textContent = originalBtnText;
      globalError.textContent = 'Network error. Please check your connection.';
      globalError.style.display = 'block';
    }
  });
})();