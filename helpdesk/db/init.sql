-- ============================================================
-- Helpdesk Ticketing System — Database Schema & Seed Data
-- ============================================================
-- File ini akan dieksekusi otomatis saat container PostgreSQL
-- pertama kali dijalankan (via docker-entrypoint-initdb.d).
-- ============================================================

-- Tabel AGENTS: menyimpan data agen helpdesk yang bertugas
-- menangani tiket dari pengguna.
CREATE TABLE IF NOT EXISTS agents (
    agent_id    SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(100) NOT NULL UNIQUE,
    is_available BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Tabel TICKETS: menyimpan tiket bantuan yang dibuat oleh
-- pengguna. Setiap tiket memiliki prioritas, status, dan
-- dapat di-assign ke agen tertentu.
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id       VARCHAR(8) PRIMARY KEY,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    priority        VARCHAR(20) DEFAULT 'MEDIUM'
                        CHECK (priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    status          VARCHAR(20) DEFAULT 'OPEN'
                        CHECK (status IN ('OPEN','IN_PROGRESS','RESOLVED','CLOSED')),
    created_by      VARCHAR(50) NOT NULL,
    assigned_to     INTEGER REFERENCES agents(agent_id),
    processed_by_node INTEGER,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Tabel TICKET_HISTORY: mencatat setiap perubahan status pada
-- tiket, sehingga kita bisa melacak riwayat lengkap.
CREATE TABLE IF NOT EXISTS ticket_history (
    id          SERIAL PRIMARY KEY,
    ticket_id   VARCHAR(8) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    old_status  VARCHAR(20),
    new_status  VARCHAR(20),
    note        VARCHAR(200),
    changed_by  VARCHAR(50),
    changed_at  TIMESTAMP DEFAULT NOW()
);

-- Tabel NOTIFICATIONS: menyimpan notifikasi yang dihasilkan
-- oleh sistem (misalnya saat tiket di-assign atau di-update).
CREATE TABLE IF NOT EXISTS notifications (
    id          SERIAL PRIMARY KEY,
    ticket_id   VARCHAR(8) REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    type        VARCHAR(20) NOT NULL,
    message     TEXT NOT NULL,
    is_read     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Index untuk mempercepat query yang sering digunakan
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned ON tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_history_ticket ON ticket_history(ticket_id);
CREATE INDEX IF NOT EXISTS idx_notif_ticket ON notifications(ticket_id);

-- ============================================================
-- Seed Data: Agen Helpdesk Awal
-- ============================================================
INSERT INTO agents (name, email, is_available) VALUES
    ('Budi Santoso',    'budi@helpdesk.local',    TRUE),
    ('Siti Rahayu',     'siti@helpdesk.local',    TRUE),
    ('Andi Pratama',    'andi@helpdesk.local',    TRUE),
    ('Dewi Lestari',    'dewi@helpdesk.local',    TRUE),
    ('Rizky Firmansyah','rizky@helpdesk.local',   TRUE)
ON CONFLICT (email) DO NOTHING;
