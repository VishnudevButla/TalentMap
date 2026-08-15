/*
 * market-trends.js — fetches /api/market-trends and renders every section.
 * Fully client-hydrated (like history.js/activity.js) since the JWT lives
 * in localStorage, not a cookie, so the server can't personalize this page
 * on a plain navigation. See app/services/market_trends_data.py for what
 * each field means and how it's computed from real data.
 *
 * Every number here traces to a real aggregation over job_postings_collection
 * / job_matches_collection / analysis_collection. Nothing here fabricates a
 * historical trend, a "daily scan limit," or a cross-user percentile —
 * none of those are backed by real stored data in this app (job postings
 * expire after JOB_RETENTION_DAYS, so there's no multi-week history to
 * chart; the AI Job Agent runs one shared global cycle, not a per-user
 * daily quota).
 */
(function () {
  const FIT_STATUS = { 'Strong': 'good', 'Moderate': 'warn', 'Developing': 'warn', 'Needs work': 'crit' };
  const TREND_SYMBOL = { up: '&uarr;', up2: '&uarr;&uarr;', down: '&darr;', flat: '&rarr;', new: 'NEW' };
  const DEMAND_DOT = { high: 'var(--crit)', medium: 'var(--warn)', low: 'var(--ink-2)' };
  const PATH_ACCENTS = ['var(--accent)', 'var(--cyan)', 'var(--good)'];

  const FLAME_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8.5 14.5A2.5 2.5 0 0011 17c1.38 0 2.5-1.5 2.5-2.5 0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7.5 7.5 0 11-15 0c0-1.153.433-2.294 1-3a2.5 2.5 0 002.5 2.5z"/></svg>';
  const ALERT_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>';
  const COMPASS_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z"/></svg>';
  const UP_ICON = '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M23 6l-9.5 9.5-5-5L1 18"/><path d="M17 6h6v6"/></svg>';

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function titleCase(str) {
    return (str || '').replace(/\b\w/g, c => c.toUpperCase());
  }

  function timeAgo(iso) {
    if (!iso) return null;
    const diffMs = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function playWidth(el) {
    const target = el.dataset.target;
    if (target == null) return;
    requestAnimationFrame(() => { el.style.width = target; });
  }

  function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  // --- Section renderers ---

  function renderHeader(data) {
    const updatedEl = document.getElementById('mtUpdatedAt');
    if (updatedEl) {
      const ago = timeAgo(data.updated_at);
      updatedEl.textContent = ago ? `Updated ${ago}` : 'Not run yet';
    }
  }

  function renderMarketFit(fit) {
    const scoreEl = document.getElementById('mtFitScore');
    const labelEl = document.getElementById('mtFitLabel');
    if (!scoreEl || !labelEl) return;
    if (!fit) {
      scoreEl.textContent = '—';
      labelEl.textContent = '';
      labelEl.className = 'stat-status';
      return;
    }
    scoreEl.textContent = `${fit.score} / 100`;
    labelEl.textContent = fit.label;
    labelEl.className = `stat-status ${FIT_STATUS[fit.label] || ''}`;
  }

  function renderJobsAnalysed(count) {
    const el = document.getElementById('mtJobsAnalysed');
    if (el) el.textContent = count != null ? count.toLocaleString() : '—';
  }

  function renderPathCount(paths) {
    const el = document.getElementById('mtPathCount');
    if (el) el.textContent = paths ? paths.length : '0';
  }

  function renderInsights(insights) {
    const el = document.getElementById('mtInsights');
    if (!el) return;
    const items = [];
    if (insights?.rising) {
      items.push(`
        <div class="mt-insight-item">
          <div class="mt-insight-icon mt-insight-icon-flame">${FLAME_ICON}</div>
          <div><b>${escapeHtml(titleCase(insights.rising))}</b> demand is rising<span>Real, from posting frequency over the tracked window</span></div>
        </div>
      `);
    }
    if (insights?.top_gap) {
      items.push(`
        <div class="mt-insight-item">
          <div class="mt-insight-icon mt-insight-icon-alert">${ALERT_ICON}</div>
          <div><b>${escapeHtml(titleCase(insights.top_gap.name))}</b> is your #1 skill gap<span>${escapeHtml(titleCase(insights.top_gap.demand))} demand across tracked postings</span></div>
        </div>
      `);
    }
    el.innerHTML = items.length
      ? items.join('')
      : '<p class="card-sub">Not enough data yet to surface a trend or gap.</p>';
  }

  function renderDemandSkills(skills) {
    const el = document.getElementById('mtDemandSkills');
    if (!el) return;
    if (!skills || !skills.length) {
      el.innerHTML = '<div class="empty-state"><p>No skill demand data yet.</p></div>';
      return;
    }
    el.innerHTML = skills.map(s => `
      <div class="demand-row">
        <span class="demand-name">${escapeHtml(s.name)}</span>
        <div class="demand-track"><div class="demand-fill" data-target="${s.score}%"></div></div>
        <span class="demand-val">${s.score}</span>
        <span class="coverage ${s.have ? 'have' : 'gap'}">${s.have ? 'Have it' : 'Gap'}</span>
      </div>
    `).join('');
    el.querySelectorAll('.demand-fill').forEach(playWidth);
  }

  // Donut = real market_fit.score (weighted demand coverage, same number
  // as the stat-row tile above) — not a second, different metric. Legend
  // below is the real opportunity_skills list.
  function renderOpportunitySkills(skills, fitScore) {
    const el = document.getElementById('mtOpportunitySkills');
    if (!el) return;

    const pct = fitScore ?? 0;
    const circumference = 2 * Math.PI * 40;
    const filled = (pct / 100) * circumference;
    const donutHtml = `
      <div class="skill-donut-wrap mt-opp-donut-wrap">
        <svg viewBox="0 0 100 100" class="skill-donut" role="img" aria-label="${pct}% match potential">
          <circle cx="50" cy="50" r="40" fill="none" stroke="var(--track)" stroke-width="14" />
          <circle cx="50" cy="50" r="40" fill="none" stroke="var(--accent)" stroke-width="14"
            stroke-dasharray="${filled} ${circumference - filled}" stroke-linecap="round"
            transform="rotate(-90 50 50)" />
          <text x="50" y="47" text-anchor="middle" class="skill-donut-figure">${pct}%</text>
          <text x="50" y="62" text-anchor="middle" class="skill-donut-caption">match potential</text>
        </svg>
      </div>
    `;

    if (!skills || !skills.length) {
      el.innerHTML = `${donutHtml}<p class="card-sub" style="text-align:center">No gaps found — your skills cover current demand well.</p>`;
      return;
    }

    const legend = skills.map(s => `
      <div class="mt-opp-legend-row">
        <span class="mt-opp-dot" style="background:${DEMAND_DOT[s.demand] || 'var(--ink-2)'}"></span>
        <span class="mt-opp-name">${escapeHtml(titleCase(s.name))}</span>
        <span class="mt-demand-tag ${s.demand}">${escapeHtml(s.demand)}</span>
      </div>
    `).join('');

    el.innerHTML = `
      <div class="mt-opp-layout">
        ${donutHtml}
        <div class="mt-opp-legend">${legend}</div>
      </div>
      <p class="mt-opp-tip">Closing these gaps directly raises your match fit score above.</p>
    `;
  }

  function renderRoleDemand(roles) {
    const el = document.getElementById('mtRoleDemand');
    if (!el) return;
    if (!roles || !roles.length) {
      el.innerHTML = '<div class="empty-state"><p>No role data yet — the AI Job Agent hasn\'t found postings to analyse.</p></div>';
      return;
    }
    el.innerHTML = roles.map(r => `
      <div class="mt-role-row">
        <span class="mt-role-title">${escapeHtml(r.title)}</span>
        <div class="mt-role-right">
          <span class="mt-role-count">${r.count}</span>
          ${r.trend ? `<span class="mt-trend mt-trend-${r.trend}">${TREND_SYMBOL[r.trend] || ''}</span>` : ''}
        </div>
      </div>
    `).join('');
  }

  function renderCareerPaths(paths, topGap) {
    const el = document.getElementById('mtCareerPaths');
    if (!el) return;
    if (!paths || !paths.length) {
      el.innerHTML = '<div class="empty-state"><p>Run the AI Job Agent to see your real top-matching career paths.</p></div>';
      return;
    }
    const cards = paths.map((p, i) => {
      const color = PATH_ACCENTS[i % PATH_ACCENTS.length];
      return `
        <div class="mt-path-card">
          <div class="mt-path-icon" style="background:color-mix(in srgb, ${color} 16%, transparent); color:${color}">${COMPASS_ICON}</div>
          <div class="mt-path-body">
            <div class="mt-path-title">${escapeHtml(p.title)}</div>
            <div class="mt-path-score-row">
              <span class="mt-path-score" style="color:${color}">${p.score}%</span>
              <span class="mt-path-score-label">Match</span>
            </div>
            <div class="mt-path-track"><div class="mt-path-fill" style="background:${color}" data-target="${p.score}%"></div></div>
          </div>
        </div>
      `;
    }).join('');
    const tip = topGap
      ? `<div class="mt-career-tip">Keep learning — closing <b>${escapeHtml(titleCase(topGap.name))}</b> could unlock stronger matches on these paths.</div>`
      : '';
    el.innerHTML = `<div class="mt-path-grid">${cards}</div>${tip}`;
    el.querySelectorAll('.mt-path-fill').forEach(playWidth);
  }

  function renderMomentum(rows) {
    const el = document.getElementById('mtMomentum');
    if (!el) return;
    if (!rows || !rows.length) {
      el.innerHTML = '<div class="empty-state"><p>Not enough real posting history yet in the tracked window to show momentum.</p></div>';
      return;
    }
    el.innerHTML = rows.map(m => `
      <div class="mt-momentum-row">
        <span class="mt-momentum-title">${escapeHtml(m.title)}</span>
        <span class="mt-momentum-pct">${UP_ICON}+${m.pct_change}%</span>
        <div class="mt-momentum-track"><div class="mt-momentum-fill" data-target="${m.bar_pct}%"></div></div>
      </div>
    `).join('');
    el.querySelectorAll('.mt-momentum-fill').forEach(playWidth);
  }

  // AI Job Agent stat tile — real shared global scan state, same source
  // as the dashboard/agent page. Not a per-user "daily limit"; this app's
  // agent runs one shared cycle for everyone.
  async function loadAgentStat() {
    try {
      const res = await fetch('/api/agent/status', { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      const countdown = document.getElementById('mtAgentCountdown');
      if (countdown && window.TalentMapCountdown) {
        window.TalentMapCountdown.set(countdown, data.next_scan_in_seconds || 0);
      }
      const caption = document.getElementById('mtAgentCaption');
      if (caption && data.jobs_in_pool != null) {
        caption.textContent = `Next scan · ${data.jobs_in_pool.toLocaleString()} jobs in pool`;
      }
    } catch (err) {
      console.error('Error loading agent status:', err);
    }
  }

  async function loadMarketTrends() {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
      const res = await fetch('/api/market-trends', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      renderHeader(data);
      renderMarketFit(data.market_fit);
      renderJobsAnalysed(data.postings_analyzed);
      renderPathCount(data.career_paths);
      renderInsights(data.insights);
      renderDemandSkills(data.demand_skills);
      renderOpportunitySkills(data.opportunity_skills, data.market_fit?.score);
      renderRoleDemand(data.role_demand);
      renderCareerPaths(data.career_paths, data.insights?.top_gap);
      renderMomentum(data.momentum);
    } catch (err) {
      console.error('Error loading market trends:', err);
    }

    loadAgentStat();
  }

  document.addEventListener('DOMContentLoaded', loadMarketTrends);
})();
