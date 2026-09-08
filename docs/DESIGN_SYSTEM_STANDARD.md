# TRACE-X Design System Standard: Premium Fintech SaaS & Banking Aesthetic

> **Standard Version:** 2.0 (Light Premium Fintech / BankDash Foundation)  
> **Target Platform:** TRACE-X Cryptocurrency Fraud Attribution & Investigation Platform (SIH26183)  
> **Source Design Archetype:** Premium Banking & Modern Forensic Analytics Dashboard  

---

## 1. Visual Reference & Design Inspiration

The visual system is derived from a modern, high-tier fintech banking and intelligence dashboard archetype (exemplified by the BankDash standard below). It replaces traditional dark terminal or harsh corporate styling with an airy, soft, floating workspace.

![BankDash Visual Reference](/home/akshay/.gemini/antigravity-cli/brain/b929b3d1-373f-43b6-a2ad-83ce342a3582/.user_uploaded/uploaded_media_1788875305228.png)

### Key Aesthetic Principles
- **Atmosphere:** Clean, soft, spacious, premium, slightly futuristic yet deeply authoritative and institutional.
- **Surface Language:** Soft glass-like and light layered surfaces, floating cards, generous rounded containers, and extremely diffused airy shadows.
- **Contrast Philosophy:** Use whitespace, soft surface shifts, and subtle diffused shadows rather than harsh borders or heavy dividers.
- **Strictly Avoided:**
  - Harsh black or dark borders (`#000000`, heavy slate borders).
  - Dark drop shadows (`rgba(0,0,0,0.3)` or dense muddy blurs).
  - Sharp, square, brutalist card corners.
  - Overly saturated backgrounds inside the dashboard viewports.
  - Cluttered, claustrophobic grid tables or dense text-heavy admin templates.
  - Excessive, decorative glassmorphic blurs that impede high-speed forensic legibility.

---

## 2. Global Color Tokens & Palette

Use this color system consistently across all pages, components, charts, and interactive states.

### 2.1 Primary Brand Accent
The primary brand color is a royal indigo/blue that commands attention without overwhelming the viewport. It should be used purposefully as an accent rather than painted across large backgrounds.

| Token Name | Hex Value | RGB / HSL | Usage & Placement |
|---|---|---|---|
| **Primary Indigo** | `#3430D9` | `rgb(52, 48, 217)` | Primary CTA buttons, active navigation indicators, key icons, active tabs, primary data accents. |
| **Primary Blue** | `#3155E7` | `rgb(49, 85, 231)` | Interactive link states, active filter chips, secondary interactive highlights. |
| **Deep Indigo** | `#2723B8` | `rgb(39, 35, 184)` | Button hover states, gradient termination, deep brand focus rings. |

### 2.2 Secondary Analytical & Categorical Accents
Used strictly for charts, graph nodes, telemetry badges, category pills, and investigative highlights:

| Category Accent | Hex Value | RGB | Usage |
|---|---|---|---|
| **Teal** | `#20C7B5` | `rgb(32, 199, 181)` | Confirmed VASP attributions, safe nodes, positive financial inflows, deposits. |
| **Pink / Coral** | `#E96B98` | `rgb(233, 107, 152)` | Critical risk factors, mixer interactions, fund withdrawals, flagged transactions. |
| **Purple** | `#B52EE8` | `rgb(181, 46, 232)` | Cluster analysis, money laundering loops, peel-chain patterns, investment categories. |
| **Soft Blue** | `#6D7CFF` | `rgb(109, 124, 255)` | Intermediary hops, secondary telemetry metrics, pending traces, chain tags. |

### 2.3 Layered Background Architecture
Depth is established through a clean, full-bleed surface hierarchy with **zero thick colored borders or outer backdrops**:

| Surface Layer | Hex Value | Description & Implementation |
|---|---|---|
| **Global Page Viewport** | `#F5F7FA` / `#F7F8FC` | Soft, neutral off-white background spanning the entire browser viewport (full-bleed, edge-to-edge). **No outer blue border or colored background frame.** |
| **Sidebar Canvas** | `#F8F9FC` / `#FFFFFF` | Crisp full-height vertical navigation surface with subtle `border-right: 1px solid rgba(30, 40, 80, 0.05)`. |
| **Primary Card Surfaces** | `#FFFFFF` | Elevated pure white containers for forensic dossiers, tables, and KPI metrics (`border-radius: 18px-20px`, subtle `1px solid rgba(30, 40, 80, 0.04)`). |
| **Secondary Card Surfaces**| `#FAFBFE` / `#F3F5FA` | Subtle contrast containers for inspector panels, input fields, search containers, and nested tables. |

