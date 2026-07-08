CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS storage_write_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sink_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    batch_id UUID NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    first_event_time_ms BIGINT,
    last_event_time_ms BIGINT,
    status TEXT NOT NULL CHECK (status IN ('started', 'committed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    committed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_storage_write_audit_batch ON storage_write_audit(batch_id);
CREATE INDEX IF NOT EXISTS idx_storage_write_audit_status ON storage_write_audit(status, created_at DESC);

CREATE TABLE IF NOT EXISTS event_replay_manifest (
    manifest_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_path TEXT NOT NULL,
    event_type TEXT NOT NULL,
    symbol TEXT,
    first_event_time_ms BIGINT,
    last_event_time_ms BIGINT,
    event_count BIGINT NOT NULL CHECK (event_count >= 0),
    sha256_hex TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_event_replay_manifest_time ON event_replay_manifest(first_event_time_ms, last_event_time_ms);
CREATE INDEX IF NOT EXISTS idx_event_replay_manifest_metadata ON event_replay_manifest USING GIN (metadata);

CREATE TABLE IF NOT EXISTS system_health_state (
    component TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    last_event_time_ms BIGINT NOT NULL,
    last_message TEXT NOT NULL DEFAULT '',
    counters JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_system_health_state_counters ON system_health_state USING GIN (counters);
