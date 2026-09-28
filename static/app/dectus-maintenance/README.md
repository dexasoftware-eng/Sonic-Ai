# NEXUS COMMAND — vanilla HTML/CSS/JS port

This is a hand port of the original React + Vite "fantasy-dashboard" project
(React, Zustand, Framer Motion, @react-three/fiber, Tone.js, Tailwind) into
plain **HTML, CSS and JavaScript** — no build step, no npm install, no bundler.

## What changed, and why

Nothing about the original **project you uploaded uses MongoDB/Express/Node**
(there's no backend at all — it's a pure client-side React app), so "MERN → HTML/CSS/JS"
here really means "React → vanilla JS", which is what this conversion does.

| Original (React) | This version |
|---|---|
| React components (JSX) | Plain functions that build DOM with `innerHTML` / `createElement`, one file per original component |
| Zustand store | Hand-written pub/sub store in `js/store.js` with the exact same state shape and actions |
| Framer Motion animations | CSS transitions/keyframes (`css/style.css`) + small JS-driven style updates |
| Tailwind utility classes | Hand-written CSS classes in `css/style.css` that reproduce the same look |
| `@react-three/fiber` + `@react-three/postprocessing` (3D core) | Plain **Three.js** (r128 UMD build, loaded from a CDN) with the classic non-module `EffectComposer` / `UnrealBloomPass` addons — same bloom effect, no bundler needed |
| `Tone.js` via a React hook | The exact same **Tone.js** library, loaded from a CDN, wrapped in a small `SoundEngine` class (same synths, same routing) |

Two JS libraries are still used **on purpose**, loaded straight from a CDN via
`<script>` tags: **Three.js** (for the 3D quantum-core visualizer) and
**Tone.js** (for the sound engine). Reimplementing a full WebGL renderer or a
Web Audio synthesis engine by hand would not be "the same app" — using the
same libraries the original app used is what keeps the behavior identical.
Everything else (state, layout, styling, DOM updates, all game logic) is
hand-written vanilla JS.

## How to run it

Because it loads a couple of libraries from a CDN and uses plain `<script>`
tags (not ES modules), you can just **double-click `index.html`** and it will
open directly in your browser — no server, no `npm install`, no build step.

If your browser blocks anything when opened via `file://`, serving it
locally works too:

```bash
cd nexus-command
python3 -m http.server 8080
# then open http://localhost:8080
```

## File structure

```
index.html              — page shell, font + library <script> tags
css/style.css            — all styling (replaces Tailwind + index.css)
js/store.js               — app state (replaces Zustand store)
js/colors.js               — color helper functions
js/soundEngine.js           — Tone.js sound engine
js/quantumCore3d.js          — Three.js 3D quantum core scene
js/topbar.js                  — top command bar
js/bottombar.js                — bottom telemetry bar
js/leftpanel.js                  — reactor / shield / quantum / phase / exotic controls
js/rightpanel.js                   — synaptic nodes / bandwidth / alerts / comms
js/centerpanel.js                    — sector header / 3D core / hex grid / warp bar / sparklines
js/app.js                              — wires everything together (replaces App.jsx + main.jsx)
```

## Notes / known differences

- Framer Motion's spring physics and exit animations are approximated with
  CSS `transition`s — visually very close, but not pixel-identical physics.
- The 3D bloom post-processing uses Three.js r128's legacy (non-module)
  examples, since those work from plain `<script>` tags without a bundler.
- All game state, numbers, colors, and interactions (sliders, buttons, hex
  grid, alert log, warp charge, etc.) are ported 1:1 from the original store
  and component logic.
