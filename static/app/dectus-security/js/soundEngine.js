/* ============================================================
   soundEngine.js — port of src/audio/soundEngine.js + useSound.js
   Uses Tone.js (loaded from CDN in index.html) exactly like the
   original React app did — same synths, same routing.
   ============================================================ */
(function (global) {
  'use strict';

  const HEX_NOTES = {
    RELAY: 'C4',
    SENSOR: 'E4',
    SHIELD: 'G4',
    WEAPON: 'A4',
    POWER: 'D4',
    COMM: 'F4',
  };

  class SoundEngine {
    constructor() {
      this.started = false;
      this._storeUnsub = null;

      this.reactorOsc = null;
      this.reactorFilter = null;
      this.reverb = null;
      this.alertSynth = null;
      this.clickSynth = null;
      this.warpSynth = null;
      this.hexSynth = null;
      this.combatSeq = null;
      this.combatSynth = null;
    }

    async start() {
      if (this.started) return;
      const Tone = global.Tone;
      if (!Tone) return; // Tone.js failed to load from CDN
      await Tone.start();
      this.started = true;

      this.reverb = new Tone.Reverb({ decay: 1.5, wet: 0.35 }).toDestination();

      this.reactorFilter = new Tone.Filter(400, 'lowpass').connect(this.reverb);
      this.reactorOsc = new Tone.Oscillator({ type: 'sawtooth', frequency: 80, volume: -28 }).connect(this.reactorFilter);
      this.reactorOsc.start();

      this.alertSynth = new Tone.FMSynth({
        harmonicity: 3,
        modulationIndex: 10,
        envelope: { attack: 0.01, decay: 0.3, sustain: 0.1, release: 0.5 },
        volume: -12,
      }).toDestination();

      this.clickSynth = new Tone.MetalSynth({
        frequency: 400,
        envelope: { attack: 0.001, decay: 0.05, release: 0.1 },
        harmonicity: 5.1,
        modulationIndex: 32,
        resonance: 4000,
        octaves: 1.5,
        volume: -16,
      }).toDestination();

      this.warpSynth = new Tone.Synth({
        oscillator: { type: 'sine' },
        envelope: { attack: 0.5, decay: 0.2, sustain: 0.8, release: 1.5 },
        volume: -20,
      }).connect(this.reverb);

      this.hexSynth = new Tone.PluckSynth({
        attackNoise: 1,
        dampening: 4000,
        resonance: 0.98,
        volume: -14,
      }).toDestination();

      this.combatSynth = new Tone.FMSynth({
        harmonicity: 1,
        modulationIndex: 8,
        envelope: { attack: 0.01, decay: 0.2, sustain: 0.3, release: 0.3 },
        volume: -14,
      }).toDestination();

      this.combatSeq = new Tone.Sequence(
        (time, note) => { this.combatSynth.triggerAttackRelease(note, '8n', time); },
        ['A3', 'C4', 'E4', null],
        '4n'
      );

      const store = global.NEXUS.store;
      this._storeUnsub = store.subscribe((state, prev) => {
        if (state.reactorOutput !== prev.reactorOutput) this.setReactorPitch(state.reactorOutput);
        if (state.warpCharge !== prev.warpCharge && state.warpEnabled) this.setWarpCharge(state.warpCharge);
        if (state.combatMode !== prev.combatMode) this.playCombatToggle(state.combatMode);
      });

      const { reactorOutput } = store.getState();
      this.setReactorPitch(reactorOutput);
    }

    setReactorPitch(val) {
      if (!this.reactorOsc) return;
      const freq = 60 + val * 2;
      this.reactorOsc.frequency.rampTo(freq, 0.4);
      this.reactorOsc.volume.rampTo(-40 + val * 0.15, 0.4);
    }

    playButton(variant) {
      if (!this.started) return;
      switch (variant) {
        case 'click':
          this.clickSynth.triggerAttackRelease('16n');
          break;
        case 'combat':
          this.alertSynth.triggerAttackRelease('D3', '8n');
          break;
        case 'cloak':
          this.warpSynth.triggerAttackRelease('C5', '0.5');
          this.warpSynth.frequency.rampTo(100, 0.6);
          break;
        case 'emergency':
          this.alertSynth.triggerAttackRelease('A2', '4n');
          setTimeout(() => this.alertSynth.triggerAttackRelease('D2', '4n'), 250);
          setTimeout(() => this.alertSynth.triggerAttackRelease('A1', '4n'), 500);
          break;
        case 'warp':
          this.warpSynth.triggerAttackRelease('G3', '1n');
          this.warpSynth.frequency.rampTo(800, 1.0);
          break;
        case 'lock':
          this.clickSynth.triggerAttackRelease('8n');
          setTimeout(() => this.clickSynth.triggerAttackRelease('16n'), 120);
          break;
        default:
          this.clickSynth.triggerAttackRelease('16n');
      }
    }

    playHexClick(type) {
      if (!this.hexSynth) return;
      const note = HEX_NOTES[type] || 'C4';
      this.hexSynth.triggerAttack(note);
    }

    playNodeToggle(engaged) {
      if (!this.warpSynth) return;
      if (engaged) {
        this.warpSynth.triggerAttackRelease('C4', '16n');
        setTimeout(() => this.warpSynth.triggerAttackRelease('E4', '16n'), 80);
      } else {
        this.warpSynth.triggerAttackRelease('E4', '16n');
        setTimeout(() => this.warpSynth.triggerAttackRelease('C4', '16n'), 80);
      }
    }

    playAlert(level) {
      if (!this.alertSynth) return;
      switch (level) {
        case 'INFO':
          this.alertSynth.triggerAttackRelease('G4', '16n');
          break;
        case 'WARN':
          this.alertSynth.triggerAttackRelease('E4', '8n');
          setTimeout(() => { if (this.alertSynth) this.alertSynth.triggerAttackRelease('A4', '8n'); }, 180);
          break;
        case 'CRIT':
          this.alertSynth.triggerAttackRelease('A4', '8n');
          setTimeout(() => { if (this.alertSynth) this.alertSynth.triggerAttackRelease('D5', '8n'); }, 180);
          setTimeout(() => { if (this.alertSynth) this.alertSynth.triggerAttackRelease('A4', '8n'); }, 360);
          setTimeout(() => { if (this.alertSynth) this.alertSynth.triggerAttackRelease('D5', '4n'); }, 540);
          break;
      }
    }

    setWarpCharge(val) {
      if (!this.warpSynth) return;
      if (val > 20) {
        const freq = 150 + (val / 100) * 600;
        this.warpSynth.frequency.rampTo(freq, 0.5);
      }
    }

    playCombatToggle(active) {
      if (active) {
        this.playButton('combat');
      } else if (this.combatSeq) {
        this.combatSeq.stop();
      }
    }

    dispose() {
      if (this._storeUnsub) this._storeUnsub();
      if (this.reactorOsc) { this.reactorOsc.stop(); this.reactorOsc.dispose(); }
      if (this.reactorFilter) this.reactorFilter.dispose();
      if (this.reverb) this.reverb.dispose();
      if (this.alertSynth) this.alertSynth.dispose();
      if (this.clickSynth) this.clickSynth.dispose();
      if (this.warpSynth) this.warpSynth.dispose();
      if (this.hexSynth) this.hexSynth.dispose();
      if (this.combatSeq) this.combatSeq.dispose();
      if (this.combatSynth) this.combatSynth.dispose();
      this.started = false;
    }
  }

  const soundEngine = new SoundEngine();

  async function ensureStarted() {
    if (!soundEngine.started) await soundEngine.start();
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.soundEngine = soundEngine;
  global.NEXUS.ensureStarted = ensureStarted;
})(window);
