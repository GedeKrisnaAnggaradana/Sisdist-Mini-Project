# worker.py - contoh program untuk menerima pesan dari RabbitMQ dan memprosesnya
import os, json, time, random
import pika

# baca konfigurasi dari environment variable (bisa di-set lewat docker-compose.yml)
RABBIT_HOST = os.getenv("RABBIT_HOST", "localhost")
REQ_QUEUE = os.getenv("REQ_QUEUE", "payment_requests")
RES_QUEUE = os.getenv("RES_QUEUE", "payment_results")

# fungsi utama untuk menerima pesan dari RabbitMQ dan memprosesnya
def main():
    # buat koneksi ke RabbitMQ dan deklarasi queue yang sama dengan producer
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    ch = conn.channel()

    ch.queue_declare(queue=REQ_QUEUE, durable=True)
    ch.queue_declare(queue=RES_QUEUE, durable=True)

    # agar worker tidak menerima pesan baru sebelum menyelesaikan yang sedang diproses
    ch.basic_qos(prefetch_count=1)

    # callback function untuk memproses pesan yang diterima
    def on_message(ch, method, properties, body: bytes):
        req = json.loads(body.decode("utf-8"))
        print(f"[worker] Received request: {req}", flush=True)

        # simulasi latensi pemrosesan payment
        time.sleep(random.uniform(0.3, 1.2))

        # simulasi hasil payment (mis. 80% sukses)
        success = random.random() > 0.2
        result = {
            "event": "payment_processed",
            "order_id": req["order_id"],
            "correlation_id": req["correlation_id"],
            "status": "SUCCESS" if success else "FAILED",
            "processed_at": time.time()
        }

        ch.basic_publish(
            exchange="",
            routing_key=RES_QUEUE,
            body=json.dumps(result).encode(),
            properties=pika.BasicProperties(delivery_mode=2)
        )

        print(f"[worker] Processed -> {result}", flush=True)

        # beri tahu RabbitMQ bahwa pesan sudah diproses (acknowledge)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    # mulai menerima pesan dari RabbitMQ dengan callback function yang sudah didefinisikan
    ch.basic_consume(queue=REQ_QUEUE, on_message_callback=on_message, auto_ack=False)

    # tampilkan pesan bahwa worker sudah siap menerima permintaan pembayaran
    print("[worker] Waiting for payment requests...", flush=True)
    ch.start_consuming()

# jalankan fungsi utama jika file ini dieksekusi langsung
if __name__ == "__main__":
    main()