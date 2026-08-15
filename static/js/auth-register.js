(function () {
  const passEl = document.getElementById('password');
  const bars = [document.getElementById('s1'), document.getElementById('s2'), document.getElementById('s3'), document.getElementById('s4')];
  const strengthLabel = document.getElementById('strengthLabel');
  const levels = [
    { color: 'var(--crit)', label: 'Weak' },
    { color: '#fb923c', label: 'Fair' },
    { color: 'var(--warn)', label: 'Good' },
    { color: 'var(--good)', label: 'Strong' },
  ];

  function calcStrength(pw) {
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    return Math.min(4, score);
  }

  passEl.addEventListener('input', () => {
    const pw = passEl.value;
    const score = pw ? calcStrength(pw) : 0;
    bars.forEach((bar, i) => { bar.style.background = i < score ? levels[score - 1].color : 'var(--track)'; });
    strengthLabel.textContent = pw ? (levels[score - 1]?.label ?? '') : '';
    strengthLabel.style.color = pw && score > 0 ? levels[score - 1].color : 'var(--ink-2)';
  });

  const form = document.getElementById('registerForm');
  const firstNameEl = document.getElementById('firstName');
  const lastNameEl = document.getElementById('lastName');
  const emailEl = document.getElementById('email');
  const confirmEl = document.getElementById('confirmPassword');
  const termsEl = document.getElementById('terms');

  const fields = {
    firstName: { el: firstNameEl, err: document.getElementById('firstNameError'), validate: v => v.trim().length > 0 },
    lastName: { el: lastNameEl, err: document.getElementById('lastNameError'), validate: v => v.trim().length > 0 },
    email: { el: emailEl, err: document.getElementById('emailError'), validate: v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) },
    password: { el: passEl, err: document.getElementById('passwordError'), validate: v => v.length >= 8 },
    confirmPassword: { el: confirmEl, err: document.getElementById('confirmError'), validate: v => v === passEl.value },
  };

  Object.values(fields).forEach(({ el, err }) => {
    el.addEventListener('input', () => { el.classList.remove('is-error'); err.style.display = 'none'; });
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let valid = true;

    Object.values(fields).forEach(({ el, err, validate }) => {
      if (!validate(el.value)) { el.classList.add('is-error'); err.style.display = 'block'; valid = false; }
      else { el.classList.remove('is-error'); err.style.display = 'none'; }
    });

    const termsErr = document.getElementById('termsError');
    if (!termsEl.checked) { termsErr.style.display = 'block'; valid = false; }
    else { termsErr.style.display = 'none'; }

    if (!valid) return;

    const globalError = document.getElementById('globalError');
    globalError.style.display = 'none';
    globalError.textContent = '';

    const registerBtn = document.getElementById('registerBtn');
    const originalBtnText = registerBtn.textContent;
    registerBtn.disabled = true;
    registerBtn.textContent = 'Registering...';

    try {
      const username = (firstNameEl.value.trim() + ' ' + lastNameEl.value.trim()).trim();
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email: emailEl.value.trim(), password: passEl.value }),
      });
      const data = await response.json();

      if (response.ok) {
        registerBtn.textContent = 'Success! Redirecting...';
        registerBtn.style.background = 'var(--good)';
        setTimeout(() => { window.location.href = '/login'; }, 1200);
      } else {
        registerBtn.disabled = false;
        registerBtn.textContent = originalBtnText;
        globalError.textContent = data.detail || 'Registration failed. Please try again.';
        globalError.style.display = 'block';
      }
    } catch (err) {
      registerBtn.disabled = false;
      registerBtn.textContent = originalBtnText;
      globalError.textContent = 'Network error. Please check your connection.';
      globalError.style.display = 'block';
    }
  });
})();