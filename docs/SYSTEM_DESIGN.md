# SYSTEM_DESIGN.md — Smart Surveillance design system

The visual and interaction rules for every Smart Surveillance surface: the admin console, the CCTV dashboard, the public LCD screens, **and the video overlay drawn by the vision service**. The source of truth for the product is [PRD.md](PRD.md), and the users and context are in [../PRODUCT.md](../PRODUCT.md). This document turns them into tokens, components and rules that frontend and vision code both follow.

**Visual world: "Console graphite"** (chosen 2026-10-30 from an Impeccable direction round). A graphite ground, panels divided by 1 px seams instead of shadows, one elevation step, monospaced figures, small-caps panel headers, colour used only for state, and destructive actions isolated and outlined. Panels persist: navigating changes what's in a panel, not the layout.

**Signature move: the spotlight.** Selecting a hallway or checkout in the side panel dims the live video everywhere *except* that zone (and its cashier zone) and outlines it in its state colour. The list and the physical place are the same object. Implemented in `pages/Dashboard.jsx` (`CameraTile`) as an SVG mask over the MJPEG stream.

---

## 1. Product, users, surfaces

The product watches the hallways that lead to checkouts. It counts the people waiting, says which checkouts are free, busy or closed, and broadcasts that live (PRD §1, §4, §5).

| Surface | Who | Mode | Success looks like |
|---|---|---|---|
| **Login** | Admin, operator | Operate | Signed in, in under 5 s, with no doubt about what failed |
| **CCTV dashboard** (Supervision) | Operator, admin, often on a second monitor for hours | Operate · monitor | Spots a problem (a long queue, a camera offline) at a glance, without reading |
| **Cameras** | Admin, during setup and maintenance | Operate | Adds or removes a camera (IP, RTSP URL, password) without errors |
| **Mapping** | Admin, once per camera | Operate · precision | Draws hallway, checkout and cashier zones correctly the first time |
| **LCD screen** | Shoppers, 2–8 m away, glancing for under 2 s | Read · at a distance | Knows which checkout to walk to |

**Scene:** a supervisor's desk or a store back-office, often dim, with screens running all day. The LCD hangs above a checkout area under bright retail lighting. Both call for a **dark, low-glare, high-contrast** theme.

## 2. Principles

1. **Color means state, never decoration.** Hue is reserved for the six semantic meanings in §3.2. Chrome (navigation, buttons, cards) is neutral grayscale. If a color appears, it is telling you something.
2. **One vocabulary, two renderers.** The video overlay (OpenCV, `vision_service/tracker.py`) and the web UI (CSS) use **the same colors, names and shapes** for hallway, checkout, cashier and person. A red checkout on video is the same red as "occupée" on the LCD.
3. **Status first, detail on demand.** Every screen leads with the live state. Configuration and metadata are secondary.
4. **Never color alone.** Every state also has a text label and a shape (§3.3). About 8% of men can't tell red from green.
5. **Privacy is visible.** Faces are always blurred, including in snapshots. The UI never offers an "unblur" control and never shows raw RTSP credentials.
6. **Legible from across the room.** The LCD is designed for distance first, not scaled down from the dashboard.
7. **Calm motion.** Motion only marks a change of state or shows that something is live (§6). A monitoring screen that moves all the time trains people to ignore it.

---

## 3. Tokens

All tokens live as CSS custom properties on `:root` in `frontend/src/styles.css`. The overlay constants in `vision_service/tracker.py` mirror §3.2 exactly (OpenCV takes **BGR**, so the order is reversed).

### 3.1 Neutrals (chrome)

| Token | Value | Use |
|---|---|---|
| `--bg-0` | `#0d1117` | Ground: app background, LCD background |
| `--bg-1` | `#151a22` | Panels, nav bar, side panels |
| `--bg-2` | `#1b212b` | Elevated: inputs, hover and selected rows, video letterbox |
| `--bg-3` | `#232b37` | Pressed states, toast |
| `--line` | `#262c36` | 1 px seams between panels and rows |
| `--line-strong` | `#353d4a` | Input borders, selected-row border |
| `--text` | `#e6edf3` | Primary text (about 15 : 1 on `--bg-1`) |
| `--text-muted` | `#8b949e` | Secondary text, panel headers (about 6 : 1) |
| `--text-faint` | `#6b7480` | Placeholders and timestamps (non-essential text only) |

