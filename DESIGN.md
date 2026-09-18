# Smart Street Food Safety AI — DESIGN.md

> **Purpose:** Project-specific visual and UX design specification derived from
> the supplied reference design document and adapted for **Smart Street Food
> Safety AI**.
>
> **Reference direction:** warm cream + yellow + forest-green editorial SaaS,
> hand-drawn illustration, outlined rounded cards, expressive condensed
> typography, authentic photography, and integrated product UI.
>
> **Implementation principle:** Preserve the visual language of the reference,
> but adapt the information architecture to a street-food safety platform with
> three distinct roles: **Consumer, Vendor, Reviewer**.
>
> **Important:** This document defines design direction, not official
> certification or regulatory authority. The product must never visually imply
> government/FSSAI/DigiLocker certification without a real authorized
> integration.

---

# 1. Project Snapshot

- **Product:** Smart Street Food Safety AI
- **Product type:** AI-assisted street-food hygiene, transparency, and safety-information platform
- **Primary users:** Consumers, street-food vendors, reviewers/food officers
- **Primary goal:** Make street-food hygiene information more visible,
  understandable, actionable, and evidence-based.
- **Core product systems:**
  - AI-assisted hygiene assessment
  - Four-view hygiene capture
  - Food-product/ingredient scanner for vendors
  - OCR + ingredient extraction + rule-based analysis
  - Public QR stall profile
  - OpenStreetMap hygiene discovery map
  - Reviewer monitoring and evidence inspection
  - Consumer feedback/reporting
  - English/Hindi/Marathi language support
- **Visual personality:** Friendly, trustworthy, human, editorial, illustrated,
  modern, energetic, distinctly Indian without looking like a government portal.
- **Primary experience difference by role:**
  - **Consumer:** Discover → understand → scan → report
  - **Vendor:** Assess → improve → analyze products → share
  - **Reviewer:** Monitor → investigate → verify → flag
- **Important product boundary:** The **Food Product Scanner belongs to the
  Vendor experience**, not the Consumer experience.
- **Important visual boundary:** Hygiene scores are **AI-assisted assessment
  scores**, not official government certification.

---

# 2. Approved Visual Direction

## Overall Mood

The interface combines **modern civic/product technology with an illustrated
editorial identity**.

The dominant visual language is:

- Warm pale-cream background.
- Bright yellow promotional or highlight sections.
- Deep forest-green typography and structural panels.
- Fresh medium-green accents.
- Thin dark-green/ink outlines.
- Rounded cards and pill-shaped controls.
- Large condensed display headlines.
- Hand-drawn organic illustrations.
- Authentic Indian street-food photography.
- Product screenshots embedded into visual storytelling.
- Strong section-to-section color transitions.
- Generous whitespace.
- Friendly, reassuring microcopy.

The result should feel:

**human + trustworthy + modern + playful + practical**

rather than:

**clinical + corporate + bureaucratic + generic AI dashboard**.

## Premium Quality Signals

Premium execution should come from consistency:

- Restrained green/yellow/cream palette.
- Strong typographic hierarchy.
- Consistent dark outlines.
- Carefully designed score components.
- High-quality food/stall photography.
- Consistent illustration linework.
- Repeated rounded card language.
- Strong alignment between UI and imagery.
- Clear evidence hierarchy.
- Purposeful whitespace.
- Consistent map, QR, hygiene, and dashboard components.

## Density

Overall density should be **moderate**.

The product contains significant information, but users should not feel buried
under technical data.

Consumer screens should be the lightest.

Vendor screens can be moderately dense because the vendor is performing tasks.

Reviewer screens can be the densest because reviewers need investigation data.

---

# 3. Product Experience Architecture

## Consumer

The consumer experience is **discovery-first**.

Primary journey:

```text
Open App
    ↓
Nearby Stalls / Hygiene Map
    ↓
Select Stall
    ↓
View Hygiene Score
    ↓
View Public Stall Profile
    ↓
Scan QR or return to map
    ↓
Report an issue if needed
```

Consumer should NOT see the food-product scanner.

## Vendor

The vendor experience is **action-first**.

Primary journey:

```text
Dashboard
    ↓
Hygiene Check
    ↓
Overall
Preparation
Storage
Waste
    ↓
AI-assisted assessment
    ↓
Score + findings + recommendations
    ↓
Improve stall
    ↓
Food Product Scanner
    ↓
OCR → ingredients → rules → explanation
    ↓
Share QR
```

## Reviewer

The reviewer experience is **evidence-first**.

Primary journey:

```text
Reviewer Dashboard
    ↓
Stall / Vendor Table
    ↓
Assessment
    ↓
Evidence
    ↓
Score History
    ↓
Product Investigation
    ↓
Flag
    ↓
Resolve / Monitor
```

---

# 4. Design System

## 4.1 Color System

The visual identity uses a deliberately restricted palette.

### Core Palette

| Token | Approx. HEX | Role |
|---|---:|---|
| `background.primary` | `#FFFCEB` | Main canvas |
| `background.secondary` | `#FFF04A` | High-energy section |
| `surface.default` | `#EDF2C8` | Supporting cards |
| `surface.soft` | `#F7F5C7` | Quiet cards/panels |
| `surface.dark` | `#0B4516` | High-emphasis sections |
| `accent.primary` | `#35C56D` | Main green accent |
| `accent.secondary` | `#D8E86B` | Lime highlight |
| `accent.yellow` | `#FFE714` | Primary promotional accent |
| `text.primary` | `#10220F` | Main text |
| `text.inverse` | `#FFFCEB` | Text on dark surfaces |
| `border.default` | `#10220F` | Outlines |
| `white` | `#FFFFFF` | QR/photo/surface contrast |

