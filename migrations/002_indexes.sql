-- Migration 002: Add indexes for audit log performance
-- Optimizes common query patterns: slow query lookup, session history, date range scans

CREATE INDEX IF NOT EXISTS idx_audit_slow ON query_audit_log (duration_ms DESC);
CREATE INDEX IF NOT EXISTS idx_audit_session ON query_audit_log (session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_created ON query_audit_log (created_at DESC);
