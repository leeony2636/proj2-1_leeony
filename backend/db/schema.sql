CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    theme_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL,
    total_puzzles INTEGER NOT NULL,
    solved_puzzles INTEGER NOT NULL DEFAULT 0,
    solved_puzzle_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    current_puzzle_id TEXT,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS hint_events (
    event_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    team_id TEXT NOT NULL,
    puzzle_id TEXT NOT NULL,
    strength TEXT NOT NULL,
    delivered_at TIMESTAMPTZ NOT NULL,
    reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    idempotency_key TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS master_requests (
    request_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    team_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    operator_id TEXT,
    note TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS master_requests_status_created_idx
    ON master_requests(status, created_at);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    payload JSONB NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
