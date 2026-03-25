-- Phase 10: Supabase Realtime Setup
-- Run these SQL commands in the Supabase SQL editor

-- 1. Enable REPLICA IDENTITY so UPDATE events include full row data
ALTER TABLE public.case_records REPLICA IDENTITY FULL;

-- 2. Add the table to the Supabase Realtime publication
-- (Safe to run multiple times - will not add duplicates)
ALTER PUBLICATION supabase_realtime ADD TABLE public.case_records;

-- Verification queries:
-- 1. Check replica identity (should return 'f' for full)
-- SELECT relreplident FROM pg_class WHERE relname = 'case_records';

-- 2. Check realtime publication includes the table
-- SELECT * FROM pg_publication_tables WHERE pubname = 'supabase_realtime';