> Exact values are implementation starting points adapted from the reference
> direction. Treat them as tokens rather than immutable screenshot values.

### Color Usage Rules

- Cream should provide most breathing room.
- Forest green is the primary structural color.
- Fresh green is the primary positive/action accent.
- Bright yellow creates energy and section hierarchy.
- Dark ink should anchor borders and typography.
- Avoid unrelated blues, purples, or rainbow palettes unless required for
  semantic data visualization.
- Do not turn every section bright yellow; use color rhythm intentionally.

---

# 5. Hygiene Score Color System

Hygiene status must communicate through:

**color + icon + label + numeric score**

Never use color alone.

## Score Bands

| Score | Label | Visual |
|---:|---|---|
| 80–100 | HIGH HYGIENE SCORE | 🟢 Green |
| 60–79 | MODERATE HYGIENE SCORE | 🟡 Yellow |
| 40–59 | NEEDS IMPROVEMENT | 🟠 Orange |
| 0–39 | LOW HYGIENE SCORE | 🔴 Red |

### Example

```text
86 / 100
🟢 HIGH HYGIENE SCORE
```

### Consumer wording

Use:

- High hygiene score
- Moderate hygiene score
- Needs improvement
- Low hygiene score

Avoid presenting the score itself as an official declaration of:

- Government safety certification
- FSSAI certification
- Government approval
- Guaranteed food safety

---

# 6. Typography System

## Heading Style

The reference's expressive condensed/editorial typography is an important part
of the brand language.

Characteristics:

- Heavy display weight.
- Condensed proportions.
- Tight line-height.
- Strong vertical presence.
- Dark green primary color.
- Occasional italic/highlight treatment.
- Short, confident headlines.

### Recommended implementation

For a close visual direction, use one condensed display face such as:

- Barlow Condensed
- Roboto Condensed
- Oswald

Use only one primary display font.

Pair it with one clean sans-serif such as:

- Inter
- DM Sans
- Manrope

Use only one body font.

## Hierarchy

| Level | Approx. Desktop | Weight | Usage |
|---|---:|---:|---|
| Display | 64–88px | 700–800 | Landing hero |
| H1 | 48–64px | 700–800 | Major pages |
| H2 | 36–52px | 700–800 | Major section |
| H3 | 24–32px | 700 | Card/feature |
| Body Large | 18–21px | 500 | Intro copy |
| Body | 15–17px | 400–500 | Standard copy |
| Small | 13–14px | 500 | Supporting info |
| Caption | 11–13px | 500–600 | Metadata |
| Button | 12–15px | 700 | CTA |

Approximate values; tune to the chosen font.

## Role-Specific Typography

### Consumer

Prioritize:

- readable score
- short labels
- simple explanations
- large CTA

### Vendor

Prioritize:

- task labels
- step numbers
- score
- actionable recommendations

### Reviewer

Prioritize:

- compact metadata
- table density
- evidence labels
- timestamps
- status labels

---

# 7. Spacing System

Use a consistent 4px/8px-derived scale:

```text
4px    space-1
8px    space-2
12px   space-3
16px   space-4
20px   space-5
24px   space-6
32px   space-8
40px   space-10
48px   space-12
64px   space-16
80px   space-20
96px   space-24
128px  space-32
```

### Typical Usage

- Icon → label: 6–10px
- Label → value: 4–8px
- Card padding: 16–24px
- Card gap: 16–24px
- Section gap: 64–96px
- Major section padding: 72–128px
- Mobile page padding: 16–20px
- Desktop page padding: 24–48px

Do not introduce random one-off spacing.

---

# 8. Grid & Alignment

## Desktop

- Centered content container.
- Approx. max width: 1120–1280px.
- 12-column conceptual grid.
- 24–32px gutters.
- Decorative art may escape the content grid.
- Core data and controls remain aligned.

## Tablet

- 2-column layouts where practical.
- 20–28px page margins.
- Stack only when readability requires it.

## Mobile

- Single-column primary content.
- 16–20px page padding.
- 12–16px card gaps.
- Full-width or near-full-width cards.
- Touch-first controls.
- Decorative art becomes secondary.

## Invisible Alignment Rules

Maintain shared alignment lines for:

- page headings
- card edges
- score components
- section titles
- CTA groups
- map filters
- dashboard content

Never allow every section to invent its own left/right edge.

---

# 9. Shape, Border, and Radius System

## Radius

```text
radius-sm:    8px
radius-md:    12px
radius-lg:    16px
radius-xl:    20px
radius-2xl:   24px
radius-pill:  999px
radius-circle: 50%
```

## Borders

Default:

```css
1px solid var(--border-default)
```

The reference relies on visible outlines more than on heavy shadows.

Use outlines around:

- cards
- score panels
- QR cards
- product scan cards
- reviewer panels
- banners
- map popups
- forms

## Shadows

Use subtle shadows only.

```css
shadow-subtle:
0 2px 8px rgba(16, 34, 15, 0.08);

shadow-card:
0 4px 14px rgba(16, 34, 15, 0.10);
```