Depth comes from stepping up the background (`bg-0 → bg-3`) plus a 1 px border, **not** from drop shadows. Shadows look muddy on dark screens and smear on LCD panels.

### 3.2 Semantic colors (shared by UI and video overlay)

| Token | Hex (UI) | BGR (overlay) | Meaning | Shape |
|---|---|---|---|---|
| `--zone-hallway` | `#3d8bfd` | `(253, 139, 61)` | Hallway (queue zone) and its count | Outlined region |
| `--state-free` | `#2fbf71` | `(113, 191, 47)` | Checkout **open with no customer**; camera **online** | Filled dot ● |
| `--state-busy` | `#f0564f` | `(79, 86, 240)` | Checkout **serving a customer** | Filled square ■ |
| `--state-closed` | `#7d8896` | `(150, 136, 125)` | Checkout **closed** (no cashier); camera **offline** | Hollow ring ○ |
| `--zone-staff` | `#b673f0` | `(240, 115, 182)` | Cashier zone and people classified as staff | Dashed outline |
| `--person` | `#ffd23f` | `(63, 210, 255)` | A tracked customer (4-corner brackets) | Corner brackets ⌜⌟ |

Each semantic color also has:
- a **tint** for fills: the same color at **16 %** opacity in the UI (`color-mix(in srgb, var(--state-busy) 16%, transparent)`) and **25 %** alpha on video, which needs more to survive busy footage;
- **text use:** every hex above passes **4.5 : 1** on `--bg-1`, so it can be used directly for status text.

Interactive and focus elements are **neutral**: primary buttons are `--text` on `--bg-0`, and the focus ring is `--text` (2 px, offset 2 px). This stops a blue button from being mistaken for a hallway, or a green one for a free checkout.

### 3.3 State vocabulary (French UI copy)

| State | Label (FR) | Color | Shape | LCD wording |
|---|---|---|---|---|
| Checkout free | **Libre** | `--state-free` | ● | "Caisse 2 — libre" |
| Checkout busy | **Occupée** | `--state-busy` | ■ | "Caisse 2 — occupée" |
| Checkout closed | **Fermée** | `--state-closed` | ○ | "Caisse 2 — fermée" |
| Camera online | **En direct** | `--state-free` | ● (pulsing) | — |
| Camera offline | **Hors ligne** | `--state-closed` | ○ | "Couloir B — données indisponibles" |
| Queue count | **N en attente** | `--text` (number), `--text-muted` (label) | — | "4 personnes en attente" |

Copy rules: sentence case, no trailing periods in labels, and numbers as digits. Plurals are handled properly: "1 personne", "0 personne", "4 personnes", never "personne(s)".

### 3.4 Typography

Fonts are **self-hosted** (`@fontsource-variable/inter`, `@fontsource/jetbrains-mono`). LCD kiosks on a store network may have no internet access, so no CDN fonts.

| Role | Font | Notes |
|---|---|---|
| UI and LCD | **Inter Variable** | `font-feature-settings: "tnum", "cv11"`. Tabular figures stop counts from jittering as they change. |
| Technical values | **JetBrains Mono** | IP addresses, RTSP URLs, IDs |

Admin type scale (rem, 16 px base):

| Token | Size / line height | Weight | Use |
|---|---|---|---|
| `--fs-xs` | 0.75 / 1rem | 500 | Badges, timestamps, overlay legend |
| `--fs-sm` | 0.875 / 1.25rem | 400–500 | Body text, table cells, labels |
| `--fs-md` | 1 / 1.5rem | 500 | Card titles, inputs |
| `--fs-lg` | 1.25 / 1.75rem | 600 | Page titles |
| `--fs-xl` | 2 / 2.25rem | 600 | Counts on the dashboard |

