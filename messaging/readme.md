# Please follow the instructions below to run:
1. Make sure Docker is running on your system, for e.g. by opening the Docker Desktop

2. Execute services: RabbitMQ + worker + result:
root-dir> docker compose up -d --build rabbitmq worker result
OR:
root-dir> docker compose up -d --build --scale worker=3 rabbitmq worker result

3. Send “payment request”:
docker compose run --rm producer python producer.py
docker compose run --rm producer python producer.py 120000 VA_MANDIRI
docker compose run --rm producer python producer.py 50000 QRIS

4. Check the worker outpur
docker compose logs -f worker

5. To remove all services:
docker compose down

6. Check the RabbitMQ Management at: http://localhost:15672
user: guest/guest
