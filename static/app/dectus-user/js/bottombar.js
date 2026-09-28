/* ============================================================
   bottombar.js — port of src/components/layout/BottomBar.jsx
   ============================================================ */
(function (global) {
  'use strict';

  const TELEMETRY_DEFS = [
    { label: 'SAMPLE RATE', base: 44.1, unit: 'kHz', range: 0, decimals: 1 },
    { label: 'AUDIO BUFFER', base: 2.0, unit: 's ROLLING', range: 0, decimals: 1 },
    { label: 'ENCRYPTION', base: 256, unit: 'AES-GCM', range: 0, decimals: 0 },
    { label: 'SNR THRESHOLD', base: 12.0, unit: 'dB', range: 0.8, decimals: 1 },
    { label: 'CLIPPING INCIDENCE', base: 0.0, unit: '% NOMINAL', range: 0.1, decimals: 2 },
    { label: 'PYTHON 2D-CNN', base: 94.8, unit: '% ACCURACY', range: 0, decimals: 1 },
    { label: 'GTM AUDIOSET VERIFIER', base: 93.2, unit: '% ACCURACY', range: 0, decimals: 1 },
    { label: 'DUAL-MODEL CONSENSUS', base: 98.4, unit: '% SYNC', range: 0.5, decimals: 1 },
    { label: 'NOISE GATE FLOOR', base: -48.0, unit: 'dBFS', range: 1.5, decimals: 1 },
    { label: 'DYNAMIC RANGE', base: 96.0, unit: 'dB', range: 0, decimals: 1 },
    { label: 'FFT RESOLUTION', base: 256, unit: 'BINS', range: 0, decimals: 0 },
    { label: 'LATENCY PIPELINE', base: 14.2, unit: 'ms', range: 1.2, decimals: 1 },
    { label: 'PRIVACY ENGINE', base: 100, unit: '% CONSENT ENFORCED', range: 0, decimals: 0 },
    { label: 'SPECTRAL COHERENCE', base: 96.4, unit: '%', range: 1.0, decimals: 1 },
    { label: 'ACOUSTIC CHANNEL CORRELATION', base: 0.984, unit: 'r', range: 0.005, decimals: 3 },
  ];

  function buildTelemetryString(defs, offsets) {
    return defs.map((d, i) => {
      const val = d.base + offsets[i] * d.range * 2 - d.range;
      return `\u25ba ${d.label}: ${val.toFixed(d.decimals)} ${d.unit}`;
    }).join('    ');
  }

  function systemStatuses(s) {
    const micColor = s.cloakActive ? '#ef4444' : (s.isListening ? '#10b981' : '#94a3b8');
    const micStatus = s.cloakActive ? 'MUTED' : (s.isListening ? 'LISTENING' : 'STANDBY');

    const qualColor = s.shieldIntegrity >= 70 ? '#10b981' : (s.shieldIntegrity >= 40 ? '#f59e0b' : '#ef4444');
    const qualStatus = s.shieldIntegrity >= 70 ? 'NOMINAL' : (s.shieldIntegrity >= 40 ? 'ACCEPTABLE' : 'POOR');

    const consColor = s.warpEnabled ? '#00f5ff' : '#10b981';
    const consStatus = s.warpEnabled ? 'VERIFIED' : 'READY';

    const alertColor = s.combatMode ? '#ef4444' : (s.sectorThreatLevel >= 3 ? '#f59e0b' : '#10b981');
    const alertStatus = s.combatMode ? 'CRITICAL' : (s.sectorThreatLevel >= 3 ? 'ALERT' : 'NOMINAL');

    return [
      { id: 'AI-CORE', color: '#10b981', status: 'ONLINE' },
      { id: 'MIC-INPUT', color: micColor, status: micStatus },
      { id: 'QUALITY', color: qualColor, status: qualStatus },
      { id: 'CONSENSUS', color: consColor, status: consStatus },
      { id: 'SECURITY', color: alertColor, status: alertStatus },
    ];
  }

  function mountBottomBar(root) {
    const store = global.NEXUS.store;

    root.innerHTML = `
      <div class="bottombar">
        <div class="top-edge"></div>
        <div class="bb-statuses" id="bb-statuses"></div>
        <div class="bb-marquee"><div class="bb-marquee-inner" id="bb-marquee-inner"><span id="bb-marquee-text"></span></div></div>
        <div class="bb-right">
          <div class="bb-right-inner">
            <div class="bb-gridref">
              <span class="lbl">GRID REF</span>
              <span class="val" id="bb-gridref-val"></span>
            </div>
            <div class="bb-signal" id="bb-signal">
              <div class="dot"></div>
              <div class="bb-signal-text">
                <span class="a" id="bb-signal-a"></span>
                <span class="b" id="bb-signal-b"></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    const statusesEl = root.querySelector('#bb-statuses');
    let offsets = TELEMETRY_DEFS.map(() => Math.random());

    function renderStatuses(state) {
      const statuses = systemStatuses(state);
      statusesEl.innerHTML = statuses.map((s) => `
        <div class="bb-status">
          <div class="dot" style="background:${s.color};box-shadow:0 0 5px ${s.color};animation-duration:${(1.4 + Math.random() * 0.8).toFixed(2)}s;"></div>
          <span class="id" style="color:${s.color}">${s.id}</span>
          <span class="st" style="color:${s.color}88">[${s.status}]</span>
        </div>
      `).join('');
    }

    function renderMarquee() {
      const text = buildTelemetryString(TELEMETRY_DEFS, offsets);
      const doubled = `${text}          ${text}`;
      const span = root.querySelector('#bb-marquee-text');
      span.textContent = doubled;
      const duration = text.length * 0.35;
      const inner = root.querySelector('#bb-marquee-inner');
      inner.style.animation = `bbScroll ${duration}s linear infinite`;
    }

    function render(state) {
      renderStatuses(state);

      // grid ref
      root.querySelector('#bb-gridref-val').textContent = 'ZONE-01 // SEC-A';

      // signal lock
      const isListening = state.isListening && !state.cloakActive;
      const signalEl = root.querySelector('#bb-signal');
      const dot = signalEl.querySelector('.dot');
      dot.style.background = isListening ? '#10b981' : (state.cloakActive ? '#ef4444' : '#94a3b8');
      dot.style.boxShadow = isListening ? '0 0 6px #10b981' : 'none';
      dot.style.animation = isListening ? 'fadeOpacity 2s infinite' : 'none';
      const a = root.querySelector('#bb-signal-a');
      a.textContent = state.cloakActive ? 'PRIVACY MUTED' : (isListening ? 'ACOUSTIC LOCK' : 'SENSOR STANDBY');
      a.style.color = isListening ? '#10b981' : (state.cloakActive ? '#ef4444' : '#94a3b8');
      const b = root.querySelector('#bb-signal-b');
      b.textContent = isListening ? '44.1 kHz PCM [STABLE]' : 'MICROPHONE IDLE';
      b.style.color = isListening ? 'rgba(16,185,129,0.7)' : (state.cloakActive ? 'rgba(239,68,68,0.7)' : 'rgba(148,163,184,0.5)');
    }

    // inject the marquee keyframes once
    if (!document.getElementById('bb-scroll-kf')) {
      const style = document.createElement('style');
      style.id = 'bb-scroll-kf';
      style.textContent = '@keyframes bbScroll { from { transform: translateX(0%); } to { transform: translateX(-50%); } }';
      document.head.appendChild(style);
    }

    renderMarquee();
    render(store.getState());
    const unsub = store.subscribe(render);

    const offsetInterval = setInterval(() => {
      offsets = offsets.map((o) => {
        const delta = (Math.random() - 0.5) * 0.06;
        return Math.min(1, Math.max(0, o + delta));
      });
      renderMarquee();
    }, 2000);

    return {
      destroy() {
        unsub();
        clearInterval(offsetInterval);
      },
    };
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.mountBottomBar = mountBottomBar;
})(window);
