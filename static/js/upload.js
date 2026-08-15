/*
 * upload.js — drives /new-analysis. Real progress only: every pipeline
 * state transition below is set from an actual fetch result, never a
 * timer. See templates/upload.html's pipeline card comment for exactly
 * which steps are honestly trackable from this page and which aren't.
 *
 * Once /api/analyze succeeds, the "Extracted Information" card is
 * populated with the real entities that response actually returned
 * (app/schemas/result_schema.py's NERResult) — never placeholder/example
 * data. There's no auto-redirect: a "Go to Dashboard →" button appears
 * once real data exists to look at, so the tab/chip content in that card
 * is never yanked away before it renders.
 */
(function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('resumeFile');
  const fileChip = document.getElementById('fileChip');
  const fileChipLabel = document.getElementById('fileChipLabel');
  const form = document.getElementById('analysisForm');
  const analyzeBtn = document.getElementById('analyzeBtn');
  const uploadError = document.getElementById('uploadError');

  function formatSize(bytes) {
    return bytes > 1024 * 1024
      ? (bytes / (1024 * 1024)).toFixed(1) + ' MB'
      : Math.round(bytes / 1024) + ' KB';
  }

  function showFile(file) {
    fileChipLabel.textContent = `${file.name} · ${formatSize(file.size)}`;
    fileChip.classList.remove('is-hidden');
  }

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) showFile(fileInput.files[0]);
  });

  ['dragenter', 'dragover'].forEach(evt => dropzone.addEventListener(evt, (e) => {
    e.preventDefault(); dropzone.classList.add('is-dragover');
  }));
  ['dragleave', 'drop'].forEach(evt => dropzone.addEventListener(evt, (e) => {
    e.preventDefault(); dropzone.classList.remove('is-dragover');
  }));
  dropzone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      fileInput.files = e.dataTransfer.files;
      showFile(file);
    }
  });

  function showError(message) {
    uploadError.textContent = message;
    uploadError.style.display = 'block';
  }

  function setStatus(text) {
    analyzeBtn.textContent = text;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  // ---------------------------------------------------------------------
  // Pipeline card — real state, not a canned animation.
  // ---------------------------------------------------------------------

  const STATUS_LABELS = { pending: 'Pending', active: 'Active', done: 'Done', error: 'Failed' };

  function setStep(stepName, state) {
    const step = document.querySelector(`.pipe-step[data-step="${stepName}"]`);
    if (step) step.dataset.state = state;
    const pill = document.querySelector(`[data-status-for="${stepName}"]`);
    if (pill) {
      pill.textContent = STATUS_LABELS[state] || state;
      pill.className = `pipe-status-pill pipe-status-${state}`;
    }
  }

  // ---------------------------------------------------------------------
  // "How it works" modal — static explanatory content, no data involved.
  // ---------------------------------------------------------------------

  function wireHowItWorksModal() {
    const btn = document.getElementById('howItWorksBtn');
    const modal = document.getElementById('howItWorksModal');
    const closeBtn = document.getElementById('howItWorksCloseBtn');
    if (!btn || !modal) return;

    btn.addEventListener('click', () => { modal.hidden = false; });
    closeBtn?.addEventListener('click', () => { modal.hidden = true; });
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.hidden = true; });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !modal.hidden) modal.hidden = true;
    });
  }

  // ---------------------------------------------------------------------
  // Extracted Information card — populated with the real entities this
  // specific analyze response returned. Hidden entirely until then; never
  // shows example/placeholder chips.
  // ---------------------------------------------------------------------

  const NER_LABELS = { skills: 'Technical Skills', experience: 'Experience', education: 'Education', projects: 'Projects', certifications: 'Certifications' };
  const CHIP_TABS = new Set(['skills', 'certifications']);
  const SKILLS_PREVIEW_COUNT = 18; // matches the density of the reference design's "+N more" pattern

  let currentEntities = null;
  let skillsExpanded = false;

  function renderNerTab(tabKey) {
    const el = document.getElementById('uploadNerTabContent');
    if (!el || !currentEntities) return;
    const items = currentEntities[tabKey] || [];

    if (!items.length) {
      el.innerHTML = `<p class="card-sub">No ${NER_LABELS[tabKey].toLowerCase()} were extracted from this resume.</p>`;
      return;
    }

    if (!CHIP_TABS.has(tabKey)) {
      el.innerHTML = `<h4 class="ner-section-label">${NER_LABELS[tabKey]}</h4><ul class="ner-list">${items.map(s => `<li>${escapeHtml(s)}</li>`).join('')}</ul>`;
      return;
    }

    const showAll = tabKey !== 'skills' || skillsExpanded || items.length <= SKILLS_PREVIEW_COUNT;
    const visible = showAll ? items : items.slice(0, SKILLS_PREVIEW_COUNT);
    const remaining = items.length - visible.length;

    el.innerHTML = `
      <h4 class="ner-section-label">${NER_LABELS[tabKey]}</h4>
      <div class="chips">${visible.map(s => `<span class="skill-chip have">${escapeHtml(s)}</span>`).join('')}</div>
      ${remaining > 0 ? `<button type="button" class="ner-show-more" id="skillsShowMoreBtn">+ ${remaining} more skills</button>` : ''}
    `;

    document.getElementById('skillsShowMoreBtn')?.addEventListener('click', () => {
      skillsExpanded = true;
      renderNerTab('skills');
    });
  }

  function wireNerTabs() {
    document.getElementById('uploadNerTabs')?.addEventListener('click', (e) => {
      const tab = e.target.closest('.ner-tab');
      if (!tab) return;
      document.querySelectorAll('#uploadNerTabs .ner-tab').forEach(t => t.classList.toggle('is-active', t === tab));
      renderNerTab(tab.dataset.tab);
    });
  }

  function showExtractedInfo(entities) {
    currentEntities = entities;
    skillsExpanded = false;
    document.getElementById('extractedInfoCard').hidden = false;
    document.querySelectorAll('#uploadNerTabs .ner-tab').forEach(t => t.classList.toggle('is-active', t.dataset.tab === 'skills'));
    renderNerTab('skills');
    document.getElementById('goToDashboardBtn').hidden = false;
    document.getElementById('extractedInfoCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  document.getElementById('goToDashboardBtn')?.addEventListener('click', () => {
    window.location.href = '/dashboard';
  });

  // ---------------------------------------------------------------------
  // Upload + analyze
  // ---------------------------------------------------------------------

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    uploadError.style.display = 'none';

    const file = fileInput.files[0];
    if (!file) { showError('Attach your resume as a PDF before analyzing.'); return; }

    const token = localStorage.getItem('token');
    if (!token) { window.location.href = '/login'; return; }

    analyzeBtn.disabled = true;

    try {
      // ----------------------------------------------------------------
      // Upload — fast, transient, reflected in the button text rather
      // than the pipeline card (the pipeline's 5 steps all describe the
      // analysis itself, matching what happens once the file exists).
      // ----------------------------------------------------------------
      setStatus('Uploading resume…');
      const body = new FormData();
      body.append('file', file, file.name);

      const uploadRes = await fetch('/api/upload-resume', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body,
      });

      if (uploadRes.status === 401) { window.location.href = '/login'; return; }

      if (!uploadRes.ok) {
        const data = await uploadRes.json().catch(() => ({}));
        showError(data.detail || 'Upload failed. Please try again.');
        analyzeBtn.disabled = false;
        setStatus('Analyze resume');
        return;
      }

      const uploadData = await uploadRes.json();
      const resumeId = uploadData.resume_id;

      // ----------------------------------------------------------------
      // Analyze — one atomic request covers both "PDF parsing" and
      // "NLP & entity extraction" server-side, with no observable
      // boundary between them, so both pipeline steps transition
      // together rather than faking independent timing.
      // ----------------------------------------------------------------
      setStatus('Analyzing resume…');
      setStep('parse', 'active');
      setStep('extract', 'active');

      const analyzeRes = await fetch('/api/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          resume_id: resumeId,
        }),
      });

      if (analyzeRes.ok) {
        setStep('parse', 'done');
        setStep('extract', 'done');
        // Matching (embeddings + scoring) starts as a background task the
        // instant this response lands — real (see resume_analyze_2.py),
        // but its own completion isn't observable from this page, so it
        // deliberately stays "Active," never a fake "Done" here. Steps
        // 4-5 aren't independently-trackable backend steps at all — see
        // templates/upload.html's pipeline-note — so they stay "Pending."
        setStep('matching', 'active');

        const analysis = await analyzeRes.json();

        localStorage.setItem('latest_analysis', JSON.stringify({
          ...analysis,
          filename: file.name,
          analyzed_at: new Date().toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric'
          }),
        }));

        if (analysis.entities) showExtractedInfo(analysis.entities);
        setStatus('Analyze another resume');
        analyzeBtn.disabled = false;
      } else {
        setStep('parse', 'error');
        setStep('extract', 'error');
        const data = await analyzeRes.json().catch(() => ({}));
        showError(data.detail || 'Analysis failed. Please try again.');
        localStorage.removeItem('latest_analysis');
        analyzeBtn.disabled = false;
        setStatus('Analyze resume');
      }
    } catch (err) {
      // Whichever step was mid-flight when the network dropped shouldn't
      // keep pulsing "Active" forever — mark it failed instead.
      document.querySelectorAll('.pipe-step[data-state="active"]').forEach(s => {
        setStep(s.dataset.step, 'error');
      });
      showError('Network error. Please check your connection and try again.');
      analyzeBtn.disabled = false;
      setStatus('Analyze resume');
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    wireHowItWorksModal();
    wireNerTabs();
  });
})();
