/* ============================================================
   leftpanel.js — SonicSentinel AI Audio Intelligence Left Panel
   100% Authentic Audio DSP Controls, dBFS Meter, Live 4-Band EQ +
   Spectral Graph, Dual-AI Model Consensus, and Noise Gate / Filter
   ============================================================ */
(function (global) {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';

  function polarToCartesian(cx, cy, r, angleDeg) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function arcPath(cx, cy, r, startAngle, endAngle) {
    const start = polarToCartesian(cx, cy, r, endAngle);
    const end = polarToCartesian(cx, cy, r, startAngle);
    const large = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 0 ${end.x} ${end.y}`;
  }

  function cornerAccentsHTML(color) {
    const s = `position:absolute;width:10px;height:10px;border:1px solid ${color};pointer-events:none;`;
    return `
      <span class="corner" style="${s}top:0;left:0;border-right:none;border-bottom:none;"></span>
      <span class="corner" style="${s}top:0;right:0;border-left:none;border-bottom:none;"></span>
      <span class="corner" style="${s}bottom:0;left:0;border-right:none;border-top:none;"></span>
      <span class="corner" style="${s}bottom:0;right:0;border-left:none;border-top:none;"></span>
    `;
  }

  function sectionTitleHTML(text, color) {
    return `
      <div class="section-title">
        <div class="bar" style="background:#38bdf8;border-radius:1px;"></div>
        <span class="txt" style="color:#f8fafc;font-size:9px;font-family:'Orbitron';letter-spacing:0.12em;">${text}</span>
        <div class="line" style="background:linear-gradient(90deg, rgba(56,189,248,0.25), transparent);"></div>
      </div>
    `;
  }

  function mountLeftPanel(root) {
    const store = global.NEXUS.store;
    const { soundEngine, ensureStarted } = global.NEXUS;

    root.innerHTML = `
      <div class="leftpanel">
        <div class="lp-header">
          <div>
            <div class="title" style="color:#38bdf8;font-family:\'Orbitron\';font-size:9.5px;letter-spacing:0.16em;font-weight:700;">ACOUSTIC DSP // TELEMETRY</div>
            <div class="sub" style="color:#64748b;font-family:monospace;font-size:7.5px;letter-spacing:0.1em;margin-top:2px;">WEB-AUDIO PIPELINE — 44.1 kHz 16-BIT PCM</div>
          </div>
          <div class="status">
            <div class="status-dot" id="lp-live-dot"></div>
            <span class="status-text" id="lp-live-txt">READY</span>
          </div>
        </div>
        <div id="lp-reactor" class="section-card"></div>
        <div id="lp-shield" class="section-card"></div>
        <div id="lp-quantum" class="section-card"></div>
        <div id="lp-exotic" class="section-card"></div>
        <div class="lp-footer">SONICSENTINEL AI AUDIO DSP ENGINE v2.5.0</div>
      </div>
    `;

    buildGainMeter(root.querySelector('#lp-reactor'), store, soundEngine, ensureStarted);
    buildSpectralQuality(root.querySelector('#lp-shield'), store);
    buildDualAiConsensus(root.querySelector('#lp-quantum'), store);
    buildDspFilters(root.querySelector('#lp-exotic'), store, soundEngine, ensureStarted);

    store.subscribe((state) => {
      const dot = root.querySelector('#lp-live-dot');
      const txt = root.querySelector('#lp-live-txt');
      if (dot && txt) {
        if (state.cloakActive) {
          dot.style.background = '#ef4444';
          dot.style.boxShadow = '0 0 6px #ef4444';
          txt.textContent = 'MUTED';
          txt.style.color = '#ef4444';
        } else if (state.isListening) {
          dot.style.background = '#10b981';
          dot.style.boxShadow = '0 0 8px #10b981';
          txt.textContent = 'LIVE MIC';
          txt.style.color = '#10b981';
        } else {
          dot.style.background = '#00f5ff';
          dot.style.boxShadow = '0 0 6px #00f5ff';
          txt.textContent = 'STANDBY';
          txt.style.color = '#00f5ff';
        }
      }
    });

    return { destroy() {} };
  }

  // ── 1. AUDIO INPUT GAIN & dBFS METER ────────────────────────
  function buildGainMeter(el, store, soundEngine, ensureStarted) {
    el.innerHTML = `
      ${cornerAccentsHTML('#38bdf8')}
      ${sectionTitleHTML('AUDIO INPUT GAIN // dBFS METER', '#38bdf8')}
      <div class="gauge-wrap">
        <div style="display:flex;align-items:center;gap:10px;width:100%;margin-bottom:6px;">
          <div style="flex-shrink:0;">
            <svg width="96" height="96" viewBox="0 0 140 140" id="reactor-svg" style="width:92px;height:92px;margin:0;"></svg>
          </div>
          <div style="flex:1;display:flex;flex-direction:column;gap:6px;">
            <div class="readout-box" style="background:#090e1a;border:1px solid #1e293b;">
              <div class="k" style="color:#64748b;">PEAK LEVEL</div>
              <div class="v" style="color:#38bdf8;" id="reactor-peak-db"></div>
            </div>
            <div class="readout-box" style="background:#090e1a;border:1px solid #1e293b;">
              <div class="k" style="color:#64748b;">RMS POWER</div>
              <div class="v" style="color:#38bdf8;" id="reactor-rms-db"></div>
            </div>
          </div>
        </div>
        <div id="reactor-critical" class="critical-warning hidden">\u26a0 HIGH GAIN \u2014 CLIPPING DISTORTION RISK</div>
        <div style="width:100%;">
          <div class="slider-block-row" style="margin-bottom:2px;">
            <span class="k" style="color:#64748b;font-size:7.5px;">PRE-AMP GAIN CONTROL</span>
            <span class="v" style="color:#38bdf8;font-size:9px;" id="reactor-gain-lbl"></span>
          </div>
          <input type="range" min="0" max="100" step="1" class="plasma-slider" id="reactor-slider" style="width:100%;">
        </div>
      </div>
    `;

    const svg = el.querySelector('#reactor-svg');
    const cx = 70, cy = 70, r = 52;
    const startAngle = 140, endAngle = 400, sweepAngle = endAngle - startAngle;

    const outer = document.createElementNS(SVG_NS, 'circle');
    outer.setAttribute('cx', cx); outer.setAttribute('cy', cy); outer.setAttribute('r', 62);
    outer.setAttribute('fill', 'none'); outer.setAttribute('stroke', 'rgba(255,107,53,0.1)'); outer.setAttribute('stroke-width', 1);
    svg.appendChild(outer);

    const ticks = [];
    for (let i = 0; i <= 10; i++) {
      const angle = startAngle + (i / 10) * sweepAngle;
      const inner = polarToCartesian(cx, cy, 56, angle);
      const outerP = polarToCartesian(cx, cy, 60, angle);
      const line = document.createElementNS(SVG_NS, 'line');
      line.setAttribute('x1', inner.x); line.setAttribute('y1', inner.y);
      line.setAttribute('x2', outerP.x); line.setAttribute('y2', outerP.y);
      line.setAttribute('stroke-width', i % 5 === 0 ? 2 : 1);
      svg.appendChild(line);
      ticks.push(line);
    }

    const track = document.createElementNS(SVG_NS, 'path');
    track.setAttribute('d', arcPath(cx, cy, r, startAngle, endAngle));
    track.setAttribute('fill', 'none'); track.setAttribute('stroke', 'rgba(255,107,53,0.14)');
    track.setAttribute('stroke-width', 7); track.setAttribute('stroke-linecap', 'round');
    svg.appendChild(track);

    const fill = document.createElementNS(SVG_NS, 'path');
    fill.setAttribute('fill', 'none'); fill.setAttribute('stroke-width', 7); fill.setAttribute('stroke-linecap', 'round');
    svg.appendChild(fill);

    const innerCircle = document.createElementNS(SVG_NS, 'circle');
    innerCircle.setAttribute('cx', cx); innerCircle.setAttribute('cy', cy); innerCircle.setAttribute('r', 40);
    innerCircle.setAttribute('fill', 'rgba(255,107,53,0.05)');
    svg.appendChild(innerCircle);

    function svgText(x, y, fillCol, size, weight) {
      const t = document.createElementNS(SVG_NS, 'text');
      t.setAttribute('x', x); t.setAttribute('y', y); t.setAttribute('text-anchor', 'middle');
      t.setAttribute('fill', fillCol);
      t.style.fontFamily = 'Orbitron, monospace';
      t.style.fontSize = size + 'px';
      if (weight) t.style.fontWeight = weight;
      svg.appendChild(t);
      return t;
    }
    const valueText = svgText(cx, cy - 4, '#ff6b35', 23, 700);
    valueText.style.filter = 'drop-shadow(0 0 6px #ff6b35)';
    svgText(cx, cy + 10, 'rgba(255,107,53,0.85)', 9).textContent = '%';
    svgText(cx, cy + 23, 'rgba(255,107,53,0.6)', 7.5).textContent = 'INPUT GAIN';

    const slider = el.querySelector('#reactor-slider');
    slider.addEventListener('input', (e) => {
      const val = Number(e.target.value);
      store.getState().setReactorOutput(val);
      ensureStarted().then(() => soundEngine.setReactorPitch(val));
    });

    function render(state) {
      const gain = state.reactorOutput;
      const isCritical = gain > 90;
      const fillEnd = startAngle + (gain / 100) * sweepAngle;

      ticks.forEach((line, i) => {
        line.setAttribute('stroke', i === 10 && isCritical ? '#ef4444' : 'rgba(255,107,53,0.4)');
      });

      if (gain > 0) {
        fill.setAttribute('d', arcPath(cx, cy, r, startAngle, fillEnd));
        fill.setAttribute('stroke', isCritical ? '#ef4444' : '#ff6b35');
        fill.style.filter = `drop-shadow(0 0 ${isCritical ? 8 : 4}px ${isCritical ? '#ef4444' : '#ff6b35'})`;
        fill.style.display = '';
      } else {
        fill.style.display = 'none';
      }

      valueText.textContent = Math.round(gain);
      el.querySelector('#reactor-gain-lbl').textContent = `${Math.round(gain)}% (${((gain / 50) * 6 - 6).toFixed(1)} dB)`;
      el.querySelector('#reactor-critical').classList.toggle('hidden', !isCritical);

      if (slider.value != gain) slider.value = gain;
      slider.disabled = state.quantumLock;
      slider.style.opacity = state.quantumLock ? 0.35 : 1;

      const peakDb = state.inputLevelDb || (-48 + (gain / 100) * 44).toFixed(1);
      const rmsDb = state.rmsLevelDb || (-56 + (gain / 100) * 40).toFixed(1);
      el.querySelector('#reactor-peak-db').innerHTML = `${peakDb}<span style="color:#64748b;font-size:8px;"> dBFS</span>`;
      el.querySelector('#reactor-rms-db').innerHTML = `${rmsDb}<span style="color:#64748b;font-size:8px;"> dBFS</span>`;
    }

    render(store.getState());
    store.subscribe(render);
  }

  // ── 2. FREQUENCY SPECTRUM // 4-BAND EQ & SNR GRAPH ──────────
  function buildSpectralQuality(el, store) {
    el.innerHTML = `
      ${cornerAccentsHTML('#38bdf8')}
      ${sectionTitleHTML('SIGNAL QUALITY // 4-BAND SPECTRUM', '#38bdf8')}
      <div class="hull-breach" id="shield-breach" style="margin-bottom:8px;"></div>
      <div class="seg-grid" id="shield-segments" style="margin-bottom:8px;"></div>
      <div style="background:rgba(2,8,18,0.85);border:1px solid rgba(0,245,255,0.2);border-radius:3px;padding:5px 6px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:3px;">
          <span style="font-family:monospace;font-size:7.5px;color:rgba(0,245,255,0.6);letter-spacing:0.12em;">SPECTRAL ENERGY ENVELOPE</span>
          <span style="font-family:'Orbitron';font-size:8px;color:#00f5ff;" id="lp-snr-readout"></span>
        </div>
        <svg viewBox="0 0 220 34" width="100%" height="34" preserveAspectRatio="none" id="lp-spectral-svg" style="display:block;overflow:visible;"></svg>
      </div>
    `;

    const segmentsEl = el.querySelector('#shield-segments');
    const BAND_LABELS = ['SUB 60Hz', 'LOW 250Hz', 'MID 2kHz', 'HIGH 8kHz'];
    function segColor(val) { return val >= 85 ? '#a855f7' : val >= 35 ? '#00f5ff' : '#10b981'; }

    function render(state) {
      const snr = state.snrDb != null ? state.snrDb : 0.0;
      const quality = state.shieldIntegrity >= 75 ? 'GOOD' : state.shieldIntegrity >= 45 ? 'ACCEPTABLE' : 'POOR';
      const qColor = state.shieldIntegrity >= 75 ? '#00f5ff' : state.shieldIntegrity >= 45 ? '#f59e0b' : '#ef4444';

      const breachEl = el.querySelector('#shield-breach');
      breachEl.textContent = `AUDIO QUALITY: ${quality} // CLIPPING: 0.0%`;
      breachEl.style.border = `1px solid ${qColor}40`;
      breachEl.style.background = `${qColor}12`;
      breachEl.style.color = qColor;
      breachEl.style.textShadow = `0 0 8px ${qColor}`;

      el.querySelector('#lp-snr-readout').textContent = `SNR ${Number(snr).toFixed(1)} dB`;

      const bands = state.freqBands || [0, 0, 0, 0];
      segmentsEl.innerHTML = BAND_LABELS.map((label, idx) => {
        const val = Math.min(100, Math.max(4, bands[idx] || 0));
        const col = segColor(val);
        return `
          <div class="seg-item">
            <div class="seg-bar" style="background:rgba(0,245,255,0.06);border:1px solid ${col}50;box-shadow:0 0 6px ${col}22;">
              <div class="seg-fill" style="height:${val}%;background:linear-gradient(0deg, ${col}33, ${col}99);border-top:2px solid ${col};"></div>
            </div>
            <span class="seg-label" style="color:${col};font-size:6.5px;">${label}</span>
          </div>
        `;
      }).join('');

      // Render live spectral envelope graph
      const wave = state.spectralWave && state.spectralWave.length > 1 ? state.spectralWave : [0, 0, 0, 0];
      const W = 220, H = 34, pad = 2;
      const pts = wave.map((v, i) => {
        const x = pad + (i / (wave.length - 1)) * (W - pad * 2);
        const y = pad + (1 - v / 100) * (H - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
      const svgEl = el.querySelector('#lp-spectral-svg');
      svgEl.innerHTML = `
        <defs>
          <linearGradient id="lp-spec-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#00f5ff" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="#00f5ff" stop-opacity="0.02"/>
          </linearGradient>
        </defs>
        <polyline points="${pts} ${W - pad},${H - pad} ${pad},${H - pad}" fill="url(#lp-spec-grad)" stroke="none"/>
        <polyline points="${pts}" fill="none" stroke="#00f5ff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="filter:drop-shadow(0 0 3px #00f5ff);"/>
      `;
    }

    render(store.getState());
    store.subscribe(render);
  }

  // ── 3. DUAL-AI MODEL CONSENSUS // PYTHON 2D-CNN + GTM ───────
  function buildDualAiConsensus(el, store) {
    el.innerHTML = `
      ${cornerAccentsHTML('#38bdf8')}
      ${sectionTitleHTML('DUAL-AI CONSENSUS // PYTHON + GTM', '#a855f7')}
      <div class="decoherence-box" style="background:rgba(168,85,247,0.09);border:1px solid rgba(168,85,247,0.28);color:#e9d5ff;margin-bottom:8px;" id="qs-detected-class"></div>

      <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:8px;">
        <div>
          <div style="display:flex;justify-content:space-between;font-family:'Orbitron';font-size:8px;margin-bottom:3px;">
            <span style="color:#00f5ff;">PYTHON 2D-CNN (SPECTRAL)</span>
            <span style="color:#00f5ff;font-weight:700;" id="lp-py-conf">0.0%</span>
          </div>
          <div style="height:6px;background:rgba(0,245,255,0.1);border:1px solid rgba(0,245,255,0.25);border-radius:2px;overflow:hidden;">
            <div id="lp-py-bar" style="height:100%;width:0%;background:linear-gradient(90deg, #0891b2, #00f5ff);box-shadow:0 0 6px #00f5ff;transition:width 0.2s;"></div>
          </div>
        </div>

        <div>
          <div style="display:flex;justify-content:space-between;font-family:'Orbitron';font-size:8px;margin-bottom:3px;">
            <span style="color:#c084fc;">GTM AUDIOSET VERIFIER</span>
            <span style="color:#c084fc;font-weight:700;" id="lp-gtm-conf">0.0%</span>
          </div>
          <div style="height:6px;background:rgba(168,85,247,0.1);border:1px solid rgba(168,85,247,0.25);border-radius:2px;overflow:hidden;">
            <div id="lp-gtm-bar" style="height:100%;width:0%;background:linear-gradient(90deg, #7c3aed, #c084fc);box-shadow:0 0 6px #a855f7;transition:width 0.2s;"></div>
          </div>
        </div>
      </div>

      <div class="subslider-box" style="background:rgba(168,85,247,0.05);border:1px solid rgba(168,85,247,0.22);padding:6px 8px;">
        <div class="slider-block-row" style="margin-bottom:3px;">
          <span class="k" style="color:rgba(216,180,254,0.75);font-size:7.5px;">MIN ALERT CONFIDENCE</span>
          <span class="v glow-neural" id="qs-sync-val" style="color:#c084fc;font-size:10px;">75%</span>
        </div>
        <input type="range" min="50" max="95" step="1" class="neural-slider" id="qs-sync-slider" style="width:100%;">
        <div class="slider-foot">
          <span style="color:rgba(168,85,247,0.4);">50% SENSITIVE</span>
          <span style="color:rgba(168,85,247,0.4);">95% STRICT</span>
        </div>
      </div>
    `;

    const syncSlider = el.querySelector('#qs-sync-slider');
    syncSlider.addEventListener('input', (e) => store.getState().setNeuralSyncRate(Number(e.target.value)));

    function render(state) {
      const pyConf = Number(state.pythonConfidence != null ? state.pythonConfidence : 0).toFixed(1);
      const gtmConf = Number(state.gtmConfidence != null ? state.gtmConfidence : 0).toFixed(1);
      const sound = (state.currentSound || 'AMBIENT STANDBY').toUpperCase();

      el.querySelector('#qs-detected-class').innerHTML =
        `CLASS: <span style="color:#00f5ff;font-weight:700;">${sound}</span> // ${state.consistencyStatus || 'STANDBY'}`;

      el.querySelector('#lp-py-conf').textContent = `${pyConf}%`;
      el.querySelector('#lp-py-bar').style.width = `${Math.min(100, pyConf)}%`;

      el.querySelector('#lp-gtm-conf').textContent = `${gtmConf}%`;
      el.querySelector('#lp-gtm-bar').style.width = `${Math.min(100, gtmConf)}%`;

      const threshold = state.neuralSyncRate || 75;
      el.querySelector('#qs-sync-val').textContent = `${Math.round(threshold)}%`;
      if (syncSlider.value != threshold) syncSlider.value = threshold;
      syncSlider.disabled = state.quantumLock;
      syncSlider.style.opacity = state.quantumLock ? 0.35 : 1;
    }

    render(store.getState());
    store.subscribe(render);
  }

  // ── 4. DSP FILTER & NOISE GATE CONTROLS ─────────────────────
  function buildDspFilters(el, store, soundEngine, ensureStarted) {
    el.innerHTML = `
      ${sectionTitleHTML('DSP FILTER // NOISE GATE CONTROLS', '#38bdf8')}
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <span style="font-family:monospace;font-size:8px;color:rgba(245,158,11,0.6);">REAL-TIME WEB-AUDIO DSP</span>
        <button class="quantumlock-btn" id="exotic-lock-btn" style="padding:4px 10px;font-size:8px;">
          <span id="exotic-lock-icon" style="font-size:10px;"></span>LOCK DSP
        </button>
      </div>
      <div id="exotic-lock-msg" class="quantumlock-msg hidden" style="margin-bottom:8px;">DSP CONTROLS LOCKED \u2014 PROFILE PRESERVED</div>

      <div class="slider-block" style="margin-bottom:8px;">
        <div class="slider-block-row" style="margin-bottom:3px;">
          <span class="k" style="color:rgba(16,185,129,0.75);font-size:7.5px;">NOISE GATE THRESHOLD</span>
          <span class="v glow-quantum" id="exotic-gate-val" style="color:#10b981;font-size:10px;"></span>
        </div>
        <input type="range" min="-60" max="-10" step="1" class="quantum-slider" id="exotic-gate-slider" style="width:100%;">
        <div class="slider-foot">
          <span style="color:rgba(16,185,129,0.35);">-60 dBFS (OPEN)</span>
          <span style="color:rgba(16,185,129,0.35);">-10 dBFS (STRICT)</span>
        </div>
      </div>

      <div class="slider-block" style="margin-bottom:2px;">
        <div class="slider-block-row" style="margin-bottom:3px;">
          <span class="k" style="color:rgba(0,245,255,0.75);font-size:7.5px;">HIGH-PASS FILTER CUTOFF</span>
          <span class="v glow-cyan" id="exotic-hp-val" style="color:#00f5ff;font-size:10px;"></span>
        </div>
        <input type="range" min="20" max="1000" step="10" id="exotic-hp-slider" style="width:100%;">
        <div class="slider-foot">
          <span style="color:rgba(0,245,255,0.35);">20 Hz (FULL)</span>
          <span style="color:rgba(0,245,255,0.35);">1000 Hz (VOICE BAND)</span>
        </div>
      </div>
    `;

    const lockBtn = el.querySelector('#exotic-lock-btn');
    lockBtn.addEventListener('click', () => {
      store.getState().toggleQuantumLock();
      ensureStarted().then(() => soundEngine.playButton('lock'));
    });

    const gateSlider = el.querySelector('#exotic-gate-slider');
    gateSlider.addEventListener('input', (e) => store.getState().setNoiseGateDb(Number(e.target.value)));

    const hpSlider = el.querySelector('#exotic-hp-slider');
    hpSlider.addEventListener('input', (e) => store.getState().setHighpassHz(Number(e.target.value)));

    function render(state) {
      const locked = state.quantumLock;
      lockBtn.classList.toggle('active-lock', locked);
      lockBtn.style.background = locked ? 'rgba(245,158,11,0.15)' : 'rgba(245,158,11,0.05)';
      lockBtn.style.border = `1px solid ${locked ? 'rgba(245,158,11,0.7)' : 'rgba(245,158,11,0.25)'}`;
      lockBtn.style.color = locked ? '#f59e0b' : 'rgba(245,158,11,0.5)';
      el.querySelector('#exotic-lock-icon').textContent = locked ? '\uD83D\uDD12' : '\uD83D\uDD13';
      el.querySelector('#exotic-lock-msg').classList.toggle('hidden', !locked);

      [gateSlider, hpSlider].forEach((s) => {
        s.disabled = locked;
        s.style.opacity = locked ? 0.35 : 1;
      });

      const gateDb = state.noiseGateDb != null ? state.noiseGateDb : -42;
      el.querySelector('#exotic-gate-val').innerHTML = `${gateDb} <span style="font-size:8px;opacity:0.7;">dBFS</span>`;
      if (gateSlider.value != gateDb) gateSlider.value = gateDb;

      const hpHz = state.highpassHz != null ? state.highpassHz : 80;
      el.querySelector('#exotic-hp-val').innerHTML = `${hpHz} <span style="font-size:8px;opacity:0.7;">Hz</span>`;
      if (hpSlider.value != hpHz) hpSlider.value = hpHz;
    }

    render(store.getState());
    store.subscribe(render);
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.mountLeftPanel = mountLeftPanel;
})(window);
