---
name: replicate-motion-scene
description: Use when reverse-engineering, replicating, or translating video motion graphics, animations, or kinetic title sequences into performant Canvas 2D scene archetypes or Community .scene.json bundles for Motion Studio Pro
---

# Replicate Motion Scene: Video to Canvas 2D Archetype Reverse-Engineering Guide

This guide details the complete protocol for reverse-engineering video motion graphics, 3D animations, and kinetic title sequences into performant Canvas 2D scene archetypes for Motion Studio Pro.

Follow this methodology to analyze video source footage, decompose choreography, extract geometric primitives and velocity curves, and implement standard `ArchetypeRenderer` modules or standalone Community `.scene.json` bundles.

---

## 1. System Architecture Overview

Motion Studio Pro executes animations via a 60 FPS deterministic canvas rendering loop.

```
+-------------------------------------------------------------------+
|                        Motion Studio Pro                          |
|                                                                   |
|  +--------------------+        +-------------------------------+  |
|  | Audio Engine (FFT) |        | Timeline & Scene Sequence     |  |
|  | - beatPulse (0..1) |        | - localT = t - scene.start    |  |
|  | - currentBeat      |        | - dur = scene.end - scene.start|  |
|  +---------+----------+        +---------------+---------------+  |
|            |                                   |                  |
|            +-----------------+   +-------------+                  |
|                              v   v                                |
|                 +----------------------------+                    |
|                 | ArchetypeRenderOptions     |                    |
|                 +--------------+-------------+                    |
|                                |                                  |
|                                v                                  |
|                 +----------------------------+                    |
|                 | ArchetypeRenderer.render() |                    |
|                 +--------------+-------------+                    |
|                                |                                  |
|         +----------------------+----------------------+           |
|         v                                             v           |
|  +---------------------------+             +-------------------+  |
|  | Pass 1: Background Layer  |             | Pass 2: Foreground|  |
|  | - Gradients & Grid        |             | - Geometry & 3D   |  |
|  | - Perspective / Depth     |             | - Kinetic Text    |  |
|  +---------------------------+             | - Bloom & Flares  |  |
|                                            +-------------------+  |
+-------------------------------------------------------------------+
```

Key Architectural Tenets:
- **Stateless Execution:** Renderers never store internal frame-to-frame mutable state. Every visual attribute is derived purely from `localT`, `dur`, `beatPulse`, `currentBeat`, `scene`, and `style`.
- **Zero Canvas Leaks:** All canvas state mutations must be isolated inside `ctx.save()` / `ctx.restore()` blocks. Global alpha, blend modes, shadows, and stroke properties must always return to baseline.
- **Audio Reactivity:** Geometric structures react to transient drum hits through `beatPulse` (exponential decay envelope) and `currentBeat` (continuous phase rotation).
- **Hero Typography Auto-Suppression:** If your scene archetype features prominent centered typography in Pass 1, flag it with `hasHeroTypography: true` (in registry) or `"suppressBottomLyrics": true` (in `.scene.json`). Motion Studio Pro's Auto-Safe engine will automatically suppress Pass 2 bottom subtitles to prevent duplicate text collisions.
- **Vertical 9:16 Canvas:** The default studio resolution is 720x1280 (vertical mobile format). Adapt widescreen 16:9 motion elements by vertically stacking typography, framing focal geometry in the center core, and respecting bezel safe zones.
- **Self-Contained Sandbox:** Community `.scene.json` scripts execute inside `new Function('options', script)`. They MUST declare all math, easing, and drawing helpers inline. NEVER use `import` statements or assume external helper files are in scope.
- **Faithful Aesthetic & Tone:** Do NOT force neon glow, bloom flares, or heavy shadow blur onto every scene. If the reference clip has clean, minimal typography, crisp white geometry, or solid color palettes, preserve that clean aesthetic faithfully. Do NOT allow external theme styles to override the scene's intended color palette unless requested.
- **Zero Emojis:** Code, text, HUD overlays, JSON bundles, and metadata must adhere strictly to clean typographical formatting without emojis.

---

## 2. Video and Frame Choreography Breakdown Guide

When reversing a reference video clip, execute this structured analysis.

### Phase 0: Automated Video Deconstruction Protocol (`scripts/analyze_ref.py`)

Do not guess timing or eye-ball velocities from a moving video. Run the bundled deconstruction script:

```bash
python3 scripts/analyze_ref.py input.mp4 --dur 15 --fps 4 --hook 3 --out cache/ref_analysis
```

The tool produces a structured inspection folder with zero external dependencies:
1. **`sheet_00.jpg`, `sheet_01.jpg` (Timestamped Contact Sheets):** 24 frames per sheet sampled at 4 FPS with **exact second timestamps labeled under every frame** (e.g. `0.250s`, `0.500s`, `0.750s`).
2. **`strip_hook.jpg` (Consecutive Hook Frames):** Every single frame of the first 3 seconds laid out in sequence. **The hook is where top motion designers hide their core techniques:** how each word enters, smear frames, overshoot, particles, and transitions. Study it frame-by-frame.
3. **`cuts.txt` (Scene Cut Timestamps):** Automatic cut-point detection using FFmpeg scene detection (`select='gt(scene,0.3)'`).
4. **`spectrogram.png` & `audio.wav`:** Audio frequency spectrogram revealing exact bass and transient spikes to synchronize with `beatPulse`.
5. **`analysis.json` & `info.txt`:** Full format metadata (resolution, source FPS, average scene duration, recommended pacing).

### Phase A: Keyframe and Phase Extraction

Split the target clip duration into distinct motion phases relative to total duration `dur`:

