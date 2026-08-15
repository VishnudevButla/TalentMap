/*
 * activity.js — fetches /api/activity and renders the feed.
 *
 * renderRow()/window.__renderActivityRow stay simple and flat — that's the
 * compact contract dashboard.js's small "Recent activity" preview widget
 * relies on. The full Activity page gets a richer treatment below:
 * grouped by day, color-coded by event type, with a type badge and an
 * exact timestamp on hover — built for someone scanning a growing log,
 * not a 4-item preview.
 */
(function () {
  const ICONS = {
    file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg>',
    briefcase: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>',
    mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 6l-10 7L2 6"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></svg>',
  };

  // Keyed on the `type` field written by app/services/activity_log.py
  // call sites (resume_analyze_2.py: "analysis", matcher.py: "job_match",
  // scheduler.py: "agent_scan", routes_agent.py's apply endpoint:
  // "job_applied"). "mail"/default are here for forward compatibility
  // with event types not wired up yet.
  const TYPE_META = {
    analysis: { label: 'Resume Analysis', variant: 'accent' },
    job_match: { label: 'Job Match', variant: 'good' },
    agent_scan: { label: 'Agent Scan', variant: 'cyan' },
    job_applied: { label: 'Application', variant: 'accent' },
    mail: { label: 'Email Alert', variant: 'good' },
  };

  // Where clicking an activity item should take you — data-driven off the
  // real `type` field, not a per-row hardcoded URL. Only real, currently-
  // logged types are mapped; an unrecognized future type just doesn't
  // navigate rather than guessing.
  const TYPE_ROUTES = {
    analysis: '/history',
    job_match: '/matches',
    agent_scan: '/agent',
    job_applied: '/matches',
  };

  function typeMeta(type) {
    return TYPE_META[type] || { label: 'Activity', variant: 'neutral' };
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function timeAgo(iso) {
    if (!iso) return '';
    const diffMs = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function fullTimestamp(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  }

  function dayLabel(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const startOfDay = date => new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const diffDays = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return d.toLocaleDateString(undefined, {
      weekday: 'long', month: 'short', day: 'numeric',
      year: d.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
  }

  // --- Compact row: used by dashboard.js's Recent Activity preview ---
  function renderRow(item) {
    const icon = ICONS[item.icon] || ICONS.info;
    const clickable = TYPE_ROUTES[item.type] ? ' is-clickable' : '';
    return `
      <div class="activity-row${clickable}" data-activity-id="${item._id}" data-activity-type="${item.type}">
        <div class="activity-icon">${icon}</div>
        <div class="activity-body">
          <div class="activity-message">${escapeHtml(item.message || '')}</div>
          <div class="activity-time">${timeAgo(item.created_at)}</div>
        </div>
      </div>
    `;
  }

  // --- Rich row + day grouping: used by the full Activity page ---
  function renderRichRow(item) {
    const icon = ICONS[item.icon] || ICONS.info;
    const meta = typeMeta(item.type);
    const clickable = TYPE_ROUTES[item.type] ? ' is-clickable' : '';
    return `
      <div class="activity-row-rich${clickable}" data-activity-id="${item._id}" data-activity-type="${item.type}">
        ${item.read ? '' : '<span class="activity-unread-dot" title="Unread"></span>'}
        <div class="activity-icon activity-icon-${meta.variant}">${icon}</div>
        <div class="activity-body">
          <div class="activity-row-head">
            <span class="activity-type-badge activity-type-${meta.variant}">${meta.label}</span>
            <span class="activity-time" title="${fullTimestamp(item.created_at)}">${timeAgo(item.created_at)}</span>
          </div>
          <div class="activity-message">${escapeHtml(item.message || '')}</div>
        </div>
        <button type="button" class="activity-delete-btn" data-delete-activity="${item._id}" aria-label="Delete this entry">&times;</button>
      </div>
    `;
  }

  function renderGroupedFeed(items) {
    let html = '';
    let currentGroup = null;
    for (const item of items) {
      const label = dayLabel(item.created_at);
      if (label !== currentGroup) {
        currentGroup = label;
        html += `<div class="activity-date-heading">${escapeHtml(label)}</div>`;
      }
      html += renderRichRow(item);
    }
    return html;
  }

  function authHeaders() {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function loadActivity() {
    const feedEl = document.getElementById('activityFeed');
    const token = localStorage.getItem('token');
    if (!token || !feedEl) return;

    try {
      const res = await fetch('/api/activity', { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (!data.results || data.results.length === 0) {
        feedEl.innerHTML = '<div class="empty-state"><p>No activity yet — actions TalentMap takes on your behalf will show up here.</p></div>';
        return;
      }

      feedEl.innerHTML = renderGroupedFeed(data.results);
    } catch (err) {
      feedEl.innerHTML = '<div class="empty-state"><p>Couldn\'t load activity right now.</p></div>';
      console.error('Error loading activity:', err);
    }
  }

  // -----------------------------------------------------------------------
  // Interactions — only on the full Activity page (#activityFeed present).
  // Clicking a row marks it read (fire-and-forget — the navigation isn't
  // blocked on it) and jumps to the relevant page. The delete "×" and
  // "Clear all" call the real DELETE endpoints in app/routers/activity_api.py.
  // -----------------------------------------------------------------------

  function wireActivityInteractions() {
    // Delegated on `document`, not scoped to one container — the compact
    // preview (dashboard.html's plain `.activity-feed`, no id) and the
    // full page (activity.html's `#activityFeed`, rich rows with a
    // delete button) both need click-through, and only one of the two
    // markups exists on any given page.
    document.addEventListener('click', (e) => {
      const deleteBtn = e.target.closest('[data-delete-activity]');
      if (deleteBtn) {
        e.stopPropagation();
        const id = deleteBtn.dataset.deleteActivity;
        const row = deleteBtn.closest('.activity-row-rich');
        fetch(`/api/activity/${id}`, { method: 'DELETE', headers: authHeaders() })
          .then(res => { if (res.ok && row) row.remove(); })
          .catch(err => console.error('Error deleting activity:', err));
        return;
      }

      const row = e.target.closest('.activity-row.is-clickable, .activity-row-rich.is-clickable');
      if (!row) return;
      const { activityId, activityType } = row.dataset;
      fetch(`/api/activity/${activityId}/read`, { method: 'PATCH', headers: authHeaders() }).catch(() => {});
      const dest = TYPE_ROUTES[activityType];
      if (dest) window.location.href = dest;
    });

    const clearBtn = document.getElementById('clearAllActivityBtn');
    const modal = document.getElementById('clearActivityModal');
    const confirmBtn = document.getElementById('clearActivityConfirmBtn');
    const cancelBtn = document.getElementById('clearActivityCancelBtn');
    if (!clearBtn || !modal) return;

    clearBtn.addEventListener('click', () => { modal.hidden = false; });
    cancelBtn?.addEventListener('click', () => { modal.hidden = true; });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true; });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) modal.hidden = true; });

    confirmBtn?.addEventListener('click', async () => {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Clearing…';
      try {
        const res = await fetch('/api/activity', { method: 'DELETE', headers: authHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        modal.hidden = true;
        confirmBtn.textContent = 'Clear all';
        loadActivity();
      } catch (err) {
        console.error('Error clearing activity:', err);
        confirmBtn.textContent = 'Failed — retry';
      }
      confirmBtn.disabled = false;
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    wireActivityInteractions();
    loadActivity();
  });
  window.__renderActivityRow = renderRow; // reused by dashboard.js preview widget
})();
