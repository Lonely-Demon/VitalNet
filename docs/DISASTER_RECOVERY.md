# VitalNet Disaster Recovery Runbook

**Document Version**: 1.0  
**Last Updated**: 2026-03-31  
**Owner**: DevOps Team  
**Classification**: CRITICAL - HIPAA Compliance Required

---

## 1. Recovery Objectives

### 1.1 RTO/RPO Targets

| Metric | Target | Maximum Tolerance |
|--------|--------|-------------------|
| **RPO (Recovery Point Objective)** | 1 hour | 4 hours |
| **RTO (Recovery Time Objective)** | 4 hours | 8 hours |

### 1.2 Scope

This runbook covers disaster recovery procedures for:
- **Database**: Supabase PostgreSQL (production)
- **Backend API**: Railway deployment
- **Frontend**: Vercel deployment
- **ML Models**: Git LFS versioned artifacts

---

## 2. Pre-Restore Checklist (MANDATORY)

**WARNING**: Failure to complete this checklist may result in **production data loss** or **PHI breach**.

### 2.1 Environment Validation

- [ ] **Confirm Target Environment**: Verify you are restoring to the correct environment
  - Production restores require **two-person approval** (DevOps Lead + Security Lead)
  - Staging/Test restores require team lead approval
- [ ] **Verify Current State**: Document current production state before any restore
  ```bash
  # Capture current production timestamp
  curl -s https://api.vitalnet.app/api/health | jq '.timestamp'
  ```
- [ ] **Backup Current State**: Create a backup before restoring
  ```bash
  # Export current database state (Supabase Dashboard > Database > Backups > Create Backup)
  # Or via CLI:
  pg_dump -h db.<SUPABASE_REF>.supabase.co -U postgres -d postgres > pre-restore-backup-$(date +%Y%m%d-%H%M%S).sql
  ```

### 2.2 Approval Verification

- [ ] **Production Restore Approval Form** completed (see Appendix A)
- [ ] **Stakeholder Notification**: All affected teams notified
  - [ ] Backend team
  - [ ] Frontend team
  - [ ] Clinical operations (if PHI affected)
- [ ] **Maintenance Window**: Scheduled and communicated
  - [ ] Status page updated
  - [ ] Users notified (if applicable)

### 2.3 Staging/Test First Policy

**CRITICAL**: All restore procedures MUST be validated in staging/test environment before production.

```bash
# Step 1: Restore to staging first
export TARGET_ENV="staging"
export SUPABASE_URL="https://<staging-ref>.supabase.co"

# Step 2: Verify data integrity
# Run verification scripts (see Section 5)

# Step 3: Only after staging validation, proceed to production
export TARGET_ENV="production"
```

---

## 3. Backup Schedule & Locations

### 3.1 Supabase Database

| Backup Type | Frequency | Retention | Location |
|-------------|-----------|-----------|----------|
| Point-in-Time Recovery (PITR) | Continuous | 7 days | Supabase Managed |
| Daily Full Backup | Daily 00:00 UTC | 30 days | Supabase Managed |
| Weekly Export | Weekly (Sunday) | 90 days | AWS S3 (encrypted) |

### 3.2 Application State

| Component | Backup Method | Location |
|-----------|---------------|----------|
| Backend Code | Git (GitHub) | GitHub Repository |
| Frontend Build | Vercel Auto | Vercel Platform |
| ML Models | Git LFS | GitHub LFS Storage |
| Environment Variables | Encrypted Backup | Doppler/1Password |

---

## 4. Recovery Procedures

### 4.1 Database Restore (Supabase PITR)

**Use Case**: Data corruption, accidental deletion, ransomware recovery

#### Step 1: Pre-Restore Verification

