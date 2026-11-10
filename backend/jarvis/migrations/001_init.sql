CREATE TABLE spaces(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
  ai_policy TEXT NOT NULL DEFAULT 'solo_local', notes TEXT DEFAULT '',
  archived INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE records(
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), kind TEXT NOT NULL,
  title TEXT NOT NULL, status TEXT, project_id TEXT, brand_id TEXT, data TEXT NOT NULL DEFAULT '{}',
  archived INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE INDEX idx_records_space_kind ON records(space_id, kind, archived);
CREATE TABLE connections(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, provider TEXT NOT NULL, base_url TEXT, model TEXT,
  capabilities TEXT NOT NULL DEFAULT '[]', enabled INTEGER NOT NULL DEFAULT 0,
  terms_accepted INTEGER NOT NULL DEFAULT 0, is_paid INTEGER NOT NULL DEFAULT 0,
  timeout_s REAL NOT NULL DEFAULT 60, max_tokens INTEGER NOT NULL DEFAULT 2048,
  concurrency INTEGER NOT NULL DEFAULT 1, rpm_limit INTEGER, daily_limit INTEGER,
  monthly_budget_usd REAL, price_in REAL, price_out REAL, price_unit REAL,
  data_policy TEXT NOT NULL DEFAULT 'negocio', options TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'sin_probar', last_error TEXT, last_checked_at TEXT,
  confirmed_quota TEXT, blocked_until TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE jobs(
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL,
  params TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'pending',
  stage TEXT, progress REAL NOT NULL DEFAULT 0, message TEXT, result TEXT, error TEXT,
  attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 2,
  idempotency_key TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
  heartbeat_at TEXT, worker_id TEXT, resume_at TEXT, limits TEXT NOT NULL DEFAULT '{}',
  usage TEXT NOT NULL DEFAULT '{}', created_at TEXT, started_at TEXT, finished_at TEXT, updated_at TEXT);
CREATE INDEX idx_jobs_status ON jobs(status, created_at);
CREATE UNIQUE INDEX idx_jobs_idem_active ON jobs(idempotency_key)
  WHERE idempotency_key IS NOT NULL AND status IN ('pending','running','waiting_config','waiting_quota','waiting_approval');
CREATE TABLE job_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, ts TEXT, kind TEXT, stage TEXT, message TEXT, data TEXT);
CREATE INDEX idx_job_events_job ON job_events(job_id, id);
CREATE TABLE files(
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, name TEXT NOT NULL, mime TEXT, size INTEGER, sha256 TEXT,
  rel_path TEXT NOT NULL, origin TEXT NOT NULL DEFAULT 'upload', job_id TEXT, meta TEXT NOT NULL DEFAULT '{}',
  archived INTEGER NOT NULL DEFAULT 0, created_at TEXT);
CREATE INDEX idx_files_space ON files(space_id);
CREATE TABLE sources(
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, job_id TEXT, url TEXT, title TEXT, provider TEXT, query TEXT,
  snippet TEXT, published_at TEXT, fetched_at TEXT, status TEXT, note TEXT, text TEXT);
CREATE INDEX idx_sources_job ON sources(job_id);
CREATE TABLE deliverables(
  id TEXT PRIMARY KEY, space_id TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'borrador', current_version INTEGER NOT NULL DEFAULT 1,
  project_id TEXT, brand_id TEXT, job_id TEXT, ref_id TEXT, owner TEXT,
  archived INTEGER NOT NULL DEFAULT 0, created_at TEXT, updated_at TEXT);
CREATE INDEX idx_deliverables_space ON deliverables(space_id, archived);
CREATE TABLE deliverable_versions(
  id TEXT PRIMARY KEY, deliverable_id TEXT NOT NULL REFERENCES deliverables(id), version INTEGER NOT NULL,
  content TEXT NOT NULL, content_hash TEXT NOT NULL, author TEXT, note TEXT, checks TEXT, created_at TEXT,
  UNIQUE(deliverable_id, version));
CREATE TABLE comments(
  id TEXT PRIMARY KEY, deliverable_id TEXT NOT NULL, version INTEGER, author TEXT, body TEXT,
  kind TEXT NOT NULL DEFAULT 'comentario', resolved INTEGER NOT NULL DEFAULT 0, created_at TEXT);
CREATE TABLE approvals(
  id TEXT PRIMARY KEY, deliverable_id TEXT NOT NULL, version INTEGER NOT NULL, content_hash TEXT NOT NULL,
  user TEXT NOT NULL, action TEXT NOT NULL, destination TEXT NOT NULL DEFAULT '', scope TEXT NOT NULL DEFAULT '',
  expires_at TEXT, revoked_at TEXT, revoke_reason TEXT, used_at TEXT, created_at TEXT);
CREATE TABLE cache(
  key TEXT PRIMARY KEY, space_id TEXT NOT NULL, category TEXT, provider TEXT, model TEXT, prompt_version TEXT,
  value TEXT NOT NULL, created_at TEXT, expires_at TEXT);
CREATE TABLE usage(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, space_id TEXT, job_id TEXT, connection_id TEXT, provider TEXT,
  model TEXT, capability TEXT, category TEXT, tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0,
  units REAL DEFAULT 0, est_cost_usd REAL DEFAULT 0, cost_basis TEXT, duration_ms INTEGER, cached INTEGER DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'ok', error TEXT);
CREATE INDEX idx_usage_conn_ts ON usage(connection_id, ts);
CREATE TABLE messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, space_id TEXT, role TEXT, content TEXT, data TEXT, created_at TEXT);
CREATE TABLE audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, action TEXT, target TEXT, detail TEXT);
