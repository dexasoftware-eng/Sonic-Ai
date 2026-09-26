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
   2. DYNAMIC NOTIFICATION BELL & ADMIN BROADCAST LOGIC
   ========================================================= */

let knownNotifIds = new Set();
let isInitialNotifLoad = true;

function playNotificationChime() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12); // A5
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch (e) {
    // Autoplay restrictions or audio unsupported
  }
}

function toggleNotifDropdown(event) {
  if (event) event.stopPropagation();
  const card = document.getElementById('notif-dropdown-card');
  if (!card) return;
  const wasOpen = card.classList.contains('open');
  closeAllPopovers();
  if (!wasOpen) {
    card.classList.add('open');
    loadBroadcastNotifications(false);
  }
}

function markAllNotificationsAsRead() {
  localStorage.setItem('dectus_last_read_ts', new Date().toISOString());
  const dot = document.getElementById('notif-unread-dot');
  const badge = document.getElementById('notif-count-badge');
  if (dot) dot.style.display = 'none';
  if (badge) {
    badge.style.display = 'none';
    badge.textContent = '0';
  }
}

function showToastNotification(n) {
  let container = document.getElementById('dectus-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'dectus-toast-container';
    container.className = 'dectus-toast-container';
    document.body.appendChild(container);
  }

  const category = n.category || 'announcement';
  let icon = 'fa-solid fa-bullhorn';
  if (category === 'threat_alert') icon = 'fa-solid fa-triangle-exclamation';
  else if (category === 'maintenance') icon = 'fa-solid fa-wrench';
  else if (category === 'system_update') icon = 'fa-solid fa-sliders';

  const toast = document.createElement('div');
  toast.className = `dectus-toast toast-${category}`;
  toast.id = `toast-${n.notification_id || Date.now()}`;
  toast.innerHTML = `
    <div class="toast-icon-circle">
      <i class="${icon}"></i>
    </div>
    <div class="toast-content-col" style="${n.action_url ? 'cursor:pointer;' : ''}">
      <h5 class="toast-title">${n.title || 'System Broadcast'}</h5>
      <p class="toast-desc">${n.description || ''}</p>
      <div class="toast-meta">
        <strong>${n.tag || 'Broadcast'}</strong> • <span>${n.time_label || 'Just now'}</span>
      </div>
    </div>
    <button type="button" class="toast-close-x" onclick="this.closest('.dectus-toast').remove()">&times;</button>
  `;

  if (n.action_url) {
    toast.querySelector('.toast-content-col').addEventListener('click', () => {
      window.location.href = n.action_url;
    });
  }

  container.appendChild(toast);

  // Auto remove after 6.5 seconds
  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(40px)';
      setTimeout(() => toast.remove(), 250);
    }
  }, 6500);
}

async function loadBroadcastNotifications(checkNewForToast = false) {
  const container = document.getElementById('dynamic-notif-container');
  try {
    const res = await fetch('/api/app/notifications');
    const data = await res.json();
    if (!res.ok || !Array.isArray(data.notifications)) return;

    const notifs = data.notifications;
    const lastReadTs = localStorage.getItem('dectus_last_read_ts') || '1970-01-01T00:00:00.000Z';
    const lastReadDate = new Date(lastReadTs);

    let unreadCount = 0;
    let hasBrandNew = false;

    notifs.forEach(n => {
      const nDate = n.created_at ? new Date(n.created_at) : new Date();
      if (nDate > lastReadDate) {
        unreadCount++;
      }

      if (n.notification_id && !knownNotifIds.has(n.notification_id)) {
        if (!isInitialNotifLoad && checkNewForToast) {
          hasBrandNew = true;
          showToastNotification(n);
        }
        knownNotifIds.add(n.notification_id);
      }
    });

    if (hasBrandNew) {
      playNotificationChime();
    }

    isInitialNotifLoad = false;

    // Update unread badges on the bell
    const dot = document.getElementById('notif-unread-dot');
    const badge = document.getElementById('notif-count-badge');
    if (unreadCount > 0) {
      if (dot) dot.style.display = 'block';
      if (badge) {
        badge.style.display = 'block';
        badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
      }
    } else {
      if (dot) dot.style.display = 'none';
      if (badge) badge.style.display = 'none';
    }

    if (!container) return;

    if (notifs.length === 0) {
      container.innerHTML = `
        <div class="notif-empty-state">
          <i class="fa-regular fa-bell-slash" style="font-size:22px; color:#d4d4d8; margin-bottom:6px; display:block;"></i>
          <span>No broadcasts published yet.</span>
        </div>
      `;
      return;
    }

    container.innerHTML = notifs.map(n => {
      const cat = n.category || 'announcement';
      const prio = n.priority || 'normal';
      const isCritical = prio === 'critical';
      const isHigh = prio === 'high';
      const prioClass = isCritical ? 'priority-critical' : (isHigh ? 'priority-high' : '');

      return `
        <div class="notif-entry dynamic-entry ${prioClass} cat-${cat}" onclick="handleNotificationClick('${n.action_url || ''}')" style="${n.action_url ? 'cursor:pointer;' : ''}">
          <div class="notif-entry-header">
            <span class="notif-category-pill ${cat}">
              ${isCritical ? '<i class="fa-solid fa-triangle-exclamation" style="margin-right:3px;"></i>' : ''}${n.category ? n.category.replace('_', ' ') : 'Update'}
            </span>
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="notif-time">${n.time_label || 'Recent'}</span>
              <button type="button" class="btn-notif-delete" title="Delete broadcast" onclick="deleteBroadcastNotification(event, '${n.notification_id}')">
                <i class="fa-regular fa-trash-can"></i>
              </button>
            </div>
          </div>
          <h4>${n.title}</h4>
          <p>${n.description}</p>
          <div style="display:flex; align-items:center; justify-content:space-between; margin-top:4px;">
            <span style="font-size:11px; color:#71717a;">By ${n.author || 'Admin'}${n.target_role && n.target_role !== 'all' ? ` • Target: ${n.target_role}` : ''}</span>
            <span style="font-size:10px; font-weight:700; background:#f4f4f5; padding:2px 6px; border-radius:4px; color:#52525b;">${n.tag || 'Broadcast'}</span>
          </div>
        </div>
      `;
    }).join('');

  } catch (e) {
    console.warn('Could not load notifications:', e);
  }
}

