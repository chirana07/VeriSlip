---
name: VeriSlip Visual System
description: Paper-and-ink forensic evidence console for payment fraud detection
colors:
  primary: "#2457d6"
  neutral-bg: "#f4f6f8"
  surface: "#ffffff"
  surface-muted: "#edf1f5"
  surface-dark: "#172131"
  ink: "#18212f"
  ink-soft: "#4f5d70"
  muted: "#5e6c84"
  line: "#d9e0e8"
  line-strong: "#c3ccd8"
  teal: "#087f6b"
  teal-light: "#edf8f5"
  teal-border: "#b8ded5"
  amber: "#a96c00"
  amber-light: "#fff7e7"
  amber-border: "#ebd3a0"
  rose: "#bd3b49"
  rose-light: "#fff0f2"
  rose-border: "#e9bbc1"
  violet: "#6756b1"
  cobalt-light: "#edf2ff"
  cobalt-border: "#d5def6"
typography:
  ui:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  mono:
    fontFamily: "'JetBrains Mono', monospace"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "-0.025em"
rounded:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "9px 15px"
---

# VeriSlip visual system

<!-- impeccable:design-schema 2 -->

## Overview

VeriSlip is a forensic score: a paper-and-ink evidence console for operators who need to move from ingestion to a defensible decision quickly. The visual language borrows from notation and laboratory record systems—clear bilateral inspection, strong baselines, measured labels, and state color reserved for evidence.

## Colors

- Light operational canvas (`--paper: #f4f6f8`) with a subtle paper grain made from low-contrast dots.
- White working surfaces (`--surface: #ffffff`) with one-pixel cool-gray rules (`--line: #d9e0e8`) and restrained soft elevation.
- Ink-black/navy chrome (`--surface-dark: #172131`) for trust and code-heavy surfaces.
- Cobalt (`--cobalt: #2457d6`) is the primary action and selection color.
- Teal (`#087f6b`), amber (`#a96c00`), rose (`#bd3b49`), and violet (`#6756b1`) are semantic signal colors reserved strictly for evidence states.
- Text contrast: primary ink (`#18212f`), soft ink (`#4f5d70`), and accessible muted labels (`#5e6c84`, exceeding 5:1 contrast on paper and surface).

## Typography

- UI copy uses the system sans stack for dependable product readability across macOS, Windows, and Linux.
- JetBrains Mono is reserved for measurements, risk percentages, code samples, and identifiers, using `font-variant-numeric: tabular-nums;`.
- Headings use compact negative tracking (-0.025em) and a clear hierarchy above body copy; labels use uppercase letter-spaced utility styling.

## Layout

- Desktop cockpit uses a 312px ingestion rail, flexible evidence canvas, and 326px verdict rail.
- Tablet view converts the cockpit to a two-column control grid and the verdict rail becomes a balanced grid.
- Mobile view stacks all operational regions, makes tabs horizontally scrollable with touch momentum, and scales action groups to full-width.
- Navigation bar is sticky with 1px border and subtle blur backdrop.

## Elevation & Depth

- Low-elevation ambient shadows: `--shadow-sm: 0 1px 2px rgba(18, 31, 48, .05), 0 8px 20px rgba(18, 31, 48, .04)`.
- Focused containment shadows: `--shadow-md: 0 14px 34px rgba(18, 31, 48, .10)` for overlays and device frames.
- Hard zero-blur offset shadows are prohibited.

## Shapes

- Interactive controls, buttons, and inputs share an 8px radius (`--radius-sm: 8px`).
- Card surfaces share a 12px radius (`--radius-md: 12px`).
- Overlays and stage frames use 16px radius (`--radius-lg: 16px`).

## Components

- `glass-card`: Opaque surface with a one-pixel rule and soft elevation; never gratuitous blur decoration.
- Buttons: 8px radius, visible focus ring (`box-shadow: 0 0 0 3px rgba(36, 87, 214, .25)`), explicit disabled state, and cobalt primary treatment.
- Form inputs: 8px radius, 1px cool-gray border, clear cobalt focus state, and native caret coloring.
- Evidence badges: Encoded with label + color + structural symbol cue; color is never the solitary carrier of state.
- Empty, loading, safe, suspicious, and high-risk states are all styled as first-class product states.

## Do's and Don'ts

### Do:
- **Do** show evidence before decoration and prioritize operator scanability.
- **Do** enforce tabular numeral formatting for all risk percentages, scores, and monetary values.
- **Do** preserve visible keyboard focus, keyboard shortcuts, and semantic control states.
- **Do** maintain WCAG AA contrast (≥4.5:1) for all text and secondary labels.

### Don't:
- **Don't** restore gradients, emoji-as-icons, translucent glass decoration, or thick colored side tabs.
- **Don't** add eyebrows or kickers above headings.
- **Don't** hide the verdict or triage action behind a modal.
- **Don't** replace product evidence with invented performance claims or decorative metrics.
