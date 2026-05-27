# notification_worker.py — Worker untuk Membuat Notifikasi
#
# Worker ini mengkonsumsi pesan dari dua queue di RabbitMQ:
# 1. 'ticket_assigned' — saat tiket di-assign ke agen
# 2. 'ticket_updated' — saat status tiket berubah
#
# Untuk setiap event, worker membuat record notifikasi di database.

import os
import json
import time

import pika
import psycopg2
import psycopg2.extras

# Konfigurasi dari environment variable
RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "helpdesk_db")
DB_USER = os.getenv("DB_USER", "helpdesk")
DB_PASS = os.getenv("DB_PASS", "helpdesk123")

# Queue yang dikonsumsi
ASSIGNED_QUEUE = "ticket_assigned"
UPDATED_QUEUE = "ticket_updated"


def log(msg: str):
    """Cetak log dengan prefix [notification-worker]."""
    print(f"[notification-worker] {msg}", flush=True)


def get_db_connection():
    """Buat koneksi baru ke PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )


def create_notification(ticket_id: str, notif_type: str, message: str):
    """Simpan notifikasi ke database.

    Args:
        ticket_id: ID tiket yang terkait.
        notif_type: Tipe notifikasi (ASSIGNED, UPDATED, dll).
        message: Pesan notifikasi.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications (ticket_id, type, message)
                VALUES (%s, %s, %s)
                """,
                (ticket_id, notif_type, message),
            )
        conn.commit()
    finally:
        conn.close()


def on_assigned(ch, method, properties, body: bytes):
    """Callback saat menerima event 'ticket_assigned'.

    Membuat notifikasi bahwa tiket telah di-assign ke agen tertentu.
    """
    try:
        data = json.loads(body.decode("utf-8"))
        ticket_id = data.get("ticket_id")
        agent_name = data.get("agent_name", "Unknown")
        title = data.get("title", "")

        message = f"Tiket #{ticket_id} '{title}' telah di-assign ke {agent_name}"
        create_notification(ticket_id, "ASSIGNED", message)
        log(f"🔔 {message}")

    except Exception as e:
        log(f"❌ Error processing assigned event: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def on_updated(ch, method, properties, body: bytes):
    """Callback saat menerima event 'ticket_updated'.

    Membuat notifikasi bahwa status tiket telah berubah.
    """
    try:
        data = json.loads(body.decode("utf-8"))
        ticket_id = data.get("ticket_id")
        old_status = data.get("old_status", "?")
        new_status = data.get("new_status", "?")
        note = data.get("note", "")

        message = f"Tiket #{ticket_id} berubah status: {old_status} → {new_status}"
        if note:
            message += f" ({note})"

        create_notification(ticket_id, "UPDATED", message)
        log(f"🔔 {message}")

    except Exception as e:
        log(f"❌ Error processing updated event: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Fungsi utama: koneksi ke RabbitMQ dan konsumsi dari 2 queue."""
    log("🚀 Starting Notification Worker...")
    log(f"   Consuming from queues: {ASSIGNED_QUEUE}, {UPDATED_QUEUE}")

    # Buat koneksi ke RabbitMQ
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    ch = conn.channel()

    # Deklarasi queue
    ch.queue_declare(queue=ASSIGNED_QUEUE, durable=True)
    ch.queue_declare(queue=UPDATED_QUEUE, durable=True)

    ch.basic_qos(prefetch_count=1)

    # Konsumsi dari kedua queue
    ch.basic_consume(queue=ASSIGNED_QUEUE, on_message_callback=on_assigned, auto_ack=False)
    ch.basic_consume(queue=UPDATED_QUEUE, on_message_callback=on_updated, auto_ack=False)

    log("⏳ Waiting for ticket events...")
    ch.start_consuming()


if __name__ == "__main__":
    # Tunggu RabbitMQ dan PostgreSQL siap
    time.sleep(5)

    for attempt in range(1, 11):
        try:
            main()
        except pika.exceptions.AMQPConnectionError:
            log(f"⏳ RabbitMQ not ready, retrying... ({attempt}/10)")
            time.sleep(3)
        except Exception as e:
            log(f"❌ Fatal error: {e}")
            time.sleep(5)
