---
name: replicate-motion-scene
description: Reverse-engineers video motion graphics into Canvas 2D scene archetypes for Motion Studio Pro
---

# Replicate Motion Scene: Video to Canvas 2D Archetype Reverse-Engineering Guide

This guide details the complete protocol for reverse-engineering video motion graphics, 3D animations, and kinetic title sequences into performant Canvas 2D scene archetypes for Motion Studio Pro.

Follow this methodology to analyze video source footage, decompose choreography, extract geometric primitives and velocity curves, and implement standard `ArchetypeRenderer` modules.

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
- **Zero Canvas Leaks:** All canvas state mutations must be isolated inside `ctx.save()` / `ctx.restore()` blocks. Global alpha, blend modes, and stroke properties must always return to baseline.
- **Audio Reactivity:** Geometric structures react to transient drum hits through `beatPulse` (exponential decay envelope) and `currentBeat` (continuous phase rotation).
- **Zero Emojis:** Code, text, HUD overlays, and metadata must adhere strictly to clean typographical formatting without emojis.

---

## 2. Video and Frame Choreography Breakdown Guide

When reversing a reference video clip, execute this four-phase analysis.

### Phase A: Keyframe and Phase Extraction

Split the target clip duration (typically 1.5 to 4.0 seconds) into distinct motion phases:

1. **In-Point (t = 0.00 to 0.25):** Entrance acceleration, camera push-in, scale burst, or opacity ramp.
2. **Impact / Feature Point (t = 0.25 to 0.50):** Primary transient hit, geometry alignment, or lyric emphasis.
3. **Settle / Orbit Hold (t = 0.50 to 0.85):** Secondary drift, continuous rotation, breathing cycle, or orbital spin.
4. **Out-Point / Transition (t = 0.85 to 1.00):** Wipe, camera pullback, bloom flare dissolve, or velocity stretch.

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

### Phase D: Kinetic Lyric Typography Placement

Kinetic text must balance legibility and dynamic choreography:
- **Primary Lyric:** Prominent uppercase title (font weight 800 to 900, size 36px to 64px, tracked spacing).
- **Secondary Lyric:** Subheading or counterpoint lyric (font weight 600, size 18px to 28px).
- **Motion Patterns:**
  - Masked Slide-Up: Draw text inside a clipped bounding box with easeOutCubic offset.
  - Scale Punch: Scale from 1.25 down to 1.00 on the initial word timestamp.
  - Shadow Glow: Apply `ctx.shadowColor` and `ctx.shadowBlur` matching `style.theme.glowColor`.

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

## 4. ArchetypeRenderer Interface Compliance

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

## 5. TDD Unit Testing Requirements

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

## 6. Studio Registration and Community Hub Integration

### In-Code Registration (`SceneArchetypeRegistry.ts`)

To add an archetype to the built-in system:

1. Export the renderer class from `src/styles/renderers/index.ts`.
2. Open `src/engine/SceneArchetypeRegistry.ts`.
3. Add the archetype definition to the `defaults` array in `registerDefaults()`:

```typescript
{
  id: 'my_custom_scene',
  name: '11. My Custom Scene',
  category: '3D Isometric', // Or 'Kinetic Typography', 'Geometric Orbital', 'Architectural', 'Tunnel & Warp'
  description: 'Detailed description of the motion graphics and camera choreography.',
  tags: ['isometric', 'neon', 'custom', 'geometry', 'reactive'],
  author: 'Your Name',
  defaultDuration: 1.83,
  defaultLyricPrimary: 'KINETIC TEXT',
  defaultLyricSecondary: 'SUBTITLE STREAM',
  previewGradient: ['#00f5ff', '#ff007f'],
  renderer: new MyCustomScene(),
}
```

### Standalone Executable Scene Bundle (`.scene.json`)

To make the scene immediately uploadable into Motion Studio Pro without needing source code changes or developer compilation, package the entire Canvas 2D render code inside the `renderScript` property of a single `.scene.json` file:

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
  "previewGradient": ["#00f5ff", "#7c4dff"],
  "renderScript": "function render(options) {\n  const { ctx, width: W, height: H, localT, dur, beatPulse, currentBeat, scene, style } = options;\n  // Full Canvas 2D rendering code\n}"
}
```

Users can drag and drop this `.scene.json` file directly into the **Community Scenes Hub** in Motion Studio Pro to immediately preview and append the scene to their active timeline.

---

## 7. Mandatory AI Agent Final Output Format (Creator Contract)

Do NOT output verbose, multi-page theoretical analysis of keyframes. The creator needs an immediate, working file, simple upload instructions, and a quick guide on how to request improvements.

Your response MUST follow this exact 3-part structure:

### Part 1: Standalone `.scene.json` File
Provide the complete, self-contained JSON object containing metadata and the executable `renderScript` in a clean code block (or write it to `[scene_id].scene.json`).

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

## 8. Quality Checklist Before Completion

Before submitting or committing a newly reverse-engineered scene:

1. **Zero Emojis:** Verify the document, code comments, and UI strings contain zero emojis.
2. **Deterministic Time:** Verify the renderer produces identical frames for identical `localT` without reliance on `Date.now()` or global counters.
3. **Audio Reactivity:** Verify `beatPulse` meaningfully drives transient elements (stroke width, glow intensity, scale punch).
4. **Context State Cleanliness:** Ensure `save()` and `restore()` calls are strictly balanced.
5. **Executable Bundle:** Ensure `renderScript` is valid JavaScript enclosed in the `.scene.json` object.
6. **Test Suite Pass:** Run `npm test && npm run build` to confirm zero regressions and clean TypeScript compilation.