---

## 3. Full-Bleed Application Viewport & Layout Architecture

The application uses a **standard, modern full-bleed SaaS dashboard layout** (identical to Stripe, Mercury, and Linear). **There is NO outer blue background, NO thick surrounding borders, and NO floating rounded container inside a blue box.**

```
┌────────────────────────────────────────────────────────────────────────┐
│ Full Browser Viewport Background: Clean Off-White (#F5F7FA)           │
│ ┌──────────────┬─────────────────────────────────────────────────────┐ │
│ │ Left Sidebar │ Global Top Header (#FFFFFF, height: 74px)           │ │
│ │ (#F8F9FC)    ├─────────────────────────────────────────────────────┤ │
│ │ 240px width  │ Page Content Viewport (#F5F7FA)                     │ │
│ │ Full Height  │                                                     │ │
│ │ border-right │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │ │
│ │ 1px subtle   │  │ White Card   │  │ White Card   │  │ White Card│  │ │
│ │              │  │ (#FFFFFF)    │  │ (#FFFFFF)    │  │ (#FFFFFF) │  │ │
│ │              │  └──────────────┘  └──────────────┘  └───────────┘  │ │
│ │              │                                                     │ │
│ └──────────────┴─────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

- **Viewport Spanning:** The layout spans 100% of the screen width and height (`h-screen`, `w-full`).
- **Zero Surrounding Borders:** The viewport does NOT sit inside a blue frame. The outermost background is the clean, calming `#F5F7FA`.
- **Card Elevation:** Cards sit directly on the `#F5F7FA` surface with `border-radius: 18px–20px`, `1px solid rgba(30, 40, 80, 0.04)`, and a gentle diffused shadow `box-shadow: 0 4px 16px rgba(25, 35, 80, 0.04);`.

---

## 4. Navigation Architecture: Sidebar & Header

### 4.1 Clean Minimalist Sidebar
- **Background:** `#F8F9FC` (smoothly merges with `#F7F8FC` with `border-right: 1px solid rgba(30, 40, 80, 0.05)`).
- **Width:** `240px` (desktop), collapsible to `72px` (compact icons).
- **Brand Logo:** Centered shield + "TRACE-X" typography in `#252A41` font-weight 700.
- **Nav Items:**
  - **Inactive Item:**
    - Background: `transparent`
    - Text: `#8A8FA3` (`14px`, medium)
    - Icon: `#8A8FA3` (`20px`)
  - **Active Item:**
    - Background: `#EEF0FF`
    - Text: `#3430D9` (`font-weight: 600`)
    - Icon: `#3430D9`
    - Radius: `12px`
    - Vertical Left Accent Indicator: `width: 3px; height: 24px; border-radius: 10px; background: #3430D9; position: absolute; left: 0;`
  - **Vertical Spacing:** Generous `space-y-2` (8px gap between items).

### 4.2 Spacious Top Navigation Header
- **Height:** `74px`
- **Background:** `transparent` or `#F7F8FC` (no heavy dividing borders).
- **Page Title:** Left-aligned, `24px–28px`, `font-weight: 700`, color `#252A41`.
- **Search Bar (Pill style):**
  - Background: `#F1F3F8`
  - Border: `none`
  - Radius: `20px` (pill)
  - Height: `40px`
  - Width: `280px`–`360px`
  - Placeholder & Icon: `#9AA0B3`
- **Action Icons:** Muted circular buttons (`40px x 40px`, `#F1F3F8` hover, `#73798D` icon color) for Notifications and System Settings.
- **User Avatar:** Circular `40px`, border `2px solid #FFFFFF`, shadow `0 2px 8px rgba(30, 40, 90, 0.08)`.

---

## 5. Typography Standards

The system uses modern geometric sans-serif (`Inter`) with a disciplined hierarchy. Numbers and financial/forensic metrics are given visual priority over labels.

| Element | Size | Weight | Color | Line Height |
|---|---|---|---|---|
| **Page Title** | `26px` (`1.625rem`) | 700 (Bold) | `#252A41` | `1.2` |
| **Section Heading** | `16px` (`1rem`) | 600 (SemiBold) | `#30354D` | `1.3` |
| **KPI / Metric Value** | `26px–30px` | 700 (Bold) | `#292E46` | `1.1` |
| **Body Text** | `14px` (`0.875rem`) | 400 (Regular) | `#73798D` | `1.6` |
| **Secondary / Captions** | `12px` (`0.75rem`) | 500 (Medium) | `#9BA0B2` | `1.4` |
| **Table Column Headers** | `11px` | 600 (SemiBold) | `#9A9FB1` | `1.2` (Uppercase, `tracking-wider`) |
| **Hashes & Addresses** | `13px` | 500 (Medium) | `#30354D` | JetBrains Mono / Monospace |

