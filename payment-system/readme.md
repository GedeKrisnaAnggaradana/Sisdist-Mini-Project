1. Start semua service:
docker compose up -d --build

2. Check the log:
docker compose logs -f

3. Jalankan Client:
python client.py

3. Pastikan semua jalan:
docker compose ps

3. Lihat log election/leader:
docker compose logs -f payment-1
docker compose logs -f payment-2
docker compose logs -f payment-3

4. Matikan salah satu node:
docker compose stop payment-3

5. Tunggu sebentar (±3 detik), lalu lihat siapa leader baru. Mestinya payment-2

6. Jalankan lagi:
python client.py

Seharusnya tetap sukses (Order service akan menampilkan NOT_LEADER lalu retry mencari leader baru).

7. Jika kita hidupkan lagi payment-3
docker compose start payment-3

Seharusnya node payment-3 akan menjadi leader lagi.