
1. Buka dan jalankan Docker Desktop

2. Jalankan RabbitMQ + worker:

root-dir> docker compose up -d --build rabbitmq worker result
atau:
root-dir> docker compose up -d --build --scale worker=3 rabbitmq worker result

3. Kirim beberapa “payment request”:
docker compose run --rm producer python producer.py
docker compose run --rm producer python producer.py 120000 VA_MANDIRI
docker compose run --rm producer python producer.py 50000 QRIS

4. Cek output worker
docker compose logs -f worker

5. Untuk menghapus semua service:
docker compose down

6. Cek RabbitMQ Management di: http://localhost:15672
user: guest/guest