/* ============================================================
   app.js — SonicSentinel AI Maintenance Command Center
   100% Connected to MongoDB & Dual-AI Models (Python 2D-CNN + GTM):
   - Syncs real MongoDB audio_events, alerts, and model telemetry on load
   - Streams live microphone Float32 PCM audio over /ws/live-audio to both AI models
   - Analyzes uploaded audio files via /api/app/audio/analyze and persists to MongoDB
   ============================================================ */
(function (global) {
  'use strict';

  let micStream = null;
  let micAudioContext = null;
  let micAnalyser = null;
  let micProcessor = null;
  let micProcessInterval = null;
  let liveWs = null;
  let pcmAccumulator = [];
  let pcmSampleCount = 0;

  // ── 0. SYNC REAL MONGODB & MODEL TELEMETRY ──────────────────
  async function syncDatabaseTelemetry(playPingSound) {
    const store = global.NEXUS.store;
    try {
      const resp = await fetch('/api/user/telemetry', { cache: 'no-store' });
      if (!resp.ok) return;
      const data = await resp.json();
      if (!data || data.status !== 'success') return;

      const s = store.getState();
      const ev = data.latest_event || {};
      const sys = data.system_telemetry || {};

      const nextState = {
        anomalyCount: data.total_detections != null ? data.total_detections : s.anomalyCount,
        activeProbes: data.active_classes_count != null ? data.active_classes_count : s.activeProbes,
        dbConnected: !!sys.db_connected,
        dbLatencyMs: sys.db_latency_ms || 0,
        pythonModelVersion: sys.python_model_version || 'v2.5',
        gtmModelVersion: sys.gtm_model_version || 'v2.5',
        commChannels: [
          { label: 'DSP-CALIBRATION', status: 'READY', pct: 100, color: '#10b981' },
          { label: 'DIAGNOSTIC-AI', status: 'ONLINE', pct: 100, color: '#00f5ff' },
          { label: 'TELEMETRY-LINK', status: sys.db_connected ? 'ONLINE' : 'CONNECTING', pct: sys.db_connected ? 100 : 50, color: '#a855f7' },
        ],
      };

      if (Array.isArray(data.incident_logs)) {
        nextState.alerts = data.incident_logs;
      }

      if (!s.isListening) {
        const pyConf = Math.round(Number(ev.python_confidence || 0));
        const gtmConf = Math.round(Number(ev.gtm_confidence || 0));
        const avgConf = Math.round(Number(ev.avg_confidence || (pyConf + gtmConf) / 2));
        const sevRaw = ev.severity || (ev.threat_level >= 5 ? 'Critical' : ev.threat_level === 4 ? 'High' : ev.threat_level >= 2 ? 'Medium' : 'Low');
        const gateState = global.NEXUS.computeSeverityState
          ? global.NEXUS.computeSeverityState(sevRaw, avgConf, pyConf, s.neuralSyncRate)
          : { severity: sevRaw, passesAlertGate: avgConf >= (s.neuralSyncRate || 75), sectorThreatLevel: ev.threat_level || 1, emergencyProtocol: false, combatMode: false };

        Object.assign(nextState, gateState);
        nextState.currentSound = (ev.python_prediction || 'AMBIENT STANDBY').toUpperCase();
        nextState.pythonPrediction = ev.python_prediction || 'Ambient Standby';
        nextState.pythonConfidence = pyConf;
        nextState.gtmPrediction = ev.gtm_prediction || 'Ambient Standby';
        nextState.gtmConfidence = gtmConf;
        nextState.consistencyStatus = ev.consistency_status || 'STANDBY';
        nextState.warpCharge = avgConf;
        nextState.quantumCoherence = avgConf;
        nextState.snrDb = ev.snr_db != null ? Number(ev.snr_db) : 0;
        nextState.shieldIntegrity = ev.quality_pct != null ? Number(ev.quality_pct) : 0;
        nextState.tachyonFrequency = ev.peak_khz != null ? Number(ev.peak_khz) : 0;
        nextState.inputLevelDb = ev.peak_dbfs || s.inputLevelDb;
        nextState.rmsLevelDb = ev.rms_dbfs || s.rmsLevelDb;
        nextState.sectorDesignation = 'FACILITY-BAY-01';

        if (Array.isArray(ev.freq_bands) && ev.freq_bands.length === 4) {
          nextState.freqBands = ev.freq_bands;
        }

        if (Array.isArray(data.streams) && data.streams.length === 6) {
          nextState.dataStreams = s.dataStreams.map((stream, idx) => ({
            ...stream,
            values: data.streams[idx] || stream.values,
          }));
        }
      }

      store.setState(nextState);

      if (playPingSound && global.NEXUS.ensureStarted && global.NEXUS.soundEngine) {
        global.NEXUS.ensureStarted().then(() => {
          global.NEXUS.soundEngine.playAlert('INFO');
        });
      }
    } catch (err) {
      console.warn('Maintenance telemetry sync notice:', err);
    }
  }

  function downsampleFloat32(buffer, inputSampleRate, targetSampleRate) {
    if (inputSampleRate === targetSampleRate) return buffer;
    const ratio = inputSampleRate / targetSampleRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    let offsetResult = 0;
    let offsetBuffer = 0;
    while (offsetResult < result.length) {
      const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
      let accum = 0;
      let count = 0;
      for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
        accum += buffer[i];
        count++;
      }
      result[offsetResult] = count > 0 ? accum / count : 0;
      offsetResult++;
      offsetBuffer = nextOffsetBuffer;
    }
    return result;
  }

  // ── 1. REAL MICROPHONE STREAM + WEBSOCKET DUAL-AI INFERENCE ─
  async function toggleLiveMonitoring() {
    const store = global.NEXUS.store;
    const state = store.getState();

    if (state.isListening && !state.cloakActive) {
      stopLiveMonitoring();
      return;
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert('Microphone access is not supported by your browser.');
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });

      micStream = stream;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      micAudioContext = new AudioCtx();
      if (micAudioContext.state === 'suspended') {
        await micAudioContext.resume();
      }

      const source = micAudioContext.createMediaStreamSource(stream);

      const filterNode = micAudioContext.createBiquadFilter();
      filterNode.type = 'highpass';
      filterNode.frequency.value = store.getState().highpassHz || 80;

      const gainNode = micAudioContext.createGain();
      gainNode.gain.value = (store.getState().reactorOutput || 68) / 50;

      micAnalyser = micAudioContext.createAnalyser();
      micAnalyser.fftSize = 256;
      micAnalyser.smoothingTimeConstant = 0.65;

      micProcessor = micAudioContext.createScriptProcessor(4096, 1, 1);
      const silentSink = micAudioContext.createGain();
      silentSink.gain.value = 0;

      source.connect(filterNode);
      filterNode.connect(gainNode);
      gainNode.connect(micAnalyser);
      gainNode.connect(micProcessor);
      micProcessor.connect(silentSink);
      silentSink.connect(micAudioContext.destination);

      const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProto}//${window.location.host}/ws/live-audio`;
      liveWs = new WebSocket(wsUrl);
      liveWs.binaryType = 'arraybuffer';

      liveWs.onopen = () => {
        store.setState({ wsConnected: true });
      };

      let lastLiveAlertTs = 0;

      liveWs.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          const s = store.getState();
          const minAlertConf = s.neuralSyncRate != null ? s.neuralSyncRate : 75;

          const pyClass = msg.python_prediction || msg.predicted_class || 'Background Noise';
          const gtmClass = msg.gtm_prediction || msg.predicted_class || 'Background Noise';
          const pyConf = Math.round(Number(msg.python_confidence || msg.confidence || 0) * 100);
          const gtmConf = Math.round(Number(msg.gtm_confidence || msg.confidence || 0) * 100);
          const avgConf = Math.round((pyConf + gtmConf) / 2);
          const sevRaw = msg.severity || 'Low';

          const gateState = global.NEXUS.computeSeverityState
            ? global.NEXUS.computeSeverityState(sevRaw, avgConf, pyConf, minAlertConf)
            : { severity: sevRaw, passesAlertGate: avgConf >= minAlertConf, sectorThreatLevel: 1, emergencyProtocol: false, combatMode: false };

          const partial = Object.assign({
            currentSound: (msg.predicted_class || pyClass).toUpperCase(),
            pythonPrediction: pyClass,
            pythonConfidence: pyConf,
            gtmPrediction: gtmClass,
            gtmConfidence: gtmConf,
            consistencyStatus: (msg.consistency_status || 'ACCEPTABLE MATCH').toUpperCase(),
            warpCharge: avgConf,
            quantumCoherence: avgConf,
          }, gateState);

          if (msg.snr_db != null) {
            partial.snrDb = Number(msg.snr_db);
          }
          if (msg.total_detections != null) {
            partial.anomalyCount = Number(msg.total_detections);
          }

          store.setState(partial);

          const sevLower = String(gateState.severity || 'Low').toLowerCase();
          if (gateState.passesAlertGate && (sevLower === 'critical' || sevLower === 'high' || sevLower === 'medium')) {
            const now = Date.now();
            if (now - lastLiveAlertTs > 3500 && global.NEXUS.ensureStarted && global.NEXUS.soundEngine) {
              lastLiveAlertTs = now;
              const alertLvl = sevLower === 'critical' ? 'CRIT' : sevLower === 'high' ? 'WARN' : 'INFO';
              global.NEXUS.ensureStarted().then(() => {
                global.NEXUS.soundEngine.playAlert(alertLvl);
              });
            }
          }

          if (msg.audio_id) {
            syncDatabaseTelemetry(false);
          }
        } catch (e) {
          console.warn('WS parse error:', e);
        }
      };

      liveWs.onclose = () => {
        store.setState({ wsConnected: false });
      };

      pcmAccumulator = [];
      pcmSampleCount = 0;
      const targetChunkSamples = Math.round(micAudioContext.sampleRate * 1.4);

      micProcessor.onaudioprocess = (audioEvt) => {
        if (!store.getState().isListening || !liveWs || liveWs.readyState !== WebSocket.OPEN) return;
        const inputChan = audioEvt.inputBuffer.getChannelData(0);
        const copy = new Float32Array(inputChan.length);
        copy.set(inputChan);
        pcmAccumulator.push(copy);
        pcmSampleCount += copy.length;

        if (pcmSampleCount >= targetChunkSamples) {
          const merged = new Float32Array(pcmSampleCount);
          let offset = 0;
          for (let i = 0; i < pcmAccumulator.length; i++) {
            merged.set(pcmAccumulator[i], offset);
            offset += pcmAccumulator[i].length;
          }
          pcmAccumulator = [];
          pcmSampleCount = 0;

          const downsampled = downsampleFloat32(merged, micAudioContext.sampleRate, 16000);
          try {
            liveWs.send(downsampled.buffer);
          } catch (_) {}
        }
      };

      global.NEXUS.audioAnalyser = micAnalyser;
      global.NEXUS.audioContext = micAudioContext;
      global.NEXUS.micGainNode = gainNode;
      global.NEXUS.micFilterNode = filterNode;

      store.getState().setListening(true);
      store.getState().setCloak(false);
      store.getState().pushAlert(
        'INFO',
        'Diagnostic Microphone connected to Dual-AI WebSocket (/ws/live-audio) — 16kHz calibration stream active',
        { code: 'DIAG-LIVE', tag: 'WEBSOCKET // ONLINE' }
      );

      if (micProcessInterval) clearInterval(micProcessInterval);
      const timeData = new Uint8Array(micAnalyser.fftSize);
      const freqData = new Uint8Array(micAnalyser.frequencyBinCount);

      micProcessInterval = setInterval(() => {
        if (!micAnalyser || !store.getState().isListening) return;

        micAnalyser.getByteTimeDomainData(timeData);
        micAnalyser.getByteFrequencyData(freqData);

        let sumSquares = 0;
        let peakVal = 0;
        for (let i = 0; i < timeData.length; i++) {
          const norm = (timeData[i] - 128) / 128;
          sumSquares += norm * norm;
          const absVal = Math.abs(norm);
          if (absVal > peakVal) peakVal = absVal;
        }
        const rms = Math.sqrt(sumSquares / timeData.length);
        const peakDbfs = peakVal > 0.0001 ? Math.max(-60, 20 * Math.log10(peakVal)).toFixed(1) : '-60.0';
        const rmsDbfs = rms > 0.0001 ? Math.max(-60, 20 * Math.log10(rms)).toFixed(1) : '-60.0';

        const gateDb = store.getState().noiseGateDb != null ? store.getState().noiseGateDb : -42;
        const gateOpen = Number(rmsDbfs) >= gateDb;

        let maxFreqVal = 0;
        let maxFreqIdx = 0;
        let freqSum = 0;
        let bSub = 0, bLow = 0, bMid = 0, bHigh = 0;
        const binCount = freqData.length;

        for (let i = 0; i < binCount; i++) {
          const v = gateOpen ? freqData[i] : freqData[i] * 0.15;
          freqSum += v;
          if (v > maxFreqVal) {
            maxFreqVal = v;
            maxFreqIdx = i;
          }
          if (i < 4) bSub += v;
          else if (i < 16) bLow += v;
          else if (i < 48) bMid += v;
          else bHigh += v;
        }

        const nyquist = (micAudioContext ? micAudioContext.sampleRate : 44100) / 2;
        const peakHz = (maxFreqIdx / binCount) * nyquist;
        const peakKhz = Math.max(0.1, peakHz / 1000);

        const bandSubPct = Math.min(100, Math.max(8, Math.round((bSub / (4 * 255)) * 130)));
        const bandLowPct = Math.min(100, Math.max(8, Math.round((bLow / (12 * 255)) * 140)));
        const bandMidPct = Math.min(100, Math.max(8, Math.round((bMid / (32 * 255)) * 160)));
        const bandHighPct = Math.min(100, Math.max(8, Math.round((bHigh / ((binCount - 48) * 255)) * 180)));

        const avgEnergy = freqSum / binCount;
        const snrEst = Math.max(12, Math.min(48, +(20 * Math.log10(Math.max(2, avgEnergy)) - 4).toFixed(1)));
        const prevWave = store.getState().spectralWave || [];
        const nextWave = [...prevWave.slice(1), Math.min(96, Math.max(10, Math.round((avgEnergy / 255) * 160 + 15)))];

        store.setState({
          inputLevelDb: peakDbfs,
          rmsLevelDb: rmsDbfs,
          tachyonFrequency: peakKhz,
          snrDb: snrEst,
          freqBands: [bandSubPct, bandLowPct, bandMidPct, bandHighPct],
          spectralWave: nextWave,
          shieldIntegrity: Math.max(60, Math.min(100, 100 - (peakVal > 0.92 ? 25 : 0))),
        });

        const currentStreams = store.getState().dataStreams;
        if (currentStreams && currentStreams.length >= 6) {
          const s0 = Math.min(95, Math.max(10, Math.round(rms * 180 + 15)));
          const s1 = Math.min(95, Math.max(10, Math.round((maxFreqVal / 255) * 95)));
          const s2 = Math.min(95, Math.max(10, Math.round(peakVal * 95)));
          const s3 = bandMidPct;
          const s4 = bandLowPct;
          const s5 = Math.min(95, Math.round(snrEst * 1.9));

          const updatedStreams = currentStreams.map((stream, idx) => {
            const val = idx === 0 ? s0 : idx === 1 ? s1 : idx === 2 ? s2 : idx === 3 ? s3 : idx === 4 ? s4 : s5;
            const newValues = stream.values.slice(1);
            newValues.push(val);
            return Object.assign({}, stream, { values: newValues });
          });
          store.setState({ dataStreams: updatedStreams });
        }
      }, 80);

    } catch (err) {
      console.warn('Microphone permission denied or device not found:', err);
      store.getState().pushAlert('WARN', 'Microphone permission denied or device unavailable', { code: 'MIC-ERR' });
      store.getState().setListening(false);
    }
  }

  function stopLiveMonitoring() {
    const store = global.NEXUS.store;
    if (micProcessInterval) {
      clearInterval(micProcessInterval);
      micProcessInterval = null;
    }
    if (liveWs) {
      try { liveWs.close(); } catch (_) {}
      liveWs = null;
    }
    if (micProcessor) {
      try { micProcessor.disconnect(); } catch (_) {}
      micProcessor = null;
    }
    if (micStream) {
      micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
    }
    if (micAudioContext) {
      try { micAudioContext.close(); } catch (_) {}
      micAudioContext = null;
    }
    global.NEXUS.audioAnalyser = null;
    global.NEXUS.audioContext = null;
    global.NEXUS.micGainNode = null;
    global.NEXUS.micFilterNode = null;

    store.setState({
      isListening: false,
      wsConnected: false,
    });
    syncDatabaseTelemetry(false);
  }

  function togglePrivacy() {
    const store = global.NEXUS.store;
    const current = store.getState().cloakActive;
    if (!current) {
      stopLiveMonitoring();
      store.getState().setCloak(true);
      store.getState().pushAlert('WARN', 'Hardware Privacy Engaged — Microphone & WebSocket Disconnected', { code: 'PRV-LOCK' });
    } else {
      store.getState().setCloak(false);
      store.getState().pushAlert('INFO', 'Hardware Privacy Disengaged — Ready to monitor', { code: 'PRV-OPEN' });
    }
  }

  // ── 2. REAL AUDIO ANALYSIS VIA BACKEND & MONGODB ─────────────
  async function analyzeAudioFile(file) {
    const store = global.NEXUS.store;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('zone_name', 'FACILITY-BAY-01');

    try {
      const resp = await fetch('/api/app/audio/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!resp.ok) {
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || errJson.message || `Server responded with ${resp.status}`);
      }

      const data = await resp.json();
      applyDetectionResult(data);
      await syncDatabaseTelemetry(false);
      return data;
    } catch (err) {
      console.error('Analysis failed:', err);
      store.getState().pushAlert('CRIT', `Analysis failed: ${err.message}`, { code: 'ERR-500' });
      throw err;
    }
  }

  function applyDetectionResult(data) {
    const store = global.NEXUS.store;
    const soundEngine = global.NEXUS.soundEngine;
    const ensureStarted = global.NEXUS.ensureStarted;
    const s = store.getState();

    const ev = data.event || {};
    const py = data.python_model || { predicted_class: ev.python_prediction, confidence: ev.python_confidence };
    const gtm = data.gtm_model || { predicted_class: ev.gtm_prediction, confidence: ev.gtm_confidence };
    const consensus = data.consensus || { consistency_status: ev.consistency_status, severity: ev.severity };
    const quality = data.quality || { snr_db: ev.snr_db, quality: ev.quality };

    const detectedSound = py.predicted_class || 'Sound Detected';
    const pyConf = Math.round(Number(py.confidence || 0) * 100);
    const gtmConf = Math.round(Number(gtm.confidence || 0) * 100);
    const avgConf = Math.round((pyConf + gtmConf) / 2);
    const sevRaw = consensus.severity || 'Low';
    const minAlertConf = s.neuralSyncRate != null ? s.neuralSyncRate : 75;

    const gateState = global.NEXUS.computeSeverityState
      ? global.NEXUS.computeSeverityState(sevRaw, avgConf, pyConf, minAlertConf)
      : { severity: sevRaw, passesAlertGate: avgConf >= minAlertConf, sectorThreatLevel: 1, emergencyProtocol: false, combatMode: false };

    store.setState(Object.assign({
      currentSound: detectedSound.toUpperCase(),
      currentCategory: detectedSound,
      confidence: avgConf,
      pythonPrediction: py.predicted_class || detectedSound,
      pythonConfidence: pyConf,
      gtmPrediction: gtm.predicted_class || detectedSound,
      gtmConfidence: gtmConf,
      consistencyStatus: (consensus.consistency_status || 'ACCEPTABLE MATCH').toUpperCase(),
      warpCharge: avgConf,
      warpEnabled: true,
      snrDb: quality.snr_db != null ? +Number(quality.snr_db).toFixed(1) : 0,
      shieldIntegrity: quality.quality === 'Poor' ? 45 : 98,
      quantumCoherence: avgConf,
      anomalyCount: s.anomalyCount + 1,
    }, gateState));

    const sevLower = String(gateState.severity || 'Low').toLowerCase();
    if (gateState.passesAlertGate && ensureStarted && soundEngine) {
      const alertLevel = sevLower === 'critical' ? 'CRIT' : sevLower === 'high' ? 'WARN' : 'INFO';
      ensureStarted().then(() => {
        soundEngine.playAlert(alertLevel);
      });
    }
  }

  // ── 3. SCI-FI MODAL FOR AUDIO FILE ANALYSIS ──────────────────
  function openAudioModal() {
    let existing = document.getElementById('dectus-audio-modal-backdrop');
    if (existing) existing.remove();

    const backdrop = document.createElement('div');
    backdrop.id = 'dectus-audio-modal-backdrop';
    backdrop.style.cssText = `
      position:fixed;inset:0;background:rgba(2,6,12,0.88);backdrop-filter:blur(8px);
      z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;
    `;

    backdrop.innerHTML = `
      <div class="box-glow-cyan" style="
        background:#070d18;border:1px solid #00f5ff;box-shadow:0 0 35px rgba(0,245,255,0.25);
        border-radius:4px;width:100%;max-width:580px;color:#e2e8f0;font-family:'Share Tech Mono', monospace;
        position:relative;overflow:hidden;
      ">
        <div style="position:absolute;top:0;left:0;width:12px;height:12px;border-top:2px solid #00f5ff;border-left:2px solid #00f5ff;"></div>
        <div style="position:absolute;top:0;right:0;width:12px;height:12px;border-top:2px solid #00f5ff;border-right:2px solid #00f5ff;"></div>
        <div style="position:absolute;bottom:0;left:0;width:12px;height:12px;border-bottom:2px solid #00f5ff;border-left:2px solid #00f5ff;"></div>
        <div style="position:absolute;bottom:0;right:0;width:12px;height:12px;border-bottom:2px solid #00f5ff;border-right:2px solid #00f5ff;"></div>

        <div style="padding:14px 18px;border-bottom:1px solid rgba(0,245,255,0.2);display:flex;align-items:center;justify-content:space-between;background:rgba(0,245,255,0.03);">
          <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:8px;height:8px;background:#00f5ff;box-shadow:0 0 8px #00f5ff;border-radius:50%;"></div>
            <span style="font-family:'Orbitron', sans-serif;font-weight:700;font-size:12px;letter-spacing:0.14em;color:#00f5ff;">
              DIAGNOSTIC ACOUSTIC ANALYZER // UPLOAD PORTAL
            </span>
          </div>
          <button id="modal-close-btn" style="background:none;border:none;color:#94a3b8;font-size:16px;cursor:pointer;padding:2px 6px;">✕</button>
        </div>

        <div style="padding:18px;max-height:80vh;overflow-y:auto;">
          <div id="modal-drop-zone" style="
            border:2px dashed rgba(0,245,255,0.35);border-radius:4px;padding:26px 16px;text-align:center;
            background:rgba(0,245,255,0.02);cursor:pointer;transition:border-color 0.2s;margin-bottom:16px;
          ">
            <div style="font-size:24px;margin-bottom:8px;color:#00f5ff;">📡</div>
            <div style="font-family:'Orbitron';font-size:11px;font-weight:600;color:#fff;margin-bottom:4px;">
              DROP AUDIO FILE HERE OR CLICK TO BROWSE
            </div>
            <div style="font-size:10px;color:#94a3b8;margin-bottom:12px;">
              Supports WAV, MP3, FLAC, OGG, M4A · Max 50 MB
            </div>
            <input type="file" id="modal-file-input" accept="audio/*" style="display:none;" />
            <div id="modal-selected-filename" style="font-size:11px;color:#10b981;font-weight:bold;"></div>
          </div>

          <div id="modal-status-box" style="display:none;padding:12px;border:1px solid rgba(0,245,255,0.3);background:rgba(0,245,255,0.04);margin-bottom:14px;border-radius:2px;">
            <div id="modal-status-text" style="font-size:11px;color:#00f5ff;font-family:'Orbitron';">PROCESSING...</div>
          </div>

          <div id="modal-results" style="display:none;border-top:1px solid rgba(0,245,255,0.2);padding-top:14px;">
            <div style="font-family:'Orbitron';font-size:11px;color:#10b981;font-weight:700;margin-bottom:10px;">
              DUAL-AI DIAGNOSTIC RESULT CONFIRMED
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:10px;margin-bottom:12px;">
              <div style="background:rgba(0,0,0,0.3);padding:8px;border:1px solid rgba(0,245,255,0.15);">
                <div style="color:#94a3b8;font-size:8px;">PYTHON 2D-CNN</div>
                <div id="res-py" style="color:#00f5ff;font-weight:bold;font-size:12px;">—</div>
              </div>
              <div style="background:rgba(0,0,0,0.3);padding:8px;border:1px solid rgba(168,85,247,0.15);">
                <div style="color:#94a3b8;font-size:8px;">GTM VERIFIER</div>
                <div id="res-gtm" style="color:#a855f7;font-weight:bold;font-size:12px;">—</div>
              </div>
              <div style="background:rgba(0,0,0,0.3);padding:8px;border:1px solid rgba(16,185,129,0.15);">
                <div style="color:#94a3b8;font-size:8px;">CONSENSUS STATUS</div>
                <div id="res-consensus" style="color:#10b981;font-weight:bold;">—</div>
              </div>
              <div style="background:rgba(0,0,0,0.3);padding:8px;border:1px solid rgba(245,158,11,0.15);">
                <div style="color:#94a3b8;font-size:8px;">SEVERITY / SNR</div>
                <div id="res-severity" style="color:#fbbf24;font-weight:bold;">—</div>
              </div>
            </div>
            <div id="res-player-wrap" style="margin-top:8px;">
              <audio id="res-audio-player" controls style="width:100%;height:32px;filter:invert(0.9);"></audio>
            </div>
          </div>
        </div>

        <div style="padding:12px 18px;border-top:1px solid rgba(0,245,255,0.2);display:flex;justify-content:flex-end;gap:10px;background:rgba(0,245,255,0.02);">
          <button id="modal-cancel-btn" style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.2);color:#94a3b8;padding:7px 14px;font-family:'Share Tech Mono';font-size:10px;cursor:pointer;border-radius:2px;">
            CLOSE
          </button>
          <button id="modal-submit-btn" style="background:#00f5ff;border:none;color:#02060c;padding:7px 18px;font-family:'Orbitron';font-weight:700;font-size:10px;cursor:pointer;border-radius:2px;box-shadow:0 0 10px rgba(0,245,255,0.4);">
            ANALYZE AUDIO
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);

    const closeBtn = backdrop.querySelector('#modal-close-btn');
    const cancelBtn = backdrop.querySelector('#modal-cancel-btn');
    const dropZone = backdrop.querySelector('#modal-drop-zone');
    const fileInput = backdrop.querySelector('#modal-file-input');
    const filenameEl = backdrop.querySelector('#modal-selected-filename');
    const submitBtn = backdrop.querySelector('#modal-submit-btn');
    const statusBox = backdrop.querySelector('#modal-status-box');
    const statusText = backdrop.querySelector('#modal-status-text');
    const resultsBox = backdrop.querySelector('#modal-results');
    const resPy = backdrop.querySelector('#res-py');
    const resGtm = backdrop.querySelector('#res-gtm');
    const resConsensus = backdrop.querySelector('#res-consensus');
    const resSeverity = backdrop.querySelector('#res-severity');
    const resAudio = backdrop.querySelector('#res-audio-player');

    let selectedFile = null;

    function closeModal() {
      backdrop.remove();
    }
    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) closeModal();
    });

    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.style.borderColor = '#10b981'; });
    dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = 'rgba(0,245,255,0.35)'; });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = 'rgba(0,245,255,0.35)';
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        selectedFile = e.dataTransfer.files[0];
        filenameEl.textContent = `SELECTED: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`;
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        selectedFile = e.target.files[0];
        filenameEl.textContent = `SELECTED: ${selectedFile.name} (${(selectedFile.size / 1024).toFixed(1)} KB)`;
      }
    });

    submitBtn.addEventListener('click', async () => {
      if (!selectedFile) {
        alert('Please select or drop an audio file first.');
        return;
      }

      statusBox.style.display = 'block';
      statusText.style.color = '#00f5ff';
      statusText.textContent = 'EXTRACTING SPECTROGRAM & RUNNING DUAL-AI INFERENCE...';
      submitBtn.disabled = true;

      try {
        const res = await analyzeAudioFile(selectedFile);
        renderResults(res);
      } catch (err) {
        statusText.textContent = `ERROR: ${err.message}`;
        statusText.style.color = '#ef4444';
      } finally {
        submitBtn.disabled = false;
      }
    });

    function renderResults(data) {
      statusBox.style.display = 'none';
      resultsBox.style.display = 'block';

      const ev = data.event || {};
      const py = data.python_model || { predicted_class: ev.python_prediction, confidence: ev.python_confidence };
      const gtm = data.gtm_model || { predicted_class: ev.gtm_prediction, confidence: ev.gtm_confidence };
      const consensus = data.consensus || { consistency_status: ev.consistency_status, severity: ev.severity };
      const quality = data.quality || { snr_db: ev.snr_db, quality: ev.quality };

      resPy.textContent = `${py.predicted_class || '—'} (${Math.round((py.confidence || 0) * 100)}%)`;
      resGtm.textContent = `${gtm.predicted_class || '—'} (${Math.round((gtm.confidence || 0) * 100)}%)`;
      resConsensus.textContent = consensus.consistency_status || 'Acceptable Match';
      resSeverity.textContent = `${(consensus.severity || 'Normal').toUpperCase()} / ${quality.snr_db != null ? Number(quality.snr_db).toFixed(1) + ' dB' : 'Good'}`;

      if (data.audio_id) {
        resAudio.src = `/api/app/audio/${data.audio_id}/stream`;
        resAudio.load();
      }
    }
  }

  // ── 4. MOUNT APPLICATION SLOTS & START TELEMETRY POLLING ─────
  function mountApp() {
    const store = global.NEXUS.store;
    const root = document.getElementById('root');

    root.innerHTML = `
      <div class="app-root" id="app-root">
        <div class="app-topbar-slot" id="slot-topbar"></div>
        <div class="app-main">
          <div class="app-left-slot" id="slot-left"></div>
          <div class="app-center-slot" id="slot-center"></div>
          <div class="app-right-slot" id="slot-right"></div>
        </div>
        <div class="app-bottombar-slot" id="slot-bottombar"></div>
      </div>
    `;

    const appRoot = document.getElementById('app-root');

    function renderRootMode(state) {
      appRoot.classList.toggle('mode-emergency', state.emergencyProtocol);
      appRoot.classList.toggle('mode-combat', !state.emergencyProtocol && state.combatMode);
    }
    renderRootMode(store.getState());
    store.subscribe((state, prev) => {
      if (state.emergencyProtocol !== prev.emergencyProtocol || state.combatMode !== prev.combatMode) renderRootMode(state);
    });

    global.NEXUS.mountTopBar(document.getElementById('slot-topbar'));
    global.NEXUS.mountLeftPanel(document.getElementById('slot-left'));
    global.NEXUS.mountCenterPanel(document.getElementById('slot-center'));
    global.NEXUS.mountRightPanel(document.getElementById('slot-right'));
    global.NEXUS.mountBottomBar(document.getElementById('slot-bottombar'));

    syncDatabaseTelemetry(false);
    setInterval(() => syncDatabaseTelemetry(false), 4000);
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.toggleLiveMonitoring = toggleLiveMonitoring;
  global.NEXUS.togglePrivacy = togglePrivacy;
  global.NEXUS.openAudioModal = openAudioModal;
  global.NEXUS.analyzeAudioFile = analyzeAudioFile;
  global.NEXUS.syncDatabaseTelemetry = syncDatabaseTelemetry;

  document.addEventListener('DOMContentLoaded', mountApp);
})(window);