```bash
# 4.1.1 Verify you are NOT connected to production
echo "Current Supabase URL: $SUPABASE_URL"
if [[ "$SUPABASE_URL" == *"production"* ]]; then
    echo "ERROR: Production URL detected. Confirm this is intentional."
    read -p "Type 'CONFIRM' to continue: " confirm
    if [[ "$confirm" != "CONFIRM" ]]; then
        echo "Restore aborted."
        exit 1
    fi
fi

# 4.1.2 Check current database state
psql -h db.<SUPABASE_REF>.supabase.co -U postgres -d postgres -c "SELECT NOW() as current_time, COUNT(*) as case_count FROM case_records;"
```

#### Step 2: Initiate PITR Restore

1. Navigate to **Supabase Dashboard** > **Database** > **Backups**
2. Select **Point-in-Time Recovery**
3. Choose recovery timestamp (must be within 7-day window)
4. **CRITICAL**: Select target database
   - For production: Requires approval code from DevOps Lead
   - For staging: Team lead approval sufficient
5. Click **Restore** and confirm

#### Step 3: Post-Restore Verification

```bash
# Verify data integrity
psql -h db.<SUPABASE_REF>.supabase.co -U postgres -d postgres << EOF
-- Check table counts
SELECT 'case_records' as table_name, COUNT(*) as row_count FROM case_records
UNION ALL
SELECT 'profiles', COUNT(*) FROM profiles
UNION ALL
SELECT 'facilities', COUNT(*) FROM facilities;

-- Verify latest timestamps
SELECT MAX(created_at) as latest_case FROM case_records;
SELECT MAX(updated_at) as latest_profile FROM profiles;
EOF
```

### 4.2 Backend Rollback (Railway)

**Use Case**: Bad deployment, regression, service degradation

#### Step 1: Identify Last Known Good Deployment

```bash
# List recent deployments
railway deployments --service vitalnet-backend

# Check current deployment status
railway status --service vitalnet-backend
```

#### Step 2: Execute Rollback

```bash
# Rollback to previous deployment
railway rollback --service vitalnet-backend --deployment-id <LAST_GOOD_ID>

# Or rollback to specific commit
railway rollback --service vitalnet-backend --commit <COMMIT_SHA>
```

#### Step 3: Verify Health

```bash
# Wait for deployment to complete
sleep 30

# Check health endpoint
curl -s https://api.vitalnet.app/api/health | jq '.'

# Verify key functionality
curl -s https://api.vitalnet.app/api/cases?limit=1 | jq '.data[0].id'
```

### 4.3 Frontend Rollback (Vercel)

**Use Case**: UI regression, broken user flows

#### Step 1: Identify Last Known Good Deployment

```bash
# List recent deployments
vercel list --scope vitalnet

# Or via dashboard: https://vercel.com/vitalnet/frontend/deployments
```

#### Step 2: Execute Rollback

```bash
# Rollback to previous deployment
vercel rollback --scope vitalnet

# Or promote a specific deployment
vercel alias set <DEPLOYMENT_ID>.vitalnet.app vitalnet.app
```

### 4.4 ML Model Recovery

**Use Case**: Model corruption, classification failures

#### Step 1: Identify Known Good Model Version

```bash
# List model versions in Git LFS
git lfs ls-files | grep models

# Check current model hash
sha256sum backend/models/enhanced_classifier.onnx
```

#### Step 2: Restore Model

```bash
# Checkout specific model version
git checkout <COMMIT_SHA> -- backend/models/

# Or regenerate from known good data
cd backend
python scripts/retrain_and_export.py --output models/enhanced_classifier.onnx
```

---

## 5. Verification Commands

### 5.1 Data Integrity Checks

