# Motion Studio Pro - Scene Replication Skills

Official AI agent skills and methodology for reverse-engineering video motion graphics into high-performance Canvas 2D scene archetypes for Motion Studio Pro.

---

## Overview

Motion Studio Pro renders real-time, audio-reactive 60 FPS kinetic typography and 3D visual sequences using an optimized HTML5 Canvas 2D pipeline.

This repository provides portable skills and agent instructions (`SKILL.md`) that allow AI coding assistants (Google Antigravity, Anthropic Claude Code, Cursor, GitHub Copilot, Codex, and compatible agents) to:
1. Deconstruct reference video clips into geometric primitives, keyframe phases, and easing curves.
2. Implement robust, stateless `ArchetypeRenderer` TypeScript modules.
3. Package and export reusable scene definitions into standard `.scene.json` bundles compatible with the Motion Studio Pro Community Hub.

---

## Supported AI Agent Environments

The skill instructions are distributed in standardized Markdown skill formats compatible across multiple agent ecosystems.

### 1. Google Antigravity

Install globally for all your Antigravity workspaces:
```bash
mkdir -p ~/.gemini/antigravity/skills/replicate-motion-scene
curl -sSL https://raw.githubusercontent.com/MAPscheidt/motion-studio-skills/main/skills/replicate-motion-scene/SKILL.md \
  -o ~/.gemini/antigravity/skills/replicate-motion-scene/SKILL.md
```

Or install locally in your Motion Studio Pro workspace:
```bash
mkdir -p .agents/skills/replicate-motion-scene
curl -sSL https://raw.githubusercontent.com/MAPscheidt/motion-studio-skills/main/.agents/skills/replicate-motion-scene/SKILL.md \
  -o .agents/skills/replicate-motion-scene/SKILL.md
```

### 2. Anthropic Claude Code

Install globally into your Claude Code skills directory:
```bash
mkdir -p ~/.claude/skills/replicate-motion-scene
curl -sSL https://raw.githubusercontent.com/MAPscheidt/motion-studio-skills/main/skills/replicate-motion-scene/SKILL.md \
  -o ~/.claude/skills/replicate-motion-scene/SKILL.md
```

Or install in your project root:
```bash
mkdir -p .claude/skills/replicate-motion-scene
curl -sSL https://raw.githubusercontent.com/MAPscheidt/motion-studio-skills/main/skills/replicate-motion-scene/SKILL.md \
  -o .claude/skills/replicate-motion-scene/SKILL.md
```

### 3. Cursor IDE

Install as a project rule or agent skill in Cursor:
```bash
mkdir -p .cursor/rules
curl -sSL https://raw.githubusercontent.com/MAPscheidt/motion-studio-skills/main/skills/replicate-motion-scene/SKILL.md \
  -o .cursor/rules/replicate-motion-scene.mdc
```

### 4. GitHub Copilot & Generic Agents

Add the reference skill to your repository's `.github` prompt directory or load it as project documentation:
```bash
mkdir -p .github/skills
curl -sSL https://raw.githubusercontent.com/MAPscheidt/motion-studio-skills/main/skills/replicate-motion-scene/SKILL.md \
  -o .github/skills/replicate-motion-scene.md
```

---

## 3-Step Creator Recipe

Once the skill is active in your agent, follow this 3-step prompt workflow to replicate motion graphics from video clips:

### Step 1: Supply Reference Video & Motion Breakdown

Prompt your agent with a link, video file path, or detailed motion breakdown:

```text
I want to replicate this 2.5-second motion graphic sequence for Motion Studio Pro.
Reference: [Attach video / provide link / paste breakdown]
- Key focus: Concentric neon isometric rings expanding with a central text reveal.
- Palette: Cyan (#00f5ff) and Magenta (#ff007f) on deep charcoal (#0a0a0f).
- Beat transient: Bass pulse triggers radial ring expansion and chromatic flare.
```

### Step 2: Request Easing & Geometry Synthesis

Ask the agent to synthesize the choreography using the `replicate-motion-scene` skill:

