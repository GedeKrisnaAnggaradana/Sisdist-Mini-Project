# client.py adalah sebuah script Python yang berfungsi sebagai client untuk memanggil order service yang sudah dibuat.
# Script ini akan membuat sebuah order baru dengan jumlah tertentu, kemudian mencoba untuk melakukan pembayaran pada order tersebut menggunakan endpoint yang disediakan oleh order service.
# Hasil dari setiap operasi akan memperlihatkan apakah operasi berhasil atau tidak.

import time

import requests, uuid

# URL dasar untuk mengakses order service
BASE = "http://localhost:8000"

# Fungsi untuk membuat order baru dengan jumlah tertentu
def create_order(amount: int):
    # Panggil HTTP POST ke endpoint /orders dengan payload yang berisi jumlah order
    r = requests.post(f"{BASE}/orders", json={"amount": amount})
    # Periksa apakah request berhasil (status code 2xx), jika tidak maka akan memunculkan exception
    r.raise_for_status()
    # Kirim response dalam format JSON
    return r.json()

# Fungsi untuk melakukan pembayaran pada order yang sudah ada
def pay(order_id: str, max_retries=10, delay_seconds=2.5):
    # Buat correlation ID unik untuk melacak request ini
    corr = str(uuid.uuid4())
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[*] Melakukan pembayaran... (Percobaan {attempt}/{max_retries})")
            
            # Panggil HTTP POST ke endpoint /orders/{order_id}/pay dengan header yang berisi correlation ID
            r = requests.post(f"{BASE}/orders/{order_id}/pay", headers={"X-Correlation-Id": corr})
            
            # Periksa apakah request berhasil (status code 2xx)
            r.raise_for_status()
            
            # Jika tidak ada error, kembalikan JSON
            print("Pembayaran berhasil diproses oleh Leader!")
            return r.json()
            
        except requests.exceptions.HTTPError as e:
            # Error seperti 503 (Service Unavailable) atau 409 (Conflict) akan ditangkap di sini
            status_code = e.response.status_code
            print(f"Gagal memproses pembayaran (Status: {status_code}).")
            print("Sistem mungkin sedang memproses Leader Election.")
            
        except requests.exceptions.ConnectionError:
            # Error jika Order Service belum menyala sama sekali
            print("Tidak dapat terhubung ke server Order Service.")
            
        # Jika belum mencapai batas percobaan, tunggu beberapa detik sebelum mencoba lagi
        if attempt < max_retries:
            print(f"Menunggu {delay_seconds} detik sebelum mencoba lagi...\n")
            time.sleep(delay_seconds)
        else:
            print("Batas percobaan habis. Pembayaran gagal dilakukan.")
            raise

if __name__ == "__main__":
    # Buat order baru dengan jumlah 50000
    o = create_order(50000)
    print("Created:", o)

    # Lakukan pembayaran pada order yang baru dibuat
    out = pay(o["order_id"])
    print("Pay result:", out)