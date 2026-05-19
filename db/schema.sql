-- AI Income Engine — PostgreSQL schema
-- Apply with: psql $DATABASE_URL -f db/schema.sql

CREATE TABLE IF NOT EXISTS lanes (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    config      JSONB NOT NULL DEFAULT '{}',
    schedule    TEXT NOT NULL DEFAULT '*/15 * * * *',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS run_queue (
    id          SERIAL PRIMARY KEY,
    lane        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | running | done | failed
    payload     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

-- Append-only audit log — never UPDATE this table
CREATE TABLE IF NOT EXISTS run_log (
    id          BIGSERIAL PRIMARY KEY,
    lane        TEXT NOT NULL,
    action      TEXT NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}',
    result      JSONB NOT NULL DEFAULT '{}',
    success     BOOLEAN NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS income_events (
    id          BIGSERIAL PRIMARY KEY,
    lane        TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    amount_usd  NUMERIC(10, 2) NOT NULL DEFAULT 0,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kv_store (
    lane        TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (lane, key)
);

-- Seed the content lane
INSERT INTO lanes (name, config, schedule) VALUES
    ('content',     '{"niche": "AI productivity for founders"}', '0 9 * * 1'),  -- Monday 9am
    ('marketplace', '{}',                                         '0 10 * * *'), -- Daily 10am
    ('finance',     '{}',                                         '0 8 * * 1')   -- Monday 8am
ON CONFLICT (name) DO NOTHING;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_run_log_lane       ON run_log      (lane, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_income_events_lane ON income_events (lane, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_queue_status   ON run_queue    (status, lane);
