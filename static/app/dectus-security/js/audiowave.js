/* ============================================================
   audiowave.js — SonicSentinel AI SECURITY COMMAND CENTER
   Tactical 360° Perimeter Acoustic Radar + Ballistic Impulse Scope
   + Directional Threat Vector & Frequency Band Analyzer
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

    let timeData = null;
    let freqData = null;
    let timeSec = 0;

    // Persistent impulse history for right-hand ballistic scope
    const impulseHistory = Array.from({ length: 90 }, () => 0.08);

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

      const sev = String(props.severity || 'Low').toLowerCase();
      const minConf = Number(props.neuralSyncRate != null ? props.neuralSyncRate : 75);
      const effConf = Math.max(Number(props.warpCharge || 0), Number(props.pythonConfidence || 0));
      const passesGate = props.passesAlertGate != null ? !!props.passesAlertGate : (effConf >= minConf);

      // Security Tactical Color Palette (Emerald Radar default -> Amber High -> Crimson Critical)
      let primaryCol = '#10b981';
      let secondaryCol = '#38bdf8';
      let accentRgba = 'rgba(16, 185, 129, ';
      let bgTint = 'rgba(16, 185, 129, 0.05)';

      if (passesGate && sev === 'critical') {
        primaryCol = '#ef4444';
        secondaryCol = '#f97316';
        accentRgba = 'rgba(239, 68, 68, ';
        bgTint = 'rgba(239, 68, 68, 0.15)';
      } else if (passesGate && sev === 'high') {
        primaryCol = '#f59e0b';
        secondaryCol = '#ef4444';
        accentRgba = 'rgba(245, 158, 11, ';
        bgTint = 'rgba(245, 158, 11, 0.12)';
      } else if (passesGate && sev === 'medium') {
        primaryCol = '#eab308';
        secondaryCol = '#10b981';
        accentRgba = 'rgba(234, 179, 8, ';
        bgTint = 'rgba(234, 179, 8, 0.08)';
      }

      // Tactical background grid
      ctx.save();
      const radGrad = ctx.createRadialGradient(width * 0.27, height * 0.52, 5, width * 0.27, height * 0.52, Math.max(width, height) * 0.55);
      radGrad.addColorStop(0, bgTint);
      radGrad.addColorStop(1, 'rgba(2, 8, 14, 0)');
      ctx.fillStyle = radGrad;
      ctx.fillRect(0, 0, width, height);

      ctx.strokeStyle = accentRgba + '0.07)';
      ctx.lineWidth = 1;
      for (let x = 0; x < width; x += 28) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
      }
      for (let y = 0; y < height; y += 28) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
      }
      ctx.restore();

      // Split layout: Left 48% = 360° Perimeter Acoustic Radar, Right 52% = Ballistic Impulse & Threat Vector Scope
      const radarCx = Math.min(width * 0.25, height * 0.52 + 20);
      const radarCy = height * 0.53;
      const maxR = Math.max(36, Math.min(width * 0.20, height * 0.37));

      // ── 1. 360° PERIMETER ACOUSTIC RADAR (LEFT) ──────────────
      ctx.save();
      // Concentric range rings
      const rings = [0.28, 0.55, 0.80, 1.0];
      rings.forEach((ratio, idx) => {
        ctx.beginPath();
        ctx.arc(radarCx, radarCy, maxR * ratio, 0, Math.PI * 2);
        ctx.strokeStyle = accentRgba + (idx === 3 ? '0.45)' : '0.18)');
        ctx.lineWidth = idx === 3 ? 1.5 : 1;
        ctx.stroke();
      });

      // Crosshairs & diagonal sector lines
      for (let a = 0; a < Math.PI; a += Math.PI / 4) {
        ctx.beginPath();
        ctx.moveTo(radarCx - Math.cos(a) * maxR, radarCy - Math.sin(a) * maxR);
        ctx.lineTo(radarCx + Math.cos(a) * maxR, radarCy + Math.sin(a) * maxR);
        ctx.strokeStyle = accentRgba + '0.15)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Compass / Sector degree labels
      ctx.fillStyle = accentRgba + '0.7)';
      ctx.font = '700 7.5px "Orbitron", monospace';
      ctx.textAlign = 'center';
      ctx.fillText('N 000°', radarCx, radarCy - maxR - 5);
      ctx.fillText('S 180°', radarCx, radarCy + maxR + 11);
      ctx.textAlign = 'left';
      ctx.fillText('E 090°', radarCx + maxR + 5, radarCy + 3);
      ctx.textAlign = 'right';
      ctx.fillText('W 270°', radarCx - maxR - 5, radarCy + 3);

      // Circular Polar Acoustic Spectrum Spikes around radar perimeter
      const spokeCount = 48;
      for (let i = 0; i < spokeCount; i++) {
        const angle = (i / spokeCount) * Math.PI * 2 - Math.PI / 2;
        let mag = 0;
        if (freqData && freqData.length > 0) {
          const bin = Math.floor((i / spokeCount) * Math.min(64, freqData.length));
          mag = (freqData[bin] / 255) * 0.35;
        } else {
          const pulse = passesGate && (sev === 'critical' || sev === 'high') ? 0.24 : 0.10;
          mag = (Math.sin(timeSec * 3.2 + i * 0.45) * 0.5 + 0.5) * pulse;
        }
        const rInner = maxR * 0.80;
        const rOuter = maxR * (0.80 + mag);
        ctx.beginPath();
        ctx.moveTo(radarCx + Math.cos(angle) * rInner, radarCy + Math.sin(angle) * rInner);
        ctx.lineTo(radarCx + Math.cos(angle) * rOuter, radarCy + Math.sin(angle) * rOuter);
        ctx.strokeStyle = mag > 0.18 ? secondaryCol : primaryCol;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Rotating Radar Sweep Cone
      const sweepSpeed = passesGate && (sev === 'critical' || sev === 'high') ? 2.8 : 1.4;
      const sweepAngle = (timeSec * sweepSpeed) % (Math.PI * 2);
      const coneSteps = 18;
      for (let c = 0; c < coneSteps; c++) {
        const a0 = sweepAngle - (c / coneSteps) * 0.75;
        const a1 = sweepAngle - ((c + 1) / coneSteps) * 0.75;
        ctx.beginPath();
        ctx.moveTo(radarCx, radarCy);
        ctx.arc(radarCx, radarCy, maxR, a0, a1, true);
        ctx.closePath();
        ctx.fillStyle = accentRgba + ((1 - c / coneSteps) * 0.22).toFixed(3) + ')';
        ctx.fill();
      }
      // Leading sweep line
      ctx.beginPath();
      ctx.moveTo(radarCx, radarCy);
      ctx.lineTo(radarCx + Math.cos(sweepAngle) * maxR, radarCy + Math.sin(sweepAngle) * maxR);
      ctx.strokeStyle = primaryCol;
      ctx.lineWidth = 2;
      ctx.shadowColor = primaryCol;
      ctx.shadowBlur = 8;
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Target Blip (Locks onto bearing based on dominant frequency & confidence)
      const bearingDeg = Math.round(((Number(props.tachyonFrequency || 1.4) * 137) % 360));
      const bearingRad = ((bearingDeg - 90) * Math.PI) / 180;
      const blipDist = maxR * (passesGate ? 0.58 : 0.42);
      const bx = radarCx + Math.cos(bearingRad) * blipDist;
      const by = radarCy + Math.sin(bearingRad) * blipDist;

      const blipCol = passesGate && (sev === 'critical' || sev === 'high') ? '#ef4444' : primaryCol;
      const pulseRadius = 4 + (Math.sin(timeSec * 6) * 0.5 + 0.5) * 8;
      ctx.beginPath();
      ctx.arc(bx, by, pulseRadius, 0, Math.PI * 2);
      ctx.strokeStyle = blipCol;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(bx, by, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = blipCol;
      ctx.shadowColor = blipCol;
      ctx.shadowBlur = 10;
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.fillStyle = blipCol;
      ctx.font = '700 7.5px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(`VEC ${String(bearingDeg).padStart(3, '0')}°`, bx + 7, by + 3);
      ctx.restore();

      // ── 2. RIGHT SIDE: BALLISTIC IMPULSE & THREAT TRANSIENT SCOPE ──
      const scopeLeft = Math.max(radarCx + maxR + 34, width * 0.48);
      const scopeRight = width - 16;
      const scopeW = Math.max(60, scopeRight - scopeLeft);
      const scopeTop = 28;
      const scopeBottom = height - 24;
      const scopeH = Math.max(40, scopeBottom - scopeTop);
      const scopeMidY = scopeTop + scopeH * 0.42;

      // Compute current transient peak
      let currentPeak = 0.08;
      if (timeData && timeData.length > 0) {
        let maxAbs = 0;
        for (let i = 0; i < timeData.length; i++) {
          const v = Math.abs((timeData[i] - 128) / 128);
          if (v > maxAbs) maxAbs = v;
        }
        currentPeak = Math.min(1, Math.max(0.05, maxAbs * 1.3));
      } else {
        const baseAmp = passesGate && sev === 'critical' ? 0.72 : passesGate && sev === 'high' ? 0.52 : 0.18;
        currentPeak = Math.min(0.95, Math.max(0.05, baseAmp * (0.6 + 0.4 * Math.sin(timeSec * 4.5) * Math.cos(timeSec * 2.3))));
      }
      impulseHistory.push(currentPeak);
      if (impulseHistory.length > 90) impulseHistory.shift();

      ctx.save();
      // Scope frame box
      ctx.strokeStyle = accentRgba + '0.28)';
      ctx.fillStyle = 'rgba(2, 10, 18, 0.55)';
      ctx.lineWidth = 1;
      ctx.fillRect(scopeLeft, scopeTop, scopeW, scopeH * 0.82);
      ctx.strokeRect(scopeLeft, scopeTop, scopeW, scopeH * 0.82);

      // Center zero line
      ctx.strokeStyle = accentRgba + '0.25)';
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(scopeLeft, scopeMidY);
      ctx.lineTo(scopeRight, scopeMidY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw symmetric ballistic impulse bars + envelope
      const barStep = scopeW / impulseHistory.length;
      const maxHalfH = scopeH * 0.36;
      ctx.beginPath();
      for (let i = 0; i < impulseHistory.length; i++) {
        const x = scopeLeft + i * barStep;
        const amp = impulseHistory[i] * maxHalfH;
        const isSpike = impulseHistory[i] > 0.45;
        ctx.strokeStyle = isSpike ? '#ef4444' : primaryCol;
        ctx.lineWidth = Math.max(1, barStep * 0.65);
        ctx.beginPath();
        ctx.moveTo(x, scopeMidY - amp);
        ctx.lineTo(x, scopeMidY + amp);
        ctx.stroke();
      }

      // Scope label inside top-left of scope
      ctx.fillStyle = primaryCol;
      ctx.font = '700 8px "Orbitron", monospace';
      ctx.fillText('BALLISTIC & TRANSIENT IMPULSE ENVELOPE', scopeLeft + 8, scopeTop + 12);

      // 4 Tactical Threat Band Meters at bottom of right scope
      const bands = props.freqBands || [18, 28, 42, 24];
      const bandLabels = ['LOW RUMBLE', 'IMPACT/BREACH', 'VOCAL/SCREAM', 'BALLISTIC/GLASS'];
      const bandY = scopeTop + scopeH * 0.86;
      const bandW = (scopeW - 18) / 4;
      for (let b = 0; b < 4; b++) {
        const bx0 = scopeLeft + b * (bandW + 6);
        const pct = Math.min(100, Math.max(6, Number(bands[b] || 12)));
        const bCol = pct > 75 ? '#ef4444' : pct > 50 ? '#f59e0b' : primaryCol;
        ctx.fillStyle = 'rgba(255,255,255,0.05)';
        ctx.fillRect(bx0, bandY, bandW, 6);
        ctx.fillStyle = bCol;
        ctx.fillRect(bx0, bandY, (bandW * pct) / 100, 6);
        ctx.fillStyle = 'rgba(226,232,240,0.75)';
        ctx.font = '6.5px monospace';
        ctx.fillText(`${bandLabels[b]} ${pct}%`, bx0, bandY + 14);
      }
      ctx.restore();

      // ── 3. TOP & BOTTOM TACTICAL HUD OVERLAY ─────────────────
      ctx.save();
      ctx.font = '700 9px "Orbitron", monospace';
      const curClass = (props.currentSound || 'AMBIENT STANDBY').toUpperCase();
      const statusTitle = passesGate && (sev === 'critical' || sev === 'high')
        ? `▲ PERIMETER ALERT [${sev.toUpperCase()}] // ${curClass} (${Math.round(effConf)}%)`
        : isListening
          ? '● LIVE PERIMETER RADAR // 16 kHz TACTICAL STREAM'
          : `◉ PERIMETER RADAR ARMED // ${curClass}`;
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
      const rightText = `BEARING: ${String(bearingDeg).padStart(3, '0')}°  |  PEAK: ${peakFreq}  |  SNR: ${snr}  |  PING: ${lat}`;
      ctx.fillText(rightText, width - ctx.measureText(rightText).width - 14, 16);

      ctx.fillStyle = primaryCol + '88';
      ctx.fillText('TACTICAL PERIMETER RADAR // DUAL-AI THREAT VERIFIER', 14, height - 6);
      const gateTxt = `THREAT GATE: ${Math.round(minConf)}% // SEVERITY: ${sev.toUpperCase()}`;
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
