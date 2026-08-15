/*
 * history.js — "Your Resumes" page. Fetches GET /api/history (real data:
 * every resume the user has uploaded, the active one flagged via
 * is_active, and a pagination-independent `stats` summary — see
 * app/step1_api/routes_history.py) and renders:
 *   - a stats row (total resumes / active / best match / skills extracted)
 *   - a "Current Resume" hero card (hidden entirely if there is none —
 *     no fabricated placeholder card)
 *   - the full resume history list, sortable client-side (already-fetched
 *     data, no re-fetch per sort)
 *   - a shared "Extracted Information" panel (tabs + a 2-slice donut of
 *     matched vs. missing skills) opened from any row
 * Delete and rename both call real endpoints and re-fetch afterward.
 */
(function () {
  let historyResults = [];
  let currentSort = 'newest';
  let pendingDeleteId = null;
  let openKebabMenu = null;

  // -----------------------------------------------------------------------
  // Small helpers
  // -----------------------------------------------------------------------

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function formatDateTime(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    const datePart = d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
    const timePart = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    return `${datePart} · ${timePart}`;
  }

  function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  // -----------------------------------------------------------------------
  // Stats row
  // -----------------------------------------------------------------------

  function renderStats(stats) {
    const el = document.getElementById('resumeStatsRow');
    if (!el) return;
    const cards = [
      { label: 'Total Resumes', value: stats.total_resumes },
      { label: 'Active Resume', value: stats.has_active_resume ? 1 : 0 },
      { label: 'Best Match Score', value: stats.best_match_score != null ? `${stats.best_match_score}%` : '—' },
      { label: 'Skills Extracted', value: stats.skills_extracted },
    ];
    el.innerHTML = cards.map(c => `
      <div class="card resume-stat">
        <span class="stat-label">${c.label}</span>
        <div class="stat-figure">${c.value}</div>
      </div>
    `).join('');
  }

  // -----------------------------------------------------------------------
  // Match / score bits shared by the hero card and history rows
  // -----------------------------------------------------------------------

  function scoreBlock(match) {
    if (!match) {
      return `<p class="card-sub" style="margin:0">Not scored yet — analyze this resume to get real matches.</p>`;
    }
    return `
      <div class="resume-score">
        <span class="resume-score-value ${match.status}">${match.score}%</span>
        <span class="card-sub">Match Score</span>
      </div>
      <div class="meter"><span style="width:${match.score}%"></span></div>
      <p class="card-sub resume-best-match">${match.note}</p>
    `;
  }

  function countChips(counts) {
    const labels = { skills: 'Skills', experience: 'Experience', education: 'Education', projects: 'Projects', certifications: 'Certifications' };
    return Object.entries(labels)
      .filter(([key]) => counts[key] > 0)
      .map(([key, label]) => `<span class="chip">${counts[key]} ${label}</span>`)
      .join('');
  }

  function versionBadge(item) {
    if (item.is_active) return `<span class="stat-status good">Current</span>`;
    if (!item.entities) return `<span class="stat-status" style="background:var(--track);color:var(--ink-2)">Not analyzed</span>`;
    return `<span class="stat-status" style="background:var(--track);color:var(--ink-2)">Previous version</span>`;
  }

  // -----------------------------------------------------------------------
  // Kebab menu (shared by hero + rows)
  // -----------------------------------------------------------------------

  function kebabMenu(item) {
    return `
      <div class="kebab-wrap">
        <button type="button" class="kebab-btn" data-kebab="${item.resume_id}" aria-label="Resume actions">&#8942;</button>
        <div class="kebab-menu" data-kebab-menu="${item.resume_id}" hidden>
          <button type="button" data-action="view" data-id="${item.resume_id}">View extracted info</button>
          <button type="button" data-action="download" data-id="${item.resume_id}">Download PDF</button>
          <button type="button" data-action="rename" data-id="${item.resume_id}">Rename</button>
          <button type="button" data-action="delete" data-id="${item.resume_id}" class="is-danger">Delete</button>
        </div>
      </div>
    `;
  }

  // -----------------------------------------------------------------------
  // Current Resume hero card
  // -----------------------------------------------------------------------

  function renderCurrentResume(item) {
    const section = document.getElementById('currentResumeSection');
    const container = document.getElementById('currentResumeCard');
    if (!section || !container) return;

    if (!item) {
      section.style.display = 'none';
      return;
    }
    section.style.display = '';

    const uploaded = formatDateTime(item.uploaded_at);
    const analyzed = formatDateTime(item.analyzed_at);

    container.innerHTML = `
      <div class="resume-hero" data-resume-id="${item.resume_id}">
        <div class="resume-hero-main">
          <div class="resume-file-icon">PDF</div>
          <div class="resume-hero-info">
            <div class="resume-hero-title">
              <h3 data-filename-el>${escapeHtml(item.filename)}</h3>
              ${versionBadge(item)}
            </div>
            <div class="history-meta">
              ${uploaded ? `<span>Uploaded ${escapeHtml(uploaded)}</span>` : ''}
              ${analyzed ? `<span>Analyzed ${escapeHtml(analyzed)}</span>` : '<span>Not analyzed yet</span>'}
            </div>
            <div class="history-meta" style="margin-top:.5rem">${countChips(item.entity_counts)}</div>
            <div class="resume-hero-actions">
              <button type="button" class="btn-primary btn-sm" data-view="${item.resume_id}">View Extracted Info</button>
              <button type="button" class="btn-ghost btn-sm" data-download="${item.resume_id}">Download</button>
            </div>
          </div>
        </div>
        <div class="resume-hero-score">
          ${scoreBlock(item.match)}
        </div>
        ${kebabMenu(item)}
      </div>
    `;
  }

  // -----------------------------------------------------------------------
  // Resume History list
  // -----------------------------------------------------------------------

  function sortResults(results, mode) {
    const copy = results.slice();
    if (mode === 'oldest') {
      copy.sort((a, b) => new Date(a.uploaded_at || 0) - new Date(b.uploaded_at || 0));
    } else if (mode === 'score') {
      copy.sort((a, b) => (b.match?.score ?? -1) - (a.match?.score ?? -1));
    } else {
      copy.sort((a, b) => new Date(b.uploaded_at || 0) - new Date(a.uploaded_at || 0));
    }
    return copy;
  }

  function renderHistoryRow(item) {
    const uploaded = formatDateTime(item.uploaded_at);
    const analyzed = formatDateTime(item.analyzed_at);

    return `
      <div class="history-row-card" data-resume-id="${item.resume_id}">
        <div class="resume-file-icon resume-file-icon-sm">PDF</div>
        <div class="history-row-main">
          <div class="resume-hero-title">
            <h3>${escapeHtml(item.filename)}</h3>
            ${versionBadge(item)}
          </div>
          <div class="history-meta">
            ${uploaded ? `<span>Uploaded ${escapeHtml(uploaded)}</span>` : ''}
            ${analyzed ? `<span>Analyzed ${escapeHtml(analyzed)}</span>` : '<span>Not analyzed</span>'}
          </div>
          <div class="history-meta" style="margin-top:.4rem">${countChips(item.entity_counts)}</div>
        </div>
        <div class="history-row-score">${scoreBlock(item.match)}</div>
        ${kebabMenu(item)}
      </div>
    `;
  }

  function renderHistoryList() {
    const listEl = document.getElementById('historyList');
    if (!listEl) return;

    if (!historyResults.length) {
      listEl.innerHTML = '<div class="empty-state"><p>No resumes yet — upload your first one to see it here.</p></div>';
      return;
    }

    // The active resume already has its own hero card above with the same
    // actions (view/download/rename/delete) — listing it again here too
    // duplicated both the row and its resume_id-keyed kebab menu, which is
    // what made the wrong menu open when a row's kebab was clicked (see
    // wireGlobalEvents' kebab handler). "History" now means "everything
    // else," not "everything including the one already shown above."
    const others = historyResults.filter(r => !r.is_active);
    if (!others.length) {
      listEl.innerHTML = '<div class="empty-state"><p>No other resume versions yet.</p></div>';
      return;
    }

    const sorted = sortResults(others, currentSort);
    listEl.innerHTML = sorted.map(renderHistoryRow).join('');
  }

  // -----------------------------------------------------------------------
  // Extracted Information panel — shared, opened from hero or any row.
  // Real data only: entities come straight from analysis_collection via
  // GET /api/history, nothing computed client-side except the skill
  // donut's two real counts (matched_skills vs. missing_skills — both
  // already provided, no third "partial match" category exists in the
  // data model, so this stays an honest 2-slice breakdown).
  // -----------------------------------------------------------------------

  const NER_LABELS = { skills: 'Skills', experience: 'Experience', education: 'Education', projects: 'Projects', certifications: 'Certifications' };
  let activeExtractedItem = null;
  let activeTab = 'skills';

  function renderNerTab(tabKey) {
    const el = document.getElementById('nerTabContent');
    if (!el || !activeExtractedItem) return;
    const entities = activeExtractedItem.entities;
    const items = entities ? entities[tabKey] : null;

    if (!entities) {
      el.innerHTML = `<p class="card-sub">This resume hasn't been analyzed yet.</p>`;
      return;
    }
    if (!items || !items.length) {
      el.innerHTML = `<p class="card-sub">No ${NER_LABELS[tabKey].toLowerCase()} were extracted from this resume.</p>`;
      return;
    }
    const isChipList = tabKey === 'skills' || tabKey === 'certifications';
    el.innerHTML = isChipList
      ? `<div class="chips">${items.map(s => `<span class="skill-chip have">${escapeHtml(s)}</span>`).join('')}</div>`
      : `<ul class="ner-list">${items.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>`;
  }

  function renderSkillSummary() {
    const el = document.getElementById('skillSummaryPanel');
    if (!el || !activeExtractedItem) return;

    const matched = (activeExtractedItem.matched_skills || []).length;
    const missing = (activeExtractedItem.missing_skills || []).length;
    const total = matched + missing;

    if (total === 0) {
      el.innerHTML = `<h4>Skill Summary</h4><p class="card-sub">Not enough data yet to compare against market demand.</p>`;
      return;
    }

    const matchedPct = Math.round((matched / total) * 100);
    // Donut via stroke-dasharray on a circle, circumference = 2*pi*r (r=40 -> ~251.33).
    const circumference = 2 * Math.PI * 40;
    const matchedLen = (matchedPct / 100) * circumference;

    el.innerHTML = `
      <h4>Skill Summary</h4>
      <div class="skill-donut-wrap">
        <svg viewBox="0 0 100 100" class="skill-donut" role="img" aria-label="${matched} matched skills, ${missing} missing skills">
          <circle cx="50" cy="50" r="40" fill="none" stroke="var(--warn)" stroke-width="14" />
          <circle cx="50" cy="50" r="40" fill="none" stroke="var(--good)" stroke-width="14"
            stroke-dasharray="${matchedLen} ${circumference - matchedLen}" stroke-linecap="round"
            transform="rotate(-90 50 50)" />
          <text x="50" y="47" text-anchor="middle" class="skill-donut-figure">${matchedPct}%</text>
          <text x="50" y="62" text-anchor="middle" class="skill-donut-caption">matched</text>
        </svg>
        <div class="skill-donut-legend">
          <div><span class="dot" style="background:var(--good)"></span> Matched Skills <b>${matched}</b></div>
          <div><span class="dot" style="background:var(--warn)"></span> Missing (in-demand) <b>${missing}</b></div>
        </div>
      </div>
    `;
  }

  function openExtractedInfo(item) {
    activeExtractedItem = item;
    activeTab = 'skills';
    document.getElementById('extractedInfoFilename').textContent = item.filename;
    document.querySelectorAll('.ner-tab').forEach(t => t.classList.toggle('is-active', t.dataset.tab === 'skills'));
    renderNerTab('skills');
    renderSkillSummary();
    const panel = document.getElementById('extractedInfoPanel');
    panel.hidden = false;
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function closeExtractedInfo() {
    document.getElementById('extractedInfoPanel').hidden = true;
    activeExtractedItem = null;
  }

  // -----------------------------------------------------------------------
  // Kebab menu open/close (event delegation — rows are re-rendered often)
  // -----------------------------------------------------------------------

  function closeKebabMenu() {
    if (openKebabMenu) { openKebabMenu.hidden = true; openKebabMenu = null; }
  }

  function findItem(resumeId) {
    return historyResults.find(r => r.resume_id === resumeId);
  }

  // -----------------------------------------------------------------------
  // Download
  // -----------------------------------------------------------------------

  async function downloadResume(resumeId) {
    try {
      const res = await fetch(`/api/resumes/${resumeId}/download`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      window.open(data.url, '_blank', 'noopener');
    } catch (err) {
      console.error('Error getting download link:', err);
    }
  }

  // -----------------------------------------------------------------------
  // Rename — inline edit on the clicked card's filename heading.
  // -----------------------------------------------------------------------

  function startRename(resumeId) {
    const card = document.querySelector(`[data-resume-id="${resumeId}"]`);
    const heading = card?.querySelector('h3');
    if (!heading) return;
    const original = heading.textContent;

    const input = document.createElement('input');
    input.type = 'text';
    input.value = original;
    input.className = 'rename-input';
    heading.replaceWith(input);
    input.focus();
    input.select();

    async function save() {
      const newName = input.value.trim();
      if (!newName || newName === original) { cancel(); return; }
      try {
        const res = await fetch(`/api/resumes/${resumeId}/rename`, {
          method: 'PATCH',
          headers: { ...authHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: newName }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        loadHistory();
      } catch (err) {
        console.error('Error renaming resume:', err);
        cancel();
      }
    }
    function cancel() {
      const h3 = document.createElement('h3');
      h3.textContent = original;
      input.replaceWith(h3);
    }

    input.addEventListener('blur', save);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') input.blur();
      if (e.key === 'Escape') { input.removeEventListener('blur', save); cancel(); }
    });
  }

  // -----------------------------------------------------------------------
  // Delete modal
  // -----------------------------------------------------------------------

  function openDeleteModal(resumeId) {
    pendingDeleteId = resumeId;
    document.getElementById('deleteResumeModal').hidden = false;
  }

  function closeDeleteModal() {
    pendingDeleteId = null;
    document.getElementById('deleteResumeModal').hidden = true;
  }

  async function confirmDelete() {
    const resumeId = pendingDeleteId;
    if (!resumeId) return;
    const confirmBtn = document.getElementById('deleteResumeConfirmBtn');
    if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.textContent = 'Deleting…'; }

    try {
      const res = await fetch(`/api/resumes/${resumeId}`, { method: 'DELETE', headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      closeDeleteModal();
      if (activeExtractedItem && activeExtractedItem.resume_id === resumeId) closeExtractedInfo();
      loadHistory();
    } catch (err) {
      console.error('Error deleting resume:', err);
      if (confirmBtn) { confirmBtn.textContent = 'Failed — retry'; confirmBtn.disabled = false; }
      return;
    }
    if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.textContent = 'Delete'; }
  }

  // -----------------------------------------------------------------------
  // Upload — same two-step flow as static/js/upload.js (upload, then
  // analyze), triggered from this page instead of /new-analysis. Every
  // upload already replaces the active resume (see upload_resume_1.py),
  // so there's no separate "replace" action to build.
  // -----------------------------------------------------------------------

  async function uploadAndAnalyze(file) {
    const btn = document.getElementById('uploadResumeBtn');
    const token = localStorage.getItem('token');
    if (!token) { window.location.href = '/login'; return; }

    const originalHtml = btn.innerHTML;
    btn.disabled = true;

    try {
      btn.textContent = 'Uploading…';
      const body = new FormData();
      body.append('file', file, file.name);
      const uploadRes = await fetch('/api/upload-resume', {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body,
      });
      if (!uploadRes.ok) throw new Error(`Upload failed (HTTP ${uploadRes.status})`);
      const { resume_id } = await uploadRes.json();

      btn.textContent = 'Analyzing…';
      const analyzeRes = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ resume_id }),
      });
      if (!analyzeRes.ok) throw new Error(`Analysis failed (HTTP ${analyzeRes.status})`);

      btn.innerHTML = originalHtml;
      btn.disabled = false;
      loadHistory();
    } catch (err) {
      console.error('Error uploading resume:', err);
      btn.textContent = 'Failed — try again';
      setTimeout(() => { btn.innerHTML = originalHtml; btn.disabled = false; }, 2000);
    }
  }

  // -----------------------------------------------------------------------
  // Event delegation — one set of listeners on the page body, since rows
  // are re-rendered on every load/sort rather than diffed.
  // -----------------------------------------------------------------------

  function wireGlobalEvents() {
    document.addEventListener('click', (e) => {
      const kebabBtn = e.target.closest('[data-kebab]');
      if (kebabBtn) {
        // Scoped to this button's own wrapper, not a page-wide
        // data-kebab-menu="<id>" lookup — the latter used
        // document.querySelector, which only ever returns the first
        // matching element on the whole page. That silently broke any
        // row whose resume_id also matched an earlier one in the DOM.
        const menu = kebabBtn.closest('.kebab-wrap')?.querySelector('[data-kebab-menu]');
        if (openKebabMenu && openKebabMenu !== menu) closeKebabMenu();
        if (menu) { menu.hidden = !menu.hidden; openKebabMenu = menu.hidden ? null : menu; }
        return;
      }

      const actionBtn = e.target.closest('[data-action]');
      if (actionBtn) {
        closeKebabMenu();
        const { action, id } = actionBtn.dataset;
        const item = findItem(id);
        if (action === 'view' && item) openExtractedInfo(item);
        if (action === 'download') downloadResume(id);
        if (action === 'rename') startRename(id);
        if (action === 'delete') openDeleteModal(id);
        return;
      }

      const viewBtn = e.target.closest('[data-view]');
      if (viewBtn) { const item = findItem(viewBtn.dataset.view); if (item) openExtractedInfo(item); return; }

      const downloadBtn = e.target.closest('[data-download]');
      if (downloadBtn) { downloadResume(downloadBtn.dataset.download); return; }

      if (!e.target.closest('.kebab-wrap')) closeKebabMenu();
    });

    document.getElementById('extractedInfoCloseBtn')?.addEventListener('click', closeExtractedInfo);

    document.getElementById('nerTabs')?.addEventListener('click', (e) => {
      const tab = e.target.closest('.ner-tab');
      if (!tab) return;
      activeTab = tab.dataset.tab;
      document.querySelectorAll('.ner-tab').forEach(t => t.classList.toggle('is-active', t === tab));
      renderNerTab(activeTab);
    });

    document.getElementById('historySortSelect')?.addEventListener('change', (e) => {
      currentSort = e.target.value;
      renderHistoryList();
    });

    document.getElementById('deleteResumeCancelBtn')?.addEventListener('click', closeDeleteModal);
    document.getElementById('deleteResumeConfirmBtn')?.addEventListener('click', confirmDelete);
    document.getElementById('deleteResumeModal')?.addEventListener('click', (e) => {
      if (e.target.id === 'deleteResumeModal') closeDeleteModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      const modal = document.getElementById('deleteResumeModal');
      if (modal && !modal.hidden) closeDeleteModal();
    });

    const fileInput = document.getElementById('resumeFileInput');
    document.getElementById('uploadResumeBtn')?.addEventListener('click', () => fileInput.click());
    fileInput?.addEventListener('change', () => {
      if (fileInput.files[0]) uploadAndAnalyze(fileInput.files[0]);
      fileInput.value = '';
    });
  }

  // -----------------------------------------------------------------------
  // Load
  // -----------------------------------------------------------------------

  async function loadHistory() {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
      const res = await fetch('/api/history', { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      historyResults = data.results || [];
      renderStats(data.stats || { total_resumes: 0, has_active_resume: false, best_match_score: null, skills_extracted: 0 });
      renderCurrentResume(historyResults.find(r => r.is_active) || null);
      renderHistoryList();
    } catch (err) {
      console.error('Error loading history:', err);
      document.getElementById('historyList').innerHTML = '<div class="empty-state"><p>Couldn\'t load history right now.</p></div>';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    wireGlobalEvents();
    loadHistory();
  });
})();