Depth should primarily come from:

- color
- borders
- overlap
- composition
- section contrast

---

# 10. Imagery & Photography

## Photography Direction

The product should use authentic Indian street-food environments.

Preferred:

- real-looking food stalls
- stainless-steel carts
- vendors preparing food
- Indian streets and markets
- natural daylight
- realistic skin tones
- candid human expressions
- documentary/lifestyle feeling
- food close-ups
- practical hygiene contexts

Avoid:

- generic Western stock photography
- unrealistic futuristic food stalls
- overly polished corporate stock
- fake government inspection imagery
- dramatic "dirty vendor" stereotypes

The vendor should be represented as a partner trying to improve, not as an
antagonist.

## Product Imagery

Use product screenshots inside:

- rounded outlined containers
- phones/device frames when useful
- editorial feature layouts
- illustrated scenes

## Image Ratios

Recommended:

- Hero: 4:3 or device-shaped
- Stall photo: 4:3
- Testimonial: 16:9 or 4:3
- Evidence image: preserve source aspect ratio
- Map: responsive container
- QR: square

---

# 11. Illustration Language

The visual reference uses a hand-drawn world. Adapt that language to street
food.

## Suitable Motifs

- food carts
- pani puri plate/bowl
- chai glass
- cooking pot
- vegetables
- utensils
- water container
- covered food
- hand-washing illustration
- trash/waste bin
- leaves
- clouds
- city/street silhouettes
- small food icons

## Style

- Dark forest-green outline.
- Flat fills.
- Organic forms.
- Minimal shading.
- Slightly imperfect handmade contours.
- Cream/green/yellow palette.
- Simple expressive characters.

The illustrations should feel like one visual universe.

Do not use unrelated 3D iconography.

---

# 12. Navigation System

## Consumer

Mobile-first bottom navigation:

```text
Home
Map
Scan QR
Profile
```

Potential desktop adaptation:

```text
Logo | Home | Map | Scan QR | Profile
```

## Vendor

```text
Dashboard
Hygiene Check
Food Scan
History
My QR
My Stall
```

Mobile may use bottom navigation with an emphasized action for Hygiene Check.

## Reviewer

Desktop sidebar:

```text
Dashboard
Vendors
Assessments
Product Investigations
Flags
Hygiene Map
Analytics
Audit Log
Settings
```

The same color, type, icon, and spacing system should be used across all
roles.

---

# 13. Consumer Experience

## Consumer Design Principle

**Discover → Understand → Decide → Report**

The consumer should be able to understand stall status within seconds.

## Consumer Home

Possible structure:

```text
Header

Find street food near you

[ Search ]

[ Hygiene Map ]

Nearby stalls
┌──────────┐ ┌──────────┐
│ Stall    │ │ Stall    │
│ 🟢 86    │ │ 🟡 68    │
└──────────┘ └──────────┘
```

## Hygiene Map

OpenStreetMap is the primary map layer.

Display:

- food-stall markers
- score
- score band
- search
- filtering
- stall popup
- public profile entry

### Marker

```text
    🟢
   86/100
```

### Popup

```text
Sharma Pani Puri

86/100
🟢 High hygiene score

Last assessed:
18 Sep 2026

[View Stall]
```

## Map Filters

```text
All
High
Moderate
Needs Improvement
Low
```

Optional:

- Food category
- Radius/distance
- Search

Do not overload the consumer map with reviewer controls.

## Public Stall Profile

Show:

- Stall name
- Food category
- Hygiene score
- Score band
- Last assessment date
- Consumer-friendly explanation
- Public location/map
- QR identity
- Advisory notice

Do not expose:

- vendor email
- internal IDs
- reviewer notes
- private audit information
- sensitive vendor data

## Consumer Feedback

Provide a simple report mechanism:

```text
Is this stall information accurate?

[ Yes ] [ No ]

Report:
- Stall moved
- Stall no longer exists
- Location incorrect
- Hygiene condition appears different
- QR mismatch
- Other
```

Feedback must enter a review/flag workflow.

Consumer feedback must NOT directly rewrite the AI score.

---

# 14. Vendor Experience

## Vendor Design Principle

**Assess → Improve → Analyze → Share**

The vendor interface should feel practical, fast, and usable outdoors.

Large controls, short instructions, strong contrast, and minimal typing.

## Vendor Dashboard

```text
My Stall

Sharma Pani Puri

86 / 100
🟢 HIGH HYGIENE SCORE

↑ 8 from previous assessment

Issues:
⚠ Uncovered food
⚠ Surface clutter

[ Start Hygiene Check ]

[ Scan Food Product ]

[ My QR ]
```

## Hygiene Check

Four required views:

1. Overall
2. Preparation Area
3. Storage Area
4. Waste Area

Capture flow:

```text
Step 1 of 4
OVERALL

[ Camera Preview ]

Take photo
```

Then:

```text
Step 2 of 4
PREPARATION AREA
```

Continue through 4/4.

Do not allow incomplete checks to become valid completed assessments.

## Checklist

Checklist should be visually simple.

Example:

```text
✓ Food covered
✓ Utensils clean
✓ Storage covered
✓ Waste area maintained
```

The checklist should supplement visual evidence rather than overpower it.

## Hygiene Result

Show:

- Final score
- Visual score
- Checklist score
- Score band
- Findings
- Evidence
- Recommended action
- Assessment date

Example:

```text
86 / 100
🟢 HIGH HYGIENE SCORE

Found:
⚠ Surface clutter

Recommended:
Clear preparation surface.
```

Always show:

> AI-assisted assessment — not an official certification.

## Hygiene History

Show:

- date
- score
- score change
- major findings
- assessment status

Use a fixed 0–100 chart scale.

## Food Product Scanner — Vendor Only

This is a major vendor tool.

Flow:

```text
Camera / Upload
      ↓
Image Quality
      ↓
OCR
      ↓
Ingredient Extraction
      ↓
Normalization
      ↓
Knowledge-Base Match
      ↓
Rule Evaluation
      ↓
Confidence
      ↓
Explanation
      ↓
Translation
```

### Scan Result

```text
Product:
XYZ Chilli Sauce

OCR Confidence      94%
Ingredient Match    89%
Rule Strength       High

Potential concern

[ Explanation ]

[ View OCR ]
[ View Ingredients ]
```

Support:

- English
- Hindi
- Marathi

Reuse the existing local translation architecture.

Do not move this feature into the consumer experience.

## Product Scan History

Vendor can view:

- product
- date
- status
- confidence
- explanation
- scan image where permitted

## Vendor QR

Vendor can:

- view QR
- enlarge QR
- download QR
- print QR
- share QR
- open public profile

Keep a clean white safety area around the QR.

Do not overlap decorative artwork over the QR finder patterns.

## Vendor Stall Profile

Editable fields may include:

- stall name
- food category
- address
- latitude
- longitude
- approved public contact information
- preferred language

The vendor explicitly chooses/provides their stall location.

---

# 15. Reviewer Experience

## Reviewer Design Principle

**Monitor → Investigate → Verify → Flag**

The reviewer UI can be denser than consumer/vendor UI.

## Dashboard

KPI cards:

```text
Total Stalls
Assessed Stalls
Flagged Stalls
Average Score
Checks – Last 7 Days
```

Score distribution:

```text
80–100
60–79
40–59
0–39
```

Do not invent statistics.

## Vendor Table

Columns:

- Stall
- Hygiene Score
- Band
- Last Assessment
- Flag Status
- Product Activity
- Actions

Controls:

- search
- band filter
- flagged filter
- product-scan filter
- sort
- pagination

## Stall Detail

Show:

- stall information
- current score
- score history
- assessment history
- four hygiene views
- findings
- flags
- product scans

## Evidence Panel

For each detection, show where available:

- indicator
- confidence
- view
- source
- raw model label
- count
- bounding box
- penalty
- evidence image

If a detection has no bounding box, do not fabricate one.

## Score Breakdown

Show:

```text
Visual Score
Checklist Score
Final Score

Weights
Formula Version
Assessment Date
```

Reuse the project's existing scoring logic.

## Product Investigation

Show the evidence chain:

```text
IMAGE
 ↓
OCR
 ↓
INGREDIENTS
 ↓
MATCH
 ↓
RULE
 ↓
RESULT
 ↓
CONFIDENCE
```

Reviewer can inspect the original image and intermediate evidence.

## Flags

Show:

- open flags
- resolved flags
- reason
- creator
- created time
- resolver
- resolution note
- resolved time

## Reviewer Map

Reuse the same hygiene map system used for consumers.

Reviewer can additionally inspect more detail on selection.

## Analytics

Possible panels:

- score distribution
- score trend
- assessment activity
- indicator frequency
- flags open/resolved
- product scan activity

---

# 16. Digital Hygiene Assessment Badge

The reference direction includes certificate-like visuals. Adapt this concept
carefully.

Allowed:

```text
SMART STREET FOOD SAFETY AI

Sharma Pani Puri

86 / 100
HIGH HYGIENE SCORE

AI-ASSISTED ASSESSMENT

Last assessed:
18 September 2026

QR
```

Do NOT use claims such as:

- Government Certified
- FSSAI Certified
- Government Approved
- DigiLocker Verified
- Official Food Safety Certificate

unless a real authorized integration exists.

The badge should be a product assessment artifact, not a fake regulatory
credential.

---

# 17. QR Visual System

The physical QR sticker/sign is an important product touchpoint.

## Recommended composition

```text
SMART STREET FOOD
SAFETY AI

     [ QR ]

86 / 100
HIGH HYGIENE SCORE

Scan to view stall
```

Use:

- cream/white QR background
- dark green border
- strong whitespace around QR
- score badge
- short explanation
- optional illustrated border

The QR must remain machine-readable.

## Flow

```text
Physical Stall
     ↓
QR
     ↓
Public Stall Profile
     ↓
Hygiene Score
     ↓
Map / Details / Feedback
```

---

# 18. OpenStreetMap Hygiene Map

This should be a major product feature, not decoration.

## Map Visuals

Use:

- OpenStreetMap base layer
- branded score markers
- compact popups
- map legend
- score filters
- search
- responsive controls

## Marker System

High:

```text
🟢 86
```

Moderate:

```text
🟡 68
```

Needs Improvement:

```text
🟠 47
```

Low:

```text
🔴 29
```

## Mobile

Use:

```text
MAP

[ Search ] [ Filter ]

        Map

      ↓ Tap

┌────────────────────────┐
│ Sharma Pani Puri       │
│ 86/100 🟢              │
│ High hygiene score     │
│ [ View Stall ]         │
└────────────────────────┘
```

Prefer a bottom sheet for selected stalls rather than a cramped desktop
popup.

---

# 19. Product/UI Mockups

Product UI should appear as realistic evidence of the platform.

Useful mockups:

- hygiene capture screen
- hygiene score card
- food-product scan
- OCR/ingredient result
- QR profile
- hygiene map
- reviewer evidence panel
- score history

The mockups should share:

- same typography
- same color tokens
- same radius
- same borders
- same iconography

Avoid making each screenshot look like a different application.

---

# 20. Cards

Reusable card variants:

### HygieneScoreCard

Contains:

- title
- score
- band
- trend
- date

### StallCard

Contains:

- image
- stall name
- category
- score
- distance/status if supported

### MapPopupCard

Contains:

- stall
- score
- date
- CTA

### AssessmentCard

Contains:

- assessment date
- score
- findings
- status

### ProductScanCard

Contains:

- product
- scan status
- confidence
- explanation

### EvidenceCard

Contains:

- image
- detection
- confidence
- evidence metadata

### FlagCard

Contains:

- reason
- stall
- state
- dates
- resolution

---

# 21. Buttons

## Primary

Bright yellow or fresh green depending on surface.

Examples:

```text
Scan QR
Start Hygiene Check
Scan Product
View Stall
```

## Secondary

Outlined:

```text
View History
See Evidence
Open Map
```

## Destructive / Flag

Use a clearly distinct semantic treatment without introducing a whole new
visual language.

## Button Rules

Approx.:

- height: 40–48px
- horizontal padding: 16–24px
- compact bold label
- rounded/pill or soft-rounded

Consumer and vendor touch targets should be at least ~44px.

---

# 22. Forms

Use:

- clear labels
- compact helper text
- rounded fields
- dark outlines
- strong focus ring
- simple validation

Important forms:

- vendor onboarding
- stall profile
- location
- product scan upload
- consumer report
- reviewer flag

Avoid dense multi-column forms on mobile.

---

# 23. Tables

Reviewer tables only.

Visual rules:

- clear header
- thin borders
- moderate row height
- score badge
- status icon + label
- compact actions
- hover state
- selected state
- pagination
- empty state
- loading skeleton

Avoid turning consumer/vendor experiences into table-heavy interfaces.

---

# 24. Charts

Use the same brand palette.

Priority:

1. Deep green
2. Fresh green
3. Yellow
4. Lime
5. Dark ink

Avoid rainbow charts.

Recommended charts:

- Hygiene score history
- Score-band distribution
- Assessment activity
- Hygiene indicator frequency
- Flag status
- Product scan activity

For hygiene history:

- fixed 0–100 y-axis
- visible data points
- clear dates
- no exaggerated fitted scale

---

# 25. State Design

Every major component should define:

```text
DEFAULT
HOVER
ACTIVE
FOCUS
DISABLED
LOADING
ERROR
EMPTY
SUCCESS
```

Especially:

- Map
- QR scanner
- Hygiene capture
- Product scanner
- Score card
- Tables
- Forms
- Feedback

## Error Style

Prefer:

```text
[ icon ]

Something went wrong.

Try again.
```

Keep language human and actionable.

---

# 26. Camera / Scan UI

Camera is a key vendor interaction.

## Hygiene Capture

Use:

- large camera area
- subtle framing guides
- view title
- progress indicator
- capture CTA
- retake option
- photo-quality feedback

Example:

```text
Preparation Area

Place the preparation surface
inside the frame.

┌─────────────────────┐
│                     │
│    camera view      │
│                     │
└─────────────────────┘

[ Capture ]
```

## Product Scan

Provide:

- camera
- upload fallback
- quality feedback
- retry
- processing state

Do not expose technical pipeline names unless useful.

---

# 27. AI Explainability

AI output should follow:

```text
RESULT
 ↓
WHY?
 ↓
EVIDENCE
 ↓
CONFIDENCE
 ↓
RECOMMENDED ACTION
```

Example:

```text
Potential hygiene concern

Why?
Uncovered food detected in the preparation area.

Confidence:
78%

Evidence:
[ image ]

Recommended:
Cover exposed food and retake the preparation-area photo.
```

For vendor product scans:

```text
Potential concern

Why?
A configured ingredient rule matched the scanned label.

OCR confidence:
94%

Match confidence:
89%

Rule strength:
High
```

Do not make AI feel like an unexplained black box.

---

# 28. Trust & Safety Language

Preferred terms:

- AI-assisted assessment
- Hygiene score
- High hygiene score
- Moderate hygiene score
- Needs improvement
- Low hygiene score
- Potential concern
- Needs review
- Evidence
- Confidence
- Recommended action

Avoid implying:

- absolute safety
- laboratory certification
- government certification
- guaranteed food safety

Every assessment/result surface should retain an appropriate advisory notice.

---

# 29. Responsive Behavior

Responsive behavior is partly inferred from the reference visual direction.

## Desktop

- rich editorial compositions
- split hero/features
- reviewer sidebar
- 3-column content when useful
- large score cards
- full map controls

## Tablet

- reduce display scale
- 2-column feature layouts
- smaller artwork
- tighter but still generous spacing
- reviewer tables may horizontally scroll

