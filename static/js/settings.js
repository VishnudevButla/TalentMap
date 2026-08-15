/*
 * settings.js — theme toggle (fully client-side, persisted to localStorage)
 * and notification preferences (real CRUD against /api/settings and its
 * /email-frequency, /digest-hour, /match-threshold sub-endpoints — see
 * app/routers/settings_api.py). Every value here is actually read by the
 * live worker (app/step4_agent/scheduler.py, matcher.py), not just stored.
 */
(function () {
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.querySelectorAll('.theme-option').forEach(el => {
      el.classList.toggle('is-active', el.dataset.themeValue === theme);
    });
  }

  function setupThemeToggle() {
    const toggle = document.getElementById('themeToggle');
    if (!toggle) return;
    const current = localStorage.getItem('theme') || 'dark';
    applyTheme(current);

    toggle.addEventListener('click', () => {
      const next = (localStorage.getItem('theme') || 'dark') === 'dark' ? 'light' : 'dark';
      localStorage.setItem('theme', next);
      applyTheme(next);
    });
  }

  function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function formatHour(h) {
    const period = h < 12 ? 'AM' : 'PM';
    const display = h % 12 === 0 ? 12 : h % 12;
    return `${display}:00 ${period} UTC`;
  }

  function populateDigestHourOptions(select) {
    for (let h = 0; h < 24; h++) {
      const opt = document.createElement('option');
      opt.value = String(h);
      opt.textContent = formatHour(h);
      select.appendChild(opt);
    }
  }

  function showSavedNote(note) {
    if (!note) return;
    note.textContent = 'Saved.';
    setTimeout(() => { note.textContent = ''; }, 1500);
  }

  async function setupNotifications() {
    const checkbox = document.getElementById('emailAlertsToggle');
    const note = document.getElementById('emailAlertsNote');
    const frequencySelect = document.getElementById('emailFrequencySelect');
    const digestHourSelect = document.getElementById('digestHourSelect');
    const digestHourRow = document.getElementById('digestHourRow');
    const thresholdRange = document.getElementById('matchThresholdRange');
    const thresholdValue = document.getElementById('matchThresholdValue');
    const token = localStorage.getItem('token');
    if (!checkbox || !token) return;

    if (digestHourSelect) populateDigestHourOptions(digestHourSelect);

    // The digest-hour picker only ever does something when frequency is
    // "daily" (see scheduler.py's send_daily_digest) — grey it out rather
    // than leave it looking live when it currently has no effect.
    function syncDigestHourVisibility() {
      if (!digestHourRow || !digestHourSelect || !frequencySelect) return;
      const applies = frequencySelect.value === 'daily';
      digestHourSelect.disabled = !applies;
      digestHourRow.style.opacity = applies ? '1' : '.5';
    }

    try {
      const res = await fetch('/api/settings', { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        checkbox.checked = !!data.notifications?.email_alerts_enabled;
        if (frequencySelect) frequencySelect.value = data.notifications?.email_frequency || 'daily';
        if (digestHourSelect) digestHourSelect.value = String(data.notifications?.digest_hour ?? 9);
        const threshold = data.match_threshold ?? 70;
        if (thresholdRange) thresholdRange.value = String(threshold);
        if (thresholdValue) thresholdValue.textContent = `${threshold}%`;
        syncDigestHourVisibility();
      }
    } catch (err) {
      console.error('Error loading settings:', err);
    }

    checkbox.addEventListener('change', async () => {
      try {
        const res = await fetch('/api/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ email_alerts_enabled: checkbox.checked }),
        });
        if (res.ok) showSavedNote(note);
      } catch (err) {
        console.error('Error saving settings:', err);
      }
    });

    frequencySelect?.addEventListener('change', async () => {
      syncDigestHourVisibility();
      try {
        const res = await fetch('/api/settings/email-frequency', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ email_frequency: frequencySelect.value }),
        });
        if (res.ok) showSavedNote(note);
      } catch (err) {
        console.error('Error saving email frequency:', err);
      }
    });

    digestHourSelect?.addEventListener('change', async () => {
      try {
        const res = await fetch('/api/settings/digest-hour', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ digest_hour: Number(digestHourSelect.value) }),
        });
        if (res.ok) showSavedNote(note);
      } catch (err) {
        console.error('Error saving digest hour:', err);
      }
    });

    thresholdRange?.addEventListener('input', () => {
      if (thresholdValue) thresholdValue.textContent = `${thresholdRange.value}%`;
    });
    thresholdRange?.addEventListener('change', async () => {
      try {
        const res = await fetch('/api/settings/match-threshold', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ match_threshold: Number(thresholdRange.value) }),
        });
        if (res.ok) showSavedNote(note);
      } catch (err) {
        console.error('Error saving match threshold:', err);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    setupThemeToggle();
    setupNotifications();
  });
})();
