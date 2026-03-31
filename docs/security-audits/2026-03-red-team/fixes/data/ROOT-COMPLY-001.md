# Fix Log: ROOT-COMPLY-001

**Unit ID:** ROOT-COMPLY-001
**Priority:** P0 (CRITICAL)
**Title:** PHI transmitted to LLM services without Data Processing Agreement
**Status:** BLOCKED (requires legal/business action)

## Finding Summary
Patient health information (PHI) is sent to Groq LLM services for triage assistance without a formal Business Associate Agreement (BAA) or Data Processing Agreement (DPA).

## Location
`backend/app/services/llm.py:100-125`

## Analysis
This is a **business/legal compliance issue**, not a code fix:

1. **Technical implementation is correct** - PHI is transmitted securely over HTTPS
2. **BAA/DPA required** - HIPAA (US) and equivalent regulations require formal agreements before sharing PHI with third parties
3. **Groq BAA availability** - Need to verify if Groq offers HIPAA BAA for healthcare use cases

## Required Actions (Non-Code)
1. [ ] Contact Groq to request BAA/DPA for healthcare use
2. [ ] If Groq cannot provide BAA, evaluate HIPAA-compliant alternatives:
   - Azure OpenAI (offers BAA)
   - AWS Bedrock (offers BAA)
   - Self-hosted models (no third-party sharing)
3. [ ] Legal review of data flows and agreements
4. [ ] Update privacy policy and consent forms to disclose LLM processing

## Technical Mitigations (Implemented)
While awaiting legal resolution, these technical controls are in place:
- **Consent capture** (ROOT-COMPLY-005) - Patients informed of AI processing
- **Audit logging** (ROOT-COMPLY-002) - All LLM calls logged
- **Data minimization** - Only necessary fields sent to LLM

## Files Modified
None (requires legal action)

## Risk Assessment
- **Severity:** CRITICAL (compliance)
- **Status:** BLOCKED pending legal review
- **Residual Risk:** HIGH until BAA is in place
