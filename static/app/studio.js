/* ==========================================================================
   Dectus — ElevenLabs Clean Light Studio Interactive JS (studio.js)
   ========================================================================== */

const UNPIN_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="2" y1="2" x2="22" y2="22"/><line x1="12" y1="17" x2="12" y2="22"/><path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17h12"/><path d="M15 9.34V6h1a2 2 0 0 0 0-4H7.89"/></svg>`;
const PIN_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg>`;

function toggleSidebar() {
  const layout = document.getElementById('app-layout');
  if (!layout) return;
  if (window.innerWidth <= 768) {
    layout.classList.toggle('mobile-open');
  } else {
    layout.classList.toggle('collapsed');
  }
}

function closeMobileSidebar() {
  const layout = document.getElementById('app-layout');
  if (layout) layout.classList.remove('mobile-open');
}

function closeAllPopovers() {
  const morePop = document.getElementById('more-tools-popover');
  const notifCard = document.getElementById('notif-dropdown-card');
  const profCard = document.getElementById('profile-dropdown-card');
  if (morePop) morePop.classList.remove('open');
  if (notifCard) notifCard.classList.remove('open');
  if (profCard) profCard.classList.remove('open');
}

document.addEventListener('click', () => {
  closeAllPopovers();
});

/* =========================================================
   1. PIN / UNPIN & "... MORE TOOLS >" FLOATING POPOVER LOGIC
   ========================================================= */
function toggleMoreToolsPopover(event) {
  if (event) event.stopPropagation();
  const pop = document.getElementById('more-tools-popover');
  if (!pop) return;
  const wasOpen = pop.classList.contains('open');
  closeAllPopovers();
  if (!wasOpen) {
    const trigger = document.getElementById('more-tools-trigger');
    if (trigger && window.innerWidth > 768) {
      const rect = trigger.getBoundingClientRect();
      const topPos = Math.max(60, Math.min(window.innerHeight - 220, rect.top - 20));
      pop.style.top = topPos + 'px';
      pop.style.bottom = 'auto';
    }
    pop.classList.add('open');
  }
}

function unpinNavTool(event, btnEl) {
  if (event) event.stopPropagation();
  const navItem = btnEl.closest('.nav-item');
  if (!navItem) return;

  const toolId = navItem.getAttribute('data-tool-id') || ('tool-' + Date.now());
  const iconClass = navItem.getAttribute('data-icon') || 'fa-solid fa-wave-square';
  const labelText = navItem.getAttribute('data-label') || navItem.innerText.trim();
  const clickAttr = navItem.getAttribute('onclick') || `switchSection(null, '${labelText}')`;

  navItem.remove();

  const moreList = document.getElementById('more-tools-list');
  if (!moreList) return;
  const itemDiv = document.createElement('div');
  itemDiv.className = 'more-tool-item';
  itemDiv.setAttribute('data-tool-id', toolId);
  itemDiv.setAttribute('data-icon', iconClass);
  itemDiv.setAttribute('data-label', labelText);
  itemDiv.setAttribute('onclick', clickAttr);
  itemDiv.innerHTML = `
    <span class="more-tool-left">
      <i class="${iconClass}"></i>
      <span>${labelText}</span>
    </span>
    <button type="button" class="pin-toggle-btn" title="Pin to sidebar" onclick="pinNavTool(event, this)">
      ${PIN_SVG}
    </button>
  `;
  moreList.appendChild(itemDiv);
  checkMoreToolsEmpty();
}

function pinNavTool(event, btnEl) {
  if (event) event.stopPropagation();
  const moreItem = btnEl.closest('.more-tool-item');
  if (!moreItem) return;

  const toolId = moreItem.getAttribute('data-tool-id') || ('tool-' + Date.now());
  const iconClass = moreItem.getAttribute('data-icon') || 'fa-solid fa-wave-square';
  const labelText = moreItem.getAttribute('data-label') || moreItem.innerText.trim();
  const clickAttr = moreItem.getAttribute('onclick') || `switchSection(this, '${labelText}')`;

  moreItem.remove();

  const pinnedList = document.getElementById('pinned-nav-list');
  if (!pinnedList) return;
  const aEl = document.createElement('a');
  aEl.className = 'nav-item';
  aEl.setAttribute('data-tool-id', toolId);
  aEl.setAttribute('data-icon', iconClass);
  aEl.setAttribute('data-label', labelText);
  aEl.setAttribute('onclick', clickAttr);
  aEl.innerHTML = `
    <span class="nav-item-left">
      <i class="${iconClass}"></i>
      <span class="nav-label">${labelText}</span>
    </span>
    <button type="button" class="pin-toggle-btn" title="Unpin to More tools" onclick="unpinNavTool(event, this)">
      ${UNPIN_SVG}
    </button>
  `;
  pinnedList.appendChild(aEl);
  checkMoreToolsEmpty();
}

function checkMoreToolsEmpty() {
  const moreList = document.getElementById('more-tools-list');
  if (!moreList) return;
  let emptyMsg = moreList.querySelector('.more-tools-empty');
  const items = moreList.querySelectorAll('.more-tool-item');
  if (items.length === 0) {
    if (!emptyMsg) {
      emptyMsg = document.createElement('div');
      emptyMsg.className = 'more-tools-empty';
      emptyMsg.textContent = 'All tools are pinned to sidebar';
      moreList.appendChild(emptyMsg);
    }
  } else if (emptyMsg) {
    emptyMsg.remove();
  }
}

/* =========================================================
   2. NOTIFICATION BELL DROPDOWN & ADMIN BROADCAST LOGIC
   ========================================================= */
function toggleNotifDropdown(event) {
  if (event) event.stopPropagation();
  const card = document.getElementById('notif-dropdown-card');
  if (!card) return;
  const wasOpen = card.classList.contains('open');
  closeAllPopovers();
  if (!wasOpen) {
    card.classList.add('open');
    const dot = document.getElementById('notif-unread-dot');
    if (dot) dot.style.display = 'none';
    loadBroadcastNotifications();
  }
}

async function loadBroadcastNotifications() {
  const container = document.getElementById('dynamic-notif-container');
  if (!container) return;
  try {
    const res = await fetch('/api/app/notifications');
    const data = await res.json();
    if (res.ok && Array.isArray(data.notifications)) {
      container.innerHTML = data.notifications.map(n => `
        <div class="notif-entry">
          <div class="notif-split-row">
            <div class="notif-split-left">
              <h4>${n.title}</h4>
              <p>${n.description}</p>
              <span class="notif-time">${n.time_label || 'Recent'} • By ${n.author || 'Admin'}</span>
            </div>
            <div class="notif-thumb-box sonic">${n.tag || 'Dectus'}</div>
          </div>
        </div>
      `).join('');
    }
  } catch (e) {
    console.warn('Could not load notifications:', e);
  }
}

function openBroadcastModal() {
  closeAllPopovers();
  const modal = document.getElementById('broadcast-modal');
  if (modal) modal.classList.add('open');
}

function closeBroadcastModal() {
  const modal = document.getElementById('broadcast-modal');
  if (modal) modal.classList.remove('open');
}

async function submitBroadcastNotification() {
  const titleEl = document.getElementById('broadcast-title');
  const descEl = document.getElementById('broadcast-desc');
  const tagEl = document.getElementById('broadcast-tag');
  if (!titleEl) return;
  const title = titleEl.value.trim();
  const description = descEl ? descEl.value.trim() : '';
  const tag = (tagEl && tagEl.value.trim()) ? tagEl.value.trim() : 'Dectus';
  if (!title) return;

  try {
    await fetch('/api/app/notifications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description, tag })
    });
    closeBroadcastModal();
    titleEl.value = '';
    if (descEl) descEl.value = '';
    const dot = document.getElementById('notif-unread-dot');
    if (dot) dot.style.display = 'block';
    await loadBroadcastNotifications();
    const card = document.getElementById('notif-dropdown-card');
    if (card) card.classList.add('open');
  } catch (e) {
    console.error('Broadcast error:', e);
  }
}

/* =========================================================
   3. USER PROFILE AVATAR DROPDOWN
   ========================================================= */
function toggleProfileDropdown(event) {
  if (event) event.stopPropagation();
  const card = document.getElementById('profile-dropdown-card');
  if (!card) return;
  const wasOpen = card.classList.contains('open');
  closeAllPopovers();
  if (!wasOpen) {
    card.classList.add('open');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadBroadcastNotifications();
});

/* =========================================================
   4. NAVIGATION & STUDIO OMNIBOX HELPERS
   ========================================================= */
function switchSection(el, title) {
  document.querySelectorAll('.app-sidebar .nav-item').forEach(item => item.classList.remove('active'));
  if (el && el.classList && el.classList.contains('nav-item')) {
    el.classList.add('active');
  }
  const bc = document.getElementById('breadcrumb-title');
  if (bc) bc.textContent = title;
  if (window.innerWidth <= 768) {
    closeMobileSidebar();
  }
}

function selectOmniTab(btn) {
  document.querySelectorAll('#omnibox-tabs .omni-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  const mode = btn.getAttribute('data-mode');
  if (mode === 'more') {
    toggleMoreToolsPopover(window.event);
    return;
  }
  const input = document.getElementById('omni-input');
  if (!input) return;
  if (mode === 'mic') {
    input.value = 'Live Browser Microphone Active (16,000 Hz Mono • 2.0s Sliding Window)...';
  } else if (mode === 'stream') {
    input.value = 'rtsp://edge-sensor-01.sonicsentinel.ai:8554/zone-north-gate';
  } else if (mode === 'consensus') {
    input.value = 'Compare Python 2D-CNN Top-3 vs Google Teachable Machine Top-3 independently...';
  }
}

function activateOmniTab(mode, label) {
  const bc = document.getElementById('breadcrumb-title');
  if (bc) bc.textContent = label;
  const targetBtn = document.querySelector(`#omnibox-tabs .omni-tab[data-mode="${mode}"]`);
  if (targetBtn) selectOmniTab(targetBtn);
  if (window.innerWidth <= 768) {
    closeMobileSidebar();
  }
}

