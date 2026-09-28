/* ============================================================
   colors.js — port of src/utils/colors.js
   ============================================================ */
(function (global) {
  'use strict';

  function lerpHex(a, b, t) {
    const parse = (hex) => [
      parseInt(hex.slice(1, 3), 16),
      parseInt(hex.slice(3, 5), 16),
      parseInt(hex.slice(5, 7), 16),
    ];
    const [ar, ag, ab] = parse(a);
    const [br, bg, bb] = parse(b);
    const r = Math.round(ar + (br - ar) * t);
    const g = Math.round(ag + (bg - ag) * t);
    const bl = Math.round(ab + (bb - ab) * t);
    return `rgb(${r},${g},${bl})`;
  }

  function tachyonToColor(freq) {
    if (freq <= 3.3) return lerpHex('#38bdf8', '#10b981', freq / 3.3);
    if (freq <= 6.6) return lerpHex('#10b981', '#f59e0b', (freq - 3.3) / 3.3);
    return lerpHex('#f59e0b', '#ef4444', (freq - 6.6) / 3.4);
  }

  function hexAlpha(color, alpha) {
    if (color.startsWith('rgb')) {
      return color.replace('rgb', 'rgba').replace(')', `,${alpha})`);
    }
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function colorToRgb(color) {
    if (color.startsWith('#')) {
      return [
        parseInt(color.slice(1, 3), 16),
        parseInt(color.slice(3, 5), 16),
        parseInt(color.slice(5, 7), 16),
      ];
    }
    const m = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
    return [0, 245, 255];
  }

  function colorToThree(color) {
    const [r, g, b] = colorToRgb(color);
    return [r / 255, g / 255, b / 255];
  }

  global.NEXUS = global.NEXUS || {};
  global.NEXUS.colors = { lerpHex, tachyonToColor, hexAlpha, colorToRgb, colorToThree };
})(window);