1. **In-Point (p = 0.00 to 0.25):** Entrance acceleration, camera push-in, scale burst, or opacity ramp.
2. **Impact / Feature Point (p = 0.25 to 0.50):** Primary transient hit, geometry alignment, or lyric emphasis.
3. **Settle / Orbit Hold (p = 0.50 to 0.85):** Secondary drift, continuous rotation, breathing cycle, or orbital spin.
4. **Out-Point / Transition (p = 0.85 to 1.00):** Wipe, camera pullback, bloom flare dissolve, or velocity stretch.

### Phase B: Velocity Curves and Easing Formulas

Video motion graphics rely on non-linear easing. Never use linear interpolation for primary spatial movement.

#### Standard Easing Formulas

```typescript
// Clamp utility
export const clamp = (v: number, min: number, max: number): number =>
  Math.min(Math.max(v, min), max);

// Linear interpolation
export const lerp = (a: number, b: number, t: number): number =>
  a + (b - a) * clamp(t, 0, 1);

// Ease-Out Cubic: Rapid start with soft deceleration (ideal for reveals and snaps)
export const easeOutCubic = (t: number): number =>
  1 - Math.pow(1 - clamp(t, 0, 1), 3);

// Ease-In-Out Cubic: S-curve acceleration and deceleration (ideal for camera swings)
export const easeInOutCubic = (t: number): number => {
  const c = clamp(t, 0, 1);
  return c < 0.5 ? 4 * c * c * c : 1 - Math.pow(-2 * c + 2, 3) / 2;
};

// Ease-Out Expo: High explosive impulse settling smoothly
export const easeOutExpo = (t: number): number => {
  const c = clamp(t, 0, 1);
  return c === 1 ? 1 : 1 - Math.pow(2, -10 * c);
};

// Elastic Overshoot: Mechanical or playful bounce on settle
export const easeOutBack = (t: number, overshoot = 1.70158): number => {
  const c = clamp(t, 0, 1) - 1;
  return c * c * ((overshoot + 1) * c + overshoot) + 1;
};

// Segmented Normalizer: Maps a time window [t0, t1] to [0, 1] with an easing curve
export const windowEase = (
  time: number,
  t0: number,
  t1: number,
  easing: (v: number) => number = easeOutCubic
): number => {
  if (t1 <= t0) return time >= t1 ? 1 : 0;
  const progress = clamp((time - t0) / (t1 - t0), 0, 1);
  return easing(progress);
};
```

#### Cubic-Bezier Evaluation (CSS / After Effects Curve Matcher)

To replicate After Effects cubic bezier speed graphs `cubic-bezier(x1, y1, x2, y2)`:

```typescript
export function solveCubicBezier(
  p1x: number,
  p1y: number,
  p2x: number,
  p2y: number,
  t: number
): number {
  const clampedT = clamp(t, 0, 1);
  // Newton-Raphson approximation for parameter u where x(u) = clampedT
  let u = clampedT;
  for (let i = 0; i < 5; i++) {
    const currentX =
      3 * (1 - u) * (1 - u) * u * p1x +
      3 * (1 - u) * u * u * p2x +
      u * u * u;
    const dx =
      3 * (1 - u) * (1 - u) * p1x +
      6 * (1 - u) * u * (p2x - p1x) +
      3 * u * u * (1 - p2x);
    if (Math.abs(dx) < 1e-6) break;
    u -= (currentX - clampedT) / dx;
    u = clamp(u, 0, 1);
  }
  // Compute y(u)
  return (
    3 * (1 - u) * (1 - u) * u * p1y +
    3 * (1 - u) * u * u * p2y +
    u * u * u
  );
}
```

### Phase C: Geometry and Spatial Hierarchy

Deconstruct the video into layered elements:
1. **Distant Background:** Deep gradient radial falloff, starfields, scanlines, or horizon grid lines.
2. **Midground Geometric Scaffold:** Wireframe cubes, isometric cylinders, concentric orbital rings, stepped pyramids.
3. **Foreground Focal Target:** Hero shape, glowing energy orb, kinetic typography, dynamic transient strike elements.
4. **Atmospheric Overlay:** Bloom flashes, chromatic aberration fringes, vignette, and ambient particles.

### Phase D: Kinetic Lyric Typography & Auto-Safe Hero Suppression

Kinetic text must balance legibility and dynamic choreography:
- **Primary Lyric:** Prominent uppercase title (font weight 800 to 900, size 36px to 64px, tracked spacing).
- **Secondary Lyric:** Subheading or counterpoint lyric (font weight 600, size 18px to 28px).
- **Motion Patterns:**
  - Masked Slide-Up: Draw text inside a clipped bounding box with easeOutCubic offset.
  - Scale Punch: Scale from 1.25 down to 1.00 on the initial word timestamp.
  - Shadow Glow: Apply `ctx.shadowColor` and `ctx.shadowBlur` matching `style.theme.glowColor`.
- **Auto-Safe Hero Suppression Flag:**
  If your scene archetype renders prominent centered hero typography in Pass 1, you MUST mark:
  - In `SceneArchetypeRegistry.ts`: `hasHeroTypography: true`
  - In `.scene.json`: `"suppressBottomLyrics": true`
  This informs Motion Studio Pro's Auto-Safe engine to mute the bottom subtitle stream during this scene, preventing double-text overlap.

### Phase E: 9:16 Vertical Safe Zones & Layout Translation (16:9 to 9:16)

Most motion graphics references are widescreen 16:9 (`1920x1080`), whereas Motion Studio Pro operates on a 9:16 vertical canvas (`720x1280` base):

- **Vertical Stacking:** Translate horizontal layouts into vertical columns. Place the secondary lyric or scene eyebrow at `y = 0.18 * H`, the primary focal geometry at `cy = 0.44 * H`, and the primary hero lyric at `y = 0.68 * H` to `0.78 * H`.
- **Center Optical Core:** Keep all high-velocity elements within the central core `cx = 0.5 * W ± 0.38 * W`.
- **Lateral Safe Margins:** Ensure no text or critical geometry extends outside `[0.08 * W, 0.92 * W]` to avoid being clipped by stage bezels or mobile interface chrome.
- **Isotropic Scaling:** Calculate sizes using `const S = Math.min(W, H)` so visual proportions remain identical regardless of export resolution (720x1280 vs 1080x1920).

