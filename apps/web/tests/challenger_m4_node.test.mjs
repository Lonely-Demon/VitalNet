// apps/web/tests/challenger_m4_node.test.mjs
// Empirical Challenger test for sw-push.js and vercel.json configurations.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert';

console.log('--- STARTING CHALLENGER M4 NODE SUITE ---');

// =============================================================================
// TEST 1: Service Worker Push Notification Tags (MEDIUM-7a)
// =============================================================================
console.log('\n[1/2] Testing apps/web/public/sw-push.js...');

const swPushPath = path.resolve('apps/web/public/sw-push.js');
assert(fs.existsSync(swPushPath), `File not found: ${swPushPath}`);
const swCode = fs.readFileSync(swPushPath, 'utf8');

// Create mock Service Worker sandbox
const handlers = {};
let capturedNotification = null;

const mockSelf = {
  addEventListener(event, handler) {
    handlers[event] = handler;
  },
  registration: {
    showNotification(title, options) {
      capturedNotification = { title, options };
      return Promise.resolve();
    },
  },
  clients: {
    matchAll: async () => [],
    openWindow: async () => {},
  },
};

// Execute sw-push.js inside isolated sandbox
const context = vm.createContext({
  self: mockSelf,
  Date: Date,
  String: String,
  console: console,
});
vm.runInContext(swCode, context);

assert(typeof handlers.push === 'function', 'sw-push.js did not register a push event listener');
assert(typeof handlers.notificationclick === 'function', 'sw-push.js did not register notificationclick listener');

function triggerPush(dataPayload) {
  capturedNotification = null;
  let waitUntilPromise = null;
  const mockEvent = {
    data: dataPayload
      ? {
          json: () => {
            if (typeof dataPayload === 'string') {
              return JSON.parse(dataPayload);
            }
            return dataPayload;
          },
        }
      : null,
    waitUntil(p) {
      waitUntilPromise = p;
    },
  };
  handlers.push(mockEvent);
  return { captured: capturedNotification, promise: waitUntilPromise };
}

// 1.1: Distinct case_id values produce distinct tags
const push1 = triggerPush({ title: 'Critical Alert', body: 'Emergency patient', case_id: 'case-alpha-123' });
assert.strictEqual(push1.captured.options.tag, 'vitalnet-case-case-alpha-123', 'tag must match vitalnet-case-<case_id>');
assert.strictEqual(push1.captured.title, 'VitalNet · Critical Alert');
assert.strictEqual(push1.captured.options.body, 'Emergency patient');

const push2 = triggerPush({ title: 'Critical Alert', body: 'Another emergency', case_id: 'case-beta-456' });
assert.strictEqual(push2.captured.options.tag, 'vitalnet-case-case-beta-456');
assert.notStrictEqual(push1.captured.options.tag, push2.captured.options.tag, 'Distinct case_ids must produce distinct notification tags');

// 1.2: Missing case_id falls back to id or timestamp
const push3 = triggerPush({ title: 'System Notice', body: 'Backup complete', id: 'backup-789' });
assert.strictEqual(push3.captured.options.tag, 'vitalnet-notif-backup-789', 'Notification without case_id but with id must use vitalnet-notif-<id>');

const beforeTime = Date.now();
const push4 = triggerPush({ title: 'Generic Alert', body: 'No case or id' });
const afterTime = Date.now();
assert(push4.captured.options.tag.startsWith('vitalnet-notif-'), 'Notification without case_id or id must start with vitalnet-notif-');
const timestampExtracted = Number(push4.captured.options.tag.replace('vitalnet-notif-', ''));
assert(!Number.isNaN(timestampExtracted) && timestampExtracted >= beforeTime && timestampExtracted <= afterTime, 'Timestamp fallback must be valid current time');

// 1.3: Malformed / non-JSON payload falls back gracefully without unhandled throw
const pushMalformed = triggerPush(null);
assert(pushMalformed.captured.options.tag.startsWith('vitalnet-notif-'));
assert.strictEqual(pushMalformed.captured.title, 'VitalNet · VitalNet');
assert.strictEqual(pushMalformed.captured.options.body, 'New notification');