LCD type scale (relative to the screen, so one layout fits 32″ to 65″):

| Role | Size | Weight |
|---|---|---|
| Hallway name | `clamp(28px, 4.5vh, 72px)` | 600 |
| Waiting count (number) | `clamp(64px, 16vh, 240px)` | 700, `tnum` |
| Count label | `clamp(20px, 3vh, 48px)` | 500, `--text-muted` |
| Checkout row | `clamp(24px, 4vh, 64px)` | 600 |

Minimum LCD text: **4 vh** for anything a shopper must read (about 43 px on a 1080p panel, legible at 6 m).

### 3.5 Space, radius, layout

- **Spacing** (4 px base): `--s-1: 4px`, `--s-2: 8px`, `--s-3: 12px`, `--s-4: 16px`, `--s-5: 24px`, `--s-6: 32px`, `--s-7: 48px`, `--s-8: 64px`.
- **Radius:** `--r-sm: 4px` (inputs, badges), `--r-md: 8px` (cards, video), `--r-full: 999px` (status pills, dots).
- **Widths:** admin content up to 1440 px; forms up to 640 px.
- **Breakpoints:** `640px` (single column), `1024px` (2 camera tiles), `1600px` (3 camera tiles). The LCD fills the screen and switches columns by aspect ratio, not by width.
- **Hit targets:** at least 36 × 36 px with a mouse, 44 × 44 px under `(pointer: coarse)`.

---

## 4. Components

### 4.1 App shell
- A top bar on `--bg-1`, 56 px high, with a bottom border. It holds the product mark, the navigation (Supervision · Caméras · Écran LCD ↗), and on the right a **live summary** ("2 caméras en direct · 9 en attente") followed by the user menu.
- The active nav item gets a `--text` color and a 2 px bottom bar. Inactive items are `--text-muted`.
- The product mark is a neutral monogram (a lens or bracket shape), never a semantic color.

### 4.2 Buttons
| Variant | Style | Use |
|---|---|---|
| Primary | `--text` background, `--bg-0` text | One per view: Ajouter, Enregistrer, Se connecter |
| Secondary | `--bg-2` background, `--line-strong` border | Effacer le tracé, Annuler |
| Danger | Transparent, `--state-busy` text and border | Supprimer, always confirmed first |
| Ghost | Text only, `--text-muted` | Inline actions in lists |

Height 36 px (44 px on touch), `--r-sm`, label at `--fs-sm`/500. Disabled buttons drop to 40 % opacity with a `not-allowed` cursor. A loading button keeps its width and shows a 14 px spinner in place of its label.

### 4.3 Form fields
- The label sits above the field (`--fs-xs`, uppercase, 0.04em letter spacing, `--text-muted`). Fields have a `--bg-2` background, a `--line-strong` border, and height 36 px.
- Focus: the border changes to `--text`, plus the focus ring. An invalid field gets a `--state-busy` border and a message directly underneath.
- The RTSP URL and IP fields use the mono font. The password field always masks its value and can't be read back. When editing, its placeholder is "•••••• (inchangé)".

### 4.4 Status badge
A pill: `--r-full`, the state's tint as background, the state color for text, and its drawn state shape (SVG dot, square or ring, from `StatusShape`) before the label: dot + "Libre", square + "Occupée", ring + "Fermée". It is the only place where state text appears in a compact form.

### 4.5 Camera tile (dashboard)
- 16:9 video on `--bg-2`, `--r-md`, with the annotated MJPEG stream filling it.
- Top-left over the video: a **live badge** (`● En direct`, the dot pulsing per §6) or `○ Hors ligne`. Top-right: the camera name.
- Below the video: one **hallway row** per hallway, showing the name, a big count (`--fs-xl`), and a status badge for each checkout.
- **Offline:** the last frame stays, dimmed to 30 %, with "Caméra hors ligne — reconnexion…" centered over it. A stale frame that still looks live would be misleading.
- **Loading:** a shimmer skeleton (§6), never a blank black box.

