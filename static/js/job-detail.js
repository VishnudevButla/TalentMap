/*
 * job-detail.js — drives /matches/<job_id>. Every number on this page
 * comes from GET /api/jobs/matches/{job_id} (real, see
 * app/step4_agent/routes_agent.py's get_job_match_detail) — no separate
 * "company profile" or "reviews" data source exists anywhere in this app,
 * so this page deliberately has no Company/Reviews tabs; it would just be
 * decoration with nothing real behind it.
 */
(function () {
  const COMPONENT_LABELS = { skills: 'Skills', experience: 'Experience', education: 'Education', certifications: 'Certifications' };
  let current = null;

  function jobIdFromPath() {
    const parts = window.location.pathname.split('/').filter(Boolean);
    return decodeURIComponent(parts[parts.length - 1] || '');
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function formatSalary(min, max) {
    if (!min && !max) return null;
    const fmt = n => `$${Math.round(n / 1000)}k`;
    return min && max ? `${fmt(min)} - ${fmt(max)}` : fmt(min || max);
  }

  function timeAgo(iso) {
    if (!iso) return null;
    const diffMs = Date.now() - new Date(iso).getTime();
    const days = Math.floor(diffMs / 86400000);
    if (days < 1) return 'today';
    if (days === 1) return '1 day ago';
    if (days < 30) return `${days} days ago`;
    const months = Math.floor(days / 30);
    return `${months} month${months === 1 ? '' : 's'} ago`;
  }

  function formatDateTime(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  }

  function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  // ---------------------------------------------------------------------
  // Radar chart — 4 real scored components (Skills/Experience/Education/
  // Certifications). A component the matcher couldn't compare (no data on
  // one side) plots at 0 and is labeled "No data" rather than hiding the
  // axis, which would make the polygon's shape misleading.
  // ---------------------------------------------------------------------

  function renderRadar(componentScores) {
    const el = document.getElementById('jdRadar');
    if (!el) return;
    const keys = ['skills', 'experience', 'education', 'certifications'];
    // cx/cy/maxR leave enough room that labelRadius + half of the widest
    // label ("Certifications") never crosses the viewBox edge — a tighter
    // first pass at this clipped every side label; verified by actually
    // rendering it, not by eyeballing the numbers.
    const cx = 130, cy = 130, maxR = 70, labelRadius = maxR + 30;
    const angleFor = i => -Math.PI / 2 + (i * 2 * Math.PI) / keys.length;

    const points = keys.map((k, i) => {
      const raw = componentScores ? componentScores[k] : null;
      const pct = raw == null ? 0 : Math.max(0, Math.min(1, raw));
      const angle = angleFor(i);
      const r = pct * maxR;
      return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), pct, hasData: raw != null };
    });

    const polygon = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

    const rings = [0.25, 0.5, 0.75, 1].map(f => {
      const ringPts = keys.map((_, i) => {
        const angle = angleFor(i);
        return `${(cx + f * maxR * Math.cos(angle)).toFixed(1)},${(cy + f * maxR * Math.sin(angle)).toFixed(1)}`;
      }).join(' ');
      return `<polygon points="${ringPts}" class="jd-radar-ring" />`;
    }).join('');

    const spokes = keys.map((_, i) => {
      const angle = angleFor(i);
      return `<line x1="${cx}" y1="${cy}" x2="${(cx + maxR * Math.cos(angle)).toFixed(1)}" y2="${(cy + maxR * Math.sin(angle)).toFixed(1)}" class="jd-radar-spoke" />`;
    }).join('');

    const labels = keys.map((k, i) => {
      const angle = angleFor(i);
      const x = cx + labelRadius * Math.cos(angle);
      const y = cy + labelRadius * Math.sin(angle);
      const p = points[i];
      const valueText = p.hasData ? `${Math.round(p.pct * 100)}%` : 'No data';
      return `
        <text x="${x.toFixed(1)}" y="${(y - 5).toFixed(1)}" text-anchor="middle" class="jd-radar-label">${COMPONENT_LABELS[k]}</text>
        <text x="${x.toFixed(1)}" y="${(y + 9).toFixed(1)}" text-anchor="middle" class="jd-radar-value${p.hasData ? '' : ' jd-radar-value-empty'}">${valueText}</text>
      `;
    }).join('');

    el.innerHTML = `
      <svg viewBox="0 0 260 260" class="jd-radar-svg">
        ${rings}
        ${spokes}
        <polygon points="${polygon}" class="jd-radar-fill" />
        ${points.map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3.5" class="jd-radar-dot" />`).join('')}
        ${labels}
      </svg>
    `;
  }

  // ---------------------------------------------------------------------
  // Tabs
  // ---------------------------------------------------------------------

  function renderOverviewTab(job) {
    const facts = [
      ['Source', job.source ? job.source.charAt(0).toUpperCase() + job.source.slice(1) : null],
      ['Location', job.location],
      ['Work type', job.remote_type],
      ['Posted', timeAgo(job.posted_at)],
      ['Salary', formatSalary(job.salary_min, job.salary_max)],
    ].filter(([, v]) => v);

    const descHtml = job.description
      ? `<div class="jd-description">${escapeHtml(job.description).replace(/\n{2,}/g, '</p><p>').replace(/\n/g, '<br>')}</div>`
      : '<p class="card-sub">No description available for this posting.</p>';

    return `
      <h4 class="ner-section-label">Job overview</h4>
      <div class="jd-facts">${facts.map(([k, v]) => `<div><span>${escapeHtml(k)}</span><b>${escapeHtml(v)}</b></div>`).join('')}</div>
      <h4 class="ner-section-label" style="margin-top:1.3rem">Description</h4>
      <p class="jd-description-wrap">${descHtml}</p>
    `;
  }

  function renderWhyTab(job) {
    const scores = job.component_scores || {};
    const entries = Object.entries(scores).filter(([, v]) => v != null);
    const top = entries.sort((a, b) => b[1] - a[1])[0];
    const topSkills = (job.matched_skills || []).slice(0, 3);

    const rows = ['skills', 'experience', 'education', 'certifications'].map(k => {
      const v = scores[k];
      const pct = v == null ? null : Math.round(v * 100);
      return `
        <div class="jd-score-row">
          <span class="jd-score-label">${COMPONENT_LABELS[k]} match</span>
          <div class="demand-track"><div class="demand-fill" style="width:${pct || 0}%"></div></div>
          <span class="jd-score-val">${pct == null ? 'No data' : pct + '%'}</span>
        </div>
      `;
    }).join('');

    const strengthNote = top
      ? `Your ${COMPONENT_LABELS[top[0]].toLowerCase()}${topSkills.length ? ' — especially ' + topSkills.map(escapeHtml).join(', ') : ''} line up well with this role.`
      : 'Not enough data yet to explain this match in detail.';

    return `
      <h4 class="ner-section-label">Score breakdown</h4>
      ${rows}
      ${top ? `
        <div class="jd-strength-note">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8L12 2z"/></svg>
          <div><b>Top strength</b><p>${strengthNote}</p></div>
        </div>
      ` : ''}
    `;
  }

  function renderRequirementsTab(job) {
    const matched = job.matched_skills || [];
    const missing = job.missing_skills || [];
    if (!matched.length && !missing.length) {
      return '<p class="card-sub">No specific skills were detected for this posting.</p>';
    }
    return `
      ${matched.length ? `<h4 class="ner-section-label">On your resume</h4><div class="chips">${matched.map(s => `<span class="skill-chip have">${escapeHtml(s)}</span>`).join('')}</div>` : ''}
      ${missing.length ? `<h4 class="ner-section-label" style="margin-top:1.1rem">Not on your resume yet</h4><div class="chips">${missing.map(s => `<span class="skill-chip gap">${escapeHtml(s)}</span>`).join('')}</div>` : ''}
    `;
  }

  function renderTab(tab) {
    const el = document.getElementById('jdTabContent');
    if (!el || !current) return;
    if (tab === 'overview') el.innerHTML = renderOverviewTab(current);
    else if (tab === 'why') el.innerHTML = renderWhyTab(current);
    else if (tab === 'requirements') el.innerHTML = renderRequirementsTab(current);
  }

  function wireTabs() {
    document.getElementById('jdTabs')?.addEventListener('click', (e) => {
      const btn = e.target.closest('.ner-tab');
      if (!btn) return;
      document.querySelectorAll('#jdTabs .ner-tab').forEach(t => t.classList.toggle('is-active', t === btn));
      renderTab(btn.dataset.tab);
    });
  }

  // ---------------------------------------------------------------------
  // Similar jobs + activity
  // ---------------------------------------------------------------------

  function renderSimilar(jobs) {
    const el = document.getElementById('jdSimilarList');
    const card = document.getElementById('jdSimilarCard');
    if (!el) return;
    if (!jobs || !jobs.length) { if (card) card.classList.add('is-hidden'); return; }
    el.innerHTML = jobs.map(j => {
      const salary = formatSalary(j.salary_min, j.salary_max);
      return `
        <a href="/matches/${encodeURIComponent(j.job_id)}" class="jd-similar-row">
          <div class="job-logo">${escapeHtml((j.company || '?')[0].toUpperCase())}</div>
          <div class="jd-similar-body">
            <h4>${escapeHtml(j.title || '')}</h4>
            <p>${escapeHtml(j.company || '')} · ${escapeHtml(j.location || '')}${salary ? ' · ' + salary : ''}</p>
          </div>
          <span class="stat-status ${j.status || ''}">${j.match_score}%</span>
        </a>
      `;
    }).join('');
  }

  function renderActivity(job) {
    const el = document.getElementById('jdActivityList');
    if (!el) return;
    const rows = [
      ['Viewed', job.first_viewed_at, 'eye'],
      ['Saved', job.saved ? job.saved_at : null, 'bookmark'],
      ['Applied', job.applied ? job.applied_at : null, 'check'],
    ];
    el.innerHTML = rows.map(([label, ts]) => `
      <div class="jd-activity-row">
        <span>${label}</span>
        <b class="${ts ? '' : 'jd-activity-empty'}">${ts ? formatDateTime(ts) : '—'}</b>
      </div>
    `).join('');
  }

  // ---------------------------------------------------------------------
  // Header + actions
  // ---------------------------------------------------------------------

  function renderHeader(job) {
    document.getElementById('jdLogo').innerHTML = job.company_logo_url
      ? `<img src="${escapeHtml(job.company_logo_url)}" alt="" />`
      : escapeHtml((job.company || '?')[0].toUpperCase());

    const matchBadge = document.getElementById('jdMatchBadge');
    matchBadge.textContent = `${job.match_score}% Match`;
    matchBadge.className = `stat-status ${job.status || ''}`;

    document.getElementById('jdBestBadge').classList.toggle('is-hidden', !job.is_best_match);
    document.getElementById('jdAppliedBadge').classList.toggle('is-hidden', !job.applied);

    document.getElementById('jdTitle').textContent = job.title || 'Untitled role';
    document.getElementById('jdCompany').textContent = job.company || 'Unknown company';

    const salary = formatSalary(job.salary_min, job.salary_max);
    document.getElementById('jdMeta').textContent = [job.location, job.remote_type, salary].filter(Boolean).join(' · ');

    const chipsEl = document.getElementById('jdChips');
    const posted = timeAgo(job.posted_at);
    chipsEl.innerHTML = [
      job.source ? `<span class="chip">${escapeHtml(job.source.charAt(0).toUpperCase() + job.source.slice(1))}</span>` : '',
      posted ? `<span class="chip">Posted ${posted}</span>` : '',
    ].join('');

    document.getElementById('jdApplyBtn').href = job.url || '#';
    document.getElementById('jdSaveBtn').classList.toggle('is-saved', !!job.saved);
  }

  async function toggleApplied(jobId) {
    const token = localStorage.getItem('token');
    const nowApplied = true; // "Apply Now" only ever transitions to applied
    try {
      await fetch(`/api/jobs/matches/${encodeURIComponent(jobId)}/apply`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ applied: nowApplied }),
      });
    } catch (e) { /* the outbound tab still opens even if this write fails */ }
  }

  function wireActions(jobId) {
    document.getElementById('jdApplyBtn')?.addEventListener('click', () => {
      toggleApplied(jobId);
      document.getElementById('jdAppliedBadge').classList.remove('is-hidden');
    });

    document.getElementById('jdSaveBtn')?.addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const nowSaved = !btn.classList.contains('is-saved');
      btn.disabled = true;
      try {
        const res = await fetch(`/api/jobs/matches/${encodeURIComponent(jobId)}/save`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...authHeaders() },
          body: JSON.stringify({ saved: nowSaved }),
        });
        if (res.ok) btn.classList.toggle('is-saved', nowSaved);
      } catch (err) { /* leave state unchanged */ }
      btn.disabled = false;
    });

    document.getElementById('jdShareBtn')?.addEventListener('click', async () => {
      const btn = document.getElementById('jdShareBtn');
      const url = window.location.href;
      if (navigator.share) {
        try { await navigator.share({ title: document.title, url }); return; } catch (e) { /* user cancelled or unsupported — fall through to copy */ }
      }
      try {
        await navigator.clipboard.writeText(url);
        const original = btn.textContent;
        btn.textContent = 'Link copied!';
        setTimeout(() => { btn.textContent = original; }, 1500);
      } catch (e) { /* clipboard unavailable — no-op */ }
    });
  }

  // ---------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------

  async function load() {
    const jobId = jobIdFromPath();
    const token = localStorage.getItem('token');
    if (!token) { window.location.href = '/login'; return; }

    let res, data;
    try {
      res = await fetch(`/api/jobs/matches/${encodeURIComponent(jobId)}`, { headers: authHeaders() });
      data = await res.json().catch(() => ({}));
    } catch (e) {
      document.getElementById('jdLoading').classList.add('is-hidden');
      document.getElementById('jdError').classList.remove('is-hidden');
      document.getElementById('jdErrorMsg').textContent = 'Network error. Please check your connection and try again.';
      return;
    }

    if (res.status === 401) { window.location.href = '/login'; return; }
    if (!res.ok) {
      document.getElementById('jdLoading').classList.add('is-hidden');
      document.getElementById('jdError').classList.remove('is-hidden');
      document.getElementById('jdErrorMsg').textContent = data.detail || 'This job match could not be found.';
      return;
    }

    current = data;
    renderHeader(data);
    renderTab('overview');
    renderRadar(data.component_scores);
    renderSimilar(data.similar_jobs);
    renderActivity(data);
    wireActions(jobId);

    document.getElementById('jdLoading').classList.add('is-hidden');
    document.getElementById('jdContent').classList.remove('is-hidden');
  }

  document.addEventListener('DOMContentLoaded', () => {
    wireTabs();
    load();
  });
})();