### Phase F: Relative Duration Normalization (Trimming Resilience)

In Motion Studio Pro, users can trim clips to any duration (e.g. 0.8s to 12.0s).

**CRITICAL RULE:** Never hardcode absolute time thresholds (e.g. `if (localT > 1.5)`). All keyframe calculations must be normalized against `dur`:

```typescript
// Always compute normalized safe progress
const safeDur = Math.max(0.1, dur);
const progress = clamp(localT / safeDur, 0, 1);

// Animate phases relative to total duration
const introProgress = windowEase(localT, 0, safeDur * 0.25, easeOutCubic);
const outroProgress = windowEase(localT, safeDur * 0.80, safeDur, easeInOutCubic);
```

### Phase G: Motion Intensity Calibration (Scale 1–5)

Match the aesthetic and motion intensity of the source reference. Do not force hyper-active effects onto a restrained piece:

| Tier | Pacing & Style | Visual Characteristics | Canvas 2D Elements to Use |
|---|---|---|---|
| **Tier 1: Restrained** | Corporate, Luxury, Editorial | Generous whitespace, slow push-ins, lower thirds, 1 font family, zero flashes | Crisp geometry, smooth cubic easing, subtle line strokes, no blur or bloom |
| **Tier 2: Clarity-First** | SaaS, Tech Explainer | Focus zooms, clean card elevations, crisp typography, cursor highlights | 2.5D card tilts, smooth bezier tracking, soft drop shadows (`shadowBlur: 10`) |
| **Tier 3: Dynamic** | Commercial, Promo | Paced reveals, orbital rings, step counters, beat-synced pulses | Concentric arcs, radial gradients, beat-scale punches (1.05x), subtle glow |
| **Tier 4: High Energy** | Social UGC, Brand Anthem | Kinetic punch zooms, kinetic word pops, directional smears | Chromatic split passes (2–4px), masked slide-ups, expanding shockwaves |
| **Tier 5: Hyper Frenetic** | UKG, Bass Music, Stutter Reel | Rapid cuts (<1.2s), strobe flashes, glitch offsets, high bloom | Full bloom flares (`lighter`), RGB stutter, matrix rune decode, audio shockwaves |

**The Golden Rule:** The more clarity and trust the message requires, the less decorative motion is applied. Every effect must serve attention, emphasis, or transition.

### Phase H: Color Hierarchy (60-30-10) & Eye-Trace Continuity

- **60-30-10 Composition:**
  - **60% Dominant Canvas:** Dark background, deep radial falloff, or clean solid color.
  - **30% Structural Scaffolding:** Geometric wireframes, isometric cubes, orbital rings, or card panels.
  - **10% High-Energy Accent:** Reserved strictly for hero words, audio pulse spikes, or the central glowing focal point.
- **Eye-Trace Continuity:** When transitioning between keyframe phases or cuts, keep the next focal point near where the previous one settled. Do not force the viewer's gaze to jump from bottom-left to top-right across a rapid cut. Lead with motion, then settle on text.

---

## 3. Canvas 2D Mathematics and Geometry Algorithms

### Isometric Projection Mathematics

True isometric projection uses an angle of 30 degrees (Math.PI / 6 radians).

```typescript
export interface Point3D {
  x: number;
  y: number;
  z: number;
}

export interface Point2D {
  x: number;
  y: number;
}

/**
 * Projects 3D world coordinates into 2D isometric canvas coordinates.
 * x: Right axis (+X moves down-right)
 * y: Depth axis (+Y moves down-left)
 * z: Vertical height (+Z moves straight up)
 */
export function projectIso(
  x: number,
  y: number,
  z: number,
  originX: number,
  originY: number,
  scale = 1
): Point2D {
  const cos30 = Math.cos(Math.PI / 6); // ~0.866025
  const sin30 = Math.sin(Math.PI / 6); // 0.5

  const screenX = originX + (x - y) * cos30 * scale;
  const screenY = originY + (x + y) * sin30 * scale - z * scale;

  return { x: screenX, y: screenY };
}
```

#### Depth Sorting for Isometric Objects

Render order determines visibility. Sort geometric faces or items by their depth metric:

```typescript
// For isometric scenes, depth increases with (x + y) and decreases with z:
const depthScore = item.x + item.y + item.z * 0.01;
items.sort((a, b) => (a.x + a.y) - (b.x + b.y));
```

#### Isometric Cube Rendering Algorithm

```typescript
export function drawIsoCube(
  ctx: CanvasRenderingContext2D,
  originX: number,
  originY: number,
  sizeX: number,
  sizeY: number,
  sizeZ: number,
  topColor: string,
  leftColor: string,
  rightColor: string
): void {
  const cos30 = Math.cos(Math.PI / 6);
  const sin30 = Math.sin(Math.PI / 6);

  // Top Face Vertices
  const t0 = { x: originX, y: originY - sizeZ };
  const t1 = { x: originX + sizeX * cos30, y: originY + sizeX * sin30 - sizeZ };
  const t2 = { x: originX + (sizeX - sizeY) * cos30, y: originY + (sizeX + sizeY) * sin30 - sizeZ };
  const t3 = { x: originX - sizeY * cos30, y: originY + sizeY * sin30 - sizeZ };

  // 1. Top Face
  ctx.fillStyle = topColor;
  ctx.beginPath();
  ctx.moveTo(t0.x, t0.y);
  ctx.lineTo(t1.x, t1.y);
  ctx.lineTo(t2.x, t2.y);
  ctx.lineTo(t3.x, t3.y);
  ctx.closePath();
  ctx.fill();

  // 2. Left Face
  ctx.fillStyle = leftColor;
  ctx.beginPath();
  ctx.moveTo(t3.x, t3.y);
  ctx.lineTo(t2.x, t2.y);
  ctx.lineTo(t2.x, t2.y + sizeZ);
  ctx.lineTo(t3.x, t3.y + sizeZ);
  ctx.closePath();
  ctx.fill();

  // 3. Right Face
  ctx.fillStyle = rightColor;
  ctx.beginPath();
  ctx.moveTo(t2.x, t2.y);
  ctx.lineTo(t1.x, t1.y);
  ctx.lineTo(t1.x, t1.y + sizeZ);
  ctx.lineTo(t2.x, t2.y + sizeZ);
  ctx.closePath();
  ctx.fill();
}
```

