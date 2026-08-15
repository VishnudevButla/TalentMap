/*
 * dashboard.js — hydrates the dashboard from GET /api/dashboard/summary
 * (real, see app/routers/dashboard_api.py) and from the 'latest_analysis'
 * localStorage snapshot written right after an analyze completes (so the
 * page reflects a just-finished analysis instantly, before the next
 * summary fetch lands). Every section is always overwritten, even when
 * empty, so a real-but-empty result never leaves stale sample content
 * on screen.
 */
(function () {
  const WORKER_BADGE = {
    healthy: { cls: 'good', label: 'Worker healthy' },
    stale: { cls: 'warn', label: 'Worker stale' },
    down: { cls: 'crit', label: 'Worker down' },
  };

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function formatSalary(min, max) {
    if (!min && !max) return null;
    const fmt = n => `$${Math.round(n / 1000)}k`;
    if (min && max) return `${fmt(min)} - ${fmt(max)}`;
    return fmt(min || max);
  }

  function initials(name) {
    return ((name || '?')[0] || '?').toUpperCase();
  }

  // -----------------------------------------------------------------------
  // Greeting — real time-of-day + real username, not a canned string.
  // -----------------------------------------------------------------------

  function timeOfDayGreeting() {
    const h = new Date().getHours();
    if (h < 12) return 'Good morning';
    if (h < 18) return 'Good afternoon';
    return 'Good evening';
  }

  function applyUserName() {
    const el = document.getElementById('dashGreeting');
    if (!el) return;
    const userStr = localStorage.getItem('user');
    let name = '';
    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        name = (user && user.username) ? user.username.split(/\s+/)[0] : '';
      } catch (e) { /* ignore */ }
    }
    el.innerHTML = name
      ? `${timeOfDayGreeting()}, <span class="accent-name">${escapeHtml(name)}</span> 👋`
      : `${timeOfDayGreeting()} 👋`;
  }

  // -----------------------------------------------------------------------
  // Search — real navigation into /matches with a query, filtered there.
  // -----------------------------------------------------------------------

  function wireSearch() {
    const input = document.getElementById('dashSearch');
    if (!input) return;
    input.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const q = input.value.trim();
      window.location.href = q ? `/matches?q=${encodeURIComponent(q)}` : '/matches';
    });
  }

  // -----------------------------------------------------------------------
  // Skill chip helpers
  // -----------------------------------------------------------------------

  function renderChips(containerId, items, cls, emptyMessage) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!items || !items.length) {
      el.innerHTML = `<p class="card-sub">${emptyMessage}</p>`;
      return;
    }
    el.innerHTML = items.map(s => `<span class="skill-chip ${cls}">${escapeHtml(typeof s === 'string' ? s : s.name)}</span>`).join('');
  }

  function renderLandscapeDonut(matchedCount, missingCount) {
    const el = document.getElementById('landscapeDonut');
    if (!el) return;
    const total = matchedCount + missingCount;
    if (!total) {
      el.innerHTML = '<p class="card-sub">Not enough data yet.</p>';
      return;
    }
    const pct = Math.round((matchedCount / total) * 100);
    const circumference = 2 * Math.PI * 40;
    const matchedLen = (pct / 100) * circumference;
    el.innerHTML = `
      <svg viewBox="0 0 100 100" class="skill-donut" role="img" aria-label="${pct}% skills overall strength">
        <circle cx="50" cy="50" r="40" fill="none" stroke="var(--warn)" stroke-width="14" />
        <circle cx="50" cy="50" r="40" fill="none" stroke="var(--good)" stroke-width="14"
          stroke-dasharray="${matchedLen} ${circumference - matchedLen}" stroke-linecap="round"
          transform="rotate(-90 50 50)" />
        <text x="50" y="47" text-anchor="middle" class="skill-donut-figure">${pct}%</text>
        <text x="50" y="62" text-anchor="middle" class="skill-donut-caption">strength</text>
      </svg>
      <p class="landscape-donut-caption">Overall strength</p>
    `;
  }

  // -----------------------------------------------------------------------
  // AI Recommended row — real top matches, real skill chips, real
  // bookmark toggle (PATCH /api/jobs/matches/{id}/save). Links into the
  // real job-details page, not a dead card.
  // -----------------------------------------------------------------------

  function bookmarkIcon(filled) {
    return filled
      ? '<svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-4-7 4V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>'
      : '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21l-7-4-7 4V5a2 2 0 012-2h10a2 2 0 012 2z"/></svg>';
  }

  function renderRecommended(jobMatches) {
    const el = document.getElementById('recoRow');
    if (!el) return;
    if (!jobMatches || !jobMatches.length) {
      el.innerHTML = '<p class="card-sub">No matches yet — the AI Job Agent will populate this once it finds real postings that fit your resume.</p>';
      return;
    }

    el.innerHTML = jobMatches.map((job, i) => {
      const skills = job.skills_detected || [];
      const shown = skills.slice(0, 4);
      const extra = skills.length - shown.length;
      const salary = formatSalary(job.salary_min, job.salary_max);
      const logo = job.company_logo_url
        ? `<img src="${escapeHtml(job.company_logo_url)}" alt="" class="reco-logo-img" />`
        : `<div class="reco-logo-fallback">${escapeHtml(initials(job.company))}</div>`;

      return `
        <div class="reco-card${i === 0 ? ' is-best' : ''}" data-job-id="${escapeHtml(job.job_id)}">
          <div class="reco-card-head">
            <span class="stat-status ${job.status}">${job.match_score}% Match</span>
            ${i === 0 ? '<span class="best-match-badge">🔒 Best Match</span>' : ''}
          </div>
          <div class="reco-company">
            ${logo}
            <div>
              <h3>${escapeHtml(job.title)}</h3>
              <p>${escapeHtml(job.company || '')}</p>
            </div>
          </div>
          <p class="reco-meta">${escapeHtml(job.location || 'Location unknown')}${job.remote_type ? ' · ' + escapeHtml(job.remote_type) : ''}${salary ? ' · ' + salary : ''}</p>
          <div class="chips reco-chips">
            ${shown.map(s => `<span class="skill-chip have">${escapeHtml(s)}</span>`).join('')}
            ${extra > 0 ? `<span class="skill-chip gap">+${extra}</span>` : ''}
          </div>
          <div class="reco-card-actions">
            <a href="/matches/${encodeURIComponent(job.job_id)}" class="btn-primary btn-sm reco-details-btn">View details →</a>
            <button type="button" class="reco-bookmark-btn${job.saved ? ' is-saved' : ''}" data-job-id="${escapeHtml(job.job_id)}" aria-label="${job.saved ? 'Remove bookmark' : 'Bookmark'}">${bookmarkIcon(job.saved)}</button>
          </div>
        </div>
      `;
    }).join('');

    el.querySelectorAll('.reco-bookmark-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const jobId = btn.dataset.jobId;
        const nowSaved = !btn.classList.contains('is-saved');
        const token = localStorage.getItem('token');
        btn.disabled = true;
        try {
          const res = await fetch(`/api/jobs/matches/${encodeURIComponent(jobId)}/save`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ saved: nowSaved }),
          });
          if (res.ok) {
            btn.classList.toggle('is-saved', nowSaved);
            btn.innerHTML = bookmarkIcon(nowSaved);
            btn.setAttribute('aria-label', nowSaved ? 'Remove bookmark' : 'Bookmark');
          }
        } catch (e) { /* leave state unchanged on network error */ }
        btn.disabled = false;
      });
    });
  }

  // -----------------------------------------------------------------------
  // Notification bell — a real unread dot, from the same 5 most-recent
  // activity items the "Recent activity" card already renders (not a
  // separate fetch, not a guess).
  // -----------------------------------------------------------------------

  function renderNotifDot(activity) {
    const dot = document.getElementById('dashNotifDot');
    if (!dot) return;
    const hasUnread = (activity || []).some(a => a.read === false);
    dot.classList.toggle('is-hidden', !hasUnread);
  }

  // -----------------------------------------------------------------------
  // Main hydration
  // -----------------------------------------------------------------------

  async function hydrateFromSummary() {
    const token = localStorage.getItem('token');
    if (!token) return null;

    let data;
    try {
      const res = await fetch('/api/dashboard/summary', { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) return null;
      data = await res.json();
    } catch (e) {
      console.error('Error loading dashboard summary:', e);
      return null;
    }

    const subEl = document.getElementById('dashGreetingSub');
    if (subEl) {
      const poolCount = data.agent ? data.agent.jobs_in_pool : 0;
      subEl.textContent = poolCount
        ? `We've scanned ${poolCount.toLocaleString()} job${poolCount === 1 ? '' : 's'} and found the best opportunities that match your skills and goals.`
        : "The AI Job Agent hasn't scanned any postings yet — check back after the next scan cycle.";
    }

    // --- Stat row ---
    const topMatchEl = document.getElementById('statTopMatch');
    const topMatchCaptionEl = document.getElementById('statTopMatchCaption');
    if (data.match) {
      if (topMatchEl) topMatchEl.textContent = `${data.match.score}%`;
      if (topMatchCaptionEl) topMatchCaptionEl.textContent = (data.job_matches && data.job_matches[0]) ? data.job_matches[0].title : '';
    } else {
      if (topMatchEl) topMatchEl.textContent = '—';
      if (topMatchCaptionEl) topMatchCaptionEl.textContent = 'No matches yet';
    }

    const newMatchesEl = document.getElementById('statNewMatches');
    const newMatchesCaptionEl = document.getElementById('statNewMatchesCaption');
    if (newMatchesEl) newMatchesEl.textContent = data.agent ? data.agent.new_matches_today : '—';
    if (newMatchesCaptionEl) {
      newMatchesCaptionEl.textContent = data.jobs_since_last_scan
        ? `+${data.jobs_since_last_scan} postings since last scan`
        : 'Since last scan';
    }

    const coverageEl = document.getElementById('statSkillsCoverage');
    if (coverageEl) coverageEl.textContent = data.skills_coverage_pct != null ? `${data.skills_coverage_pct}%` : '—';

    const appliedEl = document.getElementById('statAppliedMonth');
    if (appliedEl) appliedEl.textContent = data.applied_this_month != null ? data.applied_this_month : '—';

    // --- AI Recommended ---
    renderRecommended(data.job_matches);

    // --- Skills landscape ---
    const matched = (data.analysis && data.analysis.matched_skills) || [];
    const missing = (data.analysis && data.analysis.missing_skills) || [];
    renderChips('strongSkillsChips', matched, 'have', data.analysis ? 'No skills extracted from this resume.' : 'Upload a resume to see your strong skills.');
    renderChips('growSkillsChips', missing.map(s => (typeof s === 'string' ? s : s.name)), 'gap', 'Not enough market data yet to compute gaps.');
    renderLandscapeDonut(matched.length, missing.length);

    // --- AI Job Agent panel ---
    const countdown = document.getElementById('agentCountdown');
    if (countdown && data.agent && window.TalentMapCountdown) {
      window.TalentMapCountdown.set(countdown, data.agent.next_scan_in_seconds || 0);
    }
    if (data.agent) {
      const statFields = {
        agentJobsScanned: data.agent.jobs_in_pool,
        agentNewMatches: data.agent.new_matches_today,
        agentEmailsSent: data.agent.emails_sent_today,
        agentSources: data.agent.sources_monitored,
      };
      for (const [id, value] of Object.entries(statFields)) {
        const elx = document.getElementById(id);
        if (elx && value != null) elx.textContent = value;
      }
      const workerBadge = document.getElementById('agentWorkerBadge');
      if (workerBadge && data.agent.worker) {
        const info = WORKER_BADGE[data.agent.worker.status] || { cls: 'warn', label: 'Unknown' };
        workerBadge.className = `stat-status ${info.cls}`;
        workerBadge.textContent = info.label;
      }
    }

    // --- Recent activity + notification dot ---
    if (data.activity && window.__renderActivityRow) {
      const feed = document.querySelector('.activity-feed');
      if (feed) {
        feed.innerHTML = data.activity.length
          ? data.activity.map(window.__renderActivityRow).join('')
          : '<p class="card-sub">No recent activity yet.</p>';
      }
    }
    renderNotifDot(data.activity);

    return data;
  }

  // -----------------------------------------------------------------------
  // A resume was just analyzed and matching now runs as a background task
  // — re-poll the summary a few times until the match shows up.
  // -----------------------------------------------------------------------

  const MATCH_POLL_INTERVAL_MS = 5000;
  const MATCH_POLL_MAX_TRIES = 10;

  function isAnalysisRecent(analysis) {
    if (!analysis || !analysis.analyzed_at) return false;
    const analyzedAt = new Date(analysis.analyzed_at).getTime();
    if (Number.isNaN(analyzedAt)) return false;
    return (Date.now() - analyzedAt) < 5 * 60 * 1000;
  }

  async function pollForMatchIfPending(triesLeft) {
    const data = await hydrateFromSummary();
    if (!data || data.match || triesLeft <= 0 || !isAnalysisRecent(data.analysis)) return;
    setTimeout(() => pollForMatchIfPending(triesLeft - 1), MATCH_POLL_INTERVAL_MS);
  }

  // -----------------------------------------------------------------------
  // Refresh control
  // -----------------------------------------------------------------------

  let refreshInFlight = false;

  async function refreshDashboard() {
    if (refreshInFlight) return;
    refreshInFlight = true;
    await hydrateFromSummary();
    refreshInFlight = false;
  }

  const AUTO_REFRESH_INTERVAL_MS = 60000;

  document.addEventListener('DOMContentLoaded', () => {
    applyUserName();
    wireSearch();
    pollForMatchIfPending(MATCH_POLL_MAX_TRIES);
    setInterval(refreshDashboard, AUTO_REFRESH_INTERVAL_MS);
  });
})();
