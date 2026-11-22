---
name: Midnight Hypergraph
colors:
  surface: '#101221'
  surface-dim: '#101221'
  surface-bright: '#363848'
  surface-container-lowest: '#0b0d1b'
  surface-container-low: '#191b29'
  surface-container: '#1d1f2d'
  surface-container-high: '#272938'
  surface-container-highest: '#323443'
  on-surface: '#e1e1f5'
  on-surface-variant: '#cbc3d7'
  inverse-surface: '#e1e1f5'
  inverse-on-surface: '#2e2f3f'
  outline: '#958ea0'
  outline-variant: '#494454'
  surface-tint: '#d0bcff'
  primary: '#d0bcff'
  on-primary: '#3c0091'
  primary-container: '#a078ff'
  on-primary-container: '#340080'
  inverse-primary: '#6d3bd7'
  secondary: '#c3c0ff'
  on-secondary: '#1d00a5'
  secondary-container: '#3626ce'
  on-secondary-container: '#b3b1ff'
  tertiary: '#4cd7f6'
  on-tertiary: '#003640'
  tertiary-container: '#009eb9'
  on-tertiary-container: '#002f38'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e9ddff'
  primary-fixed-dim: '#d0bcff'
  on-primary-fixed: '#23005c'
  on-primary-fixed-variant: '#5516be'
  secondary-fixed: '#e2dfff'
  secondary-fixed-dim: '#c3c0ff'
  on-secondary-fixed: '#0f0069'
  on-secondary-fixed-variant: '#3323cc'
  tertiary-fixed: '#acedff'
  tertiary-fixed-dim: '#4cd7f6'
  on-tertiary-fixed: '#001f26'
  on-tertiary-fixed-variant: '#004e5c'
  background: '#101221'
  on-background: '#e1e1f5'
  surface-variant: '#323443'
typography:
  display:
    fontFamily: Plus Jakarta Sans
    fontSize: 3.5rem
    fontWeight: '800'
    lineHeight: 4rem
    letterSpacing: -0.03em
  display-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 2.25rem
    fontWeight: '800'
    lineHeight: 2.75rem
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 2.25rem
    fontWeight: '700'
    lineHeight: 2.75rem
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.75rem
    fontWeight: '700'
    lineHeight: 2.25rem
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.5rem
    fontWeight: '600'
    lineHeight: 2rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 1.125rem
    fontWeight: '400'
    lineHeight: 1.75rem
    letterSpacing: -0.005em
  body-md:
    fontFamily: Inter
    fontSize: 0.9375rem
    fontWeight: '400'
    lineHeight: 1.5rem
    letterSpacing: '0'
  body-sm:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.25rem
    letterSpacing: 0.005em
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 0.875rem
    fontWeight: '500'
    lineHeight: 1.375rem
    letterSpacing: -0.01em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '500'
    lineHeight: 1.125rem
    letterSpacing: '0'
  label-md:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '600'
    lineHeight: 1rem
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 0.6875rem
    fontWeight: '600'
    lineHeight: 0.875rem
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-2xs: 0.25rem
  space-xs: 0.5rem
  space-sm: 0.75rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
---

## Brand & Style

This design system targets next-generation artificial intelligence platforms, machine learning operations (MLOps), and high-throughput data intelligence dashboards. The visual personality balances technical rigor with futuristic luxury—evoking precision, immense computing power, and effortless control.

The aesthetic fuses **Dark Cyber-Minimalism** with **Luminous Glassmorphism**:
- Deep obsidian and midnight indigo canvases keep eye strain low during prolonged technical sessions.
- High-intensity spectral accents—radiant royal purple, electric indigo, electric cyan, and warm amber—guide visual focus to telemetry, prompt throughput, and inference health.
- Precise, thin luminous outlines replace dense drop shadows, simulating polished dark glass with neon edge refraction.
- Data typography is treated with extreme clarity, combining sleek geometric headings with hyper-legible tabular figures.

## Colors