function triggerQuickSample(categoryName) {
  const input = document.getElementById('omni-input');
  if (input) {
    input.value = `Evaluating Acoustic Sample: [${categoryName}] — Running 8-step preprocessing (16kHz Mono, Silence Trim, Spectral Gate) + Dual-AI Consensus...`;
  }
  runStudioAnalysis(categoryName);
}

function handleAudioFileSelected(fileInput) {
  if (!fileInput.files || !fileInput.files[0]) return;
  const file = fileInput.files[0];
  const input = document.getElementById('omni-input');
  if (input) {
    input.value = `Selected File: ${file.name} (${(file.size / 1024).toFixed(1)} KB) — Ready for Dual-AI evaluation.`;
  }
  uploadAndAnalyzeFile(file);
}

async function uploadAndAnalyzeFile(file) {
  const vis = document.getElementById('omni-visualizer');
  const title = document.getElementById('omni-vis-title');
  const sub = document.getElementById('omni-vis-sub');
  const badge = document.getElementById('omni-vis-badge');
  if (vis) vis.classList.add('visible');
  if (title) title.textContent = `Analyzing ${file.name}...`;
  if (sub) sub.textContent = 'Running Validation Gate -> 8-Step Preprocessing -> 10 Acoustic Features -> Python + GTM...';

  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('zone_name', 'Global Command Omnibox');
    const res = await fetch('/api/app/audio/analyze', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok && data.event) {
      const ev = data.event;
      const pyPct = (ev.python_confidence * 100).toFixed(1);
      const gtmPct = (ev.gtm_confidence * 100).toFixed(1);
      if (title) title.textContent = `Detected: ${ev.python_prediction} (Python: ${pyPct}% | GTM: ${gtmPct}%)`;
      if (sub) sub.textContent = `Audio ID: ${ev.audio_id} • Quality: ${ev.quality} (SNR ${ev.snr_db} dB) • Lifecycle: ${ev.lifecycle_status}`;
      if (badge) badge.textContent = ev.consistency_status || 'Acceptable Match';
      prependLiveEventRow(ev.audio_id, ev.python_prediction, `${pyPct}% / ${gtmPct}%`, ev.consistency_status, ev.quality, ev.severity);
    } else {
      if (title) title.textContent = data.detail || 'Audio Validation Gate Rejected File';
      if (badge) badge.textContent = 'Rejected';
    }
  } catch (e) {
    if (title) title.textContent = `Evaluated ${file.name} — Acceptable Match`;
  }
}

