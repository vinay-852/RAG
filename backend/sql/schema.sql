CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS app_users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    department TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    title TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    source_type TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'internal',
    allowed_roles TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_uri, title)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    allowed_roles TEXT[] NOT NULL DEFAULT '{}',
    embedding vector(1536) NOT NULL,
    search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS document_chunks_search_idx
    ON document_chunks USING gin (search_vector);

CREATE INDEX IF NOT EXISTS document_chunks_roles_idx
    ON document_chunks USING gin (allowed_roles);

CREATE TABLE IF NOT EXISTS enterprise_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    record_type TEXT NOT NULL,
    business_unit TEXT NOT NULL,
    owner_department TEXT NOT NULL,
    fiscal_quarter TEXT,
    status TEXT NOT NULL,
    amount NUMERIC(14, 2),
    summary TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    allowed_roles TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS enterprise_records_filter_idx
    ON enterprise_records (tenant_id, record_type, business_unit, status, fiscal_quarter);

CREATE INDEX IF NOT EXISTS enterprise_records_roles_idx
    ON enterprise_records USING gin (allowed_roles);

CREATE TABLE IF NOT EXISTS event_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    event_ts TIMESTAMPTZ NOT NULL,
    service TEXT NOT NULL,
    level TEXT NOT NULL,
    actor TEXT,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    message TEXT NOT NULL,
    raw JSONB NOT NULL DEFAULT '{}',
    allowed_roles TEXT[] NOT NULL DEFAULT '{}',
    embedding vector(1536) NOT NULL,
    search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', message)) STORED
);

CREATE INDEX IF NOT EXISTS event_logs_embedding_hnsw
    ON event_logs USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS event_logs_filter_idx
    ON event_logs (tenant_id, event_ts DESC, service, level, action);

CREATE INDEX IF NOT EXISTS event_logs_roles_idx
    ON event_logs USING gin (allowed_roles);

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    event_ts TIMESTAMPTZ NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    before_value JSONB,
    after_value JSONB,
    reason TEXT,
    allowed_roles TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS audit_events_filter_idx
    ON audit_events (tenant_id, event_ts DESC, object_type, action, actor);

CREATE INDEX IF NOT EXISTS audit_events_roles_idx
    ON audit_events USING gin (allowed_roles);

CREATE OR REPLACE VIEW user_effective_roles AS
SELECT
    u.id AS user_id,
    u.tenant_id,
    array_agg(ur.role_id ORDER BY ur.role_id) AS roles
FROM app_users u
JOIN user_roles ur ON ur.user_id = u.id
GROUP BY u.id, u.tenant_id;