### Matrix Transformations and Nested Coordinate Systems

Always isolate transformations using paired `ctx.save()` and `ctx.restore()`.

```typescript
export function renderTransformedEntity(
  ctx: CanvasRenderingContext2D,
  pivotX: number,
  pivotY: number,
  rotationRad: number,
  scaleX: number,
  scaleY: number,
  drawFn: () => void
): void {
  ctx.save();
  ctx.translate(pivotX, pivotY);
  ctx.rotate(rotationRad);
  ctx.scale(scaleX, scaleY);

  drawFn();

  ctx.restore();
}
```

### Bezier Curves for Organic Motion Trails and Ribbons

To draw smooth kinetic ribbons and laser ribbons between points:

```typescript
export function drawRibbonTrail(
  ctx: CanvasRenderingContext2D,
  points: Array<{ x: number; y: number }>,
  strokeColor: string,
  lineWidth: number
): void {
  if (points.length < 2) return;

  ctx.save();
  ctx.strokeStyle = strokeColor;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);

  for (let i = 1; i < points.length - 1; i++) {
    const xc = (points[i].x + points[i + 1].x) * 0.5;
    const yc = (points[i].y + points[i + 1].y) * 0.5;
    ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
  }

  const last = points[points.length - 1];
  ctx.lineTo(last.x, last.y);
  ctx.stroke();
  ctx.restore();
}
```

### Radial Gradients, Bloom Flares, and Canvas Blend Modes

To produce glowing neon visuals in Canvas 2D without post-processing shaders:

```typescript
export function drawBloomFlare(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  innerRadius: number,
  outerRadius: number,
  coreColor: string,
  glowColor: string,
  alpha = 1.0
): void {
  if (outerRadius <= 0.1) return;

  ctx.save();
  // Additive blend mode for luminous optical flare stacking
  ctx.globalCompositeOperation = 'lighter';
  ctx.globalAlpha = clamp(alpha, 0, 1);

  const grad = ctx.createRadialGradient(cx, cy, innerRadius, cx, cy, outerRadius);
  grad.addColorStop(0.0, coreColor);
  grad.addColorStop(0.2, glowColor);
  grad.addColorStop(1.0, 'rgba(0, 0, 0, 0)');

  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(cx, cy, outerRadius, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();
}
```

#### Chromatic Aberration Simulation

Simulate chromatic aberration on explosive transient beats by drawing offset color-split passes:

```typescript
export function drawWithChromaticAberration(
  ctx: CanvasRenderingContext2D,
  offsetPx: number,
  renderContent: (ctx: CanvasRenderingContext2D, colorTint: string) => void
): void {
  if (offsetPx <= 0.5) {
    renderContent(ctx, '#ffffff');
    return;
  }

  ctx.save();
  ctx.globalCompositeOperation = 'screen';

  // Red Channel Offset Left
  ctx.save();
  ctx.translate(-offsetPx, 0);
  renderContent(ctx, 'rgba(255, 0, 50, 0.85)');
  ctx.restore();

  // Cyan Channel Offset Right
  ctx.save();
  ctx.translate(offsetPx, 0);
  renderContent(ctx, 'rgba(0, 240, 255, 0.85)');
  ctx.restore();

  // Green / Neutral Channel Center
  renderContent(ctx, 'rgba(255, 255, 255, 0.95)');

  ctx.restore();
}
```

---

## 4. Motion Graphics Recipe Catalog (Canvas 2D Patterns)

Battle-tested procedural motion patterns adapted from top motion design sequences:

### Recipe 1: 2.5D Perspective Pop & Extruded Depth

Simulates a tilted 3D card or UI panel with extruded side faces and dynamic light rim in pure Canvas 2D without WebGL overhead:

```typescript
export function draw25DCard(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  w: number,
  h: number,
  tiltXRad: number,
  tiltYRad: number,
  depthPx: number,
  faceColor: string,
  edgeColor: string,
  strokeColor: string
): void {
  ctx.save();
  ctx.translate(cx, cy);

  // Compute 2.5D sheared corner offsets
  const cosY = Math.cos(tiltYRad);
  const sinX = Math.sin(tiltXRad);
  const hw = (w * 0.5) * cosY;
  const hh = (h * 0.5);
  const shearY = (w * 0.5) * Math.sin(tiltYRad) * 0.5;
  const shearX = (h * 0.5) * sinX * 0.5;

  // Front face vertices
  const p0 = { x: -hw + shearX, y: -hh - shearY };
  const p1 = { x:  hw + shearX, y: -hh + shearY };
  const p2 = { x:  hw - shearX, y:  hh + shearY };
  const p3 = { x: -hw - shearX, y:  hh - shearY };

  // 1. Extruded Depth Shadow / Side Faces
  if (depthPx > 0.5) {
    ctx.fillStyle = edgeColor;
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p1.x + depthPx, p1.y + depthPx * 0.6);
    ctx.lineTo(p2.x + depthPx, p2.y + depthPx * 0.6);
    ctx.lineTo(p2.x, p2.y);
    ctx.closePath();
    ctx.fill();

    ctx.beginPath();
    ctx.moveTo(p2.x, p2.y);
    ctx.lineTo(p2.x + depthPx, p2.y + depthPx * 0.6);
    ctx.lineTo(p3.x + depthPx, p3.y + depthPx * 0.6);
    ctx.lineTo(p3.x, p3.y);
    ctx.closePath();
    ctx.fill();
  }

  // 2. Front Face
  ctx.fillStyle = faceColor;
  ctx.beginPath();
  ctx.moveTo(p0.x, p0.y);
  ctx.lineTo(p1.x, p1.y);
  ctx.lineTo(p2.x, p2.y);
  ctx.lineTo(p3.x, p3.y);
  ctx.closePath();
  ctx.fill();

  // 3. Highlight Stroke Rim
  if (strokeColor) {
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  ctx.restore();
}
```