```text
Use your replicate-motion-scene skill to:
1. Deconstruct the keyframes into in-point, impact, settle, and out-point phases.
2. Select appropriate non-linear easing functions (easeOutCubic, easeInOutQuad).
3. Draft a stateless ArchetypeRenderer implementation in TypeScript.
```

### Step 3: Package into `.scene.json` and Import

Ask the agent to generate the archetype bundle:

```text
Export this archetype as a valid .scene.json definition with metadata (id, name, category, tags, author, defaultDuration, defaultLyricPrimary, defaultLyricSecondary, previewGradient).
```

Once generated, drag and drop the `.scene.json` file into Motion Studio Pro via **Community Hub -> Import Archetype** or copy the TypeScript class directly into `src/styles/renderers/`.

---

## Architecture & Rendering Pipeline

Motion Studio Pro uses a deterministic 60 FPS Canvas 2D pipeline designed for low latency, zero memory leaks, and reactive audio synchronization.

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

### Core Requirements for Renderers

1. **Stateless Execution:** Renderers MUST NOT store internal frame-to-frame mutable state. Every visual attribute is derived purely from `localT`, `dur`, `beatPulse`, `currentBeat`, `scene`, and `style`.
2. **Zero Canvas Leaks:** All canvas transformations and blend modes MUST be enclosed in `ctx.save()` and `ctx.restore()` blocks. Global alpha, blend modes, and stroke properties must return to baseline after execution.
3. **Audio Reactivity:** Geometries react to transient drum hits through `beatPulse` (exponential decay envelope between `0.0` and `1.0`) and `currentBeat` (continuous phase rotation).
4. **Resolution Independence:** All dimensions and coordinates must scale proportionally with `canvas.width` and `canvas.height` (`1920x1080` base viewport).
5. **Clean Typography:** Code, text overlays, and metadata must maintain strict typographic styling without emojis.

---

## Scene Archetype Schema (`.scene.json`)

Community archetypes are stored in portable JSON format:

```json
{
  "id": "cyber_glitch_vortex",
  "name": "Cyber Glitch Vortex",
  "category": "Tunnel & Warp",
  "description": "High-velocity radial tunnel with chromatic dispersion lines, depth rings, and transient audio-reactive burst flashes.",
  "tags": [
    "warp",
    "tunnel",
    "cyber",
    "reactive",
    "chromatic",
    "burst"
  ],
  "author": "Joe Doe",
  "defaultDuration": 1.82,
  "defaultLyricPrimary": "HYPERSPACE DRIVE",
  "defaultLyricSecondary": "SYSTEM NOMINAL",
  "previewGradient": [
    "#00f5ff",
    "#ff007f"
  ]
}
```

### Schema Properties

| Property | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique lowercase alphanumeric identifier (e.g. `orbital_rings`). |
| `name` | `string` | Human-readable title displayed in the archetype browser. |
| `category` | `string` | Categorization group (`Kinetic Typography`, `3D Isometric`, `Geometric Orbital`, `Architectural`, `Tunnel & Warp`). |
| `description` | `string` | Concise description of the visual choreography and effects. |
| `tags` | `string[]` | Search and filter keywords. |
| `author` | `string` | Creator attribution or GitHub username. |
| `defaultDuration`| `number` | Default clip length in seconds (typically `1.5` to `3.0`). |
| `defaultLyricPrimary` | `string` | Sample primary lyric displayed in previews. |
| `defaultLyricSecondary` | `string` | Sample secondary lyric or sub-caption. |
| `previewGradient` | `[string, string]` | Two-color CSS hex tuple used for the card background gradient. |

---

## Repository Structure

```
motion-studio-skills/
|-- .agents/
|   \-- skills/
|       \-- replicate-motion-scene/
|           \-- SKILL.md             # Antigravity project skill format
|-- skills/
|   \-- replicate-motion-scene/
|       \-- SKILL.md                 # Universal skill format (Claude, Antigravity)
|-- examples/
|   \-- sample-scene.scene.json      # Valid sample archetype definition
|-- .gitignore
|-- LICENSE                          # MIT License
\-- README.md
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
Copyright (c) 2026 Motion Studio Pro Contributors.
