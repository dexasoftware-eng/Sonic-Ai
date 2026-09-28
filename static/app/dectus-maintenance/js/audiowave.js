/* ============================================================
   audiowave.js — SonicSentinel AI MAINTENANCE COMMAND CENTER
   Dual-Channel Engineering Diagnostics Visualizer:
   - Left: Live Scrolling Thermal Waterfall Spectrogram + Harmonic Cursors (f0, 2f0, 3f0)
   - Right: X-Y Acoustic Phase Lissajous Orbit & Vibration Crest Scope
   ============================================================ */
(function (global) {
  'use strict';

  function mountAudioWave(container, getProps) {
    if (!container) return { destroy() {} };

    container.innerHTML = '';
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;';
    container.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    let width = 0, height = 0;
    let raf = null;

    // Waterfall spectrogram buffer (columns of 32 frequency bins)
    const WF_COLS = 72;
    const WF_BINS = 28;
    const waterfall = Array.from({ length: WF_COLS }, () => Array.from({ length: WF_BINS }, () => 0.1));

    function resize() {
      const rect = container.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(10, rect.width);
      height = Math.max(10, rect.height);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
    }
    resize();
    window.addEventListener('resize', resize);
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
    if (ro) ro.observe(container);

    let timeData = null;
    let freqData = null;
    let timeSec = 0;
    let frameCount = 0;

    function thermalColor(val, sev, passesGate) {
      const v = Math.max(0, Math.min(1, val));
      if (passesGate && sev === 'critical') {
        const r = Math.round(60 + v * 195);
        const g = Math.round(10 + Math.pow(v, 2) * 140);
        const b = Math.round(20 + (1 - v) * 30);
        return `rgba(${r},${g},${b},${(0.18 + v * 0.78).toFixed(2)})`;
      }
      // Industrial Amber / Cyan / Thermal spectrum
      if (v < 0.35) {
        const t = v / 0.35;
        return `rgba(${Math.round(8 + t * 20)}, ${Math.round(45 + t * 110)}, ${Math.round(90 + t * 110)}, ${(0.18 + t * 0.3).toFixed(2)})`;
      }
      if (v < 0.7) {
        const t = (v - 0.35) / 0.35;
        return `rgba(${Math.round(28 + t * 217)}, ${Math.round(155 + t * 30)}, ${Math.round(200 - t * 180)}, ${(0.48 + t * 0.25).toFixed(2)})`;
      }
      const t = (v - 0.7) / 0.3;
      return `rgba(255, ${Math.round(185 - t * 115)}, ${Math.round(20 + t * 40)}, ${(0.75 + t * 0.22).toFixed(2)})`;
    }

    function render(timestamp) {
      timeSec = timestamp * 0.001;
      frameCount++;
      const props = getProps ? getProps() : {};
      const isListening = !!(props.isListening || (global.NEXUS && global.NEXUS.audioAnalyser));
      const analyser = global.NEXUS ? global.NEXUS.audioAnalyser : null;

      if (analyser) {
        if (!timeData || timeData.length !== analyser.fftSize) {
          timeData = new Uint8Array(analyser.fftSize);
        }
        if (!freqData || freqData.length !== analyser.frequencyBinCount) {
          freqData = new Uint8Array(analyser.frequencyBinCount);
        }
        analyser.getByteTimeDomainData(timeData);
        analyser.getByteFrequencyData(freqData);
      }

      ctx.clearRect(0, 0, width, height);

      const sev = String(props.severity || 'Low').toLowerCase();
      const minConf = Number(props.neuralSyncRate != null ? props.neuralSyncRate : 75);
      const effConf = Math.max(Number(props.warpCharge || 0), Number(props.pythonConfidence || 0));
      const passesGate = props.passesAlertGate != null ? !!props.passesAlertGate : (effConf >= minConf);

      // Maintenance Engineering Palette (Amber/Gold default -> Orange High -> Crimson Critical)
      let primaryCol = '#f59e0b';
      let secondaryCol = '#00f5ff';
      let accentRgba = 'rgba(245, 158, 11, ';
      if (passesGate && sev === 'critical') {
        primaryCol = '#ef4444';
        secondaryCol = '#f97316';
        accentRgba = 'rgba(239, 68, 68, ';
      } else if (passesGate && sev === 'high') {
        primaryCol = '#ff6b35';
        secondaryCol = '#fbbf24';
        accentRgba = 'rgba(255, 107, 53, ';
      }

      // Push new column into waterfall every 2 frames
      if (frameCount % 2 === 0) {
        const newCol = [];
        for (let b = 0; b < WF_BINS; b++) {
          if (freqData && freqData.length > 0) {
            const idx = Math.floor((b / WF_BINS) * Math.min(96, freqData.length));
            newCol.push(freqData[idx] / 255);
          } else {
            const baseScale = passesGate && (sev === 'critical' || sev === 'high') ? 0.85 : 0.48;
            const h1 = Math.exp(-Math.pow((b - 7 - Math.sin(timeSec * 1.4) * 2) / 3.2, 2));
            const h2 = Math.exp(-Math.pow((b - 15 - Math.cos(timeSec * 1.9) * 2) / 4.0, 2)) * 0.75;
            const h3 = Math.exp(-Math.pow((b - 22) / 3.5, 2)) * 0.45;
            const noise = (Math.sin(timeSec * 7.1 + b * 1.7) * 0.5 + 0.5) * 0.15;
            newCol.push(Math.min(1, (h1 + h2 + h3 + noise) * baseScale));
          }
        }
        waterfall.push(newCol);
        if (waterfall.length > WF_COLS) waterfall.shift();
      }

      // Background engineering grid
      ctx.save();
      ctx.strokeStyle = accentRgba + '0.07)';
      ctx.lineWidth = 1;
      for (let x = 0; x < width; x += 28) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
      }
      for (let y = 0; y < height; y += 28) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
      }
      ctx.restore();

      // ── 1. LEFT PANEL: LIVE SCROLLING THERMAL WATERFALL SPECTROGRAM + HARMONIC CURSORS ──
      const wfLeft = 38;
      const wfTop = 28;
      const wfW = Math.max(80, width * 0.54 - wfLeft);
      const wfH = Math.max(50, height - 52);
      const cellW = wfW / WF_COLS;
      const cellH = wfH / WF_BINS;

      ctx.save();
      ctx.fillStyle = 'rgba(4, 9, 18, 0.75)';
      ctx.fillRect(wfLeft, wfTop, wfW, wfH);

      for (let c = 0; c < waterfall.length; c++) {
        const col = waterfall[c];
        const x = wfLeft + c * cellW;
        for (let b = 0; b < WF_BINS; b++) {
          const y = wfTop + (WF_BINS - 1 - b) * cellH;
          ctx.fillStyle = thermalColor(col[b], sev, passesGate);
          ctx.fillRect(x, y, Math.ceil(cellW), Math.ceil(cellH));
        }
      }

      // Harmonic Cursor Lines (f0 Fundamental, 2f0 2nd Harmonic, 3f0 3rd Harmonic)
      const peakKhz = Number(props.tachyonFrequency || 1.25);
      const f0Y = wfTop + wfH * 0.72;
      const f1Y = wfTop + wfH * 0.45;
      const f2Y = wfTop + wfH * 0.20;
      const harmonics = [
        { y: f0Y, lbl: `f0 ${(peakKhz).toFixed(2)}kHz`, col: primaryCol },
        { y: f1Y, lbl: `2f0 ${(peakKhz * 2).toFixed(2)}kHz`, col: secondaryCol },
        { y: f2Y, lbl: `3f0 ${(peakKhz * 3).toFixed(2)}kHz`, col: '#a855f7' },
      ];
      harmonics.forEach((h) => {
        ctx.strokeStyle = h.col + 'aa';
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(wfLeft, h.y);
        ctx.lineTo(wfLeft + wfW, h.y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = h.col;
        ctx.font = '700 7px monospace';
        ctx.fillText(h.lbl, wfLeft + 5, h.y - 3);
      });

      // Waterfall border & frequency axis labels
      ctx.strokeStyle = accentRgba + '0.4)';
      ctx.lineWidth = 1.2;
      ctx.strokeRect(wfLeft, wfTop, wfW, wfH);

      ctx.fillStyle = accentRgba + '0.75)';
      ctx.font = '7px monospace';
      ctx.textAlign = 'right';
      ctx.fillText('8kHz', wfLeft - 4, wfTop + 8);
      ctx.fillText('4kHz', wfLeft - 4, wfTop + wfH * 0.35);
      ctx.fillText('1kHz', wfLeft - 4, wfTop + wfH * 0.68);
      ctx.fillText('60Hz', wfLeft - 4, wfTop + wfH - 2);
      ctx.textAlign = 'left';
      ctx.font = '700 8px "Orbitron", monospace';
      ctx.fillStyle = primaryCol;
      ctx.fillText('THERMAL SPECTROGRAM WATERFALL // HARMONIC TRACKER', wfLeft + 6, wfTop + 11);
      ctx.restore();

      // ── 2. RIGHT PANEL: X-Y PHASE LISSAJOUS & VIBRATION VECTOR SCOPE ──
      const rightStart = wfLeft + wfW + 16;
      const rightW = Math.max(60, width - rightStart - 14);
      const scopeCx = rightStart + rightW * 0.5;
      const scopeCy = wfTop + wfH * 0.48;
      const scopeR = Math.max(28, Math.min(rightW * 0.38, wfH * 0.36));

      ctx.save();
      // Box around Phase Scope
      ctx.fillStyle = 'rgba(4, 9, 18, 0.65)';
      ctx.strokeStyle = accentRgba + '0.32)';
      ctx.lineWidth = 1;
      ctx.fillRect(rightStart, wfTop, rightW, wfH);
      ctx.strokeRect(rightStart, wfTop, rightW, wfH);

      ctx.fillStyle = primaryCol;
      ctx.font = '700 8px "Orbitron", monospace';
      ctx.fillText('PHASE LISSAJOUS // VIBRATION SCOPE', rightStart + 8, wfTop + 12);

      // Reticle circles & axes
      ctx.strokeStyle = accentRgba + '0.2)';
      ctx.beginPath();
      ctx.arc(scopeCx, scopeCy, scopeR, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(scopeCx, scopeCy, scopeR * 0.55, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(scopeCx - scopeR - 6, scopeCy);
      ctx.lineTo(scopeCx + scopeR + 6, scopeCy);
      ctx.moveTo(scopeCx, scopeCy - scopeR - 6);
      ctx.lineTo(scopeCx, scopeCy + scopeR + 6);
      ctx.stroke();

      // Lissajous X-Y Phase Curve (driven by timeData or harmonic synthesis)
      ctx.beginPath();
      const lissSteps = 110;
      for (let i = 0; i < lissSteps; i++) {
        let xNorm = 0, yNorm = 0;
        if (timeData && timeData.length > 32) {
          const idx1 = Math.floor((i / lissSteps) * (timeData.length - 16));
          const idx2 = idx1 + 12;
          xNorm = ((timeData[idx1] - 128) / 128) * 1.15;
          yNorm = ((timeData[idx2] - 128) / 128) * 1.15;
        } else {
          const t = (i / lissSteps) * Math.PI * 2;
          const jitter = passesGate && (sev === 'critical' || sev === 'high') ? 0.92 : 0.65;
          xNorm = Math.sin(3 * t + timeSec * 2.4) * jitter;
          yNorm = Math.sin(2 * t + timeSec * 1.7 + 0.6) * jitter;
        }
        const px = scopeCx + xNorm * scopeR * 0.88;
        const py = scopeCy + yNorm * scopeR * 0.88;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = primaryCol;
      ctx.lineWidth = 1.8;
      ctx.shadowColor = primaryCol;
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Engineering Diagnostic Readouts at bottom of right scope
      const snrVal = Number(props.snrDb || 0).toFixed(1);
      const qPct = Math.round(Number(props.shieldIntegrity || 98));
      const crest = (3.2 + (effConf / 100) * 4.8).toFixed(1);
      const diagY = wfTop + wfH - 10;
      ctx.font = '700 7.5px monospace';
      ctx.fillStyle = secondaryCol;
      ctx.fillText(`SNR: ${snrVal} dB`, rightStart + 8, diagY);
      ctx.fillStyle = primaryCol;
      ctx.fillText(`CREST: ${crest} dB`, rightStart + rightW * 0.38, diagY);
      ctx.fillStyle = qPct >= 70 ? '#10b981' : '#ef4444';
      ctx.fillText(`INTEGRITY: ${qPct}%`, rightStart + rightW * 0.68, diagY);
      ctx.restore();

      // ── 3. TOP & BOTTOM DIAGNOSTIC HUD OVERLAY ───────────────
      ctx.save();
      ctx.font = '700 9px "Orbitron", monospace';
      const curClass = (props.currentSound || 'AMBIENT STANDBY').toUpperCase();
      const statusTitle = passesGate && (sev === 'critical' || sev === 'high')
        ? `▲ DIAGNOSTIC FAULT [${sev.toUpperCase()}] // ${curClass} (${Math.round(effConf)}%)`
        : isListening
          ? '● LIVE ACOUSTIC & VIBRATION DIAGNOSTICS // 16 kHz PCM'
          : `◉ DIAGNOSTIC ANALYZER READY // ${curClass}`;
      ctx.fillStyle = primaryCol;
      ctx.shadowColor = primaryCol;
      ctx.shadowBlur = 6;
      ctx.fillText(statusTitle, 14, 16);
      ctx.shadowBlur = 0;

      ctx.font = '8px monospace';
      ctx.fillStyle = primaryCol + 'dd';
      const peakFreq = Number(props.tachyonFrequency || 0).toFixed(2) + ' kHz';
      const snr = Number(props.snrDb || 0).toFixed(1) + ' dB';
      const lat = props.dbLatencyMs ? `${props.dbLatencyMs}ms` : 'READY';
      const rightText = `HARMONIC f0: ${peakFreq}  |  SNR: ${snr}  |  PING: ${lat}`;
      ctx.fillText(rightText, width - ctx.measureText(rightText).width - 14, 16);

      ctx.fillStyle = primaryCol + '88';
      ctx.fillText('ACOUSTIC SPECTROGRAM & PHASE ANALYZER // DUAL-AI ENGINE', 14, height - 6);
      const gateTxt = `FAULT GATE: ${Math.round(minConf)}% // SEVERITY: ${sev.toUpperCase()}`;
      ctx.fillText(gateTxt, width - ctx.measureText(gateTxt).width - 14, height - 6);
      ctx.restore();

      raf = requestAnimationFrame(render);
    }

    raf = requestAnimationFrame(render);

    return {
      destroy() {
        window.removeEventListener('resize', resize);
        if (ro) ro.disconnect();
        if (raf) cancelAnimationFrame(raf);
      },
    };
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.mountAudioWave = mountAudioWave;
})(window);
