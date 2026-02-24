-- Raw SQL schema reference (SQLAlchemy ORM is the primary schema source).
-- This file is kept for documentation and manual DB inspection.

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    sku         TEXT UNIQUE,
    category    TEXT,
    size        TEXT,
    cost_price  REAL NOT NULL,
    sell_price  REAL NOT NULL,
    slot        TEXT,
    quantity    INTEGER DEFAULT 0,
    max_quantity INTEGER DEFAULT 10,
    is_active   BOOLEAN DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    type          TEXT NOT NULL,
    product_id    INTEGER REFERENCES products(id),
    quantity      INTEGER,
    amount        REAL NOT NULL,
    balance_after REAL,
    notes         TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_decisions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger     TEXT NOT NULL,
    action      TEXT NOT NULL,
    reasoning   TEXT,
    was_blocked BOOLEAN DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scratchpad (
    key   TEXT PRIMARY KEY,
    value TEXT,
    ts    DATETIME
);

CREATE TABLE IF NOT EXISTS kv_store (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    direction   TEXT NOT NULL,
    content     TEXT NOT NULL,
    sender_id   TEXT,
    platform    TEXT,
    channel     TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_interactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL,
    sender_id        TEXT,
    sender_name      TEXT,
    platform         TEXT,
    user_cohort      TEXT,
    interaction_type TEXT,
    message_text     TEXT,
    agent_response   TEXT,
    was_successful   BOOLEAN,
    guardrail_hit    BOOLEAN DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,
    starting_balance REAL,
    ending_balance  REAL,
    total_revenue   REAL,
    total_cost      REAL,
    profit_margin   REAL,
    items_sold      INTEGER,
    stockout_events INTEGER,
    adversarial_attempts INTEGER,
    adversarial_blocked INTEGER,
    total_messages  INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
