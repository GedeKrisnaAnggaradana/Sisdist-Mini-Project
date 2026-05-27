# db.py — Helper koneksi PostgreSQL untuk Ticket Service
# Menyediakan fungsi-fungsi untuk mengeksekusi query SQL
# ke database helpdesk_db dengan connection pooling sederhana.

import os
import psycopg2
import psycopg2.extras

# Konfigurasi koneksi database dari environment variable
# (akan di-set melalui docker-compose.yml)
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "helpdesk_db")
DB_USER = os.getenv("DB_USER", "helpdesk")
DB_PASS = os.getenv("DB_PASS", "helpdesk123")


def get_connection():
    """Buat koneksi baru ke PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )


def query(sql: str, params: tuple = (), fetch_one=False):
    """Eksekusi query SELECT dan kembalikan hasilnya sebagai list of dict.

    Args:
        sql: Query SQL yang akan dieksekusi.
        params: Parameter untuk query (mencegah SQL injection).
        fetch_one: Jika True, hanya kembalikan satu baris.

    Returns:
        List of dict (atau satu dict jika fetch_one=True),
        atau None jika tidak ada hasil.
    """
    conn = get_connection()
    try:
        # Gunakan RealDictCursor agar hasil query berupa dictionary
        # (bukan tuple) sehingga lebih mudah diakses berdasarkan nama kolom.
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            if fetch_one:
                return dict(rows[0]) if rows else None
            return [dict(r) for r in rows]
    finally:
        conn.close()


def execute(sql: str, params: tuple = (), returning=False):
    """Eksekusi query INSERT/UPDATE/DELETE.

    Args:
        sql: Query SQL yang akan dieksekusi.
        params: Parameter untuk query (mencegah SQL injection).
        returning: Jika True, kembalikan baris yang terpengaruh
                   (digunakan bersama klausa RETURNING di SQL).

    Returns:
        Dict dari baris yang dikembalikan jika returning=True,
        atau None jika returning=False.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            result = None
            if returning:
                row = cur.fetchone()
                result = dict(row) if row else None
            conn.commit()
            return result
    finally:
        conn.close()