## Mobile

### Consumer

- bottom navigation
- map-first experience
- bottom-sheet stall details
- stacked stall cards
- one-column pages

### Vendor

- camera-first interactions
- large touch targets
- step-by-step hygiene capture
- stacked result cards
- compact bottom navigation

### Reviewer

- desktop-first but usable on tablet
- sidebar may collapse
- tables can scroll horizontally
- evidence panel may stack

---

# 30. Motion

Motion intensity:

**Subtle to moderate.**

The brand is already expressive through color, type, and illustration.

Recommended:

- button response: quick
- score reveal: short
- card hover: subtle
- map marker selection: small scale/opacity change
- scan processing: restrained
- illustration movement: very subtle
- feature entrances: short staggered reveals

Suggested tokens:

```text
fast:   120–180ms
normal: 180–280ms
slow:   300–450ms
```

Respect:

`prefers-reduced-motion`.

Avoid:

- large bouncing animations
- constant floating art
- aggressive parallax
- scroll hijacking
- long entrance delays

---

# 31. Accessibility

The visual system must remain accessible.

Requirements:

- strong contrast
- visible focus
- semantic HTML
- keyboard navigation
- descriptive labels
- alt text
- 44px+ touch targets
- color-independent statuses
- readable body copy
- reduced-motion support

Score must always communicate:

```text
ICON + COLOR + TEXT + NUMBER
```

rather than color alone.

Map markers must have an accessible text representation.

QR scanner needs a non-camera fallback such as manual/public-code flow when
the product supports it.

---

# 32. Design Tokens

## Colors

```text
--color-background-primary
--color-background-secondary
--color-surface-default
--color-surface-soft
--color-surface-dark
--color-accent-primary
--color-accent-secondary
--color-accent-yellow
--color-text-primary
--color-text-inverse
--color-border-default
```

## Hygiene

```text
--hygiene-high
--hygiene-moderate
--hygiene-needs-improvement
--hygiene-low
```

## Typography

```text
--font-display
--font-body
--font-size-display
--font-size-h1
--font-size-h2
--font-size-h3
--font-size-body
--font-size-small
--font-size-caption
```

## Spacing

```text
--space-1
--space-2
--space-3
--space-4
--space-5
--space-6
--space-8
--space-10
--space-12
--space-16
--space-20
--space-24
--space-32
```

## Radius

```text
--radius-sm
--radius-md
--radius-lg
--radius-xl
--radius-2xl
--radius-pill
```

## Shadow

```text
--shadow-subtle
--shadow-card
```

## Motion

```text
--duration-fast
--duration-normal
--duration-slow
```

---

# 33. Component Inventory

## Shared

```text
AppShell
Container
Section
Header
Button
Badge
Pill
Card
IconButton
Modal
Toast
Tabs
```

## Consumer

```text
ConsumerHome
HygieneMap
StallMarker
MapLegend
MapFilters
StallPopup
StallBottomSheet
PublicStallProfile
HygieneScore
QRScanner
ConsumerReport
```

## Vendor

```text
VendorDashboard
HygieneScoreCard
HygieneCapture
HygieneStepIndicator
HygieneChecklist
HygieneResult
HygieneHistory
ProductScanner
OCRResult
IngredientResult
ProductScanHistory
QRCard
VendorProfile
```

## Reviewer

```text
ReviewerDashboard
VendorTable
AssessmentDetail
EvidencePanel
ScoreHistoryChart
ProductInvestigation
FlagPanel
Analytics
ReviewerMap
AuditLog
```

---

# 34. Page Specifications

## Consumer Home

### Purpose

Help consumers discover food stalls and quickly understand hygiene information.

### Primary elements

- search
- nearby stalls
- hygiene map CTA
- QR scan CTA
- recent stalls

### Visual priority

1. Nearby/map action
2. Hygiene score
3. Stall
4. Supporting information

---

## Consumer Hygiene Map

### Purpose

Discover stalls by hygiene score.

### Layout

- full map
- top search/filter controls
- marker layer
- legend
- mobile bottom sheet

### Primary action

Select stall.

### Required information

- name
- score
- band
- last assessed
- view profile

---

## Public Stall Profile

### Purpose

Provide trustworthy, public, concise stall information.

### Layout

- stall identity
- large hygiene score
- score band
- last assessment
- relevant findings
- public location/map
- feedback/report

---

## Vendor Dashboard

### Purpose

Give the vendor immediate operational awareness.

### Layout

- stall header
- large score card
- issues
- primary actions
- history preview
- QR preview

---

## Vendor Hygiene Check

### Purpose

Capture the four required views.

### Required sequence

```text
Overall
↓
Preparation Area
↓
Storage Area
↓
Waste Area
```

### Primary interaction

Camera capture.

---

## Vendor Product Scanner

### Purpose

Analyze packaged food-product labels.

### Layout

- camera/upload
- scan guidance
- result
- OCR/ingredient details
- confidence
- explanation
- language switch

### Important

Vendor only.

---

## Vendor QR

### Purpose

Provide the physical/public stall identity.

### Layout

- large QR
- score
- stall name
- scan instruction
- download/print/share

---

## Reviewer Dashboard

### Purpose

Monitor the entire platform.

### Layout

- KPI row
- score distribution
- assessment activity
- flagged stalls
- recent activity

---

## Reviewer Stall Detail

