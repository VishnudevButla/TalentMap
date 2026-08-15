/*
 * agent.js — drives the /agent page. Two real endpoints:
 *   /api/agent/status      → global schedule/stats + this user's own
 *                            counters + AI Insights (plain-language
 *                            sentences built server-side from real data,
 *                            see app/step4_agent/routes_agent.py)
 *   /api/jobs/matches?sort=recent&limit=6 → Recent Discoveries: the
 *                            newest real job matches, not scan log rows.
 * No manual trigger and no per-user settings here — the scan is fully
 * global.
 */
(function () {
  const WORKER_BADGE = {
    healthy: { cls: 'good', label: 'Worker healthy' },
    stale: { cls: 'warn', label: 'Worker stale' },
    down: { cls: 'crit', label: 'Worker down' },
  };

  function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function timeAgo(iso) {
    if (!iso) return null;
    const diffMs = Date.now() - new Date(iso).getTime();
    if (Number.isNaN(diffMs)) return null;
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function renderInsights(insights) {
    const el = document.getElementById('agentInsights');
    if (!el) return;
    // insight.text is server-composed from our own data (see
    // _build_insights in routes_agent.py) and may contain <strong> tags —
    // same trusted-server-string pattern dashboard.js already uses for
    // match.note, not user input.
    el.innerHTML = (insights || []).length
      ? insights.map(i => `<div class="insight-row"><span class="insight-dot"></span><p>${i.text}</p></div>`).join('')
      : '<p class="card-sub">No insights yet — analyze your resume to get started.</p>';
  }

  function barRow(name, count, total, color) {
    const pct = total > 0 ? Math.round((count / total) * 100) : 0;
    return `
      <div class="agent-bar-row">
        <span class="agent-bar-name">${escapeHtml(name)}</span>
        <div class="agent-bar-track"><div class="agent-bar-fill" style="width:${pct}%;background:${color}"></div></div>
        <span class="agent-bar-val">${count}</span>
      </div>
    `;
  }

  function renderSourcesBreakdown(sourcesBreakdown) {
    const el = document.getElementById('sourcesBreakdown');
    if (!el) return;
    const rows = sourcesBreakdown || [];
    const total = rows.reduce((sum, s) => sum + s.count, 0);
    el.innerHTML = total > 0
      ? rows.map(s => barRow(s.label, s.count, total, 'var(--accent)')).join('')
      : '<p class="card-sub">The job pool is empty right now — nothing fetched yet, or postings have aged out (see Job Retention in Settings).</p>';
  }

  function renderMatchDistribution(distribution, totalMatches) {
    const el = document.getElementById('matchDistribution');
    if (!el) return;
    if (!totalMatches) {
      el.innerHTML = '<p class="card-sub">No matches yet — your agent will populate this once it finds real postings that fit your resume.</p>';
      return;
    }
    const rows = [
      ['Excellent', distribution.excellent, 'var(--gold)'],
      ['Good', distribution.good, 'var(--good)'],
      ['Needs work', distribution.warn, 'var(--warn)'],
      ['Weak fit', distribution.crit, 'var(--crit)'],
    ];
    el.innerHTML = rows.map(([label, count, color]) => barRow(label, count, totalMatches, color)).join('');
  }

  function applyStatus(data) {
    const countdown = document.getElementById('agentCountdown');
    if (countdown && window.TalentMapCountdown) {
      window.TalentMapCountdown.set(countdown, data.next_scan_in_seconds || 0);
    }

    const lastScanWhen = document.getElementById('lastScanWhen');
    if (lastScanWhen) {
      const ago = timeAgo(data.last_scan_at);
      lastScanWhen.textContent = ago ? `Last ran ${ago}` : 'No global scan has run yet.';
    }

    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    setText('lastScanFetched', data.last_fetch_fetched ?? 0);
    setText('lastScanSaved', data.last_fetch_saved ?? 0);
    setText('statNewMatches', data.new_matches_today ?? 0);
    setText('statTotalMatches', data.total_matches ?? 0);
    setText('statHighQuality', data.high_quality_matches ?? 0);
    setText('statEmailsSent', data.emails_sent_today ?? 0);
    setText('statJobsInPool', data.jobs_in_pool ?? 0);
    setText('statUsersMatched', data.last_users_matched ?? 0);
    setText('statTotalNewMatches', data.last_total_new_matches ?? 0);

    renderSourcesBreakdown(data.sources_breakdown);
    renderMatchDistribution(data.match_distribution || {}, data.total_matches ?? 0);

    const workerBadge = document.getElementById('agentWorkerBadge');
    if (workerBadge && data.worker) {
      const info = WORKER_BADGE[data.worker.status] || { cls: 'warn', label: 'Unknown' };
      workerBadge.className = `stat-status ${info.cls}`;
      workerBadge.textContent = info.label;
    }

    renderInsights(data.insights);
  }

  async function loadStatus() {
    try {
      const res = await fetch('/api/agent/status', { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      applyStatus(await res.json());
    } catch (err) {
      console.error('Error loading agent status:', err);
    }
  }

  function renderDiscoveryRow(job) {
    const when = timeAgo(job.discovered_at) || '';
    return `
      <div class="history-item" style="padding:.7rem 0">
        <a href="${job.url || '#'}" target="_blank" rel="noopener" style="display:block;font-weight:600;font-size:.85rem;text-decoration:none">${escapeHtml(job.title || 'Role')}</a>
        <div class="history-meta">
          <span>${escapeHtml(job.company || '')}</span>
          <span class="stat-status ${job.status}">${job.match_score}% match</span>
          <span>${escapeHtml(when)}</span>
        </div>
      </div>
    `;
  }

  async function loadRecentDiscoveries() {
    const el = document.getElementById('recentDiscoveries');
    if (!el) return;
    try {
      const res = await fetch('/api/jobs/matches?sort=recent&limit=6', { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      el.innerHTML = (data.results || []).length
        ? data.results.map(renderDiscoveryRow).join('')
        : '<p class="card-sub">No discoveries yet — your agent will populate this once it finds real postings that fit your resume.</p>';
    } catch (err) {
      el.innerHTML = '<p class="card-sub">Couldn\'t load recent discoveries right now.</p>';
      console.error('Error loading recent discoveries:', err);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadStatus();
    loadRecentDiscoveries();
  });
})();
