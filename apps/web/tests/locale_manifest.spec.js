import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'

const readJson = (name) => JSON.parse(readFileSync(new URL(`../src/locales/${name}`, import.meta.url), 'utf8'))
const en = readJson('en.json')
const hi = readJson('hi.json')
const ta = readJson('ta.json')
const manifest = readJson('localeReviewManifest.json')

function leafKeys(value, prefix = '') {
  if (Array.isArray(value)) return [`${prefix}[]`]
  if (!value || typeof value !== 'object') return [prefix]
  return Object.entries(value).flatMap(([key, child]) => leafKeys(child, prefix ? `${prefix}.${key}` : key))
}

test.describe('localization review manifest', () => {
  test('locale resources preserve English key parity', () => {
    expect(leafKeys(hi).sort()).toEqual(leafKeys(en).sort())
    expect(leafKeys(ta).sort()).toEqual(leafKeys(en).sort())
  })

  test('wire identifiers remain stable and draft locales are not pilot approved', () => {
    expect(manifest.sourceLocale).toBe('en')
    expect(manifest.wireIdentifiersStable).toBe(true)
    expect(manifest.locales.hi.pilotApproved).toBe(false)
    expect(manifest.locales.ta.pilotApproved).toBe(false)
    expect(manifest.locales.hi.reviewStatus).toContain('qualified-medical-language-review')
    expect(manifest.locales.ta.reviewStatus).toContain('qualified-medical-language-review')
  })
})
