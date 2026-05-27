# assignment_worker.py — Worker untuk Auto-Assign Tiket ke Agen
#
# Worker ini mengkonsumsi pesan dari queue 'ticket_created' di RabbitMQ.
# Ketika ada tiket baru, worker memilih agen yang tersedia menggunakan
# algoritma round-robin, lalu meng-update tiket di database dan
# mempublikasikan event 'ticket_assigned' ke queue berikutnya.

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

# Queue yang dikonsumsi dan diproduksi
CONSUME_QUEUE = "ticket_created"
PRODUCE_QUEUE = "ticket_assigned"

# Counter round-robin untuk distribusi agen secara merata
_rr_counter = 0


def log(msg: str):
    """Cetak log dengan prefix [assignment-worker]."""
    print(f"[assignment-worker] {msg}", flush=True)


def get_db_connection():
    """Buat koneksi baru ke PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )


def get_available_agents():
    """Ambil daftar agen yang tersedia (is_available = true)."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM agents WHERE is_available = TRUE ORDER BY agent_id")
            return cur.fetchall()
    finally:
        conn.close()


def assign_ticket(ticket_id: str, agent_id: int, agent_name: str):
    """Update tiket di database: set assigned_to dan status = IN_PROGRESS.

    Args:
        ticket_id: ID tiket yang akan di-assign.
        agent_id: ID agen yang dipilih.
        agent_name: Nama agen (untuk history log).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Update tiket: assign ke agen dan ubah status ke IN_PROGRESS
            cur.execute(
                """
                UPDATE tickets
                SET assigned_to = %s, status = 'IN_PROGRESS', updated_at = NOW()
                WHERE ticket_id = %s
                """,
                (agent_id, ticket_id),
            )

            # Catat perubahan di ticket_history
            cur.execute(
                """
                INSERT INTO ticket_history (ticket_id, old_status, new_status, note, changed_by)
                VALUES (%s, 'OPEN', 'IN_PROGRESS', %s, 'assignment-worker')
                """,
                (ticket_id, f"Auto-assigned ke {agent_name}"),
            )

        conn.commit()
    finally:
        conn.close()


def publish_event(channel, queue: str, event: dict):
    """Publish event ke RabbitMQ queue."""
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(event, default=str).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),
    )


def on_message(ch, method, properties, body: bytes):
    """Callback ketika menerima pesan dari queue 'ticket_created'.

    Proses:
    1. Parse pesan JSON
    2. Ambil daftar agen yang tersedia
    3. Pilih agen secara round-robin
    4. Update tiket di database (assign ke agen)
    5. Publish event 'ticket_assigned' ke queue berikutnya
    6. Acknowledge pesan
    """
    global _rr_counter

    try:
        data = json.loads(body.decode("utf-8"))
        ticket_id = data.get("ticket_id")
        title = data.get("title", "")

        log(f"📩 Received: ticket_id={ticket_id}, title='{title}'")

        # Ambil daftar agen yang tersedia
        agents = get_available_agents()
        if not agents:
            log(f"⚠️ No available agents! Ticket {ticket_id} remains unassigned.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Pilih agen secara round-robin
        _rr_counter = (_rr_counter + 1) % len(agents)
        chosen_agent = agents[_rr_counter]

        log(
            f"👤 Assigning ticket {ticket_id} to "
            f"{chosen_agent['name']} (agent_id={chosen_agent['agent_id']})"
        )

        # Update di database
        assign_ticket(ticket_id, chosen_agent["agent_id"], chosen_agent["name"])

        # Publish event ke queue berikutnya
        publish_event(
            ch,
            PRODUCE_QUEUE,
            {
                "event": "ticket_assigned",
                "ticket_id": ticket_id,
                "title": title,
                "agent_id": chosen_agent["agent_id"],
                "agent_name": chosen_agent["name"],
                "timestamp": time.time(),
            },
        )

        log(f"✅ Ticket {ticket_id} assigned to {chosen_agent['name']}")

    except Exception as e:
        log(f"❌ Error processing message: {e}")

    # Acknowledge pesan agar dihapus dari queue
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Fungsi utama: koneksi ke RabbitMQ dan mulai mengkonsumsi pesan."""
    log("🚀 Starting Assignment Worker...")
    log(f"   Consuming from queue: {CONSUME_QUEUE}")
    log(f"   Publishing to queue: {PRODUCE_QUEUE}")

    # Buat koneksi ke RabbitMQ
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    ch = conn.channel()

    # Deklarasi queue yang akan dikonsumsi dan diproduksi
    ch.queue_declare(queue=CONSUME_QUEUE, durable=True)
    ch.queue_declare(queue=PRODUCE_QUEUE, durable=True)

    # Hanya proses satu pesan pada satu waktu
    ch.basic_qos(prefetch_count=1)

    # Mulai mengkonsumsi pesan
    ch.basic_consume(queue=CONSUME_QUEUE, on_message_callback=on_message, auto_ack=False)

    log("⏳ Waiting for ticket_created events...")
    ch.start_consuming()


if __name__ == "__main__":
    # Tunggu RabbitMQ dan PostgreSQL siap sebelum mulai
    time.sleep(5)

    # Retry loop untuk koneksi
    for attempt in range(1, 11):
        try:
            main()
        except pika.exceptions.AMQPConnectionError:
            log(f"⏳ RabbitMQ not ready, retrying... ({attempt}/10)")
            time.sleep(3)
        except Exception as e:
            log(f"❌ Fatal error: {e}")
            time.sleep(5)
