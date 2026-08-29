# Locales

`en.json` is the source of truth for all i18n keys.

`hi.json` and `ta.json` are currently **byte-for-byte English placeholders**,
not real translations. This is deliberate (FEATURES_ROADMAP §2.1): machine-
translating clinical terminology (symptom names, complaint labels) without a
clinician review pass is a patient-safety issue, not a cosmetic one — a
mistranslated symptom option could change what a worker believes they're
recording. Populating these files with real, clinician-reviewed Hindi/Tamil
text is tracked as follow-on work requiring that review, not a coding task.

Until then, selecting Hindi or Tamil in the language switcher changes
`document.documentElement.lang` and persists the preference, but every
displayed string is still English. This is safer than shipping unreviewed
translations and calling it done.

When real translations are ready: replace the values (never the keys) in
`hi.json`/`ta.json`. Keys must stay in sync with `en.json` — `i18n.js`'s
`fallbackLng: 'en'` means a missing key falls back to English rather than
rendering blank, but a stale/missing key should still be added for
completeness.

`localeReviewManifest.json` is the machine-checkable review record. It records
the source version, translator and reviewer identities, review status, and
pilot-approval state for each locale. Hindi and Tamil must remain
`draft-placeholder` and `pilotApproved: false` until a qualified medical-language
reviewer completes a matched source-to-translation review. The language controls
surface this status to prevent draft text being mistaken for approved clinical
localization.
