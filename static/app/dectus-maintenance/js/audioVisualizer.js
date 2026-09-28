/* ============================================================
   audioVisualizer.js — Dectus Live Interactive Audio Visualizer
   Replaces the fictional 3D Quantum Core with a high-performance
   dynamic HTML5 Canvas acoustic visualizer reacting to live microphone
   input, time-domain waveform, frequency spectrum, and severity.
   ============================================================ */
(function (global) {
  'use strict';

  function mountAudioVisualizer(container, getProps) {
    if (!container) return { destroy() {} };

    container.innerHTML = `
      <div class="audio-viz-wrap" style="position:relative;width:100%;height:100%;min-height:330px;display:flex;align-items:center;justify-content:center;overflow:hidden;">
        <!-- Canvas Visualizer Layer -->
        <canvas id="dectus-live-canvas" width="600" height="340" style="width:100%;height:100%;object-fit:contain;"></canvas>

        <!-- Holographic HUD Overlay Elements -->
        <div class="viz-hud-reticle" style="position:absolute;inset:10px;pointer-events:none;border:1px dashed rgba(0,245,255,0.18);border-radius:50%;max-width:320px;max-height:320px;margin:auto;">
          <div style="position:absolute;top:0;left:50%;transform:translate(-50%, -50%);font-family:monospace;font-size:7px;color:rgba(0,245,255,0.7);background:#02060c;padding:0 4px;">0° NORTH SENSOR</div>
          <div style="position:absolute;bottom:0;left:50%;transform:translate(-50%, 50%);font-family:monospace;font-size:7px;color:rgba(0,245,255,0.7);background:#02060c;padding:0 4px;">180° SENSOR ARRAY</div>
          <div style="position:absolute;top:50%;left:0;transform:translate(-50%, -50%);font-family:monospace;font-size:7px;color:rgba(0,245,255,0.7);background:#02060c;padding:0 4px;">270° L</div>
          <div style="position:absolute;top:50%;right:0;transform:translate(50%, -50%);font-family:monospace;font-size:7px;color:rgba(0,245,255,0.7);background:#02060c;padding:0 4px;">90° R</div>
        </div>

        <!-- Real-time Sensor HUD Corner Readouts -->
        <div style="position:absolute;top:8px;left:12px;font-family:monospace;font-size:8px;color:rgba(0,245,255,0.85);pointer-events:none;line-height:1.4;">
          <div>ACOUSTIC SENSOR: <span id="viz-sensor-tag" style="color:#10b981;font-weight:bold;">STANDBY</span></div>
          <div>INPUT LEVEL: <span id="viz-input-db" style="color:#00f5ff;">-28.4 dBFS</span></div>
        </div>

        <div style="position:absolute;top:8px;right:12px;font-family:monospace;font-size:8px;color:rgba(0,245,255,0.85);pointer-events:none;text-align:right;line-height:1.4;">
          <div>PEAK FREQ: <span id="viz-peak-freq" style="color:#a855f7;">320 Hz</span></div>
          <div>SAMPLING: <span style="color:#38bdf8;">44.1 kHz 24b</span></div>
        </div>

        <div style="position:absolute;bottom:8px;left:12px;font-family:monospace;font-size:8px;color:rgba(0,245,255,0.7);pointer-events:none;">
          <span>SNR: <b id="viz-snr-val" style="color:#10b981;">28.5 dB</b></span>
        </div>

        <div style="position:absolute;bottom:8px;right:12px;font-family:monospace;font-size:8px;color:rgba(0,245,255,0.7);pointer-events:none;">
          <span>AI LATENCY: <b id="viz-latency-val" style="color:#10b981;">16ms</b></span>
        </div>

        <!-- Critical Threat Flashing Banner -->
        <div id="viz-crit-banner" class="hidden" style="position:absolute;top:50%;left:50%;transform:translate(-50%, -50%);background:rgba(239,68,68,0.25);border:1px solid #ef4444;box-shadow:0 0 25px rgba(239,68,68,0.7);padding:6px 14px;border-radius:4px;pointer-events:none;text-align:center;animation:pulseCrit 0.8s infinite alternate;">
          <div style="font-family:'Orbitron';font-size:11px;font-weight:800;color:#fca5a5;letter-spacing:0.18em;">⚠️ CRITICAL THREAT DETECTED</div>
          <div style="font-family:'Share Tech Mono';font-size:9px;color:#fff;" id="viz-crit-msg">GUNSHOT ACOUSTIC SIGNATURE REGISTERED</div>
        </div>
      </div>
    `;

    const canvas = container.querySelector('#dectus-live-canvas');
    const ctx = canvas.getContext('2d');
    const critBanner = container.querySelector('#viz-crit-banner');
    const critMsg = container.querySelector('#viz-crit-msg');
    const sensorTag = container.querySelector('#viz-sensor-tag');
    const inputDb = container.querySelector('#viz-input-db');
    const peakFreq = container.querySelector('#viz-peak-freq');
    const snrVal = container.querySelector('#viz-snr-val');
    const latencyVal = container.querySelector('#viz-latency-val');

    let animId = null;
    let phase = 0;
    const particles = [];
    const NUM_PARTICLES = 45;

    for (let i = 0; i < NUM_PARTICLES; i++) {
      particles.push({
        angle: Math.random() * Math.PI * 2,
        distance: 20 + Math.random() * 110,
        speed: 0.2 + Math.random() * 0.8,
        size: 1 + Math.random() * 2.2,
        alpha: 0.2 + Math.random() * 0.7,
      });
    }

    function renderFrame() {
      animId = requestAnimationFrame(renderFrame);

      const state = (getProps && getProps()) || global.NEXUS.store.getState();
      const isListening = state.isListening && !state.privacyMode;
      const isPrivacy = state.privacyMode;
      const severity = (state.severity || 'SAFE').toUpperCase();
      const isCrit = severity === 'CRITICAL';
      const isHigh = severity === 'HIGH';

      // Update HUD metrics
      if (sensorTag) {
        if (isPrivacy) {
          sensorTag.textContent = 'MIC DISABLED';
          sensorTag.style.color = '#ef4444';
        } else if (isListening) {
          sensorTag.textContent = 'ACTIVE LISTENING';
          sensorTag.style.color = '#10b981';
        } else {
          sensorTag.textContent = 'STANDBY';
          sensorTag.style.color = '#94a3b8';
        }
      }

      if (inputDb) inputDb.textContent = `${state.inputLevelDb || -28.4} dBFS`;
      if (peakFreq) peakFreq.textContent = `${state.frequencyHz || 320} Hz`;
      if (snrVal) snrVal.textContent = `${state.snrDb || 28.5} dB`;
      if (latencyVal) latencyVal.textContent = `${isListening ? 14 : 18}ms`;

      // Critical alert banner
      if (critBanner) {
        if (isCrit) {
          critBanner.classList.remove('hidden');
          if (critMsg) critMsg.textContent = `${(state.currentSound || 'THREAT').toUpperCase()} SIGNATURE CONFIRMED`;
        } else {
          critBanner.classList.add('hidden');
        }
      }

      // Theme Colors based on Severity
      let primaryColor = '#00f5ff';
      let secondaryColor = '#a855f7';
      let glowColor = 'rgba(0, 245, 255, 0.4)';

      if (isCrit) {
        primaryColor = '#ef4444';
        secondaryColor = '#ff6b35';
        glowColor = 'rgba(239, 68, 68, 0.6)';
      } else if (isHigh) {
        primaryColor = '#ff6b35';
        secondaryColor = '#f59e0b';
        glowColor = 'rgba(255, 107, 53, 0.5)';
      } else if (severity === 'MEDIUM') {
        primaryColor = '#f59e0b';
        secondaryColor = '#38bdf8';
        glowColor = 'rgba(245, 158, 11, 0.4)';
      } else if (severity === 'LOW') {
        primaryColor = '#38bdf8';
        secondaryColor = '#10b981';
        glowColor = 'rgba(56, 189, 248, 0.4)';
      }

      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;

      ctx.clearRect(0, 0, w, h);

      // ── PRIVACY / IDLE FLATLINE MODE ──────────────────────
      if (isPrivacy) {
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.35)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, cy);
        ctx.lineTo(w, cy);
        ctx.stroke();

        ctx.fillStyle = '#ef4444';
        ctx.font = '10px Orbitron, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('HARDWARE PRIVACY ACTIVATED // MICROPHONE DISCONNECTED', cx, cy - 14);
        return;
      }

      // Get real audio frequency / time data if analyser exists
      let timeData = null;
      let freqData = null;
      const analyser = global.NEXUS.audioAnalyser;

      if (analyser && isListening) {
        timeData = new Uint8Array(analyser.frequencyBinCount);
        freqData = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteTimeDomainData(timeData);
        analyser.getByteFrequencyData(freqData);
      }

      phase += isListening ? 0.045 : 0.015;
      const ampMultiplier = isListening ? (state.amplitude || 30) / 100 : 0.12;

      // ── 1. BACKGROUND GLOW & RADIAL RETICLES ─────────────
      const radialGrad = ctx.createRadialGradient(cx, cy, 10, cx, cy, 150);
      radialGrad.addColorStop(0, glowColor);
      radialGrad.addColorStop(0.7, 'rgba(2, 6, 12, 0.1)');
      radialGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = radialGrad;
      ctx.fillRect(0, 0, w, h);

      // Central concentric acoustic pulse rings
      const pulseBase = (phase * 15) % 120;
      for (let r = pulseBase; r < 140; r += 35) {
        const ringAlpha = Math.max(0, 1 - r / 140) * (isListening ? 0.45 : 0.18);
        ctx.beginPath();
        ctx.arc(cx, cy, r + (ampMultiplier * 15), 0, Math.PI * 2);
        ctx.strokeStyle = isCrit ? `rgba(239,68,68,${ringAlpha})` : `rgba(0,245,255,${ringAlpha})`;
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      // ── 2. FLOATING FREQUENCY PARTICLES ───────────────────
      particles.forEach((p) => {
        p.distance += p.speed * (1 + ampMultiplier * 1.5);
        if (p.distance > 145) {
          p.distance = 15 + Math.random() * 20;
          p.angle = Math.random() * Math.PI * 2;
        }
        const px = cx + Math.cos(p.angle) * p.distance;
        const py = cy + Math.sin(p.angle) * p.distance;

        ctx.fillStyle = isCrit ? `rgba(248,113,113,${p.alpha})` : `rgba(0,245,255,${p.alpha})`;
        ctx.beginPath();
        ctx.arc(px, py, p.size * (1 + ampMultiplier * 0.8), 0, Math.PI * 2);
        ctx.fill();
      });

      // ── 3. FFT FREQUENCY SPECTRUM BARS (Mirrored Center) ─
      const numBars = 48;
      const barWidth = 3;
      const barSpacing = 4;
      const totalWidth = numBars * (barWidth + barSpacing);
      const startX = cx - totalWidth / 2;

      for (let i = 0; i < numBars; i++) {
        let barHeight = 8;
        if (freqData) {
          const bin = Math.floor((i / numBars) * (freqData.length / 3));
          barHeight = (freqData[bin] / 255) * 85 * (1 + ampMultiplier * 0.5);
        } else {
          // Simulated organic acoustic waves when mic is calibrating
          const wave = Math.sin(i * 0.28 + phase * 2) * Math.cos(i * 0.15 - phase);
          barHeight = 10 + Math.abs(wave) * 65 * (isListening ? (ampMultiplier + 0.3) : 0.2);
        }

        const bx = startX + i * (barWidth + barSpacing);
        const grad = ctx.createLinearGradient(0, cy - barHeight, 0, cy + barHeight);
        grad.addColorStop(0, primaryColor);
        grad.addColorStop(0.5, secondaryColor);
        grad.addColorStop(1, primaryColor);

        ctx.fillStyle = grad;
        ctx.shadowColor = primaryColor;
        ctx.shadowBlur = isCrit ? 12 : 6;
        ctx.fillRect(bx, cy - barHeight / 2, barWidth, Math.max(3, barHeight));
      }
      ctx.shadowBlur = 0;

      // ── 4. MULTI-LAYER OSCILLATING AUDIO WAVEFORMS ────────
      const waves = [
        { freq: 0.022, speed: 2.4, amp: 45 * ampMultiplier + 6, color: primaryColor, width: 2.2 },
        { freq: 0.035, speed: -1.8, amp: 28 * ampMultiplier + 4, color: secondaryColor, width: 1.6 },
        { freq: 0.015, speed: 1.2, amp: 18 * ampMultiplier + 3, color: '#10b981', width: 1.2 },
      ];

      waves.forEach((wDef) => {
        ctx.beginPath();
        ctx.strokeStyle = wDef.color;
        ctx.lineWidth = wDef.width;
        ctx.shadowColor = wDef.color;
        ctx.shadowBlur = isCrit ? 10 : 4;

        for (let x = 0; x < w; x += 3) {
          let y = cy;
          if (timeData) {
            const dataIndex = Math.floor((x / w) * timeData.length);
            const normalized = (timeData[dataIndex] - 128) / 128;
            y = cy + normalized * wDef.amp * 2.2;
          } else {
            y = cy + Math.sin(x * wDef.freq + phase * wDef.speed) * wDef.amp;
          }

          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      });
      ctx.shadowBlur = 0;

      // ── 5. CENTER ACOUSTIC CORE RETICLE ───────────────────
      ctx.beginPath();
      ctx.arc(cx, cy, 26 + ampMultiplier * 14, 0, Math.PI * 2);
      ctx.strokeStyle = primaryColor;
      ctx.lineWidth = 2;
      ctx.shadowColor = primaryColor;
      ctx.shadowBlur = 10;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cx, cy, 6, 0, Math.PI * 2);
      ctx.fillStyle = primaryColor;
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    renderFrame();

    return {
      destroy() {
        if (animId) cancelAnimationFrame(animId);
      },
    };
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.mountAudioVisualizer = mountAudioVisualizer;
  // Seamless fallback for existing references to mountQuantumCore
  global.NEXUS.mountQuantumCore = mountAudioVisualizer;
})(window);
