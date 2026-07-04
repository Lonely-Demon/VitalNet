# Phase 10: Realtime Verification Checklist

## SQL Setup (Run in Supabase SQL Editor)

1. **Enable REPLICA IDENTITY FULL:**
   ```sql
   ALTER TABLE public.case_records REPLICA IDENTITY FULL;
   ```

2. **Add table to realtime publication:**
   ```sql
   ALTER PUBLICATION supabase_realtime ADD TABLE public.case_records;
   ```

3. **Verify setup:**
   ```sql
   -- Should return 'f' (full replica identity)
   SELECT relreplident FROM pg_class WHERE relname = 'case_records';

   -- Should show case_records in the list
   SELECT * FROM pg_publication_tables WHERE pubname = 'supabase_realtime';
   ```

## Frontend Testing

### Realtime — Doctor Dashboard:
- [ ] Open doctor dashboard in Browser A
- [ ] Submit a new case from ASHA panel in Browser B (or incognito)
- [ ] Case appears in Browser A within 2 seconds (no refresh needed)
- [ ] Submit EMERGENCY case → toast notification appears in Browser A
- [ ] Mark case as reviewed in Browser A → timestamp updates without refresh

### Realtime — ASHA History:
- [ ] Submit a case offline (DevTools → Network → Offline)
- [ ] Restore network connection
- [ ] Background Sync fires (check DevTools → Application → Background Sync)
- [ ] Submission history row updates from "Syncing…" to show triage badge (no refresh)

### Analytics Dashboard:
- [ ] Open Admin panel → Analytics tab
- [ ] All 4 summary cards show actual numbers (not 0/undefined)
- [ ] Triage distribution bar renders with proportional widths
- [ ] Daily volume chart shows bars for days with data
- [ ] Submit new case → live counter increments within 2 seconds
- [ ] Top submitters list shows ASHA worker names (not UUIDs)

## Backend Testing

### Analytics API Endpoints:
- [ ] GET `/api/analytics/summary` returns facility-scoped data
- [ ] super_admin sees system-wide stats, other roles see facility-only
- [ ] Triage distribution counts are accurate
- [ ] Daily volume grouping works correctly
- [ ] Top ASHA workers shows names from profiles table join

### Error Scenarios:
- [ ] Analytics endpoints return 403 for unauthorized roles
- [ ] Malformed realtime subscriptions fail gracefully
- [ ] Network disconnection doesn't break real-time reconnection

## Performance

- [ ] No memory leaks from uncleaned realtime subscriptions
- [ ] Live counter resets on page refresh (expected behavior)
- [ ] No excessive API calls (analytics refetch only every 5 new cases)
- [ ] Real-time events don't cause infinite loops