### Recipe 2: Kinetic Tracking Collapse & Slam

Spreads letter spacing wide during entrance acceleration, then rapidly collapses tracking into a punchy, tight lockup on drum transient impact:

```typescript
export function renderTrackingCollapse(
  ctx: CanvasRenderingContext2D,
  text: string,
  cx: number,
  cy: number,
  progress: number, // 0.0 to 1.0
  fontSizePx: number,
  fontFamily: string,
  color: string,
  accentColor: string,
  beatPulse = 0
): void {
  ctx.save();

  // Phase 1: Rapid tracking collapse (0.0 to 0.4 progress)
  const collapseT = clamp(progress / 0.4, 0, 1);
  const trackingPx = lerp(fontSizePx * 0.45, 0, easeOutCubic(collapseT));

  // Phase 2: Transient punch scale on impact
  const scalePunch = 1.0 + (1 - collapseT) * 0.25 + beatPulse * 0.08;

  ctx.translate(cx, cy);
  ctx.scale(scalePunch, scalePunch);
  ctx.font = `800 ${fontSizePx}px "${fontFamily}", sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  // Fallback for browsers supporting experimental canvas letterSpacing
  try {
    (ctx as any).letterSpacing = `${trackingPx.toFixed(1)}px`;
    ctx.fillStyle = color;
    ctx.fillText(text.toUpperCase(), 0, 0);
    (ctx as any).letterSpacing = '0px';
  } catch {
    // Manual character advance fallback
    const chars = text.toUpperCase().split('');
    const charWidths = chars.map((c) => ctx.measureText(c).width);
    const totalW = charWidths.reduce((a, b) => a + b, 0) + (chars.length - 1) * trackingPx;
    let curX = -totalW * 0.5;

    ctx.fillStyle = color;
    for (let i = 0; i < chars.length; i++) {
      ctx.fillText(chars[i], curX + charWidths[i] * 0.5, 0);
      curX += charWidths[i] + trackingPx;
    }
  }

  ctx.restore();
}
```

### Recipe 3: Directional Motion Echo (Colored Motion Blur)

Simulates high-velocity directional motion blur in Canvas 2D without shader overhead by drawing offset ghost copies with decaying alpha:

```typescript
export function drawMotionEcho(
  ctx: CanvasRenderingContext2D,
  copies: number,
  dx: number,
  dy: number,
  accentColor: string,
  drawTarget: (ctx: CanvasRenderingContext2D, alpha: number) => void
): void {
  ctx.save();
  for (let i = copies; i >= 1; i--) {
    const fraction = i / (copies + 1);
    const alpha = (1 - fraction) * 0.4;
    ctx.save();
    ctx.translate(dx * fraction, dy * fraction);
    drawTarget(ctx, alpha);
    ctx.restore();
  }
  // Draw sharp hero pass
  drawTarget(ctx, 1.0);
  ctx.restore();
}
```

### Recipe 4: Audio-Reactive Concentric Arc Cascade

Generates high-energy concentric orbital rings that pulse and counter-rotate with musical beats:

```typescript
export function drawArcCascade(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  baseRadius: number,
  rings: number,
  currentBeat: number,
  beatPulse: number,
  strokeColor: string,
  glowColor: string
): void {
  ctx.save();
  for (let r = 0; r < rings; r++) {
    const radius = baseRadius + r * 28 + beatPulse * 16 * (r + 1);
    const dir = r % 2 === 0 ? 1 : -1;
    const startAngle = (currentBeat * 0.5 * dir) + (r * Math.PI * 0.25);
    const arcLength = Math.PI * (0.8 + beatPulse * 0.4);

    ctx.save();
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 2.5 + (r === 0 ? beatPulse * 2 : 0);
    ctx.shadowColor = glowColor;
    ctx.shadowBlur = 12 * (beatPulse + 0.2);

    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle, startAngle + arcLength);
    ctx.stroke();

    // Secondary counter-arc
    ctx.beginPath();
    ctx.arc(cx, cy, radius, startAngle + Math.PI, startAngle + Math.PI + (arcLength * 0.6));
    ctx.stroke();

    ctx.restore();
  }
  ctx.restore();
}
```

---

## 5. ArchetypeRenderer Interface Compliance

All scene renderers in Motion Studio Pro must conform to `ArchetypeRenderer` defined in `src/styles/renderers/types.ts`.

### Interface Definition

```typescript
import type { Scene, MotionStyle } from '../../types';

export interface ArchetypeRenderOptions {
  ctx: CanvasRenderingContext2D;
  width: number;
  height: number;
  localT: number;        // Elapsed scene seconds: 0.00 <= localT <= dur
  dur: number;           // Scene duration in seconds (e.g. 1.82)
  beatPulse: number;     // Normalized transient hit: 0.0 to 1.0
  currentBeat: number;   // Continuous beat counter: e.g. 14.25
  scene: Scene;          // Scene metadata (lyrics, archetype, remixChop)
  style: MotionStyle;    // Active theme colors, typography, bloom parameters
}

