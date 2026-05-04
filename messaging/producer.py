# producer.py - contoh program untuk mengirim pesan ke RabbitMQ
import os, json, uuid, time, sys
import pika

# baca konfigurasi dari environment variable (bisa di-set lewat docker-compose.yml)
RABBIT_HOST = os.getenv("RABBIT_HOST", "localhost")
REQ_QUEUE = os.getenv("REQ_QUEUE", "payment_requests")

# fungsi utama untuk membuat payload dan mengirim pesan ke RabbitMQ
def main():
    # opsional: input amount lewat argumen CLI  misalnya: python producer.py 75000 VA_BCA
    # jika tidak maka akan di-default
    amount = int(sys.argv[1]) if len(sys.argv) > 1 else 75000
    method = sys.argv[2] if len(sys.argv) > 2 else "VA_BCA"

    # buat payload pesan dengan format JSON
    payload = {
        "event": "payment_requested",
        "order_id": str(uuid.uuid4())[:8],
        "user_id": "U1001",
        "amount": amount,
        "currency": "IDR",
        "method": method,
        "correlation_id": str(uuid.uuid4()),
        "requested_at": time.time()
    }

    # buat koneksi ke RabbitMQ dan kirim pesan ke queue yang sudah didefinisikan
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    ch = conn.channel()
    ch.queue_declare(queue=REQ_QUEUE, durable=True)

    # kirim pesan ke RabbitMQ dengan properti delivery_mode=2 agar pesan disimpan di disk (persistent)
    ch.basic_publish(
        exchange="",
        routing_key=REQ_QUEUE,
        body=json.dumps(payload).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2)  # persistent (best effort)
    )

    print(f"[producer] Sent -> {payload}", flush=True)
    conn.close()

# jalankan fungsi utama jika file ini dieksekusi langsung
if __name__ == "__main__":
    main()