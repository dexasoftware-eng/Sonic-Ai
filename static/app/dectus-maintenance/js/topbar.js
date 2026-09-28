/* ============================================================
   topbar.js — SonicSentinel AI Maintenance Command Center Top Bar
   ============================================================ */
(function (global) {
  'use strict';

  function getStardate() {
    const now = new Date();
    const y = now.getUTCFullYear();
    const m = String(now.getUTCMonth() + 1).padStart(2, '0');
    const d = String(now.getUTCDate()).padStart(2, '0');
    return `${y}.${m}.${d}`;
  }

  function getUtcTime() {
    const now = new Date();
    const h = String(now.getUTCHours()).padStart(2, '0');
    const m = String(now.getUTCMinutes()).padStart(2, '0');
    const s = String(now.getUTCSeconds()).padStart(2, '0');
    const ds = Math.floor(now.getUTCMilliseconds() / 100);
    return `${h}:${m}:${s}.${ds}`;
  }

  function statusColor(value) {
    if (value >= 70) return { text: 'rgb(52, 211, 153)', border: 'rgba(16, 185, 129, 0.4)', bg: 'rgba(16, 185, 129, 0.1)', glow: true };
    if (value >= 40) return { text: 'rgb(251, 191, 36)', border: 'rgba(245, 158, 11, 0.4)', bg: 'rgba(245, 158, 11, 0.1)', glow: false };
    return { text: 'rgb(248, 113, 113)', border: 'rgba(239, 68, 68, 0.4)', bg: 'rgba(239, 68, 68, 0.1)', glow: false };
  }

  const THREAT_COLORS = ['rgb(52, 211, 153)', 'rgb(52, 211, 153)', 'rgb(251, 191, 36)', 'rgb(251, 191, 36)', 'rgb(248, 113, 113)', 'rgb(248, 113, 113)'];
  const THREAT_LABELS = ['NOMINAL', 'ELEVATED', 'GUARDED', 'HIGH', 'SEVERE', 'CRITICAL'];

  function mountTopBar(root) {
    const store = global.NEXUS.store;
    const { soundEngine, ensureStarted } = global.NEXUS;

    root.innerHTML = `
      <div class="topbar box-glow-cyan">
        <div class="edge-glow"></div>
        <div class="corner-tl"></div>
        <div class="corner-tr"></div>

        <div class="topbar-title">
          <div class="brand">
            <span class="nexus">SONICSENTINEL AI</span>
            <span class="command">MAINTENANCE HUD</span>
          </div>
          <div class="sub">
            <div class="sub-dot"></div>
            <span class="sub-text" id="tb-sector-sub">FACILITY-BAY-01 // MNT v2.5.0</span>
          </div>
        </div>

        <div class="divider-v"></div>

        <div class="topbar-center">
          <div class="topbar-sector-row">
            <span class="topbar-alert-tag hidden" id="tb-alert-tag">[ALERT]</span>
            <span class="topbar-sector-name" id="tb-sector-name">FACILITY-BAY-01</span>
            <div class="threat-display">
              <span class="lbl">FAULT</span>
              <div class="threat-bars" id="tb-threat-bars">
                <div class="bar"></div>
                <div class="bar"></div>
                <div class="bar"></div>
                <div class="bar"></div>
                <div class="bar"></div>
                <div class="bar"></div>
              </div>
              <span class="status" id="tb-threat-status">NOMINAL</span>
            </div>
            <span class="sep" style="color:#1e293b;margin:0 3px;">//</span>
            <span class="k" style="font-family:monospace;font-size:8px;color:#475569;">SYS-DATE</span>
            <span class="stardate" id="tb-stardate" style="font-family:monospace;font-size:9px;color:#94a3b8;"></span>
            <span class="sep" style="color:#1e293b;margin:0 2px;">//</span>
            <span class="utc cursor-blink" id="tb-utc" style="font-family:monospace;font-size:9px;color:#38bdf8;"></span>
          </div>
          <div class="warp-row">
            <span class="lbl" style="color:#475569;">CONSENSUS</span>
            <div class="warp-track">
              <div class="warp-fill" id="tb-warp-fill"></div>
            </div>
            <span class="warp-pct" id="tb-warp-pct">–%</span>
          </div>
        </div>

        <div class="divider-v"></div>

        <div class="topbar-right">
          <div class="status-chips">
            <div class="status-chip" id="chip-reactor"><span class="lbl">INPUT</span><span class="val">STANDBY</span></div>
            <div class="status-chip" id="chip-shield"><span class="lbl">QUALITY</span><span class="val">–%</span></div>
            <div class="status-chip" id="chip-coherence"><span class="lbl">CONSENSUS</span><span class="val">–%</span></div>
          </div>
          <div class="divider-v-sm"></div>
          <div class="action-buttons">
            <button class="action-btn" id="btn-combat" data-variant="red" title="Toggle Live Acoustic Diagnostic Telemetry">LIVE MONITOR</button>
            <button class="action-btn" id="btn-cloak" data-variant="neural" title="Toggle Sensor Calibration Bypass">PRIVACY</button>
            <button class="action-btn amber" id="btn-warp" data-variant="amber" title="Analyze Machine Acoustic Spectrum">ANALYZE AUDIO</button>
            <button class="emergency-btn" id="btn-emergency" title="Exit Terminal / Return to Portal">EXIT / ROLES<span class="ring"></span></button>
          </div>
        </div>
      </div>
    `;

    const threatBarsEl = root.querySelector('#tb-threat-bars');

    function setChip(el, value) {
      if (!el) return;
      if (typeof value === 'string') {
        el.style.borderColor = 'rgba(0, 245, 255, 0.25)';
        el.style.background = 'rgba(0, 245, 255, 0.05)';
        const v = el.querySelector('.val');
        if (v) {
          v.textContent = value;
          v.style.color = 'rgb(148, 163, 184)';
          v.style.textShadow = 'none';
        }
        return;
      }
      const c = statusColor(value);
      el.style.borderColor = c.border;
      el.style.background = c.bg;
      const v = el.querySelector('.val');
      if (v) {
        v.textContent = `${value}%`;
        v.style.color = c.text;
        v.style.textShadow = c.glow ? `0 0 10px ${c.text}, 0 0 20px ${c.text}` : 'none';
      }
    }

    function setActionButton(btn, active) {
      if (!btn) return;
      btn.classList.toggle('active', Boolean(active));
      let pip = btn.querySelector('.pip');
      if (active && !pip) {
        pip = document.createElement('span');
        pip.className = 'pip';
        const variant = btn.dataset.variant;
        pip.style.background = variant === 'red' ? '#ef4444' : variant === 'amber' ? '#f59e0b' : variant === 'neural' ? '#a855f7' : '#00f5ff';
        btn.appendChild(pip);
      } else if (!active && pip) {
        pip.remove();
      }
    }

    function render(state) {
      const chipReactor = root.querySelector('#chip-reactor');
      if (state.cloakActive) {
        chipReactor.style.borderColor = 'rgba(168, 85, 247, 0.4)';
        chipReactor.style.background = 'rgba(168, 85, 247, 0.1)';
        const v = chipReactor.querySelector('.val');
        if (v) {
          v.textContent = 'MUTED';
          v.style.color = '#c084fc';
          v.style.textShadow = '0 0 10px #a855f7';
        }
      } else if (state.isListening) {
        const out = Math.round(state.reactorOutput || 94);
        chipReactor.style.borderColor = 'rgba(16, 185, 129, 0.4)';
        chipReactor.style.background = 'rgba(16, 185, 129, 0.1)';
        const v = chipReactor.querySelector('.val');
        if (v) {
          v.textContent = `${out}%`;
          v.style.color = 'rgb(52, 211, 153)';
          v.style.textShadow = 'rgb(52, 211, 153) 0px 0px 10px, rgb(52, 211, 153) 0px 0px 20px';
        }
      } else {
        chipReactor.style.borderColor = 'rgba(0, 245, 255, 0.25)';
        chipReactor.style.background = 'rgba(0, 245, 255, 0.05)';
        const v = chipReactor.querySelector('.val');
        if (v) {
          v.textContent = 'STANDBY';
          v.style.color = 'rgb(148, 163, 184)';
          v.style.textShadow = 'none';
        }
      }

      const qualityVal = Math.round(state.shieldIntegrity != null && state.shieldIntegrity > 0 ? state.shieldIntegrity : 98);
      setChip(root.querySelector('#chip-shield'), qualityVal);

      const consensusPct = Math.round(state.warpCharge != null && state.warpCharge > 0 ? state.warpCharge : 93);
      setChip(root.querySelector('#chip-coherence'), consensusPct);

      // Sector name & subtitle
      const sectorName = state.sectorDesignation || 'FACILITY-BAY-01';
      root.querySelector('#tb-sector-sub').textContent = `${sectorName} // MNT v2.5.0`;

      const sectorNameEl = root.querySelector('#tb-sector-name');
      sectorNameEl.textContent = sectorName;
      const alertActive = Boolean(state.combatMode || state.emergencyProtocol || state.sectorThreatLevel >= 3);
      sectorNameEl.classList.toggle('alert', alertActive);

      const alertTag = root.querySelector('#tb-alert-tag');
      if (alertTag) {
        alertTag.classList.toggle('hidden', !alertActive);
      }

      // Threat display — 6 bars
      const threatLvl = Number(state.sectorThreatLevel != null ? state.sectorThreatLevel : 0);
      const bars = threatBarsEl.querySelectorAll('.bar');
      bars.forEach((bar, i) => {
        if (i < threatLvl) {
          const col = i < 2 ? 'rgb(52, 211, 153)' : i < 4 ? 'rgb(251, 191, 36)' : 'rgb(239, 68, 68)';
          bar.style.background = col;
          bar.style.boxShadow = `${col} 0px 0px 5px`;
        } else {
          bar.style.background = 'rgba(8, 51, 68, 0.45)';
          bar.style.boxShadow = 'none';
        }
      });
      const statusEl = root.querySelector('#tb-threat-status');
      statusEl.textContent = THREAT_LABELS[Math.min(threatLvl, THREAT_LABELS.length - 1)] || 'NOMINAL';
      statusEl.style.color = THREAT_COLORS[Math.min(threatLvl, THREAT_COLORS.length - 1)] || 'rgb(52, 211, 153)';

      // Consensus meter
      const warpFill = root.querySelector('#tb-warp-fill');
      warpFill.style.width = `${consensusPct}%`;
      warpFill.style.background = state.warpEnabled !== false
        ? 'linear-gradient(90deg, rgb(0, 245, 255), rgb(96, 239, 255))'
        : 'linear-gradient(90deg, #f59e0b, #fbbf24)';
      warpFill.style.boxShadow = state.warpEnabled !== false ? 'rgb(0, 245, 255) 0px 0px 6px' : '0 0 6px #f59e0b';
      const warpPctEl = root.querySelector('#tb-warp-pct');
      warpPctEl.textContent = `${consensusPct}%`;
      warpPctEl.style.color = state.warpEnabled !== false ? 'rgb(0, 245, 255)' : '#fbbf24';

      // Action buttons
      setActionButton(root.querySelector('#btn-combat'), state.isListening && !state.cloakActive);
      setActionButton(root.querySelector('#btn-cloak'), state.cloakActive);
      setActionButton(root.querySelector('#btn-warp'), state.warpEnabled !== false);

      const emBtn = root.querySelector('#btn-emergency');
      if (emBtn) {
        emBtn.classList.toggle('active', true);
        let ring = emBtn.querySelector('.ring');
        if (!ring) {
          ring = document.createElement('span');
          ring.className = 'ring';
          emBtn.appendChild(ring);
        }
      }
    }

    function tickClock() {
      root.querySelector('#tb-utc').textContent = `${getUtcTime()} UTC`;
      root.querySelector('#tb-stardate').textContent = getStardate();
    }
    tickClock();
    const clockInterval = setInterval(tickClock, 100);

    // Wire buttons to SonicSentinel AI features
    root.querySelector('#btn-combat').addEventListener('click', () => {
      if (global.NEXUS.toggleLiveMonitoring) {
        global.NEXUS.toggleLiveMonitoring();
      } else {
        store.getState().toggleCombatMode();
      }
      ensureStarted().then(() => soundEngine.playButton('combat'));
    });

    root.querySelector('#btn-cloak').addEventListener('click', () => {
      if (global.NEXUS.togglePrivacy) {
        global.NEXUS.togglePrivacy();
      } else {
        store.getState().toggleCloak();
      }
      ensureStarted().then(() => soundEngine.playButton('cloak'));
    });

    root.querySelector('#btn-warp').addEventListener('click', () => {
      if (global.NEXUS.openAudioModal) {
        global.NEXUS.openAudioModal();
      } else {
        store.getState().toggleWarp();
      }
      ensureStarted().then(() => soundEngine.playButton('warp'));
    });

    root.querySelector('#btn-emergency').addEventListener('click', async () => {
      ensureStarted().then(() => soundEngine.playButton('emergency'));
      const confirmed = window.customAlert && window.customAlert.confirm
        ? await window.customAlert.confirm('Return to Maintenance Studio Dashboard or Switch Role?', { title: 'Exit Terminal', confirmText: 'Exit to Dashboard', cancelText: 'Stay in Terminal' })
        : true;
      if (confirmed) {
        window.location.href = '/app/select-role';
      }
    });

    render(store.getState());
    const unsub = store.subscribe(render);

    return {
      destroy() {
        clearInterval(clockInterval);
        unsub();
      },
    };
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.mountTopBar = mountTopBar;
})(window);