export interface ArchetypeRenderer {
  render(options: ArchetypeRenderOptions): void;
}
```

### Boilerplate Template for a New Archetype

Use this template as the starting point for every new archetype module:

```typescript
// src/styles/renderers/MyCustomScene.ts
import type { ArchetypeRenderer, ArchetypeRenderOptions } from './types';
import {
  clamp,
  lerp,
  easeOutCubic,
  easeInOutCubic,
  drawGlowingSphere,
} from './renderUtils';

export class MyCustomScene implements ArchetypeRenderer {
  public render(options: ArchetypeRenderOptions): void {
    const {
      ctx,
      width: W,
      height: H,
      localT,
      dur,
      beatPulse,
      currentBeat,
      scene,
      style,
    } = options;

    // Safety checks against non-positive durations
    const safeDur = Math.max(0.1, dur);
    const progress = clamp(localT / safeDur, 0, 1);

    // Style token extraction
    const bloomIntensity = style.theme?.bloomIntensity ?? 1.25;
    const fontFamily = style.typography?.fontFamily || 'Plus Jakarta Sans';
    const primaryColor = style.theme?.primaryColor || '#00f5ff';
    const accentColor = style.theme?.accentColor || '#ff007f';
    const glowColor = style.theme?.glowColor || '#ff00aa';

    const cx = W * 0.5;
    const cy = H * 0.5;

    ctx.save();

    // 1. Entrance and Pullback Camera Curves
    const introEase = easeOutCubic(clamp(localT / (safeDur * 0.35), 0, 1));
    const outroEase = easeInOutCubic(clamp((localT - safeDur * 0.75) / (safeDur * 0.25), 0, 1));
    const camScale = lerp(0.85, 1.05, introEase) + beatPulse * 0.04 - outroEase * 0.1;

    ctx.translate(cx, cy);
    ctx.scale(camScale, camScale);
    ctx.translate(-cx, -cy);

    // 2. Background Atmosphere
    const bgGrad = ctx.createRadialGradient(cx, cy, 40, cx, cy, Math.max(W, H) * 0.65);
    bgGrad.addColorStop(0, 'rgba(30, 20, 60, 0.6)');
    bgGrad.addColorStop(1, 'rgba(5, 5, 12, 0.95)');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // 3. Central Geometric Structure (Responsive to Beat Pulse)
    const ringRadius = 140 + beatPulse * 28;
    const rotAngle = currentBeat * (Math.PI / 4) + progress * Math.PI;

    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rotAngle);

    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 3.5;
    ctx.shadowColor = glowColor;
    ctx.shadowBlur = 18 * bloomIntensity;

