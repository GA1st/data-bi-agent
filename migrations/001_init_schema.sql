-- Migration 001: Initial schema
-- Creates the query_audit_log table and schema_version tracking table.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS query_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    sql TEXT NOT NULL,
    success INTEGER DEFAULT 1,
    row_count INTEGER DEFAULT 0,
    duration_ms REAL,
    source TEXT DEFAULT 'chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
