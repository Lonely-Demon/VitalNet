// i18n.js — react-i18next setup (FEATURES_ROADMAP §2.1).
// hi/ta are English placeholders pending clinician review — see
// src/locales/README.md. Only DISPLAYED labels are translated; wire-format
// values sent to the API (symptom ids, chief_complaint) are stable English
// identifiers untouched by language selection.
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'
import hi from './locales/hi.json'
import ta from './locales/ta.json'

const LANGUAGE_KEY = 'vn_language'

const storedLanguage = (typeof localStorage !== 'undefined' && localStorage.getItem(LANGUAGE_KEY)) || 'en'

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    ta: { translation: ta },
  },
  lng: storedLanguage,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

if (typeof document !== 'undefined') {
  document.documentElement.lang = storedLanguage
}

i18n.on('languageChanged', (lng) => {
  if (typeof localStorage !== 'undefined') localStorage.setItem(LANGUAGE_KEY, lng)
  if (typeof document !== 'undefined') document.documentElement.lang = lng
})

export default i18n
