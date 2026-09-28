/* ============================================================
   topbar.js — SonicSentinel AI Security Command Center Top Bar
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
    if (value >= 70) return { text: '#34d399', border: 'rgba(16,185,129,0.4)', bg: 'rgba(16,185,129,0.1)', glow: true };
    if (value >= 40) return { text: '#fbbf24', border: 'rgba(245,158,11,0.4)', bg: 'rgba(245,158,11,0.1)', glow: false };
    return { text: '#f87171', border: 'rgba(239,68,68,0.4)', bg: 'rgba(239,68,68,0.1)', glow: false };
  }

  const THREAT_COLORS = ['#34d399', '#34d399', '#fbbf24', '#fbbf24', '#f87171', '#f87171'];
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
            <span class="command">SECURITY COMMAND</span>
          </div>
          <div class="sub">
            <div class="sub-dot"></div>
            <span class="sub-text" id="tb-sector-sub">PERIMETER AUDIO SURVEILLANCE // TACTICAL HUD v2.5.0</span>
          </div>
        </div>

        <div class="divider-v"></div>

        <div class="topbar-center">
          <div class="topbar-sector-row">
            <span class="topbar-alert-tag hidden" id="tb-alert-tag">[ALERT]</span>
            <span class="topbar-sector-name" id="tb-sector-name">SECTOR-SECURITY</span>
            <div class="threat-display">
              <span class="lbl">THREAT</span>
              <div class="threat-bars" id="tb-threat-bars"></div>
              <span class="status" id="tb-threat-status"></span>
            </div>
            <span class="sep" style="color:#334155;margin:0 4px;">//</span>
            <span class="k" style="font-family:monospace;font-size:9px;color:#64748b;">SYS-DATE</span>
            <span class="stardate" id="tb-stardate" style="font-family:monospace;font-size:9.5px;color:#cbd5e1;"></span>
            <span class="sep" style="color:#334155;margin:0 2px;">//</span>
            <span class="utc cursor-blink" id="tb-utc" style="font-family:monospace;font-size:9.5px;color:#38bdf8;"></span>
          </div>
          <div class="warp-row" style="margin-top:2px;">
            <span class="lbl" style="color:#64748b;">CONSENSUS</span>
            <div class="warp-track" style="background:#090e1a;border:1px solid #1e293b;"><div class="warp-fill" id="tb-warp-fill" style="background:linear-gradient(90deg, #0284c7, #38bdf8);"></div></div>
            <span class="warp-pct" id="tb-warp-pct" style="color:#f8fafc;">0%</span>
          </div>
        </div>

        <div class="divider-v"></div>

        <div class="topbar-right">
          <div class="status-chips">
            <div class="status-chip" id="chip-reactor"><span class="lbl">INPUT</span><span class="val"></span></div>
            <div class="status-chip" id="chip-shield"><span class="lbl">QUALITY</span><span class="val"></span></div>
            <div class="status-chip" id="chip-coherence"><span class="lbl">CONSENSUS</span><span class="val"></span></div>
          </div>
          <div class="divider-v-sm"></div>
          <div class="action-buttons">
            <button class="action-btn" id="btn-combat" data-variant="red">LIVE MONITOR</button>
            <button class="action-btn" id="btn-cloak" data-variant="neural">PRIVACY</button>
            <button class="action-btn amber" id="btn-warp" data-variant="amber">ANALYZE AUDIO</button>
            <button class="emergency-btn" id="btn-emergency">EXIT / ROLES</button>
          </div>
        </div>
      </div>
    `;

    // Build 5 threat bars
    const threatBarsEl = root.querySelector('#tb-threat-bars');
    for (let i = 0; i < 5; i++) {
      const bar = document.createElement('div');
      bar.className = 'bar';
      threatBarsEl.appendChild(bar);
    }

    function setChip(el, value) {
      if (typeof value === 'string') {
        el.style.borderColor = 'rgba(0,245,255,0.25)';
        el.style.background = 'rgba(0,245,255,0.05)';
        const v = el.querySelector('.val');
        v.textContent = value;
        v.style.color = '#94a3b8';
        v.style.textShadow = 'none';
        return;
      }
      const c = statusColor(value);
      el.style.borderColor = c.border;
      el.style.background = c.bg;
      const v = el.querySelector('.val');
      v.textContent = `${value}%`;
      v.style.color = c.text;
      v.style.textShadow = c.glow ? `0 0 10px ${c.text}, 0 0 20px ${c.text}` : 'none';
    }

    function setActionButton(btn, active) {
      btn.classList.toggle('active', active);
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
      if (state.cloakActive) {
        setChip(root.querySelector('#chip-reactor'), 'MUTED');
      } else if (state.isListening) {
        setChip(root.querySelector('#chip-reactor'), Math.round(state.reactorOutput));
      } else {
        setChip(root.querySelector('#chip-reactor'), 'STANDBY');
      }

      setChip(root.querySelector('#chip-shield'), Math.round(state.shieldIntegrity));
      setChip(root.querySelector('#chip-coherence'), state.warpEnabled ? Math.round(state.warpCharge) : 'READY');

      // Sector name / sub
      root.querySelector('#tb-sector-sub').textContent = `${state.sectorDesignation} // SECURITY COMMAND v2.5.0`;
      const sectorNameEl = root.querySelector('#tb-sector-name');
      sectorNameEl.textContent = state.sectorDesignation;
      const alertActive = state.combatMode || state.emergencyProtocol || state.sectorThreatLevel >= 3;
      sectorNameEl.classList.toggle('alert', alertActive);

      // Threat display
      const bars = threatBarsEl.querySelectorAll('.bar');
      bars.forEach((bar, i) => {
        if (i < state.sectorThreatLevel) {
          const col = i < 2 ? '#34d399' : i < 4 ? '#fbbf24' : '#ef4444';
          bar.style.background = col;
          bar.style.boxShadow = `0 0 4px ${col}`;
        } else {
          bar.style.background = 'rgba(8,51,68,0.5)';
          bar.style.boxShadow = 'none';
        }
      });
      const statusEl = root.querySelector('#tb-threat-status');
      statusEl.textContent = THREAT_LABELS[state.sectorThreatLevel] || 'NOMINAL';
      statusEl.style.color = THREAT_COLORS[state.sectorThreatLevel] || '#34d399';

      // Consensus bar
      root.querySelector('#tb-warp-fill').style.width = `${state.warpCharge}%`;
      root.querySelector('#tb-warp-fill').style.background = state.warpEnabled
        ? 'linear-gradient(90deg, #00f5ff, #60efff)' : 'linear-gradient(90deg, #f59e0b, #fbbf24)';
      root.querySelector('#tb-warp-fill').style.boxShadow = state.warpEnabled ? '0 0 6px #00f5ff' : '0 0 6px #f59e0b';
      const warpPctEl = root.querySelector('#tb-warp-pct');
      warpPctEl.textContent = `${Math.round(state.warpCharge)}%`;
      warpPctEl.style.color = state.warpEnabled ? '#00f5ff' : '#f59e0b';

      // Action buttons
      setActionButton(root.querySelector('#btn-combat'), state.isListening && !state.cloakActive);
      setActionButton(root.querySelector('#btn-cloak'), state.cloakActive);
      setActionButton(root.querySelector('#btn-warp'), state.warpEnabled);
      root.querySelector('#btn-emergency').classList.toggle('active', state.emergencyProtocol);

      let ring = root.querySelector('#btn-emergency .ring');
      if (state.emergencyProtocol && !ring) {
        ring = document.createElement('span');
        ring.className = 'ring';
        root.querySelector('#btn-emergency').appendChild(ring);
      } else if (!state.emergencyProtocol && ring) {
        ring.remove();
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

    root.querySelector('#btn-emergency').addEventListener('click', () => {
      if (confirm('Navigate to Role Selection / Switch Dashboard?')) {
        window.location.href = '/app/select-role';
      }
      ensureStarted().then(() => soundEngine.playButton('emergency'));
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