### 4.6 Hallway panel (dashboard side panel)
- The waiting count is the hero, in mono, rolling on change. Checkouts are listed as selectable rows with their badges. Selecting a row triggers the spotlight and opens the **inspector** (state, hallway, cashier zone, last change, camera) at the bottom of the panel.
- No coloured side edges. State lives in the badges only, so the panel stays calm.
- The panel header shows "maj il y a N s", and turns red with "données périmées" after 10 s without a successful refresh.

### 4.6b Activity panel
Under the camera tiles: the last 12 state changes from `/api/occupancy-logs/` (time · hallway · people waiting · free checkouts), refreshed every 5 s. It's the PRD's "historique", made visible.

### 4.7 Tables (Cameras)
- Row height 48 px, header on `--bg-2` (`--fs-xs`, uppercase), hover row `--bg-2`. Columns: Nom · Adresse IP (mono) · URL RTSP (mono, truncated with the full value on hover) · État (badge) · actions on the right.
- **Empty state:** "Aucune caméra" plus one sentence on what to do, and a primary button that focuses the add form.

### 4.8 Mapping canvas
- The snapshot fills the width, with the SVG overlay on top. **Tool chips** above it: `Couloir`, `Caisse (côté client)`, `Zone caissier`. They're single-select, and each carries its zone color and shape, so the admin knows what they're drawing *before* clicking.
- Draft polygon: a 2 px dashed stroke in the color of the selected tool, with numbered vertex handles. **Enter** saves, **Esc** cancels, **Backspace** removes the last point.
- A legend and zone list sits in a side panel at ≥1024 px, or below the canvas on smaller screens.

### 4.9 Feedback
- Inline errors go next to the source: field, card, or the top of the form. Text is plain French, with the problem first and then the fix, e.g. "Caméra injoignable. Vérifiez l'URL RTSP et que la caméra est allumée."
- Successful saves show a toast (bottom-right, 4 s, `role="status"`). Destructive actions ask for confirmation in a dialog that names the object: "Supprimer la caméra « Entrée » et ses 3 zones ?"

---

## 5. LCD screen

- A full-screen grid of hallway cards: one card at a time, then two side by side, then a 2×2 grid. Nothing else on screen: no navigation, cursor hidden after 3 s.
- **Card:** the hallway name, then the giant waiting count and its label, then the checkout rows. A checkout row is the drawn state shape, the name and the state word, all in the state color. The best free checkout gets an **"→ Allez à la Caisse 2"** line in `--state-free`. That's the one sentence a shopper needs.
- **Offline or stale data:** the card dims, shows "Données indisponibles", and keeps no stale count on screen. If the connection to the server drops, a slim bar at the top reads "Connexion perdue — nouvelle tentative…". The rest stays visible but dimmed.
- **Burn-in protection:** the whole layout shifts 0–2 px every 10 minutes, too slowly to notice.
- **Accessibility:** cards are `aria-live="polite"` for kiosk screen readers, and announcements are throttled to state changes.

---

## 6. Motion

Library: **Motion** (`motion/react`) for component state transitions and the number roll; CSS for loops and hovers.

