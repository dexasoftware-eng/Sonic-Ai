/* ============================================================
   centerpanel.js — SonicSentinel AI Audio Intelligence Command Center
   Center Panel: Live Acoustic Waveform & Spectrum Visualizer +
   Neural Inference Buffer + All 6 Live Acoustic Telemetry Streams
   ============================================================ */
(function (global) {
  'use strict';

  const { tachyonToColor, hexAlpha } = global.NEXUS.colors;

  function mountCenterPanel(root) {
    const store = global.NEXUS.store;

    root.innerHTML = `
      <div class="centerpanel panel box-glow-cyan">
        <div id="cp-emergency-overlay" class="emergency-overlay hidden"></div>

        <div class="cp-header">
          <div class="cp-header-row">
            <div>
              <div class="cp-sector-lbl">ACOUSTIC ZONE // SECTOR-01</div>
              <h1 class="cp-sector-name" id="cp-sector-name">ZONE-RESIDENCE</h1>
            </div>
            <div class="cp-stats">
              <div class="cp-stat"><span class="k">AI CLASSES</span><span class="v glow-cyan" style="color:#00f5ff;" id="cp-probes">10</span></div>
              <div class="cp-stat"><span class="k">DETECTIONS</span><span class="v" id="cp-anomalies">00</span></div>
            </div>
          </div>
          <div class="cp-threat">
            <div class="cp-threat-row">
              <span class="k">ACOUSTIC THREAT LEVEL</span>
              <span class="v" id="cp-threat-label">NOMINAL</span>
            </div>
            <div class="cp-threat-bars" id="cp-threat-bars"></div>
          </div>
          <div class="cp-flags" id="cp-flags"></div>
        </div>

        <div class="cp-wave-section">
          <div class="cp-divider-row">
            <div class="line" style="background:linear-gradient(90deg, transparent, rgba(0,245,255,0.4));"></div>
            <span class="lbl">LIVE ACOUSTIC SPECTRUM & WAVEFORM MONITOR</span>
            <div class="line" style="background:linear-gradient(90deg, rgba(0,245,255,0.4), transparent);"></div>
          </div>
          <div class="wave-wrap" id="wave-mount"></div>
        </div>

        <div class="cp-bottom">
          <div class="cp-inference-grid" style="display:grid;grid-template-columns:repeat(3, 1fr);gap:8px;">
            <!-- BOX 1: NEURAL INFERENCE BUFFER -->
            <div id="cp-box-buffer" class="sparkline-box">
              <div class="warp-charge-header" style="display:flex;align-items:center;justify-content:space-between;">
                <span class="k" style="font-size:8px;letter-spacing:0.12em;">NEURAL INFERENCE BUFFER</span>
                <span id="cp-warp-status" style="font-family:'Orbitron';font-size:10px;font-weight:700;">0%</span>
              </div>
              <div class="warp-bar-track" id="cp-warp-track" style="height:12px;">
                <div class="warp-bar-fill" id="cp-warp-fill">
                  <div class="warp-bar-fill-inner" id="cp-warp-fill-inner"></div>
                  <div id="cp-warp-shimmer" class="hidden" style="position:absolute;inset:0;overflow:hidden;border-radius:inherit;">
                    <div class="flow-right" style="position:absolute;inset-block:0;width:33%;"></div>
                  </div>
                </div>
                <div class="warp-tick" style="left:25%;"></div>
                <div class="warp-tick" style="left:50%;"></div>
                <div class="warp-tick" style="left:75%;"></div>
                <div id="cp-gate-marker" title="Min Alert Confidence Gate" style="position:absolute;top:-1px;bottom:-1px;width:2px;background:#a855f7;box-shadow:0 0 6px #a855f7;left:75%;z-index:3;transition:left 0.15s;"></div>
                <div id="cp-warp-ready-glow" class="warp-ready-glow hidden" style="background:rgba(16,185,129,0.15);"></div>
              </div>
              <div class="warp-status-row" style="justify-content:space-between;">
                <div class="warp-status-item"><div class="dot" id="cp-warp-dot"></div><span class="txt" id="cp-warp-status-text"></span></div>
                <span id="cp-warp-jump" style="font-family:'Orbitron';font-size:7.5px;letter-spacing:0.1em;color:#c084fc;">MIN GATE: 75%</span>
              </div>
            </div>

            <!-- BOX 2: DETECTED ACTIVITY CLASS & SEVERITY -->
            <div id="cp-box-activity" class="sparkline-box">
              <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
                <span style="font-family:monospace;font-size:8px;letter-spacing:0.12em;color:rgba(0,245,255,0.7);">DETECTED ACTIVITY // CLASS</span>
                <span id="cp-act-sev-badge" style="font-family:'Orbitron';font-size:7.5px;font-weight:700;letter-spacing:0.12em;padding:1px 6px;border-radius:2px;border:1px solid #10b981;color:#10b981;background:rgba(16,185,129,0.12);">LOW</span>
              </div>
              <div style="display:flex;align-items:baseline;justify-content:space-between;gap:6px;">
                <div id="cp-act-class" style="font-family:'Orbitron';font-size:13px;font-weight:800;letter-spacing:0.08em;color:#00f5ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">AMBIENT STANDBY</div>
                <div id="cp-act-avg" style="font-family:'Orbitron';font-size:11px;font-weight:700;color:#e2e8f0;flex-shrink:0;">0%</div>
              </div>
              <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
                <span id="cp-act-consensus" style="font-family:monospace;font-size:7.5px;letter-spacing:0.08em;color:#94a3b8;">STANDBY</span>
                <span id="cp-act-gate-status" style="font-family:'Orbitron';font-size:7.5px;font-weight:700;letter-spacing:0.08em;color:#10b981;">GATE STANDBY</span>
              </div>
            </div>

            <!-- BOX 3: MODELS CONFIDENCE & MIN ALERT CONFIDENCE -->
            <div id="cp-box-models" class="sparkline-box">
              <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
                <span style="font-family:monospace;font-size:8px;letter-spacing:0.12em;color:rgba(216,180,254,0.8);">MODELS CONFIDENCE</span>
                <span id="cp-min-conf-pill" style="font-family:'Orbitron';font-size:7.5px;font-weight:700;letter-spacing:0.1em;color:#c084fc;background:rgba(168,85,247,0.12);border:1px solid rgba(168,85,247,0.35);padding:1px 5px;border-radius:2px;">MIN ALERT: 75%</span>
              </div>
              <div style="display:flex;flex-direction:column;gap:4px;">
                <div>
                  <div style="display:flex;justify-content:space-between;font-family:'Orbitron';font-size:7.5px;margin-bottom:2px;">
                    <span id="cp-mod-py-lbl" style="color:#00f5ff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:72%;">PY 2D-CNN: STANDBY</span>
                    <span id="cp-mod-py-val" style="color:#00f5ff;font-weight:700;">0%</span>
                  </div>
                  <div style="position:relative;height:4px;background:rgba(0,245,255,0.1);border-radius:2px;overflow:hidden;">
                    <div id="cp-mod-py-bar" style="height:100%;width:0%;background:#00f5ff;box-shadow:0 0 6px #00f5ff;transition:width 0.25s;"></div>
                  </div>
                </div>
                <div>
                  <div style="display:flex;justify-content:space-between;font-family:'Orbitron';font-size:7.5px;margin-bottom:2px;">
                    <span id="cp-mod-gtm-lbl" style="color:#c084fc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:72%;">GTM TMv2: STANDBY</span>
                    <span id="cp-mod-gtm-val" style="color:#c084fc;font-weight:700;">0%</span>
                  </div>
                  <div style="position:relative;height:4px;background:rgba(168,85,247,0.1);border-radius:2px;overflow:hidden;">
                    <div id="cp-mod-gtm-bar" style="height:100%;width:0%;background:#a855f7;box-shadow:0 0 6px #a855f7;transition:width 0.25s;"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="cp-streams-divider">
            <div class="line" style="background:linear-gradient(90deg, transparent, rgba(0,245,255,0.25));"></div>
            <span class="lbl">LIVE ACOUSTIC TELEMETRY STREAMS</span>
            <div class="line" style="background:linear-gradient(90deg, rgba(0,245,255,0.25), transparent);"></div>
          </div>
          <div class="cp-sparklines" id="cp-sparklines"></div>
        </div>
      </div>
    `;

    // Render all 6 live acoustic telemetry streams
    function renderSparklines(dataStreams) {
      const sparkEl = root.querySelector('#cp-sparklines');
      const streams = dataStreams || [];
      sparkEl.innerHTML = streams.map((stream) => {
        const values = stream.values || [0];
        const W = 220, H = 40, pad = 3;
        const min = Math.min(...values);
        const max = Math.max(...values) || 1;
        const range = max - min || 1;
        const points = values.map((v, i) => {
          const x = pad + (i / (values.length - 1)) * (W - pad * 2);
          const y = pad + (1 - (v - min) / range) * (H - pad * 2);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(' ');
        const lastVal = values[values.length - 1] || 0;
        const pts = points.split(' ');
        const lastPt = pts[pts.length - 1].split(',');
        return `
          <div class="sparkline-box">
            <div class="sparkline-head">
              <span class="lbl" style="color:${stream.color};opacity:0.85;">${stream.label}</span>
              <span class="val" style="color:#f8fafc;">${lastVal.toFixed(1)}</span>
            </div>
            <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none" style="overflow:visible;display:block;">
              <defs>
                <linearGradient id="fill-${stream.id}" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="${stream.color}" stop-opacity="0.3" />
                  <stop offset="100%" stop-color="${stream.color}" stop-opacity="0.02" />
                </linearGradient>
              </defs>
              <polyline points="${points} ${W - pad},${H - pad} ${pad},${H - pad}" fill="url(#fill-${stream.id})" stroke="none" />
              <polyline points="${points}" fill="none" stroke="${stream.color}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" style="filter:drop-shadow(0 0 3px ${stream.color});" />
              <circle cx="${lastPt[0]}" cy="${lastPt[1]}" r="2.8" fill="${stream.color}" style="filter:drop-shadow(0 0 5px ${stream.color});" />
            </svg>
          </div>
        `;
      }).join('');
    }

    // Mount Live Audio Wave Visualizer
    const waveMount = root.querySelector('#wave-mount');
    const waveHandle = global.NEXUS.mountAudioWave
      ? global.NEXUS.mountAudioWave(waveMount, () => store.getState())
      : { destroy() {} };

    function render(state) {
      const sev = String(state.severity || 'Low').toLowerCase();
      const minAlertConf = Number(state.neuralSyncRate != null ? state.neuralSyncRate : 75);
      const pyConf = Number(state.pythonConfidence || 0);
      const gtmConf = Number(state.gtmConfidence || 0);
      const warpCharge = Number(state.warpCharge || 0);
      const effectiveConf = Math.max(warpCharge, pyConf);
      const passesGate = effectiveConf >= minAlertConf;

      let sevColor = '#10b981';
      let sevLabel = 'LOW';
      if (sev === 'critical') {
        sevColor = '#ef4444';
        sevLabel = 'CRITICAL';
      } else if (sev === 'high') {
        sevColor = '#f59e0b';
        sevLabel = 'HIGH';
      } else if (sev === 'medium') {
        sevColor = '#eab308';
        sevLabel = 'MEDIUM';
      }

      const activeAccent = passesGate && (sev === 'critical' || sev === 'high' || sev === 'medium')
        ? sevColor
        : tachyonToColor(state.tachyonFrequency || 1.85);

      root.querySelector('#cp-emergency-overlay').classList.toggle('hidden', !state.emergencyProtocol);

      // Update wave container border glow according to active severity
      if (waveMount) {
        waveMount.style.borderColor = hexAlpha(activeAccent, 0.45);
        waveMount.style.boxShadow = `0 0 18px ${hexAlpha(activeAccent, 0.2)}, inset 0 0 24px ${hexAlpha(activeAccent, 0.06)}`;
      }

      const sectorEl = root.querySelector('#cp-sector-name');
      sectorEl.textContent = state.sectorDesignation;
      sectorEl.style.color = activeAccent;
      sectorEl.style.textShadow = `0 0 20px ${activeAccent}, 0 0 40px ${hexAlpha(activeAccent, 0.4)}`;

      root.querySelector('#cp-probes').textContent = String(state.activeProbes).padStart(2, '0');
      const anomEl = root.querySelector('#cp-anomalies');
      anomEl.textContent = String(state.anomalyCount).padStart(2, '0');
      const anomColor = state.anomalyCount > 3 ? '#ef4444' : state.anomalyCount > 1 ? '#f59e0b' : '#10b981';
      anomEl.style.color = anomColor;
      anomEl.style.textShadow = `0 0 10px ${anomColor}`;

      // Threat bar
      const level = state.sectorThreatLevel;
      const glowColor = level <= 1 ? '#10b981' : level <= 3 ? '#eab308' : level === 4 ? '#f59e0b' : '#ef4444';
      const label = level === 0 ? 'CLEAR' : level <= 1 ? 'NOMINAL' : level <= 2 ? 'ELEVATED' : level <= 3 ? 'MEDIUM' : level <= 4 ? 'HIGH ALERT' : 'CRITICAL THREAT';
      const threatLbl = root.querySelector('#cp-threat-label');
      threatLbl.textContent = label;
      threatLbl.style.color = glowColor;
      threatLbl.style.textShadow = `0 0 8px ${glowColor}`;
      threatLbl.style.animation = level >= 4 ? 'alertFlash 0.8s ease-in-out infinite' : 'none';

      const barsEl = root.querySelector('#cp-threat-bars');
      barsEl.innerHTML = '';
      for (let i = 0; i < 5; i++) {
        const active = i <= level - 1;
        const segColor = !active ? 'rgba(0,245,255,0.06)' : glowColor;
        const div = document.createElement('div');
        div.className = 'seg';
        div.style.background = segColor;
        div.style.border = `1px solid ${active ? glowColor : 'rgba(0,245,255,0.1)'}`;
        div.style.boxShadow = active ? `0 0 6px ${glowColor}` : 'none';
        if (active && level >= 4) div.style.animation = 'fadeOpacity 0.8s infinite';
        barsEl.appendChild(div);
      }

      // Flags
      const flagsEl = root.querySelector('#cp-flags');
      let flagsHTML = '';
      if (passesGate && sev === 'high') flagsHTML += '<span class="cp-flag combat" style="color:#f59e0b;border-color:rgba(245,158,11,0.5);background:rgba(245,158,11,0.12);">HIGH SEVERITY ALERT</span>';
      if (state.cloakActive) flagsHTML += '<span class="cp-flag cloak">PRIVACY MUTED</span>';
      if (state.emergencyProtocol) flagsHTML += '<span class="cp-flag emergency">!! CRITICAL ACOUSTIC THREAT !!</span>';
      flagsEl.innerHTML = flagsHTML;

      // BOX 1: Buffer Charge & Min Alert Gate Marker
      const isReady = passesGate && effectiveConf > 0;
      const barColor = passesGate && (sev === 'critical' || sev === 'high')
        ? sevColor
        : isReady ? '#10b981' : state.warpEnabled ? '#00f5ff' : '#3b82f6';

      const statusEl = root.querySelector('#cp-warp-status');
      statusEl.textContent = `${warpCharge.toFixed(0)}%`;
      statusEl.style.color = barColor;
      statusEl.style.textShadow = isReady ? `0 0 10px ${barColor}` : 'none';

      const gateMarker = root.querySelector('#cp-gate-marker');
      if (gateMarker) {
        gateMarker.style.left = `${Math.max(5, Math.min(98, minAlertConf))}%`;
      }

      root.querySelector('#cp-warp-track').style.border = `1px solid ${hexAlpha(barColor, 0.35)}`;
      const fillEl = root.querySelector('#cp-warp-fill');
      fillEl.style.width = `${Math.min(100, warpCharge)}%`;
      const fillInner = root.querySelector('#cp-warp-fill-inner');
      fillInner.style.background = `linear-gradient(90deg, ${hexAlpha(barColor, 0.35)}, ${barColor})`;
      fillInner.style.boxShadow = `inset 0 0 8px ${hexAlpha(barColor, 0.4)}`;

      root.querySelector('#cp-warp-shimmer').classList.toggle('hidden', !state.warpEnabled);
      const shimmerBar = root.querySelector('#cp-warp-shimmer > div');
      if (shimmerBar) shimmerBar.style.background = `linear-gradient(90deg, transparent, ${hexAlpha(barColor, 0.8)}, transparent)`;

      root.querySelector('#cp-warp-ready-glow').classList.toggle('hidden', !isReady);

      const dotEl = root.querySelector('#cp-warp-dot');
      dotEl.style.background = state.warpEnabled ? barColor : 'rgba(0,245,255,0.15)';
      dotEl.style.boxShadow = state.warpEnabled ? `0 0 5px ${barColor}` : 'none';
      const statusTextEl = root.querySelector('#cp-warp-status-text');
      statusTextEl.textContent = state.isListening ? 'LIVE MIC ACTIVE' : 'AI ENGINE READY';
      statusTextEl.style.color = state.warpEnabled ? barColor : 'rgba(0,245,255,0.3)';

      const jumpEl = root.querySelector('#cp-warp-jump');
      jumpEl.textContent = `MIN GATE: ${Math.round(minAlertConf)}%`;
      jumpEl.style.color = passesGate ? '#10b981' : '#c084fc';

      // BOX 2: Detected Activity Class, Severity & Gate Status
      const actBox = root.querySelector('#cp-box-activity');
      const actBorderCol = passesGate ? sevColor : 'rgba(0,245,255,0.28)';
      actBox.style.borderColor = hexAlpha(actBorderCol, 0.55);
      actBox.style.boxShadow = passesGate && (sev === 'critical' || sev === 'high')
        ? `0 0 14px ${hexAlpha(sevColor, 0.25)}, inset 0 0 14px ${hexAlpha(sevColor, 0.1)}`
        : `inset 0 0 12px ${hexAlpha(actBorderCol, 0.06)}`;

      const sevBadge = root.querySelector('#cp-act-sev-badge');
      sevBadge.textContent = sevLabel;
      sevBadge.style.color = sevColor;
      sevBadge.style.borderColor = hexAlpha(sevColor, 0.6);
      sevBadge.style.background = hexAlpha(sevColor, 0.14);
      sevBadge.style.boxShadow = passesGate && (sev === 'critical' || sev === 'high') ? `0 0 8px ${hexAlpha(sevColor, 0.4)}` : 'none';

      const actClassEl = root.querySelector('#cp-act-class');
      const detectedClass = (state.currentSound || 'AMBIENT STANDBY').toUpperCase();
      actClassEl.textContent = detectedClass;
      actClassEl.style.color = passesGate && (sev === 'critical' || sev === 'high') ? sevColor : '#00f5ff';
      actClassEl.style.textShadow = `0 0 10px ${hexAlpha(passesGate ? sevColor : '#00f5ff', 0.45)}`;

      root.querySelector('#cp-act-avg').textContent = `${Math.round(effectiveConf)}%`;
      root.querySelector('#cp-act-avg').style.color = passesGate ? sevColor : '#94a3b8';

      const consEl = root.querySelector('#cp-act-consensus');
      const consTxt = (state.consistencyStatus || 'STANDBY').toUpperCase();
      consEl.textContent = consTxt;
      consEl.style.color = consTxt.includes('DISAGREE') ? '#f59e0b' : '#94a3b8';

      const gateStatusEl = root.querySelector('#cp-act-gate-status');
      if (effectiveConf === 0 || detectedClass === 'AMBIENT STANDBY') {
        gateStatusEl.textContent = `GATE: ${Math.round(minAlertConf)}%`;
        gateStatusEl.style.color = '#64748b';
      } else if (passesGate) {
        gateStatusEl.textContent = `● ALERT ACTIVE (≥${Math.round(minAlertConf)}%)`;
        gateStatusEl.style.color = sev === 'critical' ? '#ef4444' : sev === 'high' ? '#f59e0b' : '#10b981';
      } else {
        gateStatusEl.textContent = `○ SUPPRESSED (<${Math.round(minAlertConf)}%)`;
        gateStatusEl.style.color = '#f59e0b';
      }

      // BOX 3: Dual-AI Models Confidence & Min Alert Confidence Comparison
      const minConfPill = root.querySelector('#cp-min-conf-pill');
      minConfPill.textContent = `MIN ALERT: ${Math.round(minAlertConf)}%`;

      const pyName = (state.pythonPrediction || 'Standby').toUpperCase();
      const gtmName = (state.gtmPrediction || 'Standby').toUpperCase();
      root.querySelector('#cp-mod-py-lbl').textContent = `PY CNN: ${pyName}`;
      root.querySelector('#cp-mod-py-val').textContent = `${pyConf.toFixed(0)}%`;
      root.querySelector('#cp-mod-py-val').style.color = pyConf >= minAlertConf ? '#10b981' : '#00f5ff';
      root.querySelector('#cp-mod-py-bar').style.width = `${Math.min(100, pyConf)}%`;
      root.querySelector('#cp-mod-py-bar').style.background = pyConf >= minAlertConf ? '#10b981' : '#00f5ff';

      root.querySelector('#cp-mod-gtm-lbl').textContent = `GTM TMv2: ${gtmName}`;
      root.querySelector('#cp-mod-gtm-val').textContent = `${gtmConf.toFixed(0)}%`;
      root.querySelector('#cp-mod-gtm-val').style.color = gtmConf >= minAlertConf ? '#10b981' : '#c084fc';
      root.querySelector('#cp-mod-gtm-bar').style.width = `${Math.min(100, gtmConf)}%`;
      root.querySelector('#cp-mod-gtm-bar').style.background = gtmConf >= minAlertConf ? '#10b981' : '#a855f7';

      renderSparklines(state.dataStreams);
    }

    render(store.getState());
    const unsub = store.subscribe(render);

    // Tick data streams every 500ms
    const tickInterval = setInterval(() => {
      store.getState().tickDataStreams();
    }, 500);

    return {
      destroy() {
        unsub();
        clearInterval(tickInterval);
        waveHandle.destroy();
      },
    };
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.mountCenterPanel = mountCenterPanel;
})(window);