---

## 6. Card System & Geometric Radius Hierarchy

Cards are the cornerstone of this design system. Rather than heavy borders, cards float gently on soft diffused shadows.

### 6.1 Corner Radius Scale
Strict hierarchy to avoid arbitrary radii across screens:
- **Floating Application Shell:** `28px`
- **Large Hero / Highlight Containers:** `22px`
- **Standard Analytical Cards:** `20px`
- **Small Widgets / Sub-cards:** `16px`
- **Form Inputs & Selectors:** `12px`
- **Buttons:** `12px`
- **Status Pills / Badges:** `999px` (Full Pill)
- **User Avatars:** `50%` (Circular)

### 6.2 Standard Floating Card Specification
```css
.card-standard {
  background: #FFFFFF;
  border-radius: 20px;
  border: 1px solid rgba(30, 40, 80, 0.035);
  box-shadow: 0 6px 20px rgba(30, 40, 90, 0.05);
  padding: 24px;
}
```

### 6.3 Internal Spacing & Padding
- **Large Cards (KPI, Graph Canvas, Case Dossier):** `24px` to `28px` padding.
- **Medium Cards (Risk Breakdown, Wallet Summary):** `20px` to `24px` padding.
- **Small Cards (Mini stats, Inspector items):** `16px` to `20px` padding.
- **Card Spacing Grid:** Multiples of `8px` (`16px`, `24px`, `32px` gaps). Never pack cards flush against each other.

---

## 7. Financial & Rich Gradient Cards

For primary suspect balances, victim fund loss summaries, and high-impact case cards (mirroring the BankDash primary credit card design):

```css
.card-financial-primary {
  background: linear-gradient(135deg, #3B35E6 0%, #2621C7 100%);
  color: #FFFFFF;
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 12px 28px rgba(52, 48, 217, 0.22);
}
```

- **Header:** White semi-transparent label (`#FFFFFF` with 80% opacity) + high-tech EMV chip or Shield graphic.
- **Balance / Fraud Amount:** Bold `24px–28px` white typography.
- **Footer Data:** Masked wallet address (`0x742d •••• •••• 0bEb`), network badge, and expiry/detection timestamp in crisp white.
- **Secondary Cards:** Clean white background (`#FFFFFF`), dark typography (`#292E46`), subtle muted chip icon, and `border: 1px solid rgba(30, 40, 80, 0.05)`.

---

## 8. Buttons & Interactive Controls

Buttons feature modern rounded corners (`12px`) and subtle drop glows.

| Button Variant | Background | Text Color | Border | Shadow |
|---|---|---|---|---|
| **Primary CTA** | `#3430D9` | `#FFFFFF` | `none` | `0 5px 15px rgba(52, 48, 217, 0.18)` |
| **Primary Hover** | `#2723B8` | `#FFFFFF` | `none` | `0 8px 20px rgba(52, 48, 217, 0.28)` |
| **Secondary / Soft** | `#EEF0FF` | `#3430D9` | `none` | `none` (Light hover tint) |
| **Ghost / Outline** | `transparent` | `#6E748A` | `1px solid rgba(30, 40, 80, 0.08)` | `none` |
| **Destructive / Alert**| `#FFF0F3` | `#D94F72` | `none` | `0 4px 12px rgba(217, 79, 114, 0.12)` |

---

## 9. Form Inputs & Select Controls

All inputs adhere to a soft, inviting visual language:

- **Background:** `#F7F8FC`
- **Border:** `1px solid #E8EAF1`
- **Radius:** `12px`
- **Height:** `44px`
- **Text Color:** `#252A41`
- **Placeholder:** `#9AA0B3`
- **Focus State:**
  - `border-color: #3430D9;`
  - `box-shadow: 0 0 0 3px rgba(52, 48, 217, 0.08);`
  - `outline: none;`

---

## 10. Tables & Data Ledgers

Tables should feel lightweight, open, and easy to read during long investigation shifts.

- **Grid Lines:** No vertical grid borders.
- **Row Dividers:** `border-bottom: 1px solid #EEF0F5`.
- **Header Row:**
  - Font: `11px–12px`, `font-weight: 600`, color `#9A9FB1`, uppercase, tracking `0.05em`.
  - Height: `44px`.
