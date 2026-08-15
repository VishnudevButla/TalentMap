/*
 * matches.js — fetches every real match from GET /api/jobs/matches (real,
 * see app/step4_agent/routes_agent.py) and renders the full, unabridged,
 * filterable list. The dashboard only ever shows a top-5 preview of this
 * same data; this page is where "View all matches" actually leads.
 *
 * Same accordion pattern as history.js: click a row to expand a preview
 * panel with the real per-component match breakdown (skills/experience/
 * projects/certifications — from matcher.py's embeddings_4.py scoring),
 * salary if the source posting had one, detected skills, the full job
 * description, and a direct Apply link.
 */
(function () {
  const COMPONENT_LABELS = {
    skills: 'Skills',
    experience: 'Experience',
    projects: 'Projects',
    certifications: 'Certifications',
  };

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function playWidth(el) {
    const target = el.dataset.target;
    if (target == null) return;
    requestAnimationFrame(() => { el.style.width = target; });
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

  function formatSalary(min, max) {
    if (min == null && max == null) return null;
    const fmt = n => `$${Math.round(n).toLocaleString()}`;
    if (min != null && max != null) return `${fmt(min)} – ${fmt(max)}`;
    return fmt(min != null ? min : max);
  }

  function renderPanel(item) {
    const scores = item.component_scores || {};
    const scoreRows = Object.keys(COMPONENT_LABELS)
      .filter(key => scores[key] != null)
      .map(key => {
        const pct = Math.max(0, Math.min(100, Math.round(scores[key] * 100)));
        return `
          <div class="demand-row">
            <span class="demand-name">${COMPONENT_LABELS[key]}</span>
            <div class="demand-track"><div class="demand-fill" data-target="${pct}%"></div></div>
            <span class="demand-val">${pct}</span>
          </div>
        `;
      }).join('');

    const breakdownHtml = scoreRows
      ? `<div><h4>Match breakdown</h4>${scoreRows}</div>`
      : `<p class="card-sub">No detailed breakdown available for this match.</p>`;

    const salary = formatSalary(item.salary_min, item.salary_max);
    const salaryHtml = `<div class="match-fact"><span>Salary</span><b>${salary ? escapeHtml(salary) : 'Not listed'}</b></div>`;

    const skillsHtml = (item.skills_detected || []).length
      ? `<div class="ner-group"><h5>Skills detected in this posting</h5><div class="chips">${
          item.skills_detected.map(s => `<span class="skill-chip have">${escapeHtml(s)}</span>`).join('')
        }</div></div>`
      : '';

    const descriptionHtml = item.description
      ? `<div><h4>Job description</h4><p class="match-description">${escapeHtml(item.description)}</p></div>`
      : `<p class="card-sub">No description available for this posting.</p>`;

    return `
      <div class="history-panel" hidden>
        <div class="history-panel-actions">
          <a href="/matches/${encodeURIComponent(item.job_id)}" class="btn-ghost btn-sm" style="text-decoration:none">View details →</a>
          <a href="${item.url || '#'}" target="_blank" rel="noopener" class="btn-primary btn-sm" style="text-decoration:none">Apply →</a>
        </div>
        <div class="match-facts">${salaryHtml}</div>
        ${breakdownHtml}
        ${skillsHtml}
        ${descriptionHtml}
      </div>
    `;
  }

  function renderItem(item) {
    const posted = timeAgo(item.posted_at);
    const source = item.source ? item.source.charAt(0).toUpperCase() + item.source.slice(1) : null;
    const logo = (item.company || '?')[0].toUpperCase();

    return `
      <div class="history-item" data-status="${item.status || ''}" data-remote="${item.remote_type || ''}">
        <button type="button" class="history-row-toggle" aria-expanded="false">
          <div class="job-logo">${escapeHtml(logo)}</div>
          <div class="history-main">
            <h3>${escapeHtml(item.title || 'Untitled role')}</h3>
            <div class="history-meta">
              <span>${escapeHtml(item.company || 'Unknown company')}</span>
              <span>${escapeHtml(item.location || 'Location unknown')}</span>
              ${item.remote_type ? `<span class="chip">${escapeHtml(item.remote_type)}</span>` : ''}
              ${source ? `<span class="chip">${escapeHtml(source)}</span>` : ''}
              ${posted ? `<span>Posted ${posted}</span>` : ''}
            </div>
          </div>
          <div class="history-toggle-right">
            <span class="stat-status ${item.status || ''}">${item.match_score}% Match</span>
            <span class="history-chevron">&#9662;</span>
          </div>
        </button>
        ${renderPanel(item)}
      </div>
    `;
  }

  function wireInteractions(listEl) {
    listEl.querySelectorAll('.history-row-toggle').forEach(toggle => {
      toggle.addEventListener('click', () => {
        const panel = toggle.nextElementSibling;
        const isOpen = toggle.getAttribute('aria-expanded') === 'true';

        listEl.querySelectorAll('.history-row-toggle[aria-expanded="true"]').forEach(other => {
          if (other !== toggle) {
            other.setAttribute('aria-expanded', 'false');
            other.nextElementSibling.hidden = true;
          }
        });

        toggle.setAttribute('aria-expanded', String(!isOpen));
        panel.hidden = isOpen;
        if (!isOpen) panel.querySelectorAll('.demand-fill').forEach(playWidth);
      });
    });
  }

  function wireFilters(listEl) {
    const pills = document.querySelectorAll('#jobFilterPills .pill');
    pills.forEach(pill => {
      pill.addEventListener('click', () => {
        pills.forEach(p => p.classList.remove('is-active'));
        pill.classList.add('is-active');
        const filter = pill.dataset.filter;
        listEl.querySelectorAll('.history-item').forEach(row => {
          let visible = true;
          if (filter === 'excellent' || filter === 'good') {
            visible = row.dataset.status === filter;
          } else if (filter === 'remote') {
            visible = row.dataset.remote === 'remote';
          }
          row.classList.toggle('is-hidden', !visible);
        });
      });
    });
  }

  // Real substring filter against title/company/detected skills — reached
  // from the dashboard search box (?q=...), not a decorative input.
  function filterBySearch(results, q) {
    const needle = q.trim().toLowerCase();
    if (!needle) return results;
    return results.filter(item => {
      const haystack = [item.title, item.company, ...(item.skills_detected || [])]
        .filter(Boolean).join(' ').toLowerCase();
      return haystack.includes(needle);
    });
  }

  function renderSearchNote(q, matchCount) {
    const countEl = document.getElementById('matchesCount');
    if (!countEl) return;
    const note = document.createElement('p');
    note.className = 'card-sub';
    note.style.marginTop = '.3rem';
    note.innerHTML = `Showing ${matchCount} result${matchCount === 1 ? '' : 's'} for "${escapeHtml(q)}" · <a href="/matches" class="link">Clear</a>`;
    countEl.after(note);
  }

  async function loadMatches() {
    const listEl = document.getElementById('matchesList');
    const countEl = document.getElementById('matchesCount');
    const token = localStorage.getItem('token');
    if (!token) return;

    const q = new URLSearchParams(window.location.search).get('q') || '';

    try {
      const res = await fetch('/api/jobs/matches', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      let results = data.results || [];
      if (q) results = filterBySearch(results, q);

      if (countEl) {
        countEl.textContent = data.count
          ? `${data.count} real match${data.count === 1 ? '' : 'es'} against your latest resume`
          : 'No matches yet';
      }
      if (q) renderSearchNote(q, results.length);

      if (!results.length) {
        listEl.innerHTML = q
          ? `<div class="empty-state"><p>No matches found for "${escapeHtml(q)}".</p></div>`
          : `
          <div class="empty-state">
            <p>No job matches yet. The AI Job Agent will populate this once it finds real postings that fit your resume.</p>
            <a class="see-all" href="/agent">Go to AI Job Agent →</a>
          </div>
        `;
        return;
      }

      listEl.innerHTML = results.map(renderItem).join('');
      wireInteractions(listEl);
      wireFilters(listEl);
    } catch (err) {
      listEl.innerHTML = '<div class="empty-state"><p>Couldn\'t load your matches right now.</p></div>';
      console.error('Error loading matches:', err);
    }
  }

  document.addEventListener('DOMContentLoaded', loadMatches);
})();