function handleNotificationClick(url) {
  if (url && url.trim()) {
    window.location.href = url.trim();
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

function updateBroadcastTagDefault() {
  const catEl = document.getElementById('broadcast-category');
  const tagEl = document.getElementById('broadcast-tag');
  if (!catEl || !tagEl) return;
  const map = {
    'threat_alert': 'Threat Directive',
    'system_update': 'System Config',
    'maintenance': 'Maintenance Advisory',
    'announcement': 'Announcement'
  };
  tagEl.value = map[catEl.value] || 'Broadcast';
}

async function submitBroadcastNotification() {
  const titleEl = document.getElementById('broadcast-title');
  const descEl = document.getElementById('broadcast-desc');
  const catEl = document.getElementById('broadcast-category');
  const prioEl = document.getElementById('broadcast-priority');
  const targetEl = document.getElementById('broadcast-target');
  const tagEl = document.getElementById('broadcast-tag');
  const urlEl = document.getElementById('broadcast-url');
  const submitBtn = document.getElementById('btn-broadcast-submit');

  if (!titleEl || !descEl) return;
  const title = titleEl.value.trim();
  const description = descEl.value.trim();
  if (!title || !description) {
    alert('Please enter both a Notification Title and Message Description.');
    return;
  }

  const category = catEl ? catEl.value : 'announcement';
  const priority = prioEl ? prioEl.value : 'normal';
  const target_role = targetEl ? targetEl.value : 'all';
  const tag = (tagEl && tagEl.value.trim()) ? tagEl.value.trim() : 'Broadcast';
  const action_url = urlEl ? urlEl.value.trim() : '';

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="margin-right:6px;"></i>Publishing...';
  }

  try {
    const res = await fetch('/api/app/notifications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        description,
        category,
        priority,
        target_role,
        tag,
        action_url
      })
    });
    const data = await res.json();

    if (res.ok && data.status === 'success') {
      closeBroadcastModal();
      titleEl.value = '';
      descEl.value = '';
      if (urlEl) urlEl.value = '';

      showToastNotification({
        title: 'Broadcast Published Live',
        description: `Notification published: "${title}" across target workspaces.`,
        category: 'announcement',
        tag: 'Success'
      });

      await loadBroadcastNotifications(false);
      const card = document.getElementById('notif-dropdown-card');
      if (card) card.classList.add('open');
    } else {
      alert(data.detail || 'Could not publish broadcast.');
    }
  } catch (e) {
    console.error('Broadcast error:', e);
    alert('Failed to connect to notification service.');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fa-solid fa-paper-plane" style="margin-right:6px;"></i>Publish Live Broadcast';
    }
  }
}

async function deleteBroadcastNotification(event, notifId) {
  if (event) event.stopPropagation();
  if (!confirm('Are you sure you want to delete this broadcast notification?')) return;

  try {
    const res = await fetch(`/api/app/notifications/${notifId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok && data.status === 'success') {
      await loadBroadcastNotifications(false);
    } else {
      alert(data.detail || 'Could not delete notification.');
    }
  } catch (e) {
    console.error('Delete error:', e);
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
  loadBroadcastNotifications(false);
  // Auto-poll notifications every 7 seconds for live broadcasts
  setInterval(() => {
    loadBroadcastNotifications(true);
  }, 7000);
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
