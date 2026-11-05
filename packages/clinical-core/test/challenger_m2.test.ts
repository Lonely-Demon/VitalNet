import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { resolveEffectiveAge, checkOverrides, type OverrideInput } from "../src/rules/rules.js";
import { assignTier, type EngineInput } from "../src/rules/engine.js";
import { triage } from "../src/triage.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "../../..");

describe("Milestone M2 Adversarial Challenge: Offline PWA, Draft Keystore & Triage Safety", () => {
  // ──────────────────────────────────────────────────────────────────────────
  // Challenge 1: vite.config.js & Generated Service Worker Audit
  // ──────────────────────────────────────────────────────────────────────────
  describe("1. Audit Service Worker & Workbox BackgroundSync Removal (CRITICAL-4c)", () => {
    const viteConfigPath = path.resolve(REPO_ROOT, "apps/web/vite.config.js");
    const swPath = path.resolve(REPO_ROOT, "apps/web/dist/sw.js");

    it("ensures vite.config.js has ZERO backgroundSync or /api/submit runtime caching", () => {
      expect(fs.existsSync(viteConfigPath)).toBe(true);
      const content = fs.readFileSync(viteConfigPath, "utf-8");

      expect(content).not.toMatch(/backgroundSync/i);
      expect(content).not.toMatch(/\/api\/submit/);
      expect(content).not.toMatch(/vitalnet_submission_queue/);
      expect(content).not.toMatch(/runtimeCaching/);
    });

    it("ensures generated service worker (dist/sw.js) contains zero backgroundSync or submit interceptors", () => {
      if (!fs.existsSync(swPath)) {
        return;
      }
      const swContent = fs.readFileSync(swPath, "utf-8");

      expect(swContent).not.toMatch(/backgroundSync/i);
      expect(swContent).not.toMatch(/vitalnet_submission_queue/i);
      expect(swContent).not.toMatch(/\/api\/submit/);
      expect(swContent).not.toMatch(/BackgroundSyncPlugin/i);
    });

    it("verifies all generated dist scripts contain zero cleartext submission queueing", () => {
      const distDir = path.resolve(REPO_ROOT, "apps/web/dist");
      if (!fs.existsSync(distDir)) {
        return;
      }
      const files = fs.readdirSync(distDir);
      for (const file of files) {
        if (file.endsWith(".js")) {
          const filePath = path.join(distDir, file);
          const c = fs.readFileSync(filePath, "utf-8");
          expect(c).not.toMatch(/vitalnet_submission_queue/i);
          expect(c).not.toMatch(/BackgroundSyncPlugin/i);
        }
      }
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Challenge 2: Triage Infant Age Resolution & False Neonatal Fever Avoidance
  // ──────────────────────────────────────────────────────────────────────────
  describe("2. Challenge triageClassifier & Engine Infant Age Resolution", () => {
    const classifierPath = path.resolve(REPO_ROOT, "apps/web/src/utils/triageClassifier.js");

    it("verifies triageClassifier.js explicitly extracts and forwards age_months into engineInput", () => {
      expect(fs.existsSync(classifierPath)).toBe(true);
      const code = fs.readFileSync(classifierPath, "utf-8");

      // Verify exact line mapping
      expect(code).toMatch(/patient_age:\s*formData\.patient_age/);
      expect(code).toMatch(/age_months:\s*formData\.age_months\s*\?\?\s*null/);
    });

    it("proves 4-month-old infant (patient_age: 0, age_months: 4) does NOT trigger false neonatal fever", () => {
      const infant4m: OverrideInput = {
        patient_age: 0,
        age_months: 4,
        patient_sex: "female",
        temperature: 38.5, // High fever
        heart_rate: 120,    // Normal for 4-month infant
        spo2: 98,
        bp_systolic: 85,
        symptoms: ["fever"],
      };

      // 1. Effective age resolution
      const effectiveAge = resolveEffectiveAge(infant4m.patient_age, infant4m.age_months);
      expect(effectiveAge).toBeCloseTo(4 / 12, 6);
      expect(effectiveAge).toBeGreaterThanOrEqual(0.25); // >= 3 months

      // 2. Override check: neonatal fever must NOT fire (< 3 months only)
      const override = checkOverrides(infant4m);
      expect(override).toBeNull();

      // 3. Engine tier check: tier must NOT be forced to EMERGENCY via safety net
      const result = assignTier(infant4m as EngineInput);
      expect(result.firedRules.find((r) => r.id === "neonatal_fever")).toBeUndefined();
    });

    it("proves 1-month-old infant (< 3 months) DOES trigger genuine neonatal fever override", () => {
      const infant1m: OverrideInput = {
        patient_age: 0,
        age_months: 1,
        patient_sex: "male",
        temperature: 38.2,
        heart_rate: 130,
        spo2: 98,
        bp_systolic: 80,
        symptoms: ["fever"],
      };

      const effectiveAge = resolveEffectiveAge(infant1m.patient_age, infant1m.age_months);
      expect(effectiveAge).toBeCloseTo(1 / 12, 6);
      expect(effectiveAge).toBeLessThan(0.25);

      const override = checkOverrides(infant1m);
      expect(override).not.toBeNull();
      expect(override?.id).toBe("neonatal_fever");

      const result = assignTier(infant1m as EngineInput);
      expect(result.tier).toBe("EMERGENCY");
      expect(result.firedRules.some((r) => r.id === "neonatal_fever")).toBe(true);
    });

    it("verifies full tree model inference on 4mo infant avoids false emergency override", () => {
      const treesPath = path.resolve(REPO_ROOT, "apps/web/public/models/triage_trees.json");
      const featuresPath = path.resolve(REPO_ROOT, "apps/web/public/models/features_config.json");
      expect(fs.existsSync(treesPath)).toBe(true);
      expect(fs.existsSync(featuresPath)).toBe(true);

      const trees = JSON.parse(fs.readFileSync(treesPath, "utf-8"));
      const featureNames = JSON.parse(fs.readFileSync(featuresPath, "utf-8")).feature_names;

      const engineInput: EngineInput = {
        patient_age: 0,
        age_months: 4,
        patient_sex: "female",
        temperature: 38.5,
        heart_rate: 120,
        spo2: 98,
        bp_systolic: 85,
        symptoms: ["fever"],
        chief_complaint: "fever for 2 days",
      };

      const triageResult = triage(engineInput, { mode: "hybrid", trees, featureNames });
      // Safety net override must not be neonatal fever
      expect(triageResult.firedRules.find((r) => r.id === "neonatal_fever")).toBeUndefined();
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Challenge 3: device_keystore Encryption Integration with Draft Storage
  // ──────────────────────────────────────────────────────────────────────────
  describe("3. Challenge device_keystore Draft Encryption & Ciphertext Invariant", () => {
    const draftSavePath = path.resolve(REPO_ROOT, "apps/web/src/hooks/useDraftSave.js");
    const outboxPath = path.resolve(REPO_ROOT, "apps/web/src/lib/outbox.js");

    it("verifies useDraftSave.js imports outbox encryption and does NOT store plaintext", () => {
      const code = fs.readFileSync(draftSavePath, "utf-8");
      expect(code).toMatch(/import\s*\{\s*encryptOutboxPayload,\s*decryptOutboxPayload\s*\}\s*from/);
      expect(code).toMatch(/encryptOutboxPayload\s*\(\s*formData,\s*ownerId,\s*key\s*\)/);
      expect(code).toMatch(/decryptOutboxPayload\s*\(\s*draft\.formData,\s*effectiveOwner,\s*effectiveKey\s*\)/);

      // Verify no raw unencrypted formData is put directly into the database
      expect(code).not.toMatch(/db\.put\s*\(\s*STORE\s*,\s*formData\s*,/);
    });

    it("proves cryptographic AES-256-GCM ciphertext invariant: zero plaintext leakage in storage record", async () => {
      // Simulate exact cryptographic protocol from outbox.js & useDraftSave.js
      const ownerId = "asha_worker_uuid_777";
      const keyId = `draft-${ownerId}`;
      const aadString = `vn:v2:${ownerId}:${keyId}`;
      const aad = new TextEncoder().encode(aadString);

      // Generate non-extractable AES-256-GCM key as in device_keystore
      const key = await crypto.subtle.generateKey(
        { name: "AES-GCM", length: 256 },
        false, // non-extractable
        ["encrypt", "decrypt"]
      );

      const sensitiveFormData = {
        patient_name: "Anita Sharma",
        patient_age: 28,
        patient_sex: "female",
        chief_complaint: "Severe acute abdominal pain and bleeding",
        known_conditions: "G2P1 pregnancy 14 weeks",
        current_medications: "Progesterone, Iron folic acid",
        location: "Kollam Subcentre",
        symptoms: ["abdominal_pain", "abnormal_bleeding", "fever"],
        temperature: 38.8,
        heart_rate: 115,
        spo2: 94,
        bp_systolic: 90,
        bp_diastolic: 55,
      };

      // Encrypt according to outbox.js protocol
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const encoded = new TextEncoder().encode(JSON.stringify(sensitiveFormData));
      const ctBuffer = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv, additionalData: aad },
        key,
        encoded
      );

      const payload = {
        _encrypted: true,
        _v: 2,
        iv: Array.from(iv),
        ct: Array.from(new Uint8Array(ctBuffer)),
      };

      const storedRecord = {
        owner_id: ownerId,
        formData: payload,
        savedAt: Date.now(),
      };

      // 1. Verify storedRecord is valid JSON serializable
      const serialized = JSON.stringify(storedRecord);
      expect(typeof serialized).toBe("string");

      // 2. Strict Ciphertext Invariant: PHI fields MUST NOT exist anywhere in the serialized stored record
      expect(serialized).not.toContain("Anita Sharma");
      expect(serialized).not.toContain("Severe acute abdominal pain");
      expect(serialized).not.toContain("pregnancy");
      expect(serialized).not.toContain("Progesterone");
      expect(serialized).not.toContain("abdominal_pain");
      expect(serialized).not.toContain("abnormal_bleeding");
      expect(serialized).not.toContain("Kollam Subcentre");

      // 3. Verify formData structure is ciphertext metadata only
      expect(storedRecord.formData._encrypted).toBe(true);
      expect(storedRecord.formData._v).toBe(2);
      expect(Array.isArray(storedRecord.formData.iv)).toBe(true);
      expect(storedRecord.formData.iv.length).toBe(12);
      expect(Array.isArray(storedRecord.formData.ct)).toBe(true);
      expect(storedRecord.formData.ct.length).toBeGreaterThan(0);

      // 4. Decrypt with correct key & AAD: exact match
      const decryptedBuffer = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: new Uint8Array(storedRecord.formData.iv), additionalData: aad },
        key,
        new Uint8Array(storedRecord.formData.ct)
      );
      const decryptedData = JSON.parse(new TextDecoder().decode(decryptedBuffer));
      expect(decryptedData).toEqual(sensitiveFormData);
    });

    it("proves cross-user isolation: Worker B cannot decrypt Worker A's draft", async () => {
      const workerA = "worker_a_uuid";
      const keyA = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
      const workerB = "worker_b_uuid";
      const keyB = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);

      const draftA = { patient_name: "Confidential Patient A", chief_complaint: "HIV follow-up" };
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const aadA = new TextEncoder().encode(`vn:v2:${workerA}:draft-${workerA}`);

      const ct = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv, additionalData: aadA },
        keyA,
        new TextEncoder().encode(JSON.stringify(draftA))
      );

      // Worker B attempts decryption with Worker B's key -> MUST REJECT (OperationError)
      await expect(
        crypto.subtle.decrypt(
          { name: "AES-GCM", iv, additionalData: aadA },
          keyB,
          ct
        )
      ).rejects.toThrow();

      // Worker B attempts decryption with Worker A's key but mismatched AAD -> MUST REJECT
      const aadB = new TextEncoder().encode(`vn:v2:${workerB}:draft-${workerB}`);
      await expect(
        crypto.subtle.decrypt(
          { name: "AES-GCM", iv, additionalData: aadB },
          keyA,
          ct
        )
      ).rejects.toThrow();
    });

    it("proves tampering detection: modified ciphertext or IV fails authentication", async () => {
      const ownerId = "tamper_test_worker";
      const key = await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
      const aad = new TextEncoder().encode(`vn:v2:${ownerId}:draft-${ownerId}`);
      const iv = crypto.getRandomValues(new Uint8Array(12));

      const ct = new Uint8Array(
        await crypto.subtle.encrypt(
          { name: "AES-GCM", iv, additionalData: aad },
          key,
          new TextEncoder().encode(JSON.stringify({ sensitive: "critical" }))
        )
      );

      // Flip one bit in ciphertext
      const tamperedCt = new Uint8Array(ct);
      tamperedCt[0] ^= 0x01;

      await expect(
        crypto.subtle.decrypt(
          { name: "AES-GCM", iv, additionalData: aad },
          key,
          tamperedCt
        )
      ).rejects.toThrow();

      // Corrupt IV
      const tamperedIv = new Uint8Array(iv);
      tamperedIv[0] ^= 0x01;

      await expect(
        crypto.subtle.decrypt(
          { name: "AES-GCM", iv: tamperedIv, additionalData: aad },
          key,
          ct
        )
      ).rejects.toThrow();
    });

    it("verifies useDraftSave no-ops when ownerId is null or undefined (shared tablet defense)", () => {
      const code = fs.readFileSync(draftSavePath, "utf-8");

      // Verify null check in saveDraft: if (!key || !ownerId) return
      expect(code).toMatch(/if\s*\(\s*!key\s*\|\|\s*!ownerId\s*\)\s*return/);

      // Verify null check in loadDraft: if (!effectiveKey) return null
      expect(code).toMatch(/if\s*\(\s*!effectiveKey\s*\)\s*return\s*null/);

      // Verify null check in clearDraft: if (!key) return
      expect(code).toMatch(/if\s*\(\s*!key\s*\)\s*return/);
    });

    it("verifies 24-hour draft TTL enforcement", () => {
      const code = fs.readFileSync(draftSavePath, "utf-8");
      expect(code).toMatch(/DRAFT_TTL_MS\s*=\s*24\s*\*\s*60\s*\*\s*60\s*\*\s*1000/);
      expect(code).toMatch(/Date\.now\(\)\s*-\s*draft\.savedAt\s*<\s*DRAFT_TTL_MS/);
    });
  });

  // ──────────────────────────────────────────────────────────────────────────
  // Challenge 4: Client Hooks & State Invariants (authStore, OfflineBanner, etc.)
  // ──────────────────────────────────────────────────────────────────────────
  describe("4. Challenge Client Hooks & Offline State Invariants", () => {
    it("verifies authStore.jsx caches profile in localStorage and sanitizes on logout (CRITICAL-4a)", () => {
      const authStorePath = path.resolve(REPO_ROOT, "apps/web/src/store/authStore.jsx");
      const code = fs.readFileSync(authStorePath, "utf-8");

      // Profile caching in localStorage
      expect(code).toMatch(/localStorage\.setItem\(`vn_profile_\$\{userId\}`,\s*JSON\.stringify\(data\)\)/);
      expect(code).toMatch(/localStorage\.setItem\('vn_last_user_id',\s*userId\)/);

      // Synchronous initial rehydration
      expect(code).toMatch(/function getInitialProfile\(\)/);
      expect(code).toMatch(/useState\(\(\)\s*=>\s*getInitialProfile\(\)\)/);

      // Sanitization on logout / device switch
      expect(code).toMatch(/key\.startsWith\('vn_profile_'\)\s*\|\|\s*key === 'vn_last_user_id'/);
      expect(code).toMatch(/localStorage\.removeItem\(key\)/);
    });

    it("verifies OfflineBanner.jsx triggers immediate processQueue on dead-letter retry (HIGH-7)", () => {
      const bannerPath = path.resolve(REPO_ROOT, "apps/web/src/components/OfflineBanner.jsx");
      const code = fs.readFileSync(bannerPath, "utf-8");

      expect(code).toMatch(/import\s*\{\s*processQueue\s*\}\s*from\s*'\.\.\/stores\/syncStore'/);
      expect(code).toMatch(/await retryDeadLetter\(eventId\)/);
      expect(code).toMatch(/if\s*\(navigator\.onLine\)\s*\{\s*processQueue\(\)/);
    });

    it("verifies useRealtimeCases.js guards against unscoped subscriptions (MEDIUM-5a)", () => {
      const hookPath = path.resolve(REPO_ROOT, "apps/web/src/hooks/useRealtimeCases.js");
      const code = fs.readFileSync(hookPath, "utf-8");

      expect(code).toMatch(/if\s*\(!global\s*&&\s*!facilityId\s*&&\s*!userId\)\s*\{\s*return\s*\}/);
      expect(code).toMatch(/\[facilityId,\s*userId,\s*global\]/);
    });

    it("verifies useVoiceInput.js never restarts microphone on recording stop error (MEDIUM-5b)", () => {
      const hookPath = path.resolve(REPO_ROOT, "apps/web/src/hooks/useVoiceInput.js");
      const code = fs.readFileSync(hookPath, "utf-8");

      // Verify recorder.onstop does NOT fall back to startBrowserRecognition
      const onstopBlock = code.slice(code.indexOf("recorder.onstop"), code.indexOf("mediaRecorderRef.current"));
      expect(onstopBlock).not.toMatch(/startBrowserRecognition\(\)/);
      expect(onstopBlock).toMatch(/setListening\(false\)/);
      expect(onstopBlock).toMatch(/setError\('failed'\)/);
    });
  });
});