    ctx.beginPath();
    ctx.arc(0, 0, ringRadius, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();

    // 4. Glowing Focal Core
    drawGlowingSphere(
      ctx,
      cx,
      cy,
      28 + beatPulse * 12,
      '#ffffff',
      glowColor,
      24,
      bloomIntensity
    );

    // 5. Kinetic Typography Layout
    if (scene.lyricPrimary) {
      ctx.save();
      const textAlpha = clamp(introEase * 1.5, 0, 1) * (1 - outroEase);
      ctx.globalAlpha = textAlpha;
      ctx.font = `800 ${Math.round(W * 0.052)}px "${fontFamily}", sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffffff';
      ctx.shadowColor = primaryColor;
      ctx.shadowBlur = 12 * bloomIntensity;

      const textY = cy + ringRadius + 60;
      ctx.fillText(scene.lyricPrimary.toUpperCase(), cx, textY);

      if (scene.lyricSecondary) {
        ctx.font = `600 ${Math.round(W * 0.032)}px "${fontFamily}", sans-serif`;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
        ctx.shadowBlur = 6;
        ctx.fillText(scene.lyricSecondary.toUpperCase(), cx, textY + 36);
      }
      ctx.restore();
    }

    ctx.restore();
  }
}
```

---

## 6. TDD Unit Testing Requirements

Every archetype renderer must be thoroughly verified with Vitest prior to registration. Tests must guarantee zero throws across the entire timeline window and protect against numerical instability.

### Vitest Test Suite Template

Create your unit test in `tests/styles/renderers/myCustomScene.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { MyCustomScene } from '../../../src/styles/renderers/MyCustomScene';
import type { ArchetypeRenderOptions } from '../../../src/styles/renderers/types';
import type { Scene, MotionStyle } from '../../../src/types';

function createMockContext(): CanvasRenderingContext2D {
  return {
    save: vi.fn(),
    restore: vi.fn(),
    translate: vi.fn(),
    rotate: vi.fn(),
    scale: vi.fn(),
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    fillText: vi.fn(),
    strokeText: vi.fn(),
    createLinearGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
    createRadialGradient: vi.fn(() => ({ addColorStop: vi.fn() })),
    globalAlpha: 1,
    globalCompositeOperation: 'source-over',
    shadowBlur: 0,
    shadowColor: 'transparent',
    lineWidth: 1,
  } as unknown as CanvasRenderingContext2D;
}

const mockScene: Scene = {
  id: 99,
  part: 1,
  start: 0.0,
  end: 2.0,
  title: 'Test Scene',
  lyricPrimary: 'REPLICATE',
  lyricSecondary: 'CHOREOGRAPHY',
  remixChop: false,
  archetype: 'my_custom_scene',
};

const mockStyle: MotionStyle = {
  id: 'test-style',
  name: 'Test Style',
  author: 'Vitest',
  theme: {
    primaryColor: '#00f5ff',
    secondaryColor: '#7b2cbf',
    accentColor: '#ff007f',
    backgroundColor: '#0a0a12',
    glowColor: '#ff00aa',
    bloomIntensity: 1.2,
  },
  typography: {
    fontFamily: 'Plus Jakarta Sans',
    primaryWeight: 800,
    secondaryWeight: 600,
    headlineTracking: '0.05em',
  },
};

describe('MyCustomScene Archetype Renderer', () => {
  it('renders without error at key lifecycle frames (t=0, t=mid, t=end)', () => {
    const renderer = new MyCustomScene();
    const ctx = createMockContext();

    const testTimes = [0.0, 1.0, 2.0];
    for (const localT of testTimes) {
      expect(() => {
        renderer.render({
          ctx,
          width: 720,
          height: 1280,
          localT,
          dur: 2.0,
          beatPulse: 0.5,
          currentBeat: 4.0,
          scene: mockScene,
          style: mockStyle,
        });
      }).not.toThrow();
    }
  });

  it('safely handles boundary clamping (localT < 0 and localT > dur)', () => {
    const renderer = new MyCustomScene();
    const ctx = createMockContext();

    const boundaryTimes = [-1.0, 5.0, 999.0];
    for (const localT of boundaryTimes) {
      expect(() => {
        renderer.render({
          ctx,
          width: 720,
          height: 1280,
          localT,
          dur: 2.0,
          beatPulse: 0.0,
          currentBeat: 0.0,
          scene: mockScene,
          style: mockStyle,
        });
      }).not.toThrow();
    }
  });

  it('reacts dynamically to audio FFT beatPulse', () => {
    const renderer = new MyCustomScene();
    const ctxRelaxed = createMockContext();
    const ctxBeating = createMockContext();

    renderer.render({
      ctx: ctxRelaxed,
      width: 720,
      height: 1280,
      localT: 1.0,
      dur: 2.0,
      beatPulse: 0.0,
      currentBeat: 2.0,
      scene: mockScene,
      style: mockStyle,
    });

    renderer.render({
      ctx: ctxBeating,
      width: 720,
      height: 1280,
      localT: 1.0,
      dur: 2.0,
      beatPulse: 1.0,
      currentBeat: 2.0,
      scene: mockScene,
      style: mockStyle,
    });

    // Both calls must execute draw operations
    expect(ctxRelaxed.arc).toHaveBeenCalled();
    expect(ctxBeating.arc).toHaveBeenCalled();
  });

  it('never passes NaN or Infinity coordinates to Canvas 2D calls', () => {
    const renderer = new MyCustomScene();
    const ctx = createMockContext();

    renderer.render({
      ctx,
      width: 720,
      height: 1280,
      localT: 1.0,
      dur: 2.0,
      beatPulse: 0.8,
      currentBeat: 3.5,
      scene: mockScene,
      style: mockStyle,
    });

    const checkNumericArgs = (mockFn: any) => {
      mockFn.mock.calls.forEach((callArgs: any[]) => {
        callArgs.forEach((arg) => {
          if (typeof arg === 'number') {
            expect(Number.isNaN(arg)).toBe(false);
            expect(Number.isFinite(arg)).toBe(true);
          }
        });
      });
    };

    checkNumericArgs(ctx.translate);
    checkNumericArgs(ctx.scale);
    checkNumericArgs(ctx.arc);
    checkNumericArgs(ctx.fillRect);
  });

  it('strictly balances save() and restore() calls to avoid state leaks', () => {
    const renderer = new MyCustomScene();
    const ctx = createMockContext();

    renderer.render({
      ctx,
      width: 720,
      height: 1280,
      localT: 0.5,
      dur: 2.0,
      beatPulse: 0.4,
      currentBeat: 1.2,
      scene: mockScene,
      style: mockStyle,
    });

    const saveCount = (ctx.save as any).mock.calls.length;
    const restoreCount = (ctx.restore as any).mock.calls.length;
    expect(saveCount).toBeGreaterThan(0);
    expect(saveCount).toBe(restoreCount);
  });
});
```

---

## 7. Studio Registration and Community Hub Integration

### In-Code Registration (`SceneArchetypeRegistry.ts`)

To add an archetype to the built-in system:

1. Export the renderer class from `src/styles/renderers/index.ts`.
2. Open `src/engine/SceneArchetypeRegistry.ts`.
3. Add the archetype definition to the `defaults` array in `registerDefaults()`:

```typescript
{
  id: 'my_custom_scene',
  name: '11. My Custom Scene',
  category: '3D Isometric', // 'Kinetic Typography' | 'Geometric Orbital' | '3D Isometric' | 'Architectural' | 'Tunnel & Warp'
  description: 'Detailed description of the motion graphics and camera choreography.',
  tags: ['isometric', 'neon', 'custom', 'geometry', 'reactive'],
  author: 'Your Name',
  defaultDuration: 1.83,
  defaultLyricPrimary: 'KINETIC TEXT',
  defaultLyricSecondary: 'SUBTITLE STREAM',
  hasHeroTypography: true, // Set true if the scene renders centered/prominent text in Pass 1 to trigger Auto-Safe subtitle suppression
  previewGradient: ['#00f5ff', '#ff007f'],
  renderer: new MyCustomScene(),
}
```

### Standalone Executable Scene Bundle (`.scene.json`)

To make the scene immediately uploadable into Motion Studio Pro without needing source code changes or developer compilation, package the entire Canvas 2D render code inside the `renderScript` property of a single `.scene.json` file.

#### Strict Sandbox Rules for `renderScript`
In `SceneHubModal.ts`, uploaded scripts are executed inside a lightweight runtime sandbox:
```javascript
const renderFn = new Function('options', sceneDef.renderScript);
```

1. **NO ES Module Imports:** Never write `import ...` or `export ...`. Doing so causes an immediate `SyntaxError: Cannot use import statement outside a module` in the browser.
2. **All Helpers Must Be Inlined:** Utility functions like `clamp`, `lerp`, `easeOutCubic`, and projection algorithms must be declared inside the function body.
3. **Double Typography Suppression:** If the scene contains prominent centered text, set `"suppressBottomLyrics": true` at the root of the JSON bundle.
4. **Valid JSON Serialization:** Use `JSON.stringify()` when generating programmatic JSON to ensure quotes and newlines (`\n`) are cleanly escaped.

#### Complete `.scene.json` Specification & Reference Template

```json
{
  "id": "my_custom_scene",
  "name": "My Custom Scene",
  "category": "3D Isometric",
  "description": "High-velocity isometric crystal towers pulsing with audio transients.",
  "tags": ["isometric", "crystal", "neon", "audio-reactive"],
  "author": "Community Creator",
  "defaultDuration": 2.0,
  "defaultLyricPrimary": "CRYSTAL PULSE",
  "defaultLyricSecondary": "ECHO DEPTH",
  "suppressBottomLyrics": true,
  "previewGradient": ["#00f5ff", "#7c4dff"],
  "renderScript": "const { ctx, width: W, height: H, localT, dur, beatPulse, currentBeat, scene, style } = options;\n\n// 1. Inline Math & Easing Utilities\nconst clamp = (v, min, max) => Math.min(Math.max(v, min), max);\nconst lerp = (a, b, t) => a + (b - a) * clamp(t, 0, 1);\nconst easeOutCubic = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);\nconst easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;\n\nconst safeDur = Math.max(0.1, dur);\nconst progress = clamp(localT / safeDur, 0, 1);\nconst cx = W * 0.5;\nconst cy = H * 0.44;\n\nctx.save();\n\n// 2. Background\nctx.fillStyle = '#0a0a14';\nctx.fillRect(0, 0, W, H);\n\n// 3. Audio-Reactive Core Geometry\nconst radius = (Math.min(W, H) * 0.22) + beatPulse * 24;\nctx.save();\nctx.translate(cx, cy);\nctx.rotate(currentBeat * 0.4 + progress * Math.PI);\nctx.strokeStyle = '#00f5ff';\nctx.lineWidth = 4 + beatPulse * 3;\nctx.shadowColor = '#00f5ff';\nctx.shadowBlur = 20;\nctx.beginPath();\nctx.arc(0, 0, radius, 0, Math.PI * 2);\nctx.stroke();\nctx.restore();\n\n// 4. Hero Kinetic Typography\nif (scene && scene.lyricPrimary) {\n  ctx.save();\n  const textAlpha = clamp(easeOutCubic(progress * 3), 0, 1);\n  ctx.globalAlpha = textAlpha;\n  ctx.font = '800 ' + Math.round(W * 0.065) + 'px sans-serif';\n  ctx.textAlign = 'center';\n  ctx.textBaseline = 'middle';\n  ctx.fillStyle = '#ffffff';\n  ctx.shadowColor = '#7c4dff';\n  ctx.shadowBlur = 15;\n  ctx.fillText(scene.lyricPrimary.toUpperCase(), cx, H * 0.74);\n  ctx.restore();\n}\n\nctx.restore();"
}
```

Users can drag and drop this `.scene.json` file directly into the **Community Scenes Hub** in Motion Studio Pro to immediately preview and append the scene to their active timeline.

---

## 8. Mandatory AI Agent Final Output Format (Creator Contract)

Do NOT output verbose, multi-page theoretical analysis of keyframes. The creator needs an immediate, working file, simple upload instructions, and a quick guide on how to request improvements.

Your response MUST follow this exact 3-part structure:

### Part 1: Standalone `.scene.json` File
Provide the complete, self-contained JSON object containing metadata, the `suppressBottomLyrics` flag, and the self-contained executable `renderScript` in a clean code block (or write it to `[scene_id].scene.json`).

### Part 2: How to Upload to Motion Studio Pro
Provide a 4-step guide:
1. Save the JSON code as `[scene_id].scene.json` (or copy the code block).
2. Open Motion Studio Pro and click **COMMUNITY SCENES** in the top navigation bar.
3. Drag and drop the `.scene.json` file into the upload dropzone (or click to browse).
4. Click **"Add Scene to Sequence"** to add it to your timeline, or **"Apply to Selected Clip"** to swap your active scene.

### Part 3: How to Tweak & Request Improvements
List 3 to 4 concrete prompt ideas the creator can ask you to adjust:
- **Colors & Atmosphere:** e.g., "Change the background to dark navy and make the arcs neon magenta."
- **Timing & Speed:** e.g., "Make the word reveal sequence happen twice as fast."
- **Camera & Perspective:** e.g., "Increase the camera zoom on the final focal word."
- **Audio Reactivity:** e.g., "Make the stroke glow pulse harder on drum hits."

---

## 9. Quality Checklist Before Completion

Before submitting or committing a newly reverse-engineered scene:

1. **Zero Emojis:** Verify the document, code comments, and UI strings contain zero emojis.
2. **Deterministic Time:** Verify the renderer produces identical frames for identical `localT` without reliance on `Date.now()` or global counters.
3. **Relative Duration:** Verify all animation keyframes derive from `progress = localT / dur` or `windowEase()`, with no hardcoded second cutoffs.
4. **Hero Typography Flag:** Verify `hasHeroTypography: true` (in registry) or `"suppressBottomLyrics": true` (in `.scene.json`) is set if the scene renders prominent centered text.
5. **Self-Contained Sandbox:** Verify `renderScript` contains NO `import` statements and declares all math/easing helpers inline.
6. **9:16 Mobile Framing:** Verify coordinates scale proportionally with `W` and `H` and stay within safe lateral margins (`[0.08 * W, 0.92 * W]`).
7. **Audio Reactivity:** Verify `beatPulse` and `currentBeat` meaningfully drive transient elements (stroke width, scale punch, rotation phase).
8. **Context State Cleanliness:** Ensure `ctx.save()` and `ctx.restore()` calls are strictly balanced.
9. **Test Suite Pass:** Run `npm test && npm run build` to confirm zero regressions and clean TypeScript compilation.