### Purpose

Allow evidence-based investigation.

### Layout

```text
Stall
 ↓
Current Score
 ↓
Score History
 ↓
Four Views
 ↓
Findings
 ↓
Evidence
 ↓
Flags
 ↓
Product Scans
```

---

## Reviewer Product Investigation

### Purpose

Inspect the evidence chain behind a vendor product scan.

### Layout

Image → OCR → Ingredients → Match → Rule → Result.

---

# 35. UX Flows

## Consumer QR Flow

```text
Scan QR
  ↓
Resolve public code
  ↓
Public Stall Profile
  ↓
Hygiene Score
  ↓
View details
```

## Consumer Map Flow

```text
Open Map
  ↓
Find nearby stalls
  ↓
Tap marker
  ↓
View summary
  ↓
Open public profile
```

## Vendor Hygiene Flow

```text
Start Check
  ↓
Overall
  ↓
Preparation
  ↓
Storage
  ↓
Waste
  ↓
AI Assessment
  ↓
Score
  ↓
Recommendations
```

## Vendor Product Flow

```text
Scan Label
  ↓
Quality Gate
  ↓
OCR
  ↓
Ingredient Extraction
  ↓
Rule Analysis
  ↓
Confidence
  ↓
Explanation
```

## Reviewer Flow

```text
Dashboard
  ↓
Vendor
  ↓
Assessment
  ↓
Evidence
  ↓
Investigation
  ↓
Flag
  ↓
Resolution
```

---

# 36. Illustration / Brand Asset Rules

## Core visual motifs

Prefer a recognizable visual world built around:

- Indian street-food carts
- stainless-steel cooking surfaces
- vegetables
- spices
- utensils
- food bowls
- QR signs
- smartphones
- map/location symbols
- hygiene symbols
- plants
- clouds
- subtle city/street silhouettes

## Brand mascot

A small illustrated food/street-safety mascot may be used consistently if
introduced.

Do not create a new mascot for each screen.

## Illustration consistency

Keep:

- line weight
- palette
- shape language
- facial style
- shading level
- perspective

consistent across all illustrations.

---

# 37. Marketing/Landing Page Narrative

When a marketing website is needed, adapt the supplied editorial structure to
the product:

```text
HEADER
↓
HERO
↓
STREET-FOOD PROBLEM
↓
PRODUCT INTRO
↓
VENDOR HYGIENE ASSESSMENT
↓
FOOD PRODUCT SCANNER
↓
QR TRANSPARENCY
↓
OPENSTREETMAP HYGIENE MAP
↓
CONSUMER DISCOVERY
↓
REVIEWER EVIDENCE
↓
TRUST / EXPLAINABILITY
↓
NEWS / EDUCATION
↓
FINAL CTA
↓
FOOTER
```

## Hero example

Headline direction:

**Smarter hygiene for India's street food.**

Supporting idea:

**AI-assisted assessments, transparent stall profiles, and practical tools
for vendors, consumers, and reviewers.**

Primary CTA examples:

```text
Explore Hygiene Map
```

or:

```text
See How It Works
```

Do not use invented claims such as "100% safe".

---

# 38. Marketing Visual Storytelling

Use the reference's editorial technique:

### Section 1

Authentic street-food photography.

### Section 2

Vendor using phone for hygiene check.

### Section 3

Product scanner UI integrated into an image.

### Section 4

QR sign physically displayed at stall.

### Section 5

Map visualization with score markers.

### Section 6

Reviewer inspecting evidence.

### Section 7

Human-centered outcome.

This creates a coherent narrative:

```text
REAL WORLD
   ↓
AI ASSISTANCE
   ↓
EVIDENCE
   ↓
TRANSPARENCY
   ↓
ACTION
```

---

# 39. Trust Language

Preferred messaging:

- "AI-assisted hygiene assessment"
- "See the evidence behind the score"
- "Understand hygiene before you choose"
- "Practical guidance for vendors"
- "Transparent public stall profiles"
- "Evidence-based review workflows"

Avoid:

- "Guaranteed safe"
- "100% safe food"
- "Government certified"
- "Official FSSAI rating"
- "Official DigiLocker certificate"

unless legally/technically supported by a real authorized integration.

---

# 40. Anti-Drift Rules

## Color

Do not gradually drift into generic blue SaaS styling.

Preserve:

**cream + forest green + fresh green + yellow**

## Typography

Do not replace the condensed editorial display style with an ordinary
geometric SaaS heading.

## Cards

Do not create a completely new radius/border/shadow system for each role.

## Consumer

Do not add vendor-only operational controls.

Especially:

**NO FOOD PRODUCT SCANNER.**

## Vendor

Do not bury hygiene assessment under generic analytics.

The main experience is:

**check → score → improve**

## Reviewer

Do not simplify the reviewer experience until evidence disappears.

The reviewer must be able to inspect:

**result → reason → evidence → confidence**

## Illustrations

Do not replace the hand-drawn system with unrelated 3D illustrations.

## Maps

Do not use generic map pins everywhere.

Score markers should follow the hygiene-band system.

## Government Branding

Do not create fake official seals, government badges, FSSAI certification,
DigiLocker verification, or government approval.

---

# 41. Things the Builder Must Not Invent

Do not invent:

