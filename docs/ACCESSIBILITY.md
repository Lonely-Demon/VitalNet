# VitalNet — Accessibility

**Target: WCAG 2.1 AA.** This document records what's been audited and
fixed, what's already correct by construction, and what's an honest
known gap — in the same spirit as `MODEL_CARD.md`'s limitations section:
say what's actually true, not what would look best.

This audit was a source-level review (grep + manual read of every
form-bearing component + computed color-contrast ratios), not a run of an
automated tool (axe/Lighthouse) or a test with a real screen reader —
that distinction matters and is called out again in "What's not done"
below.

## Fixed this pass

- **Form labels were visually present but not programmatically
  associated with their inputs**, the single most impactful finding.
  `IntakeForm.jsx`'s `Field` component rendered a `<label>` next to its
  input but never linked them (no `htmlFor`/`id`), so a screen reader
  landing on a field announced nothing about what it was. Fixed by
  threading an `id` prop through `Field` and every direct-input call site
  (`htmlFor`/`id` pairs, plus `aria-describedby` linking each field to its
  own error message). This is VitalNet's single most-used screen — every
  patient encounter goes through it — so this was the highest-value fix
  in the audit.
- The same pattern existed on `LoginPage.jsx` (the very first screen every
  user sees) and the admin create-user/create-facility forms
  (`AdminUsers.jsx`, `AdminFacilities.jsx`) — fixed identically.
- **Multi-input panels using a bare `<label>` as a heading** (BriefingCard's
  triage-override, outcome-recording, and referral panels — each a
  label followed by 2-3 different inputs) — a `<label htmlFor>` can only
  ever point to one control, so this was mislabeled by construction, not
  just missing an `id`. Converted each to `<fieldset>`/`<legend>`, the
  correct element for "one heading, several controls," and added
  `aria-label` to the individual selects/textareas for a redundant direct
  name.
- **No live-region announcements for async status changes.** `ToastProvider`
  (submission success/queued-offline/error feedback — the confirmation for
  the app's core action) and `OfflineBanner` (online/offline transitions,
  sync-in-progress) rendered plain `<div>`s with no `role`/`aria-live` —
  a screen reader user got no notification at all when a case was
  submitted, queued, or failed. Added `role="status" aria-live="polite"`
  to both.
- **Color contrast** — computed WCAG contrast ratios for every text/background
  pair in `index.css`'s design tokens (script-verified, not eyeballed):
  - `--color-text3` (labels, section headings, table headers — used
    everywhere) was `#9DB09D`, **~2.1:1** against the page background —
    failing AA even for large text (needs 3:1), let alone normal text
    (needs 4.5:1). Darkened to `#556B58`, **~5.0:1**.
  - `--color-urgent` (the URGENT triage color) was `#C17240`, **~3.3:1** —
    failing AA for normal-size text. Darkened to `#9C5A2B`, **~4.9:1**,
    kept in the same warm-terracotta hue family as `--color-terra` for
    palette consistency.
- **Login error message** and consent-checkbox error message weren't
  marked `role="alert"` — added, plus `aria-describedby` wiring the
  consent checkbox to its own error text.

## Already correct (verified, not assumed)

- **No images anywhere in the app** (`grep -rn "<img"` returns nothing) —
  no missing-alt-text risk exists structurally.
- **Triage severity is never color-only** — `TriageBadge.jsx` and every
  triage display always render the text label (`ROUTINE`/`URGENT`/
  `EMERGENCY`) alongside the color, so a colorblind user isn't dependent
  on hue to read triage level.
- **The one icon-only button in the app** (`VoiceInputButton`'s mic
  button, 🎤 with no visible text) already had `aria-label` before this
  audit.
- **Every `outline-none` in the codebase is paired with a `focus:ring-*`
  replacement** — verified by grep — so removing the default browser
  outline never leaves keyboard users without a visible focus indicator.
- **Heading structure**: `IntakeForm.jsx`'s `Section` component renders a
  real `<h2>` per section (Location, Patient, Vitals, Symptoms, etc.),
  giving screen reader users heading-based section navigation for the
  intake form without needing a fieldset around every group.
- **The language switcher** (`NavBar.jsx`) already had `aria-label` before
  this audit.
- **`document.documentElement.lang`** is kept in sync with the selected
  i18n language (`i18n.js`), so assistive tech uses the right
  pronunciation/hyphenation rules per language.

## Known gaps (honest, not fixed this pass)

- **Badge-background contrast is still short of AA in one specific
  context**: `TriageBadge` and the result-page badges render triage text
  at 100%-opacity color on a *10%-opacity tint* of that same color as the
  background (`bg-emergency/10 text-emergency`, etc.) — computed contrast
  there is **~4.0-4.3:1**, short of the 4.5:1 AA threshold for normal-size
  bold text (it would pass at the ≥18.66px-bold "large text" threshold of
  3:1, but `text-sm`/`text-lg` renders are borderline on that size cutoff
  depending on exact Tailwind size). Not fixed this pass — pushing the
  colors dark enough to clear 4.5:1 *on that specific tinted background*
  starts to look muddy against the plain-white/full-saturation contexts
  the same tokens are used in elsewhere. Worth a dedicated design pass,
  not a good target for a mechanical contrast bump.
- **No automated accessibility testing in CI** — no axe-core/Lighthouse-CI
  job exists. This audit was manual (source read + computed contrast
  ratios), which finds structural issues (missing labels, missing live
  regions) reliably but doesn't catch everything an automated scanner or
  a real assistive-technology user would (focus order edge cases, dynamic
  ARIA state correctness under interaction, actual screen-reader
  announcement phrasing).
- **No real screen-reader testing** (VoiceOver/NVDA/TalkBack) was
  performed — this document reflects source-level correctness, not
  verified real-world assistive-technology behavior.
- **No skip-to-content link** — every panel sits behind a persistent
  `NavBar`; a keyboard user must tab through nav on every page load. Minor
  for a role-scoped dashboard app (a handful of nav items, not a long
  menu), but a real gap for repeat keyboard-only users.
- **Symptom checkboxes** (`IntakeForm.jsx`'s symptom grid) rely on the
  `Section`'s `<h2>` for context rather than a `<fieldset>`/`<legend>`
  around the checkbox group specifically — each checkbox has its own
  clear visible label already, so this is a minor grouping enhancement,
  not a missing-label bug.

## How to keep this current

When adding a new form field anywhere in the app: give the input an `id`,
give its `<label>` a matching `htmlFor`, and if it can show a validation
error, wire `aria-describedby` to that error's own `id`
(`IntakeForm.jsx`'s `Field` component does all three automatically — reuse
it rather than a bare `<div><label/><input/></div>` on any new screen).
When adding a new async status notification, use `role="status"
aria-live="polite"` (or `"assertive"` for something that must interrupt),
matching `ToastProvider.jsx`/`OfflineBanner.jsx`.
