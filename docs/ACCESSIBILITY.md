# VitalNet — Accessibility

**Target: WCAG 2.1 AA.** This document records what's been audited and
fixed, what's already correct by construction, and what's an honest
known gap — in the same spirit as `MODEL_CARD.md`'s limitations section:
say what's actually true, not what would look best.

The original audit below was a source-level review (grep + manual read of
every form-bearing component + computed color-contrast ratios) — an
automated scanner (`axe-core`, see "Automated CI check" below) now also
runs on every PR, but neither replaces a test with a real screen reader,
which still hasn't been done — that gap is called out again in "Known
gaps" below.

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

  **Superseded by the visual-identity redesign** (`docs/DECISIONS.md`
  §34): the whole palette was re-picked around a teal
  brand color kept deliberately outside the clinical red/amber/green
  system, not around these exact hex values. Re-verified by script at
  that time, not just carried over: `--color-text3` is now `#5A6B67`
  (**~5.13:1** on the page background), `--color-urgent` is now
  `#A85A0C` (**~4.64:1**) — both still clear AA, with the same
  reasoning (`--color-terra`-adjacent warm hue for `--color-urgent`,
  now a signal color deliberately separate from brand chroma). The
  redesign re-ran this same contrast check on every text/background
  pair before shipping; see `docs/DECISIONS.md` for the full token
  table.
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
- **Icon-only buttons all have `aria-label`.** The redesign replaced
  every emoji/glyph icon with `lucide-react` icons and added a second
  icon-only control (`NavBar.jsx`'s sign-out button — previously a
  "Sign out" text link); both it and `VoiceInputButton`'s mic button
  carry `aria-label`.
- **Badge-background contrast**, flagged as a known gap in an earlier
  pass of this audit (`TriageBadge` and the result-page badges rendering
  triage text on a translucent tint of the same color, ~4.0-4.3:1,
  short of AA), is resolved as a side effect of the visual-identity
  redesign: every triage badge is now solid-fill with white text
  (`bg-emergency text-white`, etc.), computed at **~5.1-7.8:1** across
  all four tiers plus the PENDING state — comfortably clear of AA. Not
  the redesign's original motivation (it was chasing a "stamped tag"
  look, not this gap specifically) but it closes it regardless.
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

## Automated CI check (axe-core)

- **`apps/web/tests/a11y.spec.js`**, wired into a new PR-triggered CI job
  (`a11y-frontend-pr`), runs `@axe-core/playwright`'s WCAG 2 A/AA ruleset
  against every role's main screen (login, ASHA intake + submissions,
  doctor queue, supervisor team metrics, admin analytics + users) using
  the mocked-auth Playwright technique from `docs/TESTING_STRATEGY.md` —
  no live Supabase project or secrets needed, same posture as
  `build-frontend-pr`. This replaces this document's previous "no
  automated testing" gap.
- **It immediately found four real, live contrast bugs the manual
  source-level review above had missed**, all now fixed:
  - `BriefingCard.jsx`'s differential-diagnosis numbered markers used
    `text-sage` (4.31–4.52:1, sub-AA once composited over the section's
    tinted background) — changed to `text-forest` (~7.4:1).
  - Four independent, hand-duplicated role/status badge color maps
    (`NavBar.jsx` and `AdminUsers.jsx`'s `ROLE_COLORS.supervisor`,
    `ASHAPanel.jsx`'s `TRIAGE_STYLES`, `ReferralsPanel.jsx`'s
    `STATUS_COLORS`, plus inline badges in `OutbreakSignals.jsx`,
    `Dashboard.jsx`, and `IntakeForm.jsx`) all used the same
    `bg-{tier}/5–10 text-{tier}` translucent-tint pattern — the plain
    tier color only just clears 4.5:1 on white to begin with (as low as
    3.79:1 on the `bg-sand` "saved offline" badge), so any tint pushed it
    below AA. Fixed by adding three darker `--color-{tier}-ink` tokens to
    `index.css` (`emergency-ink`/`urgent-ink`/`routine-ink`, ≥5.0:1 against
    every observed tint) and repointing all fourteen affected call sites
    to them — the same class of bug the redesign's badge-contrast fix
    (above) addressed for `TriageBadge`/`PRELIM_RESULT_STYLES`/
    `BADGE_COLORS`, just in components that fix never reached because
    each maintains its own independent color map.
  - This is exactly the value an automated scanner adds over a source
    read: the manual audit checked the *shipped* badge components but
    had no reason to re-derive the contrast math for every one of the
    ~14 places the same soft-tint pattern was independently reimplemented.

## Known gaps (honest, not fixed this pass)
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