- regulatory certification
- government affiliations
- unsupported AI accuracy
- fake hygiene data
- fake analytics
- fake reviewer actions
- fake audit history
- unsupported location data
- unsupported food-safety claims
- arbitrary product capabilities
- unrelated page sections
- random brand colors
- unrelated illustration styles

If a feature is not supported by the backend, do not simulate it as real.

---

# 42. AI Implementation Instructions

When an AI coding agent receives this design file:

1. Read `DESIGN.md` first.
2. Identify the tokens.
3. Create shared styling primitives.
4. Create shared score-band utilities.
5. Build shared card/button/badge components.
6. Build the common navigation foundation.
7. Build role-specific information architecture.
8. Preserve consumer/vendor/reviewer boundaries.
9. Reuse the same hygiene score semantics everywhere.
10. Reuse one map visual language.
11. Reuse one illustration language.
12. Reuse one product-mockup language.
13. Do not introduce arbitrary colors.
14. Do not introduce random fonts.
15. Do not introduce random radii or shadows.
16. Do not duplicate existing functionality.
17. Follow responsive rules.
18. Follow accessibility requirements.
19. Preserve explanatory AI messaging.
20. Test the resulting interface at mobile and desktop widths.

---

# 43. Design Consistency Checklist

```text
[ ] Cream/green/yellow palette is consistent
[ ] Display typography is consistent
[ ] Body typography is readable
[ ] Spacing follows the token scale
[ ] Card radius is consistent
[ ] Borders are consistent
[ ] Shadows remain subtle
[ ] Buttons share one visual system
[ ] Score bands are identical everywhere
[ ] Score status uses color + icon + label + number
[ ] Consumer does not have Product Scanner
[ ] Vendor has Product Scanner
[ ] Vendor has four-view Hygiene Check
[ ] Consumer has Hygiene Map
[ ] Reviewer can access Hygiene Map
[ ] QR flow leads to public profile
[ ] Public profile hides private data
[ ] Reviewer can inspect evidence
[ ] Reviewer flags are visible and lifecycle-aware
[ ] Images feel authentically Indian
[ ] Illustrations share one style
[ ] Mobile experience is thumb-friendly
[ ] Reviewer experience supports dense data
[ ] AI disclaimer remains visible
[ ] No fake government certification
[ ] No unsupported claims
[ ] No random colors/fonts/styles
```

---

# 44. Core Product Design Principles

1. **Trust before decoration.**
2. **Make the hygiene score understandable in seconds.**
3. **Never communicate a safety status using color alone.**
4. **Consumer experience is discovery-first.**
5. **Vendor experience is action-first.**
6. **Reviewer experience is evidence-first.**
7. **Every AI result should explain why it exists.**
8. **The QR connects the physical stall to its public digital identity.**
9. **The map makes hygiene information discoverable geographically.**
10. **Food-product scanning belongs to vendors.**
11. **Consumer feedback should trigger review, not directly rewrite scores.**
12. **Use authentic Indian street-food imagery.**
13. **Keep illustrations consistent and human.**
14. **Use visual consistency as the primary premium-quality signal.**
15. **Never imply official certification without an authorized basis.**

---

# 45. Build Handoff Summary

## Strongest Design Constraints

1. **Cream + forest green + bright yellow is the defining palette.**
2. **Condensed/editorial typography is essential.**
3. **Hand-drawn illustration is a core brand system.**
4. **Thin dark outlines + rounded surfaces define components.**
5. **Whitespace and editorial composition are important.**
6. **Authentic Indian street-food photography should support trust.**
7. **Product UI should be integrated into visual storytelling.**
8. **Hygiene scores must use one shared visual language.**
9. **The OpenStreetMap hygiene map is a major consumer feature.**
10. **Vendor product scanning is separate from consumer discovery.**
11. **Reviewer interfaces must expose evidence rather than only outcomes.**
12. **The QR is a physical/digital bridge between stall and public profile.**

## Core Components

```text
Header
Container
Button
Badge
Card
HygieneScore
StallCard
HygieneMap
StallMarker
MapPopup
MapBottomSheet
QRScanner
QRCard
HygieneCapture
HygieneChecklist
HygieneResult
HygieneHistory
ProductScanner
OCRResult
IngredientResult
ProductScanHistory
VendorDashboard
PublicStallProfile
ReviewerDashboard
VendorTable
EvidencePanel
ProductInvestigation
FlagPanel
Analytics
Footer
```

## Responsive Priorities

- Preserve score and CTA hierarchy.
- Keep map usable on mobile.
- Keep camera workflows thumb-friendly.
- Keep product scan evidence readable.
- Stack feature layouts cleanly.
- Preserve whitespace.
- Protect image focal points.
- Allow reviewer tables to scroll rather than collapse into unreadable text.

---

# 46. Final Design Philosophy

Smart Street Food Safety AI should feel like a **human technology layer over
a familiar part of everyday Indian life**.

The visual grammar is:

**Warm cream  
+ forest green  
+ bright yellow  
+ fresh green  
+ expressive condensed typography  
+ outlined rounded surfaces  
+ hand-drawn food/street illustrations  
+ authentic photography  
+ clear AI evidence  
+ strong whitespace  
+ map-driven discovery**

The content can change from screen to screen.

The users can differ.

The workflows can differ.

But the visual language should remain unmistakably part of the same product.

**The experience should make technology feel approachable, make hygiene
information visible, and make AI results understandable.**
