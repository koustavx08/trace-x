# TRACE-X Global Shell Specification: Left Sidebar & Top Header Standard

> **Document Status:** Active Standard  
> **Target System:** TRACE-X UI / Google Stitch Design Generation  
> **Codebase Source of Truth:** [`apps/web/src/app/(dashboard)/layout.tsx`](file:///home/akshay/trace-x/apps/web/src/app/%28dashboard%29/layout.tsx)  
> **Visual Reference:** BankDash Fintech SaaS Archetype ([`docs/DESIGN_SYSTEM_STANDARD.md`](file:///home/akshay/trace-x/docs/DESIGN_SYSTEM_STANDARD.md))  

---

## 1. Executive Summary & Problem Addressed

During the generation of initial Stitch screens, inconsistent implementations emerged across screens:
- Different navigation item names and order in the left sidebar.
- Errant action buttons placed in the sidebar footer (e.g. "+ New Investigation" in the bottom-left).
- Divergent top bar styling, missing user profile elements, or fluctuating search bar appearances.

This document establishes the **exact, immutable specifications** for:
1. **Left Section (Sidebar Navigation)**: Unified structure, exact 9 items from codebase, brand header, active states, and clean footer.
2. **Top Section (Global Header)**: Universal 74px bar containing title/breadcrumbs, global search pill, notification bell, settings icon, and investigator profile avatar.
3. **Screen-Specific Action Area**: Explicit guidelines on allowable dynamic buttons (e.g. `+ New Investigation`, `Export CSV`, `+ Add Wallet`, `Execute Trace`) placed properly in the page content header rather than contaminating the global shell.

---

## 2. Left Section: Sidebar Navigation Standard

The sidebar is fixed to the left of the floating application shell and must remain identical across all dashboard pages, with only the **Active Item** indicator changing per route.

```
┌──────────────────────────────────────────────┐
│  [Shield Icon] TRACE-X             [◀ Collapse]
├──────────────────────────────────────────────┤
│  NAV ITEMS:                                  │
│   Dashboard           (href: /dashboard)     │
│   Cases               (href: /cases)         │
│   Analyze             (href: /analyze)       │
│   Graph               (href: /graph)         │
│   Risk                (href: /risk)          │
│   AI Assistant        (href: /ai)            │
│   Demo                (href: /demo)          │
│   Reports             (href: /reports)       │
│   Settings            (href: /settings)      │
├──────────────────────────────────────────────┤
│  FOOTER:                                     │
│  ┌────────────────────────────────────────┐  │
│  │ SIH 2026 - TRACE-X                     │  │
│  │ Real-Time Crypto Fraud Attribution...  │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### 2.1 Physical Specifications
- **Width:** `240px` on desktop (collapsible to `72px` mini mode in code).
- **Background:** `#F8F9FC` (off-white clean slate).
- **Border:** `border-right: 1px solid rgba(30, 40, 80, 0.05)`.
- **Padding:** `px-4 py-6`.

### 2.2 Brand & Logo Header (Top 74px)
- **Logo Container:** Royal Indigo rounded rectangle (`w-8 h-8 rounded-lg bg-[#3430D9]`).
- **Logo Icon:** White Shield icon (`Shield` from Lucide / Material Symbols `shield`).
- **Brand Text:** `TRACE-X` in `#252A41` (bold, `18px`, tracking-tight).
- **Subtext / Badge (Optional):** `v2.0 Forensic`.
- **Collapse Button:** Subtle chevron icon button on the right (`text-[#8A8FA3]`).

### 2.3 Navigation Items (Exact 9 Items from Codebase)
The codebase [`apps/web/src/app/(dashboard)/layout.tsx:23-33`](file:///home/akshay/trace-x/apps/web/src/app/%28dashboard%29/layout.tsx#L23-L33) defines the exact 9 navigation routes:

| # | Codebase Name | Route (`href`) | Material / Lucide Icon | Active Route Mapping |
|---|---|---|---|---|
| 1 | **Dashboard** | `/dashboard` | `LayoutDashboard` / `dashboard` | Screen 2 |
| 2 | **Cases** | `/cases` | `FolderOpen` / `folder_open` | Screen 3 & 4 |
| 3 | **Analyze** | `/analyze` | `Search` / `manage_search` | Screen 5 |
| 4 | **Graph** | `/graph` | `GitBranch` / `account_tree` | Screen 6 |
| 5 | **Risk** | `/risk` | `BarChart3` / `assessment` | Screen 7 |
| 6 | **AI Assistant** | `/ai` | `Bot` / `psychology` | Screen 8 |
| 7 | **Demo** | `/demo` | `Trophy` / `emoji_events` | Screen 9 |
| 8 | **Reports** | `/reports` | `FileText` / `description` | Screen 10 |
| 9 | **Settings** | `/settings` | `Settings` / `settings` | Screen 11 |

### 2.4 Nav Item Visual States
- **Active State (Current Screen):**
  - Background: Soft tinted lavender/indigo `#EEF0FF`.
  - Text & Icon: Royal Indigo `#3430D9` (bold weight, `14px`).
  - Active Indicator: **3px solid Royal Indigo (`#3430D9`) vertical bar on the extreme left edge**.
  - Border Radius: `12px` (or `0 12px 12px 0` if hugging left edge).
- **Inactive State:**
  - Background: `transparent`.
  - Text & Icon: Muted slate `#73798D` (medium weight, `14px`).
  - Hover: Soft neutral `#F1F3F8` with `#252A41` text transition.

### 2.5 Sidebar Footer Container
- **NO Primary Action Buttons** (e.g. never place "+ New Investigation" or "+ New Case" in the sidebar footer).
- **Footer Card:** Small information badge matching codebase:
  - Container: Soft `#EEF0FF` background, `border: 1px solid rgba(52, 48, 217, 0.15)`, radius `12px`, padding `12px`.
  - Header: `SIH 2026 - TRACE-X` in `#3430D9` (font-semibold, `11px`).
  - Description: `Real-Time Crypto Fraud Attribution & Investigation Platform` in `#73798D` (`10px`).

---

## 3. Top Section: Global Header Bar

The Global Header sits at the top of the main viewport, spanning the full content width next to the sidebar.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│  [Page Title or Breadcrumb]             [🔍 Search anything...]  [⚙]  [🔔•]  [Avatar] Insp. Rajesh │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Physical Specifications
- **Height:** `74px` (fixed).
- **Background:** `#FFFFFF` or translucent `#F7F8FC/80` with subtle backdrop blur.
- **Border:** `border-bottom: 1px solid rgba(30, 40, 80, 0.05)`.
- **Padding:** `px-8 flex items-center justify-between`.

### 3.2 Left Section: Dynamic Navigation Context
Depending on whether the page is a top-level route or a deep detail route:
- **Top-Level Route:** Clean page category title (e.g. `Dashboard`, `Investigations Registry`, `Wallet Analyzer`, `Investigation Graph`, `Risk Engine`, `AI Copilot`).
- **Deep Detail Route:** Interactive breadcrumbs (e.g. `Cases / TRX-20240115-0042 / Dossier`).

### 3.3 Right Section: Universal Control Suite (Identical Across All Screens)
1. **Global Search Input Pill:**
   - Container: `#F1F3F8`, radius `20px` (pill), width `260px` to `320px`, height `40px`.
   - Icon: Magnifying glass in `#8A8FA3`.
   - Placeholder: `"Search cases, txns, or addresses..."`.
2. **Platform Settings Quick-Access:**
   - Round button (`40px × 40px`, `#F1F3F8`, text `#73798D`), icon: `settings`.
3. **Notification Center:**
   - Round button (`40px × 40px`, `#F1F3F8`, text `#73798D`), icon: `notifications`.
   - Active Alert Dot: Coral pink `#E96B98` or `#EF4444` `8px` badge on top-right.
4. **User Profile Section:**
   - Circular Avatar: `40px × 40px` rounded-full image (`Insp. Rajesh Kumar`).
   - Text Info:
     - Name: `Insp. Rajesh Kumar` (font-semibold, `13px`, `#252A41`).
     - Role: `Senior Cyber Analyst` or `Cyber Crime Unit` (muted, `11px`, `#73798D`).

---

## 4. Universal Button Hierarchy & Placement Standard

To maintain strict visual and positional similarity across all 11 screens, every button in the application must adhere to the standardized hierarchy, layout zones, and visual design tokens below.

### 4.1 Visual Button Hierarchy Tokens

| Button Type | Background Token | Text & Icon Color | Border / Shadow | Height & Radius | Usage Example |
|---|---|---|---|---|---|
| **Primary CTA** | `#3430D9` (Royal Indigo)<br>Hover: `#2723B8` | `#FFFFFF` (Solid White)<br>Font: Medium, `14px` | No border.<br>Shadow: `0 2px 6px rgba(52, 48, 217, 0.2)` | `h-[42px]`, `px-5 py-2.5`<br>`rounded-xl` (`12px`) | `+ New Investigation`, `Execute Trace`, `Launch Graph View` |
| **Secondary Action** | `#EEF0FF` (Lavender tint)<br>Hover: `#E0E4FE` | `#3430D9` (Royal Indigo)<br>Font: Medium, `14px` | Subtle: `1px solid rgba(52, 48, 217, 0.12)` | `h-[42px]`, `px-4 py-2.5`<br>`rounded-xl` (`12px`) | `Export Registry (CSV)`, `+ Add Suspect Wallet`, `Download PDF` |
| **Outline / Ghost** | `transparent`<br>Hover: `#F1F3F8` | `#252A41` (Charcoal Slate)<br>Font: Medium, `14px` | `1px solid rgba(30, 40, 80, 0.12)`<br>No shadow | `h-[42px]`, `px-4 py-2.5`<br>`rounded-xl` (`12px`) | `Cancel`, `Reset Filters`, `Clear Parameters` |
| **Destructive / Danger** | `#FFF0F3` (Soft Pink/Red tint)<br>Hover: `#FFE2E7` | `#D94F72` / `#EF4444`<br>Font: Medium, `14px` | Subtle: `1px solid rgba(217, 79, 114, 0.2)` | `h-[42px]`, `px-4 py-2.5`<br>`rounded-xl` (`12px`) | `Archive Investigation`, `Clear Conversation`, `Revoke Key` |
| **Circular Utility Icon** | `#F1F3F8`<br>Hover: `#E5E8F0` | `#73798D` (Muted Slate)<br>Icon: `20px` | No border.<br>No shadow | `40px × 40px`<br>`rounded-full` (`999px`) | Settings gear, Notification bell, Refresh, Collapse |
| **Inline Table Action** | `transparent`<br>Hover: `#EEF0FF` | `#3430D9` (Royal Indigo)<br>Font: SemiBold, `13px` | No border | `h-[32px]`, `px-3 py-1`<br>`rounded-lg` (`8px`) | `Open Dossier →`, `Trace Flow`, `View Subpoena` |

---

### 4.2 Standard Layout Zones (Where Buttons Belong)

To ensure muscle memory and visual predictability, buttons are strictly confined to 6 standard layout zones:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [Zone 1: Global Top Header] (74px)                       [Search...] [⚙] [🔔] [Avatar] │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Page Content Viewport                                                                  │
│ ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│ │ Page Title & Subtitle             [Zone 2: Sub-Header Actions: Secondary + Primary]│ │
│ ├────────────────────────────────────────────────────────────────────────────────────┤ │
│ │ [Zone 3: Filter & Search Toolbar: Input (Left) | Filters (Mid) | Switcher (Right)] │ │
│ ├────────────────────────────────────────────────────────────────────────────────────┤ │
│ │ Primary Content / Cards / Forms                                                    │ │
│ │   ... Inputs / Parameters ...                                                      │ │
│ │                                            [Zone 4: Console Submission Bar (Right)]│ │
│ ├────────────────────────────────────────────────────────────────────────────────────┤ │
│ │ Data Tables / Dossiers                                                             │ │
│ │   Row 1 ...                                      [Zone 5: Inline Action Link (End)]│ │
│ │   Row 2 ...                                      [Zone 5: Inline Action Link (End)]│ │
│ └────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Zone 1: Global Top Header (Right Edge)**
  - Exclusively reserved for universal platform utilities: Global Search Pill, Settings Icon Button, Notification Icon Button, User Avatar.
  - **Rule:** NEVER place page-specific action buttons (like `+ New Investigation`) here.
- **Zone 2: Page Sub-Header Action Group (Top-Right of Content Area)**
  - Position: Aligned horizontally across from the Page Title & Subtitle in `flex items-center justify-between`.
  - Structure: Secondary actions on the left, Primary CTA on the far right (`gap-3`).
  - **Rule:** This is the canonical home for primary creation buttons (`+ New Investigation`, `+ Add Wallet`, `+ Generate Report`).
- **Zone 3: Filter & Search Toolbar (Below Sub-Header or KPI Grid)**
  - Left: Search input field (`w-72` to `w-96`, rounded-xl).
  - Center: Filter select dropdowns (`h-[40px]`, rounded-xl).
  - Far Right: View toggles (Table/Grid segmented pill) or auxiliary export buttons.
- **Zone 4: Configuration Console Execution Area**
  - Used in form/console cards (e.g. Wallet Analyzer, Risk Assessor).
  - Position: Bottom-right of the configuration card, or full-width prominent bar.
  - Pairing: Ghost/Secondary "Reset / Clear" button on the left, Primary CTA (`Execute Recursive Trace`) on the right.
- **Zone 5: Table Row & Card Header Actions**
  - Table Rows: Far-right column (`text-right`), styled as clean text links (`Open Dossier →`) or subtle icon menus (`MoreHorizontal`).
  - Card Headers: Top-right corner of individual cards (e.g. `View All`, `Export SVG`, `Refresh`).
- **Zone 6: Modal / Dialog Action Footer**
  - Position: Fixed at bottom-right of modal dialogs (`DialogFooter flex justify-end gap-3`).
  - Order: `[Cancel (Ghost / Outline)]` on the left, `[Confirm / Initialize (Primary Indigo #3430D9)]` on the right.

---

### 4.3 Screen-by-Screen Button Location & Styling Mapping

This table provides the exact location, visual styling token, and placement zone for **every button across all 11 screens**:

| Screen # & Route | Button Label | Button Hierarchy | Layout Zone & Exact Position | Visual Style Tokens |
|---|---|---|---|---|
| **Screen 2: Dashboard**<br>`/(dashboard)/dashboard` | `+ New Investigation` | Primary CTA | **Zone 2** (Sub-Header, Top-Right) | Bg `#3430D9`, text white, `rounded-xl`, Plus icon |
| | `View All Cases` | Ghost Link | **Zone 5** (Recent Cases Card Header, Right) | Text `#3430D9`, hover bg `#EEF0FF`, text-xs |
| | `Open Case Dossier` | Inline Action | **Zone 5** (Table Row, Far-Right Column) | Text `#3430D9`, font-semibold, arrow icon |
| **Screen 3: Cases**<br>`/(dashboard)/cases` | `Export Registry (CSV)` | Secondary Action | **Zone 2** (Sub-Header, Top-Right, Left of CTA) | Bg `#EEF0FF`, text `#3430D9`, Download icon |
| | `+ New Investigation` | Primary CTA | **Zone 2** (Sub-Header, Top-Right, Far Right) | Bg `#3430D9`, text white, Plus icon, `shadow-sm` |
| | `Table / Grid Toggle` | Segmented Pill | **Zone 3** (Filter Bar, Far Right) | Bg `#F1F3F8`, active item `#FFFFFF` with shadow |
| | `Open Dossier →` | Inline Action | **Zone 5** (Registry Table, Far-Right Column) | Text `#3430D9`, font-semibold text-sm |
| | `Cancel` (in Modal) | Outline / Ghost | **Zone 6** (New Investigation Modal Footer, Left) | Transparent, border `#E5E7EB`, text `#252A41` |
| | `Initialize Investigation` | Primary CTA | **Zone 6** (New Investigation Modal Footer, Right) | Bg `#3430D9`, text white, `rounded-xl` |
| **Screen 4: Case Dossier**<br>`/(dashboard)/cases/[caseId]` | `+ Add Suspect Wallet` | Secondary Action | **Zone 2** (Case Header Card, Right Group) | Bg `#EEF0FF`, text `#3430D9`, Plus icon |
| | `Generate Report` | Secondary Action | **Zone 2** (Case Header Card, Right Group) | Outline border, text `#252A41`, FileText icon |
| | `Launch Graph View` | Primary CTA | **Zone 2** (Case Header Card, Far Right) | Bg `#3430D9`, text white, GitBranch icon |
| | `View LEA Subpoena` | Inline Action | **Zone 5** (VASP Attribution Card, Bottom-Right) | Bg `#E9FBF7`, text `#16A98F`, ExternalLink icon |
| | `Analyze Flow` | Inline Action | **Zone 5** (Wallets Table Row, Far-Right) | Text `#3430D9`, Search icon |
| **Screen 5: Analyze**<br>`/(dashboard)/analyze` | `Clear Parameters` | Outline / Ghost | **Zone 4** (Console Execution Bar, Left) | Transparent, text `#73798D`, hover bg `#F1F3F8` |
| | `Execute Recursive Trace` | Primary CTA | **Zone 4** (Console Execution Bar, Right) | Bg `#3430D9`, text white, Zap icon, prominent |
| | `View Subpoena Packet` | Secondary Action | **Zone 5** (Nearest VASP Banner, Right) | Bg `#EEF0FF`, text `#3430D9`, FileText icon |
| | `Export Transactions (CSV)`| Secondary Action | **Zone 3** (Ledger Tab Header, Right) | Bg `#F1F3F8`, text `#252A41`, Download icon |
| **Screen 6: Graph**<br>`/(dashboard)/graph` | `Layout Switcher` | Segmented Pill | **Floating Bar** (Top Center of Canvas) | 3 options: Hierarchical / Organic / Radial |
| | `Depth Slider` | Slider Control | **Floating Bar** (Top Center, Middle) | Indigo track `#3430D9`, pill badge "3 Hops" |
| | `Filter Chips` | Filter Toggle Pills | **Floating Bar** (Top Center, Right Group) | Pills: Exchanges Only, Mixers Only, > 0.5 ETH |
| | `Re-layout Graph` | Circular Icon | **Floating Bar** (Top Center, Far Right) | Bg `#F1F3F8`, Refresh icon |
| | `Export PNG / SVG` | Secondary Action | **Floating Bar** (Top Center, Far Right) | Bg `#EEF0FF`, text `#3430D9`, Download icon |
| | `Save Snapshot to Case` | Primary CTA | **Floating Bar** (Top Center, Far Right Edge) | Bg `#3430D9`, text white, Bookmark icon |
| **Screen 7: Risk**<br>`/(dashboard)/risk` | `Export Risk Breakdown` | Secondary Action | **Zone 2** (Sub-Header, Top-Right, Left of CTA) | Bg `#EEF0FF`, text `#3430D9`, FileText icon |
| | `Recalculate Risk Engine` | Primary CTA | **Zone 2** (Sub-Header, Top-Right, Far Right) | Bg `#3430D9`, text white, RefreshCw icon |
| | `Generate Subpoena Notice`| Primary Action | **Zone 5** (Identified VASP Card, Bottom-Right) | Bg `#20C7B5` (Teal), text white, Shield icon |
| **Screen 8: AI Copilot**<br>`/(dashboard)/ai` | `Clear Conversation` | Destructive Action | **Zone 2** (Chat Header, Far Right) | Bg `#FFF0F3`, text `#D94F72`, Trash icon |
| | `Attach Evidence File` | Circular Icon | **Bottom Bar** (Chat Input Box, Left) | Transparent, text `#73798D`, Paperclip icon |
| | `Send Prompt / Query` | Primary CTA | **Bottom Bar** (Chat Input Box, Right) | Bg `#3430D9`, text white, ArrowUp icon |
| | `Copy Narrative Draft` | Secondary Action | **Zone 5** (AI Message Response Card, Top-Right) | Text `#3430D9`, hover bg `#EEF0FF`, Copy icon |
| **Screen 9: Demo**<br>`/(dashboard)/demo` | `Reset All Scenarios` | Outline / Ghost | **Zone 2** (Sub-Header, Top-Right, Left of CTA) | Transparent, border `#E5E7EB`, text `#73798D` |
| | `1-Click Auto Run Simulation`| Primary CTA | **Zone 2** (Sub-Header, Top-Right, Far Right) | Bg `#3430D9`, text white, Play icon |
| | `Launch Scenario` | Primary Action | **Zone 5** (Scenario Card Footer, Right) | Bg `#3430D9`, text white, ArrowRight icon |
| **Screen 10: Reports**<br>`/(dashboard)/reports` | `Filter Formats (PDF/CSV)`| Filter Dropdown | **Zone 3** (Filter Bar, Left Group) | Bg `#F1F3F8`, text `#252A41`, `rounded-xl` |
| | `+ Generate Evidence Report`| Primary CTA | **Zone 2** (Sub-Header, Top-Right) | Bg `#3430D9`, text white, Plus/FileText icon |
| | `Download Signed PDF` | Secondary Action | **Zone 5** (Reports Table Row, Far-Right) | Bg `#EEF0FF`, text `#3430D9`, Download icon |
| | `Verify SHA-256 Hash` | Inline Action | **Zone 5** (Reports Table Row, Middle) | Text `#16A98F` (Teal), CheckCircle icon |
| **Screen 11: Settings**<br>`/(dashboard)/settings` | `Discard Changes` | Outline / Ghost | **Zone 5** (Settings Form Footer, Left) | Transparent, text `#73798D`, hover bg `#F1F3F8` |
| | `Save Platform Configuration`| Primary CTA | **Zone 5** (Settings Form Footer, Right) | Bg `#3430D9`, text white, Check icon |
| | `Test RPC Connection` | Secondary Action | **Zone 5** (Node Provider Card, Right) | Bg `#EEF0FF`, text `#3430D9`, Activity icon |
| **Screen 1: Login**<br>`/(auth)/login` | `Authenticate & Enter` | Primary CTA | **Center Card** (Bottom of Login Form, Full-Width)| Bg `#3430D9`, text white, Lock/ArrowRight icon |

---

## 5. Reusable Stitch Prompt Blocks

To guarantee 100% uniformity in Google Stitch across all remaining screens, every prompt **MUST** include the following standardized code block:

```text
[GLOBAL SHELL SPECIFICATION - MUST REMAIN UNIFORM ACROSS ALL SCREENS]
1. Layout Structure:
   - Full-Bleed SaaS Layout: Clean full-viewport layout spanning 100% width and height. NO outer blue background, NO thick surrounding colored borders, NO floating frame inside a blue box.
   - Main Viewport Background: Crisp, calming neutral off-white (#F5F7FA) extending to all edges of the screen.
   - Surface Cards: Floating pure white containers (#FFFFFF), 18px-20px rounded corners, subtle border: 1px solid rgba(30, 40, 80, 0.04), soft diffused shadow: 0 4px 16px rgba(25, 35, 80, 0.04).

2. Left Sidebar Navigation (240px, #F8F9FC, border-right: 1px solid rgba(30, 40, 80, 0.05)):
   - Header: TRACE-X Logo with Royal Indigo (#3430D9) shield icon and "TRACE-X" bold typography.
   - Nav Items (Exact 9 items):
     1. Dashboard (/dashboard)
     2. Cases (/cases)
     3. Analyze (/analyze)
     4. Graph (/graph)
     5. Risk (/risk)
     6. AI Assistant (/ai)
     7. Demo (/demo)
     8. Reports (/reports)
     9. Settings (/settings)
   - Active Nav Item: Soft lavender-indigo (#EEF0FF) background, bold Royal Indigo (#3430D9) text and icon, with a 3px solid vertical Royal Indigo indicator on the extreme left.
   - Inactive Nav Items: Muted slate (#73798D) text and icons, clean hover state.
   - Footer: Informational badge "SIH 2026 - TRACE-X • Real-Time Crypto Fraud Attribution & Investigation Platform". NO stray action buttons in the sidebar!

3. Global Top Header (74px height, px-8, border-bottom: 1px solid rgba(30, 40, 80, 0.05)):
   - Left: Dynamic page title or breadcrumbs matching current route.
   - Right Universal Suite:
     - Search Input Pill: #F1F3F8 background, 20px radius, magnifying glass icon, placeholder "Search cases, txns, or addresses...".
     - Circular Icon Buttons (40px, #F1F3F8): Settings gear icon, Notification bell icon with coral pink alert dot (#E96B98).
     - User Profile: 40px circular avatar ("Insp. Rajesh Kumar") with name and "Senior Cyber Analyst" subtext.
```
