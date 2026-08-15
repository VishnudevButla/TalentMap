/*
 * agent-countdown.js — real client-side countdown from a `data-seconds`
 * target on any element with id/class matching .agent-countdown or
 * [data-agent-countdown]. Ticks down every second and formats HH:MM:SS.
 *
 * The starting value comes from the global scan schedule (see
 * app/step4_agent/state.py's get_global_agent_state()) — the same
 * countdown for every user, advanced only by the scheduler's own
 * interval job, never by a manual trigger (there isn't one).
 */
(function () {
  function format(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const hh = String(Math.floor(s / 3600)).padStart(2, '0');
    const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const ss = String(s % 60).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  }

  function startCountdown(el) {
    let remaining = parseInt(el.dataset.seconds || '0', 10);
    el.textContent = format(remaining);

    if (el._countdownInterval) clearInterval(el._countdownInterval);
    el._countdownInterval = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      el.textContent = format(remaining);
      if (remaining <= 0) clearInterval(el._countdownInterval);
    }, 1000);
  }

  function setCountdownSeconds(el, seconds) {
    el.dataset.seconds = String(seconds);
    startCountdown(el);
  }

  window.TalentMapCountdown = { start: startCountdown, set: setCountdownSeconds, format };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.agent-countdown[data-seconds]').forEach(startCountdown);
  });
})();