The palette operates on layered midnight tones illuminated by high-chroma gradients and semantic signals:

- **Primary (`#8b5cf6` Royal Purple) & Secondary (`#4f46e5` Electric Indigo):** Drive core brand expressions, high-priority interactive states, gradient fills, and model inference states.
- **Tertiary (`#06b6d4` Luminous Cyan / `#14b8a6` Teal):** Reserved for real-time telemetry, tokens-per-second trackers, active pipeline nodes, and latency gauges.
- **Alert Semantics:**
  - Critical / Fault: `#f43f5e` (Electric Coral/Rose)
  - Warning / Rate Limit: `#f59e0b` (Radiant Amber)
  - Healthy / Verified: `#10b981` (Vivid Emerald)
- **Surfaces & Tiers:**
  - Canvas Root: `#0b0d1b` (Obsidian Midnight)
  - Surface Tier 1 (Cards, Sidebars): `#12152b`
  - Surface Tier 2 (Hover states, Modals, Menus): `#191e3d`
  - Surface Stroke: `rgba(139, 92, 246, 0.16)` (Subtle purple edge illumination)
  - Surface Stroke Strong: `rgba(139, 92, 246, 0.35)`
- **Text & Contrast:**
  - High Contrast / Primary: `#f8fafc` (96% luminance, passes WCAG AAA against base canvases)
  - Secondary Text: `#94a3b8`
  - Subtle / Muted: `#64748b`

## Typography

The typographic hierarchy is divided into three functional pillars:
1. **Display & Headings (Plus Jakarta Sans):** Geometric, contemporary, and confident. Heavy weights (700, 800) feature negative tracking for a cohesive, branded high-tech presence.
2. **Body & Interface (Inter):** Highly neutral and tuned for screen legibility at micro sizes. Neutral tracking and optimal line heights ensure effortless scanning in information-dense views.
3. **Data, Metrics & Code (JetBrains Mono):** Reserved for model tokens, JSON payloads, inference latencies, matrix weights, and system logs. Monospaced tabular alignment guarantees numerical data remains aligned across real-time streaming updates.

## Layout & Spacing

The dashboard employs a flexible 12-column responsive fluid grid designed to host multi-pane telemetry, prompt engineering canvases, and analytics cards without visual overcrowding:

- **Desktop (>= 1280px):** 12-column grid, `gutter: 1.5rem`, `margin: 2rem`. Sidebar retains a fixed width of `16rem` or collapsed to `4.5rem`, while central analytics flow freely with min-max constraints.
- **Tablet (768px - 1279px):** 8-column grid, `gutter: 1.25rem`, `margin: 1.5rem`. Secondary inspection drawers collapse into overlay sheets.
- **Mobile (< 768px):** 4-column single-column flow, `gutter: 1rem`, `margin: 1rem`. Multi-axis graphs collapse into stacked metric summaries.

Component spacing follows an 8pt baseline cadence (`0.5rem`, `1rem`, `1.5rem`, `2rem`), with a dedicated `0.25rem` micro-step for tight tabular layouts and pill tags.

## Elevation & Depth

Visual hierarchy uses **Luminous Dark Layering** rather than traditional murky drop shadows:

1. **Base Floor (Z0):** Flat `#0b0d1b` background featuring occasional localized background radial gradients of deep indigo (`radial-gradient(circle at 50% 0%, rgba(79, 70, 229, 0.12), transparent 70%)`).
2. **Standard Containers (Z1):** Surfaces colored `#12152b` with a crisp, low-opacity border: `1px solid rgba(139, 92, 246, 0.15)`. No shadow is necessary; the contrast between base `#0b0d1b` and surface `#12152b` defines depth.
3. **Elevated & Interactive Panels (Z2):** Hover states, popovers, and floating toolbars use `#191e3d` paired with an ambient violet-tinted backglow:
   `box-shadow: 0 10px 25px -5px rgba(11, 13, 27, 0.7), 0 0 20px -2px rgba(139, 92, 246, 0.15);`
   Border sharpens to `rgba(139, 92, 246, 0.3)`.