```bash
#!/bin/bash
# verify_restore.sh

echo "=== Post-Restore Verification ==="

# 1. Database connectivity
echo "1. Checking database connectivity..."
psql -h db.$SUPABASE_REF.supabase.co -U postgres -d postgres -c "SELECT 1;" || exit 1

# 2. Table counts (should be non-zero)
echo "2. Checking table counts..."
psql -h db.$SUPABASE_REF.supabase.co -U postgres -d postgres -c "SELECT COUNT(*) FROM case_records;"

# 3. Foreign key integrity
echo "3. Checking foreign key integrity..."
psql -h db.$SUPABASE_REF.supabase.co -U postgres -d postgres << EOF
SELECT 'orphaned cases' as issue, COUNT(*) as count 
FROM case_records c 
LEFT JOIN profiles p ON c.submitted_by = p.id 
WHERE p.id IS NULL;
EOF

# 4. API health
echo "4. Checking API health..."
curl -s https://api.vitalnet.app/api/health | jq '.status'

# 5. Sample case retrieval
echo "5. Sample case retrieval..."
curl -s "https://api.vitalnet.app/api/cases?limit=1" | jq '.data[0].id'

echo "=== Verification Complete ==="
```

### 5.2 Application Health Checks

```bash
# Backend health
curl -s https://api.vitalnet.app/api/health | jq '{
  status: .status,
  timestamp: .timestamp,
  environment: .environment
}'

# Frontend availability
curl -s -o /dev/null -w "%{http_code}" https://vitalnet.app

# ML endpoint
curl -s -X POST https://api.vitalnet.app/api/cases/triage \
  -H "Content-Type: application/json" \
  -d '{"patient_age": 30, "patient_sex": "male", "symptoms": ["fever"]}' | jq '.triage_level'
```

---

## 6. Rollback Procedures

### 6.1 When to Rollback

Initiate rollback if:
- Data integrity checks fail
- API error rate > 5%
- Latency p99 > 2 seconds
- Critical functionality broken
- PHI data corruption detected

### 6.2 Rollback Steps

```bash
# 1. Stop traffic (if possible)
# Update load balancer or disable DNS

# 2. Document current state
echo "Rolling back from $(date)" > rollback-$(date +%Y%m%d-%H%M%S).log
git rev-parse HEAD >> rollback-$(date +%Y%m%d-%H%M%S).log

# 3. Execute rollback (see Section 4)

# 4. Verify rollback success
./verify_restore.sh

# 5. Notify stakeholders
echo "Rollback completed at $(date)" | slack-notify --channel "#incidents"
```

---

## 7. Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| DevOps Lead | [Name] | [Phone/Slack] |
| Security Lead | [Name] | [Phone/Slack] |
| Database Admin | [Name] | [Phone/Slack] |
| Clinical Operations | [Name] | [Phone/Slack] |

---

## Appendix A: Production Restore Approval Form

```
PRODUCTION RESTORE APPROVAL FORM
================================

Date: _______________
Time: _______________
Requestor: _______________

Restore Details:
- Target Environment: PRODUCTION
- Restore Type: [ ] PITR [ ] Full Backup [ ] Migration Rollback
- Target Timestamp: _______________
- Reason for Restore: _______________

Pre-Restore Checklist:
- [ ] Staging restore completed and verified
- [ ] Backup of current state created
- [ ] Stakeholders notified
- [ ] Maintenance window scheduled

Approvals:
- DevOps Lead: _______________ Date: _______
- Security Lead: _______________ Date: _______
- Clinical Ops (if PHI): _______________ Date: _______

Post-Restore Verification:
- [ ] Data integrity checks passed
- [ ] API health checks passed
- [ ] User functionality verified
- [ ] No PHI data loss confirmed

Completion Time: _______________
Incident Report ID (if applicable): _______________
```

---

## Appendix B: Environment Variables Reference

```bash
# Required for restore operations
export SUPABASE_URL="https://<ref>.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<key>"  # From secrets manager only
export RAILWAY_TOKEN="<token>"  # From secrets manager only
export VERCEL_TOKEN="<token>"  # From secrets manager only

# NEVER store these in plain text files
# Use: Doppler, 1Password, or Railway/Vercel secrets
```

---

*This document is part of VitalNet's HIPAA compliance requirements. Review quarterly.*
