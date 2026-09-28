/* ============================================================
   audiowave.js — Dectus AI Real-Time Acoustic Waveform & Spectrum Visualizer
   Replaces the 3D quantum core with a responsive, multi-layered
   live audio oscilloscope, frequency spectrum bars, and HUD readouts.
   Reacts in real time to microphone input from global.NEXUS.audioAnalyser.
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

    // Particles for floating acoustic dust
    const PARTICLE_COUNT = 36;
    const particles = Array.from({ length: PARTICLE_COUNT }, () => ({
      x: Math.random(),
      y: Math.random(),
      vx: (Math.random() - 0.5) * 0.0008 + 0.0003,
      vy: (Math.random() - 0.5) * 0.0006,
      size: 1 + Math.random() * 2,
      color: Math.random() > 0.4 ? 'rgba(0, 245, 255, ' : 'rgba(168, 85, 247, ',
      alpha: 0.2 + Math.random() * 0.6,
    }));

    // Data buffers for Web Audio API
    let timeData = null;
    let freqData = null;

    let timeSec = 0;

    function render(timestamp) {
      timeSec = timestamp * 0.001;
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

      // Determine active severity theme (respecting MIN ALERT CONFIDENCE gate)
      const sev = String(props.severity || 'Low').toLowerCase();
      const minConf = Number(props.neuralSyncRate != null ? props.neuralSyncRate : 75);
      const effConf = Math.max(Number(props.warpCharge || 0), Number(props.pythonConfidence || 0));
      const passesGate = props.passesAlertGate != null ? !!props.passesAlertGate : (effConf >= minConf);

      let primaryCol = '#00f5ff';
      let secondaryCol = '#a855f7';
      let barStop0 = 'rgba(16, 185, 129, 0.08)';
      let barStop1 = 'rgba(0, 245, 255, 0.35)';
      let barStop2 = 'rgba(168, 85, 247, 0.7)';
      let bgTint = null;

      if (passesGate && sev === 'critical') {
        primaryCol = '#ef4444';
        secondaryCol = '#f97316';
        barStop0 = 'rgba(239, 68, 68, 0.15)';
        barStop1 = 'rgba(249, 115, 22, 0.55)';
        barStop2 = 'rgba(239, 68, 68, 0.9)';
        bgTint = 'rgba(239, 68, 68, 0.14)';
      } else if (passesGate && sev === 'high') {
        primaryCol = '#f59e0b';
        secondaryCol = '#ff6b35';
        barStop0 = 'rgba(245, 158, 11, 0.12)';
        barStop1 = 'rgba(245, 158, 11, 0.5)';
        barStop2 = 'rgba(255, 107, 53, 0.85)';
        bgTint = 'rgba(245, 158, 11, 0.10)';
      } else if (passesGate && sev === 'medium') {
        primaryCol = '#eab308';
        secondaryCol = '#00f5ff';
        barStop0 = 'rgba(234, 179, 8, 0.10)';
        barStop1 = 'rgba(234, 179, 8, 0.42)';
        barStop2 = 'rgba(0, 245, 255, 0.75)';
        bgTint = 'rgba(234, 179, 8, 0.06)';
      }

      if (bgTint) {
        ctx.save();
        const radGrad = ctx.createRadialGradient(width * 0.5, height * 0.5, 10, width * 0.5, height * 0.5, Math.max(width, height) * 0.65);
        radGrad.addColorStop(0, bgTint);
        radGrad.addColorStop(1, 'rgba(2, 7, 18, 0)');
        ctx.fillStyle = radGrad;
        ctx.fillRect(0, 0, width, height);
        ctx.restore();
      }

      // ── 1. BACKGROUND GRID & RADAR CROSSHAIRS ──────────────
      ctx.save();
      ctx.strokeStyle = passesGate && (sev === 'critical' || sev === 'high')
        ? (sev === 'critical' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.09)')
        : 'rgba(0, 245, 255, 0.06)';
      ctx.lineWidth = 1;
      const gridStep = 32;
      for (let x = 0; x < width; x += gridStep) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
      for (let y = 0; y < height; y += gridStep) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      // Center baseline
      const centerY = height * 0.52;
      ctx.strokeStyle = primaryCol + '40';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(width, centerY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Decibel Scale Markers (Left margin)
      ctx.fillStyle = primaryCol + '66';
      ctx.font = '8px monospace';
      ctx.fillText('+12dB', 6, centerY - 45);
      ctx.fillText('  0dB', 6, centerY - 2);
      ctx.fillText('-12dB', 6, centerY + 45);
      ctx.restore();

      // ── 2. FLOATING ACOUSTIC PARTICLES ─────────────────────
      ctx.save();
      for (let p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = 1;
        if (p.x > 1) p.x = 0;
        if (p.y < 0) p.y = 1;
        if (p.y > 1) p.y = 0;

        const px = p.x * width;
        const py = p.y * height;
        ctx.fillStyle = p.color + p.alpha + ')';
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();

      // ── 3. LIVE SPECTRUM FREQUENCY BARS ────────────────────
      const barCount = 64;
      const barWidth = (width - 40) / barCount;
      const startX = 20;

      ctx.save();
      for (let i = 0; i < barCount; i++) {
        let barNorm = 0;
        if (freqData && freqData.length > 0) {
          const idx = Math.floor((i / barCount) * Math.min(freqData.length, 128));
          barNorm = freqData[idx] / 255;
        } else {
          const wave1 = Math.sin(timeSec * 2.5 + i * 0.18);
          const wave2 = Math.cos(timeSec * 1.2 - i * 0.08);
          barNorm = Math.max(0.04, (wave1 * 0.4 + wave2 * 0.3 + 0.35) * 0.45);
        }

        const barHeight = Math.max(3, barNorm * (height * 0.65));
        const bx = startX + i * barWidth;
        const by = height - 12 - barHeight;

        const grad = ctx.createLinearGradient(0, height - 12, 0, by);
        grad.addColorStop(0, barStop0);
        grad.addColorStop(0.5, barStop1);
        grad.addColorStop(1, barStop2);

        ctx.fillStyle = grad;
        ctx.fillRect(bx + 1, by, barWidth - 2, barHeight);

        if (barHeight > 6) {
          ctx.fillStyle = primaryCol;
          ctx.shadowColor = primaryCol;
          ctx.shadowBlur = 6;
          ctx.fillRect(bx + 1, by, barWidth - 2, 2);
          ctx.shadowBlur = 0;
        }
      }
      ctx.restore();

      // ── 4. OSCILLOSCOPE TIME-DOMAIN WAVEFORM ───────────────
      ctx.save();
      const points = [];
      const wavePointsCount = 120;

      for (let i = 0; i < wavePointsCount; i++) {
        const x = (i / (wavePointsCount - 1)) * width;
        let y = centerY;

        if (timeData && timeData.length > 0) {
          const sampleIdx = Math.floor((i / wavePointsCount) * timeData.length);
          const val = (timeData[sampleIdx] - 128) / 128; // -1 to +1
          y = centerY + val * (height * 0.42);
        } else {
          const ampScale = passesGate && (sev === 'critical' || sev === 'high') ? 1.35 : 0.75;
          const s1 = Math.sin(i * 0.09 + timeSec * 3.5) * 14 * ampScale;
          const s2 = Math.sin(i * 0.04 - timeSec * 2.1) * 8 * ampScale;
          const s3 = Math.cos(i * 0.16 + timeSec * 4.2) * 5 * ampScale;
          y = centerY + s1 + s2 + s3;
        }
        points.push({ x, y });
      }

      // Fill underneath main waveform
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      for (let p of points) ctx.lineTo(p.x, p.y);
      ctx.lineTo(width, centerY);
      ctx.closePath();
      const waveGrad = ctx.createLinearGradient(0, centerY - 30, 0, centerY + 30);
      waveGrad.addColorStop(0, primaryCol + '38');
      waveGrad.addColorStop(1, primaryCol + '00');
      ctx.fillStyle = waveGrad;
      ctx.fill();

      // Secondary Ribbon (Phase-shifted)
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        const px = points[i].x;
        const py = centerY + (points[i].y - centerY) * 0.7 + Math.sin(i * 0.12 + timeSec * 2.8) * 8;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = secondaryCol + 'a6';
      ctx.lineWidth = 1.4;
      ctx.shadowColor = secondaryCol;
      ctx.shadowBlur = 8;
      ctx.stroke();

      // Primary Glow Waveform
      ctx.beginPath();
      for (let i = 0; i < points.length; i++) {
        if (i === 0) ctx.moveTo(points[i].x, points[i].y);
        else ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.strokeStyle = primaryCol;
      ctx.lineWidth = 2.2;
      ctx.shadowColor = primaryCol;
      ctx.shadowBlur = 12;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Scanning Reticle Cursor
      const scanX = ((timeSec * 160) % (width + 60)) - 30;
      if (scanX >= 0 && scanX <= width) {
        ctx.strokeStyle = primaryCol + '99';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(scanX, 0);
        ctx.lineTo(scanX, height);
        ctx.stroke();

        ctx.fillStyle = primaryCol;
        ctx.shadowColor = primaryCol;
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(scanX, centerY, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
      ctx.restore();

      // ── 5. HUD READOUTS OVERLAY ────────────────────────────
      ctx.save();
      ctx.font = '700 9px "Orbitron", monospace';
      const hudCol = passesGate && (sev === 'critical' || sev === 'high')
        ? primaryCol
        : (isListening ? '#10b981' : '#00f5ff');
      ctx.fillStyle = hudCol;
      ctx.shadowColor = hudCol;
      ctx.shadowBlur = 6;
      const curClass = (props.currentSound || 'AMBIENT STANDBY').toUpperCase();
      const statusTitle = passesGate && (sev === 'critical' || sev === 'high')
        ? `▲ ${sev.toUpperCase()} SEVERITY // ${curClass} (${Math.round(effConf)}%)`
        : isListening
          ? '● LIVE ACOUSTIC MONITORING // 16 kHz PCM STREAM'
          : `◉ MONITOR READY // ${curClass}`;
      ctx.fillText(statusTitle, 16, 16);
      ctx.shadowBlur = 0;

      ctx.font = '8px monospace';
      ctx.fillStyle = primaryCol + 'cc';
      const peakFreq = Number(props.tachyonFrequency || 0).toFixed(2) + ' kHz';
      const snr = Number(props.snrDb || 0).toFixed(1) + ' dB';
      const lat = props.dbLatencyMs ? `${props.dbLatencyMs}ms` : 'READY';
      const rightText = `PEAK FREQ: ${peakFreq}  |  SNR: ${snr}  |  PING: ${lat}`;
      const rightTextWidth = ctx.measureText(rightText).width;
      ctx.fillText(rightText, width - rightTextWidth - 16, 16);

      ctx.fillStyle = primaryCol + '75';
      ctx.fillText('DUAL-AI INFERENCE ENGINE // PYTHON 2D-CNN + GTM TMv2', 16, height - 6);
      const bufferText = `MIN ALERT GATE: ${Math.round(minConf)}% // SEVERITY: ${sev.toUpperCase()}`;
      const bufWidth = ctx.measureText(bufferText).width;
      ctx.fillText(bufferText, width - bufWidth - 16, height - 6);
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