- **Data Rows:**
  - Height: `60px` to `66px` (spacious row height for readability).
  - Background: `transparent`.
  - Hover: `#F8F9FD` (gentle, instantaneous row highlight).
- **Address & Hash Cells:** Displayed in `JetBrains Mono` (`#30354D`), with 1-click copy icon.

---

## 11. Charts, Graph Visualizations & Analytics

Charts should be the strongest visual anchors on the page (e.g. Weekly Inflow/Outflow bars, Expense/Laundering breakdown donut, Balance history smooth curves).

- **Grid Lines:** Very light, minimal horizontal lines only (`#EEF0F5`).
- **Primary Series:** `#3430D9` (Electric Royal Indigo).
- **Secondary Series / Inflows:** `#20C7B5` (Teal).
- **Flagged Outflows / Mixers:** `#E96B98` (Pink / Coral).
- **Cluster Categories:** `#B52EE8` (Purple).
- **Geometry:** Rounded bar tops (`border-radius: 8px 8px 0 0`), smooth bezier curves, small clean legends without cluttered axes.

---

## 12. Status Indicators & Badges

Status badges are rounded pills (`rounded-full`) with a soft 10% tinted background and vibrant legible text.

| Status Role | Background | Text Color | Usage in TRACE-X |
|---|---|---|---|
| **Success / Confirmed** | `#E9FBF7` | `#16A98F` | Confirmed VASP attribution, safe address, operational service. |
| **Warning / Suspicious** | `#FFF7E8` | `#D99924` | Probable attribution, medium risk (30–70), peel-chain alerts. |
| **Critical / Fraud** | `#FFF0F3` | `#D94F72` | Critical risk (>70), mixer interactions, sanctions hit, OFAC match. |
| **Info / Pending** | `#EEF0FF` | `#3430D9` | Active tracing, EVM chain tags, in-progress investigation runs. |

---

## 13. Soft Diffused Shadows Matrix

Never use heavy black shadows (`rgba(0,0,0,...)`). Use soft, airy, blue-tinted shadows:

```css
/* Standard floating card */
box-shadow: 0 6px 20px rgba(25, 35, 80, 0.05);

/* Elevated card or modal */
box-shadow: 0 12px 30px rgba(25, 35, 80, 0.07);

/* Floating action dropdown or popover */
box-shadow: 0 18px 45px rgba(25, 35, 80, 0.10);

/* Primary indigo card / CTA button */
box-shadow: 0 12px 28px rgba(52, 48, 217, 0.20);

/* Outer application shell */
box-shadow: 0 20px 60px rgba(20, 30, 90, 0.12);
```

---

## 14. Dashboard Composition & Asymmetric Grid Balance

For executive and analytical pages, structure the layout into asymmetric editorial sections:

- **Top Row (KPI Cards):** 4 floating cards showing key metrics with icons in soft-tinted circular badges (`#EEF0FF`, `#E9FBF7`, etc.).
- **Primary Section (60%–70% width):** High-priority charts, transaction graphs, or active case dossiers.
- **Secondary Section (30%–40% width):** Quick transfer / suspect wallet card, recent transaction feeds, or VASP off-ramp summary.
- **Visual Rhythm:** Let the eye flow naturally from left-to-right and top-to-bottom through generous whitespace (`24px–32px` gaps) rather than border dividers.

---

## 15. Rules for Google Stitch Prompts

When generating or editing screens in Google Stitch for TRACE-X:
1. **Design System Directive:** Specify "Clean, premium fintech SaaS aesthetic inspired by modern banking dashboards (soft `#F5F7FA` page background, full-bleed edge-to-edge layout, floating pure white `#FFFFFF` cards with 18px-20px rounded corners, extremely subtle diffused shadows `0 4px 16px rgba(25,35,80,0.04)`, and royal indigo `#3430D9` primary accents)."
2. **Layout Directive (CRITICAL):** "Full-bleed dashboard viewport layout with NO outer blue background, NO thick surrounding borders, and NO floating rounded frame inside a blue box. The outermost background must be pure clean `#F5F7FA` spanning the entire screen."
3. **Card Directive:** "Do NOT use dark mode, black borders, heavy gradients, or dense admin templates. Use soft white cards, gentle row dividers `#EEF0F5`, and pill badges."
4. **Data Integrity:** Retain all TRACE-X forensic data fields (wallet addresses, tx hashes, 12 risk factors, VASP confidence badges, hop counts) while presenting them in this elegant, expensive-feeling fintech interface.
