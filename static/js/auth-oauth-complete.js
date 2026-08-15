/*
 * auth-oauth-complete.js — lands here right after Google redirects back
 * through /api/auth/google/callback. The URL carries a short-lived,
 * single-purpose "handoff" token (see app/routers/oauth_google.py) — not
 * the real session token, which never travels in a URL. This immediately
 * exchanges it server-side for the real access_token, stores it exactly
 * like a normal email/password login (auth-login.js), then moves on.
 */
(function () {
  const titleEl = document.getElementById('oauthStatusTitle');
  const subEl = document.getElementById('oauthStatusSub');
  const spinnerEl = document.getElementById('oauthSpinner');
  const errorActionsEl = document.getElementById('oauthErrorActions');

  function showError(message) {
    spinnerEl.style.display = 'none';
    titleEl.textContent = 'Sign-in failed';
    subEl.textContent = message;
    errorActionsEl.style.display = 'block';
  }

  async function finish() {
    const handoff = new URLSearchParams(window.location.search).get('handoff');
    if (!handoff) {
      showError('Missing sign-in details. Please try again.');
      return;
    }

    // Strip the token from the visible URL/history immediately — it's
    // single-use and expires in 60s, but there's no reason to leave it
    // sitting in the address bar any longer than necessary.
    window.history.replaceState({}, '', '/auth/google/complete');

    try {
      const res = await fetch('/api/auth/google/finalize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ handoff }),
      });
      const data = await res.json();

      if (!res.ok) {
        showError(data.detail || 'Sign-in link expired. Please try again.');
        return;
      }

      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      window.location.replace('/dashboard');
    } catch (err) {
      showError('Network error. Please check your connection and try again.');
    }
  }

  finish();
})();