4. **Modals & Overlays (Z3):** Frosted glass styling: `background: rgba(18, 21, 43, 0.85); backdrop-filter: blur(16px); border: 1px solid rgba(139, 92, 246, 0.28);` along with a heavy viewport backdrop dim: `rgba(5, 6, 15, 0.75)`.

## Shapes

The design system utilizes **Rounded (Level 2)** geometry:
- Standard components (buttons, input fields, dropdown trigger targets, code blocks): `0.5rem` (`8px`).
- Mid-level containers (analytics cards, telemetry modules, conversational chat bubbles): `1rem` (`16px`).
- Modal sheets, command palettes, and primary hero cards: `1.5rem` (`24px`).
- Status pills, avatars, and telemetry tags: Fully round pill shapes (`9999px`) for quick organic differentiation against structured data grids.

## Components

### Buttons
- **Primary:** Gradient fill `linear-gradient(135deg, #8b5cf6 0%, #4f46e5 100%)`. High-contrast white text (`#ffffff`), font weight 600. Subtle glow on hover (`box-shadow: 0 0 16px rgba(139, 92, 246, 0.45)`). Active transform scale down to 0.98.
- **Secondary / Glass:** Background `rgba(139, 92, 246, 0.08)`, border `1px solid rgba(139, 92, 246, 0.24)`, text `#f8fafc`. Hover shifts background to `rgba(139, 92, 246, 0.16)`.
- **Ghost / Tertiary:** Transparent background, text `#94a3b8`, hover text `#f8fafc`, hover background `rgba(255, 255, 255, 0.04)`.

### Cards & Metric Modules
- Background `#12152b` with a 1px border `rgba(139, 92, 246, 0.15)`.
- Header area houses title in `label-md` uppercase (`#94a3b8`), trailing icon, or live status indicator.
- Metric values rendered in `headline-lg` with `JetBrains Mono` or `Plus Jakarta Sans`, supplemented by colored micro-badges (`#10b981` emerald for gains, `#f43f5e` rose for degradations).

### Telemetry Badges & Chips
- Fully rounded pills (`border-radius: 9999px`) using semi-transparent status tint fills:
  - *Active / Ready:* Background `rgba(6, 182, 212, 0.1)`, text `#06b6d4`, border `1px solid rgba(6, 182, 212, 0.25)` with an optional pulsing dot.
  - *Processing:* Background `rgba(139, 92, 246, 0.12)`, text `#c4b5fd`, border `1px solid rgba(139, 92, 246, 0.3)`.
  - *Error:* Background `rgba(244, 63, 94, 0.1)`, text `#f43f5e`, border `1px solid rgba(244, 63, 94, 0.25)`.

### Input Fields & Prompt Consoles
- Dark recessed background `#0e1022`, border `1px solid rgba(139, 92, 246, 0.2)`. Height `2.5rem` (single line) or auto-expanding for prompt areas.
- Text `#f8fafc`, placeholder `#475569`.
- **Focus State:** Border transitions to `#8b5cf6` accompanied by an electric ring `box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.25)`.

### Selection Controls (Checkboxes & Radios)
- Base size `1rem x 1rem`, background `#0e1022`, border `1px solid rgba(139, 92, 246, 0.35)`.
- Checked state fills with `linear-gradient(135deg, #8b5cf6, #4f46e5)`, checked checkmark or radio dot in solid white `#ffffff`.

### Tables & Data Lists
- Alternating row zebra styling is avoided. Rows rely on subtle bottom borders `1px solid rgba(255, 255, 255, 0.05)`.
- Row hover triggers smooth background transition to `rgba(139, 92, 246, 0.06)`.
- Numerical metrics align right and use `JetBrains Mono` with tabular numbers enabled.

### Dedicated AI Streaming Node
- For chat streams and token generation: conversational containers utilize a gradient border trail and glowing cyan cursor (`2px` solid `#06b6d4` with pulse animation) indicating active inference.