/* auth-guard.js — bounce to /login when no session token is present.
   Runs blocking, before the shell paints, on every authenticated page. */
if (!localStorage.getItem('token')) {
  window.location.replace('/login');
}