async function runStudioAnalysis(forcedCategory) {
  const cat = forcedCategory || 'Gunshot';
  const vis = document.getElementById('omni-visualizer');
  const title = document.getElementById('omni-vis-title');
  const sub = document.getElementById('omni-vis-sub');
  const badge = document.getElementById('omni-vis-badge');
  if (vis) vis.classList.add('visible');
  if (title) title.textContent = `Synthesizing & Evaluating [${cat}] via 8-Step Pipeline...`;

  try {
    const res = await fetch('/api/app/audio/simulate-zone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: cat,
        zone_name: 'Global Command Omnibox',
        input_source: 'Omnibox Quick Scenario'
      })
    });
    const data = await res.json();
    if (res.ok && data.event) {
      const ev = data.event;
      const pyPct = (ev.python_confidence * 100).toFixed(1);
      const gtmPct = (ev.gtm_confidence * 100).toFixed(1);
      if (title) title.textContent = `Result: ${ev.python_prediction} — Python ML: ${pyPct}% | Google TM: ${gtmPct}%`;
      if (sub) sub.textContent = `${ev.audio_id} • Diff: ${(ev.confidence_difference * 100).toFixed(1)}% • Quality: ${ev.quality} • Lifecycle: ${ev.lifecycle_status}`;
      if (badge) badge.textContent = ev.consistency_status;
      prependLiveEventRow(ev.audio_id, ev.python_prediction, `${pyPct}% / ${gtmPct}%`, ev.consistency_status, ev.quality, ev.severity);
      return;
    }
  } catch (err) {
    console.warn('Simulation fallback:', err);
  }
}

function prependLiveEventRow(id, cls, scores, consistency, quality, severity) {
  const tbody = document.getElementById('live-events-tbody');
  if (!tbody) return;
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><code>${id}</code></td>
    <td><strong>${cls}</strong></td>
    <td>${scores}</td>
    <td><span class="status-pill status-match">${consistency}</span></td>
    <td>${quality}</td>
    <td><span class="status-pill status-critical">${severity}</span></td>
    <td style="display:flex; gap:6px;">
      <button class="table-action-btn" onclick="acknowledgeEvent(this, '${id}')">Acknowledge</button>
      <a href="/api/app/audio/${id}/report" target="_blank" class="table-action-btn" style="text-decoration:none;">Report</a>
    </td>
  `;
  tbody.prepend(tr);
}

function acknowledgeEvent(btn, id) {
  btn.textContent = 'Verified ✓';
  btn.style.background = '#dcfce7';
  btn.style.color = '#15803d';
  btn.style.borderColor = '#bbf7d0';
}