| Token | Value | Use |
|---|---|---|
| `--dur-1` | 120 ms | Hover, press, focus |
| `--dur-2` | 200 ms | Badge color and state changes, toast enter |
| `--dur-3` | 320 ms | Card or panel enter, LCD state change |
| `--ease-out` | `cubic-bezier(0.2, 0, 0, 1)` | Things entering or changing |
| `--ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | Loops |

| Moment | Motion | Why |
|---|---|---|
| Waiting count changes | The digits **roll** (old out up, new in from below) over 240 ms, ease-out | The number visibly *changed*; a silent swap is missed |
| Checkout changes state | The badge cross-fades color over 200 ms, and the row background flashes once from the state tint to transparent over 600 ms | Draws the eye once, then stops |
| Live indicator | The dot's opacity pulses 1 → 0.35 → 1 every 2 s | "This is live" without moving anything |
| Cards and tiles appear | Opacity 0 → 1 and translate 8 px → 0 over 320 ms, staggered 40 ms per tile | Calm, ordered load |
| Skeleton | A shimmer sweep every 1.6 s, low contrast (`--bg-2` → `--bg-3`) | Loading without spinners on video |
| Toast | Slides 12 px up and fades in over 200 ms; leaves faster, 150 ms | Enter slow, exit fast |

Rules:
- Animate only `opacity` and `transform`, never layout properties. The dashboard runs MJPEG decoding at the same time, so motion must stay cheap.
- **`prefers-reduced-motion: reduce`** turns off the pulse, the roll (numbers swap instantly), the stagger and the flash. Color changes still happen, instantly.
- **LCD:** only the state-change cross-fade and the number roll. No looping motion apart from the 10-minute burn-in shift.

---

## 7. Video overlay (vision service)

Drawn by `draw_zones` / `draw_corners` in `vision_service/tracker.py`. It must match §3.2.

| Element | Rendering |
|---|---|
| Zone fill | Semantic color at **25 %** alpha |
| Zone outline | Semantic color, thickness `max(2, width / 400)` px, anti-aliased |
| Zone label | A solid badge in the semantic color with white text, at the zone's top-left: "Couloir A · 5", "Caisse 2", "Caissier" |
| Draw order | Hallway → checkout → cashier zone → people, so the most specific is on top |
| Customer | Four corner brackets in `--person`, 20 % of the shorter side of the box |
| Staff | The same brackets in `--zone-staff` |
| Face | Gaussian blur over the face (pose keypoints), or over the head region when the face isn't visible. Always on. |
| Checkout state on video | Busy → `--state-busy`, free → `--state-free`, closed → `--state-closed` with "(fermée)" in the label |

The overlay labels are ASCII only (OpenCV's Hershey font has no accents), so "fermee" stands in for "fermée". If accents matter, switch to rendering labels with a TrueType font (`cv2.freetype`).

---

## 8. Accessibility checklist
- Text contrast is at least 4.5 : 1 (large text 3 : 1). All tokens in §3 meet this on `--bg-1`.
- Every interactive element is reachable by keyboard and has a visible focus ring. Mapping can be done without a mouse for everything except placing points.
- No meaning relies on color alone (shape plus label, §3.3).
- Live regions: dashboard counts are `aria-live="polite"`, and errors are `role="alert"`.
- Video `alt`: "Flux annoté de la caméra {nom}". Snapshot `alt`: "Capture de la caméra {nom} pour cartographier les zones".
- Layout holds at 200 % browser zoom.

## 9. Don'ts
- Using blue or green for buttons or links: they read as hallway or free.
- Drop shadows, glows, glassmorphism or gradients on chrome.
- Showing a count without making clear when it's stale (camera offline).
- "personne(s)", "Error 502", raw JSON in error messages.
- Animating continuously on the LCD.
- Showing RTSP credentials anywhere, including in logs and URLs.

## 10. Where it lives

| What | File |
|---|---|
| CSS tokens and base styles | `frontend/src/styles.css` (`:root`) |
| Shared components (StatusShape, StatusBadge, RollingNumber, Flash, LiveIndicator, ConfirmDelete, toasts) | `frontend/src/components.jsx` |
| Motion | `motion/react` with `<MotionConfig reducedMotion="user">` in `App.jsx`; transform and opacity only |
| Icons | `lucide-react`. State shapes are drawn SVG (`StatusShape`), never Unicode glyphs |
| LCD | `frontend/src/pages/Lcd.jsx` |
| Overlay colors | `vision_service/tracker.py` (`*_COLOR` constants, BGR) |
| Fonts | `@fontsource-variable/inter`, `@fontsource/jetbrains-mono` (npm, bundled) |

When a semantic color changes, update **both** `styles.css` and `tracker.py` in the same commit.
