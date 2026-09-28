/* ============================================================
   rightpanel.js — SonicSentinel AI Maintenance Command Center
   Right Panel: Stream Bandwidth + Real-Time Diagnostic & Quality Log + Sensor Telemetry Feed
   ============================================================ */
(function (global) {
  'use strict';

  function clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }

  function secondsAgo(ts) { return Math.max(0, Math.floor((Date.now() - ts) / 1000)); }
  function formatSecondsAgo(ts) {
    const s = secondsAgo(ts);
    if (s < 60) return `T-${s}s`;
    if (s < 3600) return `T-${Math.floor(s / 60)}m`;
    if (s < 86400) return `T-${Math.floor(s / 3600)}h`;
    return `T-${Math.floor(s / 86400)}d`;
  }

  function sectionHeaderHTML({ title, colorClass, rightSlotHTML, blink }) {
    const dotColor = colorClass === 'purple' ? '#a855f7' : colorClass === 'amber' ? '#f59e0b' : colorClass === 'emerald' ? '#10b981' : '#00f5ff';
    const textColor = colorClass === 'purple' ? '#c084fc' : colorClass === 'amber' ? '#fbbf24' : colorClass === 'emerald' ? '#34d399' : '#22d3ee';
    return `
      <div class="section-header">
        <div class="left">
          <div class="bar" style="background:${dotColor};box-shadow:0 0 6px ${dotColor};"></div>
          <span class="title ${blink ? 'cursor-blink' : ''}" style="color:${textColor};text-shadow:0 0 10px ${dotColor}, 0 0 20px ${dotColor};">${title}</span>
        </div>
        <div class="right">${rightSlotHTML || ''}</div>
      </div>
    `;
  }

  const ALERT_COLORS = {
    INFO: {
      badge: '#34d399',
      badgeBorder: 'rgba(16,185,129,0.45)',
      badgeBg: 'rgba(16,185,129,0.14)',
      border: '#10b981',
      cardBg: 'rgba(6, 24, 34, 0.75)',
      cardBorder: 'rgba(16,185,129,0.2)',
      tag: 'DIAGNOSTIC // NOMINAL',
    },
    WARN: {
      badge: '#fbbf24',
      badgeBorder: 'rgba(245,158,11,0.5)',
      badgeBg: 'rgba(245,158,11,0.16)',
      border: '#f59e0b',
      cardBg: 'rgba(28, 20, 8, 0.78)',
      cardBorder: 'rgba(245,158,11,0.28)',
      tag: 'ANOMALY // ELEVATED',
    },
    CRIT: {
      badge: '#f87171',
      badgeBorder: 'rgba(239,68,68,0.6)',
      badgeBg: 'rgba(239,68,68,0.2)',
      border: '#ef4444',
      cardBg: 'rgba(32, 10, 14, 0.82)',
      cardBorder: 'rgba(239,68,68,0.35)',
      tag: 'FAULT // CRITICAL',
    },
  };

  function mountRightPanel(root) {
    const store = global.NEXUS.store;

    root.innerHTML = `
      <div class="rightpanel">
        <div class="corner-tr" style="border-color:#00f5ff;"></div>
        <div class="rp-stack">
          <div class="rp-section-pad"><div id="rp-bandwidth" class="panel" style="padding:10px;"></div></div>
          <div class="rp-alert-pad"><div id="rp-alerts" class="panel" style="padding:10px;flex:1;min-height:0;display:flex;flex-direction:column;"></div></div>
          <div class="rp-comm-pad"><div id="rp-comm" class="panel" style="padding:10px;"></div></div>
        </div>
      </div>
    `;

    buildBandwidth(root.querySelector('#rp-bandwidth'), store);
    buildAlerts(root.querySelector('#rp-alerts'), store);
    buildComm(root.querySelector('#rp-comm'), store);

    return { destroy() {} };
  }

  // ── 1. STREAM BANDWIDTH MONITOR ─────────────────────────────
  function buildBandwidth(el, store) {
    el.innerHTML = `
      ${sectionHeaderHTML({ title: 'STREAM BANDWIDTH // BUFFER TELEMETRY', colorClass: 'cyan' })}
      <div class="bw-metrics">
        <div class="bw-metric"><span class="k">BITRATE</span><span class="v" id="bw-peak"></span></div>
        <div class="divider-v-sm"></div>
        <div class="bw-metric"><span class="k">LATENCY</span><span class="v" id="bw-latency"></span></div>
        <div class="divider-v-sm"></div>
        <div class="bw-metric"><span class="k">CONSENSUS</span><span class="v" id="bw-sync"></span></div>
      </div>
      <div class="bw-bars" id="bw-bars"></div>
    `;

    function render(state) {
      const { dataStreams } = state;
      const bitrate = state.isListening
        ? (64.0 + ((state.reactorOutput || 68) / 100) * 64.0).toFixed(1)
        : '0.0';
      const latency = Number(state.dbLatencyMs || 0).toFixed(1);

      el.querySelector('#bw-peak').innerHTML = `${bitrate} <span style="font-size:8px;color:rgba(0,145,166,0.7);">KB/s</span>`;
      const latencyEl = el.querySelector('#bw-latency');
      latencyEl.innerHTML = `${latency} <span style="font-size:8px;opacity:0.7;">ms</span>`;
      latencyEl.style.color = Number(latency) < 100 ? '#10b981' : Number(latency) < 300 ? '#f59e0b' : '#ef4444';
      const syncEl = el.querySelector('#bw-sync');
      syncEl.textContent = `${Math.round(state.quantumCoherence || 0)}%`;
      syncEl.style.color = state.dbConnected ? '#10b981' : '#f59e0b';

      const barsEl = el.querySelector('#bw-bars');
      barsEl.innerHTML = (dataStreams || []).map((stream) => {
        const lastVal = stream.values[stream.values.length - 1] || 0;
        const pct = clamp(lastVal, 0, 100);
        return `
          <div class="bw-bar-col">
            <div class="bw-bar-track" style="border:1px solid #1e293b;background:#090e1a;">
              <div class="bw-bar-fill" style="height:${pct}%;background:linear-gradient(180deg, #38bdf8 0%, #0284c7 100%);border-radius:2px;"></div>
            </div>
            <span class="bw-bar-label" style="color:#64748b;font-size:6px;" title="${stream.label}">${stream.label.slice(0, 8)}</span>
          </div>
        `;
      }).join('');
    }

    render(store.getState());
    store.subscribe((state, prev) => {
      if (
        state.dataStreams !== prev.dataStreams ||
        state.quantumCoherence !== prev.quantumCoherence ||
        state.dbLatencyMs !== prev.dbLatencyMs ||
        state.isListening !== prev.isListening
      ) {
        render(state);
      }
    });
  }

  // ── 2. REAL-TIME DIAGNOSTIC & QUALITY LOG ───────────────────
  function buildAlerts(el, store) {
    el.innerHTML = `
      ${sectionHeaderHTML({ title: 'DIAGNOSTIC & QUALITY LOG // REAL-TIME', colorClass: 'cyan', blink: true, rightSlotHTML: '<span class="alert-count-pill" id="alert-count"></span>' })}
      <div class="alert-list" id="alert-list"></div>
      <div class="inject-btns">
        <button class="inject-btn green" id="btn-live-mic">LIVE MIC</button>
        <button class="inject-btn amber" id="btn-refresh-log">REFRESH</button>
        <button class="inject-btn red" id="btn-open-upload">UPLOAD AUDIO</button>
      </div>
    `;

    const listEl = el.querySelector('#alert-list');

    el.querySelector('#btn-live-mic').addEventListener('click', () => {
      if (global.NEXUS && global.NEXUS.toggleLiveMonitoring) {
        global.NEXUS.toggleLiveMonitoring();
      }
    });
    el.querySelector('#btn-refresh-log').addEventListener('click', () => {
      if (global.NEXUS && global.NEXUS.syncDatabaseTelemetry) {
        global.NEXUS.syncDatabaseTelemetry(true);
      }
    });
    el.querySelector('#btn-open-upload').addEventListener('click', () => {
      if (global.NEXUS && global.NEXUS.openAudioModal) {
        global.NEXUS.openAudioModal();
      }
    });

    function alertItemHTML(alert, idx) {
      const c = ALERT_COLORS[alert.level] || ALERT_COLORS.INFO;
      const evtCode = alert.code || `DIAG-${String(idx + 101).padStart(3, '0')}`;
      const evtTag = alert.tag || c.tag;
      return `
        <div class="alert-item alert-enter" style="background:${c.cardBg};border:1px solid ${c.cardBorder};border-left:3px solid ${c.border};">
          <div class="alert-header">
            <div class="alert-header-left">
              <span class="badge" style="background:${c.badgeBg};color:${c.badge};border:1px solid ${c.badgeBorder};box-shadow:0 0 8px ${c.badgeBg};">${alert.level}</span>
              <span class="alert-tag" style="color:${c.badge};opacity:0.85;">${evtTag}</span>
            </div>
            <div class="alert-header-right">
              <span class="alert-code">${evtCode}</span>
              <span class="ts">${formatSecondsAgo(alert.ts)}</span>
            </div>
          </div>
          <div class="alert-msg">${alert.msg}</div>
        </div>
      `;
    }

    function render(state) {
      if (!state.alerts || state.alerts.length === 0) {
        listEl.innerHTML = `<div class="alert-empty"><span>NO DIAGNOSTIC EVENTS RECORDED YET</span></div>`;
      } else {
        listEl.innerHTML = state.alerts.map(alertItemHTML).join('');
      }
      const totalEvents = state.anomalyCount || (state.alerts || []).length;
      el.querySelector('#alert-count').textContent = `${totalEvents} EVENTS`;
      const micBtn = el.querySelector('#btn-live-mic');
      if (micBtn) {
        micBtn.textContent = state.isListening ? 'STOP MIC' : 'LIVE MIC';
      }
    }

    render(store.getState());
    store.subscribe((state, prev) => {
      if (
        state.alerts !== prev.alerts ||
        state.anomalyCount !== prev.anomalyCount ||
        state.isListening !== prev.isListening
      ) {
        render(state);
      }
    });

    setInterval(() => {
      listEl.querySelectorAll('.alert-item').forEach((item, i) => {
        const alert = store.getState().alerts[i];
        if (alert) {
          const tsEl = item.querySelector('.ts');
          if (tsEl) tsEl.textContent = formatSecondsAgo(alert.ts);
        }
      });
    }, 1000);
  }

  // ── 3. SENSOR & CLOUD TELEMETRY FEED ────────────────────────
  function buildComm(el, store) {
    let barPhase = 0;

    el.innerHTML = `
      ${sectionHeaderHTML({ title: 'SENSOR & CLOUD TELEMETRY // ACTIVE', colorClass: 'cyan', rightSlotHTML: '<span style="font-family:monospace;font-size:8px;color:#34d399;font-weight:700;" id="comm-right">ONLINE</span>' })}
      <div class="comm-channels" id="comm-channels"></div>
      <div class="comm-footer">
        <span class="lbl">PIPELINE</span>
        <span class="val" id="comm-freq-val">16.0 kHz DUAL-AI // ACTIVE</span>
      </div>
    `;

    function commBarHTML(pct, color, barPhase, animated) {
      const totalBlocks = 10;
      const filledCount = Math.round((pct / 100) * totalBlocks);
      let html = '<div class="comm-bar">';
      for (let i = 0; i < totalBlocks; i++) {
        const filled = i < filledCount;
        const isScan = animated && i === barPhase % totalBlocks;
        const col = filled ? (isScan ? '#ffffff' : color) : 'rgba(255,255,255,0.08)';
        const shadow = filled ? `text-shadow:0 0 4px ${color};` : '';
        html += `<span style="color:${col};${shadow}">${filled ? '\u2588' : '\u2591'}</span>`;
      }
      html += '</div>';
      return html;
    }

    const STATUS_COLORS = {
      STREAMING: '#34d399',
      READY: '#34d399',
      ONLINE: '#22d3ee',
      SYNCED: '#c084fc',
      CONNECTING: '#fbbf24',
      OFFLINE: '#f87171',
    };

    function render(state) {
      const channels = state.commChannels || [];
      const channelsEl = el.querySelector('#comm-channels');
      channelsEl.innerHTML = channels.map((ch, idx) => {
        const displayStatus = state.isListening && idx === 0 ? 'STREAMING' : ch.status;
        const displayPct = state.isListening && idx === 0 ? Math.min(100, Math.max(70, Math.round(state.shieldIntegrity))) : ch.pct;
        const displayColor = ch.color || '#00f5ff';
        const statusColor = STATUS_COLORS[displayStatus] || '#22d3ee';
        const phase = (barPhase + idx * 3) % 20;
        return `
          <div class="comm-channel">
            <span class="label">${ch.label}</span>
            <span class="status" style="color:${statusColor};">${displayStatus}</span>
            ${commBarHTML(displayPct, displayColor, phase, true)}
            <span class="pct" style="color:${displayColor};">${displayPct}%</span>
          </div>
        `;
      }).join('');

      const rightEl = el.querySelector('#comm-right');
      if (state.wsConnected) {
        rightEl.textContent = 'LIVE STREAM';
        rightEl.style.color = '#34d399';
      } else if (state.dbConnected) {
        rightEl.textContent = 'ONLINE';
        rightEl.style.color = '#34d399';
      } else {
        rightEl.textContent = 'STANDBY';
        rightEl.style.color = '#fbbf24';
      }

      el.querySelector('#comm-freq-val').textContent =
        `PY-CNN ${state.pythonModelVersion || 'v2.5'} + GTM ${state.gtmModelVersion || 'v2.5'} // ACTIVE`;
    }

    render(store.getState());
    store.subscribe((state) => render(state));

    setInterval(() => {
      barPhase = (barPhase + 1) % 20;
      render(store.getState());
    }, 250);
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.mountRightPanel = mountRightPanel;
})(window);