// 1.4: Sanitization defense: newline stripping and truncation
const longTitle = 'Super Critical Alert\n\nWith Malicious Injected Header ' + 'A'.repeat(100);
const longBody = 'Line 1\r\nLine 2\tTabbed ' + 'B'.repeat(300);
const pushSanitized = triggerPush({ title: longTitle, body: longBody, case_id: 'clean-1' });

assert(!pushSanitized.captured.title.includes('\n'), 'Title must not contain newlines');
assert(!pushSanitized.captured.options.body.includes('\r'), 'Body must not contain CR');
assert(!pushSanitized.captured.options.body.includes('\n'), 'Body must not contain LF');
assert(!pushSanitized.captured.options.body.includes('\t'), 'Body must not contain tabs');
assert(pushSanitized.captured.options.body.length <= 200, 'Body must be capped at 200 chars');

console.log('✓ sw-push.js dynamic tags & defense-in-depth verified successfully!');

// =============================================================================
// TEST 2: Vercel Security Headers & Rewrite Exclusions (MEDIUM-7b)
// =============================================================================
console.log('\n[2/2] Testing vercel.json & apps/web/vercel.json...');

const vercelPaths = [
  path.resolve('vercel.json'),
  path.resolve('apps/web/vercel.json'),
];

for (const vPath of vercelPaths) {
  assert(fs.existsSync(vPath), `File not found: ${vPath}`);
  const config = JSON.parse(fs.readFileSync(vPath, 'utf8'));

  // 2.1: Verify headers
  assert(Array.isArray(config.headers), `headers array missing in ${vPath}`);
  const globalHeaderRule = config.headers.find(h => h.source === '/(.*)');
  assert(globalHeaderRule, `Missing /(.*) header rule in ${vPath}`);

  const headerMap = {};
  for (const h of globalHeaderRule.headers) {
    headerMap[h.key] = h.value;
  }

  assert.strictEqual(headerMap['X-Content-Type-Options'], 'nosniff', 'X-Content-Type-Options must be nosniff');
  assert.strictEqual(headerMap['X-Frame-Options'], 'DENY', 'X-Frame-Options must be DENY');
  assert.strictEqual(headerMap['Referrer-Policy'], 'strict-origin-when-cross-origin', 'Referrer-Policy must be strict-origin-when-cross-origin');

  // 2.2: Verify rewrites rule and negative lookahead
  assert(Array.isArray(config.rewrites), `rewrites array missing in ${vPath}`);
  const spaRewrite = config.rewrites.find(r => r.destination === '/index.html');
  assert(spaRewrite, `Missing /index.html rewrite in ${vPath}`);

  assert.strictEqual(spaRewrite.source, '/((?!assets/|models/).*)', `Rewrite source pattern must exclude assets/ and models/ via negative lookahead`);

  // Test the rewrite regex matching behavior
  // In Vercel, the source regex is anchored
  const rewriteRegex = new RegExp(`^${spaRewrite.source}$`);

  // These SHOULD match the rewrite rule -> rewritten to index.html (SPA routes)
  const shouldRewrite = [
    '/',
    '/index.html',
    '/dashboard',
    '/intake/new',
    '/cases/case-123',
    '/settings',
    '/my-assets/file.js',
    '/models-viewer',
    '/api/health',
  ];

  for (const p of shouldRewrite) {
    assert(rewriteRegex.test(p), `Path '${p}' should match SPA rewrite rule but did not!`);
  }

  // These MUST NOT match the rewrite rule -> bypass rewrite to return real 404 or static file
  const shouldBypass = [
    '/assets/index.js',
    '/assets/main.css',
    '/assets/subfolder/chunk.js',
    '/models/triage_trees.json',
    '/models/features_config.json',
    '/models/nested/model.onnx',
  ];

  for (const p of shouldBypass) {
    assert(!rewriteRegex.test(p), `Path '${p}' should BYPASS SPA rewrite rule but matched it!`);
  }

  console.log(`✓ ${path.relative('.', vPath)} verified successfully!`);
}

console.log('\n--- ALL CHALLENGER M4 NODE TESTS PASSED SUCCESSFULLY! ---');
