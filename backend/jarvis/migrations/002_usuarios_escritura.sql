CREATE TABLE users(
  id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, role TEXT NOT NULL, pass_hash TEXT NOT NULL, salt TEXT NOT NULL,
  spaces TEXT NOT NULL DEFAULT '[]', active INTEGER NOT NULL DEFAULT 1, created_at TEXT, last_login TEXT);
CREATE TABLE sessions(
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT);
CREATE TABLE scripture(
  translation TEXT NOT NULL, book TEXT NOT NULL, book_order INTEGER NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL, text TEXT NOT NULL,
  PRIMARY KEY(translation, book, chapter, verse));
CREATE TABLE scripture_meta(
  translation TEXT PRIMARY KEY, title TEXT, license TEXT, verses INTEGER, loaded_at TEXT);
