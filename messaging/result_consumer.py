# result_consumer.py - contoh program untuk menerima hasil pembayaran dari RabbitMQ dan menampilkannya
import os, json
import pika

# baca konfigurasi dari environment variable (bisa di-set lewat docker-compose.yml)
RABBIT_HOST = os.getenv("RABBIT_HOST", "localhost")
RES_QUEUE = os.getenv("RES_QUEUE", "payment_results")

# fungsi utama untuk menerima hasil pembayaran
def main():
    # buat koneksi ke RabbitMQ dan deklarasi queue yang sama dengan worker
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    ch = conn.channel()

    # deklarasi queue untuk hasil pembayaran (bisa sama dengan worker atau berbeda)
    ch.queue_declare(queue=RES_QUEUE, durable=True)

    # callback function untuk memproses pesan hasil pembayaran yang diterima
    def on_message(ch, method, properties, body):
        data = json.loads(body.decode())
        print(f"[result] Payment result received: {data}", flush=True)
        # di sistem riil: bisa gunakan proses update order status di database

        # ack: baru dihapus dari queue setelah diproses
        ch.basic_ack(delivery_tag=method.delivery_tag)

    # mulai menerima pesan hasil pembayaran dari RabbitMQ dengan callback function yang sudah didefinisikan
    ch.basic_consume(queue=RES_QUEUE, on_message_callback=on_message, auto_ack=False)

    # tampilkan pesan bahwa result consumer sudah siap menerima hasil pembayaran
    print("[result] Waiting for payment results...", flush=True)
    ch.start_consuming()

# jalankan fungsi utama jika file ini dieksekusi langsung
if __name__ == "__main__":
    main()