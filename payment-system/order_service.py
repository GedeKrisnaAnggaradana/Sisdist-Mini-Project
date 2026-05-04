# order_service.py adalah sebuah script Python yang berfungsi sebagai service untuk mengelola order dan pembayaran. 
# Service ini menggunakan Flask sebagai web framework untuk menyediakan API endpoint yang dapat diakses oleh client.

import os, time, uuid
from flask import Flask, request, jsonify
import requests

# Inisialisasi Flask app
app = Flask(__name__)

# Konfigurasi node dan payment service dengan cara membaca environment variable yang sudah di-set pada docker-compose.yml
PAYMENT_NODES = [x.strip() for x in os.getenv(
    # Environment variable PAYMENT_NODES berisi daftar URL dari payment service nodes yang tersedia, dipisahkan dengan koma
    "PAYMENT_NODES",
    # Default value jika environment variable tidak diset adalah "http://payment-1:9000,http://payment-2:9000,http://payment-3:9000"
    "http://payment-1:9000,http://payment-2:9000,http://payment-3:9000"
).split(",") if x.strip()]

# ORDERS adalah dictionary yang menyimpan data order yang dibuat Dalam bentuk {key, value}
# dengan 'key' berupa order_id dan 'value' berupa detail order seperti jumlah, status, dan receipt jika sudah dibayar
ORDERS = {}
_rr = 0

# Fungsi RPC untuk memanggil method pada payment service node dengan parameter yang diberikan
def rpc_call(base_url: str, method: str, params: dict, timeout=1.5):
    # Payload RPC yang berisi method yang ingin dipanggil dan parameter yang diperlukan
    payload = {"method": method, "params": params}
    # Panggil HTTP POST ke endpoint /rpc pada payment service node dengan payload RPC dan timeout yang ditentukan
    r = requests.post(f"{base_url}/rpc", json=payload, timeout=timeout)
    # Periksa apakah request berhasil (status code 2xx), jika tidak maka akan memunculkan exception
    r.raise_for_status()
    # Kirim response dalam format JSON
    return r.json()

# Fungsi untuk memilih salah satu payment service node secara round-robin (untuk load balancing)
# Prinsip kerja round-robin yakni memilih node secara bergantian dari daftar node yang tersedia, 
# sehingga beban kerja dapat didistribusikan secara merata di antara node-node tersebut.
def pick_node():
    # Gunakan variabel global _rr untuk melacak index node yang terakhir dipilih, 
    # kemudian increment dan mod dengan jumlah node untuk mendapatkan index node berikutnya
    global _rr
    _rr = (_rr + 1) % len(PAYMENT_NODES)
    # Ambil URL node yang dipilih berdasarkan index _rr dan kembalikan URL tersebut
    return PAYMENT_NODES[_rr]

# Fungsi untuk menemukan leader di antara payment service nodes dengan cara 
# menanyakan ke setiap node siapa yang menjadi leader
def find_leader():
    # Tanya ke masing-masing node: menurutnya leader saat ini siapa
    best = None
    for n in PAYMENT_NODES:
        try:
            # Panggil RPC method "who_is_leader" pada node n untuk mendapatkan informasi tentang leader saat ini
            out = rpc_call(n, "who_is_leader", {}, timeout=0.8).get("result") or {}
            # Jika node n tidak mengetahui siapa leader saat ini (tidak ada field "leader_id" dalam response), maka lanjut ke node berikutnya
            if not out.get("leader_id"):
                continue
            # Jika node n mengetahui siapa leader saat ini, bandingkan dengan informasi leader terbaik yang sudah ditemukan sejauh ini
            if (best is None) or int(out["leader_id"]) > int(best["leader_id"]):
                best = out
        except Exception:
            continue
    # Kembalikan leader terbaik yang ditemukan, atau None jika tidak ada node yang mengetahui siapa leader saat ini
    return best  # bisa None

# Endpoint API untuk membuat order baru dengan jumlah tertentu
@app.post("/orders")
def create_order():
    body = request.get_json(force=True, silent=True) or {}
    # Ambil jumlah order dari request body, jika tidak ada maka default ke 0
    amount = int(body.get("amount", 0))

    if amount <= 0:
        return jsonify({"error": "amount must be > 0"}), 400

    # Buat order_id unik dengan menggunakan UUID dan ambil 8 karakter pertama untuk membuatnya lebih pendek
    order_id = str(uuid.uuid4())[:8]
    # Simpan order baru ke dalam dictionary ORDERS dengan status "PENDING" dan receipt None (karena belum dibayar)
    ORDERS[order_id] = {"order_id": order_id, "amount": amount, "status": "PENDING", "receipt": None}
    # Kirim response dalam format JSON yang berisi detail order yang baru dibuat, dengan status code 201 (Created)
    return jsonify(ORDERS[order_id]), 201

# Endpoint API untuk mendapatkan detail order berdasarkan order_id
@app.get("/orders/<order_id>")
def get_order(order_id):
    # Ambil order berdasarkan order_id yang diberikan, jika tidak ditemukan maka kembalikan error 404 (Not Found)
    o = ORDERS.get(order_id)
    if not o:
        return jsonify({"error": "not found"}), 404
    return jsonify(o)

# Endpoint API untuk melakukan pembayaran pada order yang sudah ada berdasarkan order_id
@app.post("/orders/<order_id>/pay")
def pay(order_id):
    # Ambil order berdasarkan order_id yang diberikan, jika tidak ditemukan maka kembalikan error 404 (Not Found)
    o = ORDERS.get(order_id)
    if not o:
        return jsonify({"error": "not found"}), 404
    # Jika order sudah berstatus "PAID", maka kembalikan detail order tersebut tanpa melakukan pembayaran lagi
    if o["status"] == "PAID":
        return jsonify(o)

    # Ambil correlation ID dari header request, jika tidak ada maka buat correlation ID baru dengan UUID
    corr_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())

    # Catat waktu mulai untuk menghitung total waktu yang dibutuhkan untuk proses pembayaran, 
    # termasuk waktu RPC dan waktu end-to-end
    t0 = time.time()

    # Pilih salah satu payment service node secara round-robin untuk mencoba melakukan pembayaran
    chosen = pick_node()

    # Fungsi lokal untuk mencoba melakukan pembayaran pada node tertentu dengan memanggil RPC method "pay" pada node tersebut
    def try_pay(base_url: str):
        # Catat waktu sebelum memanggil RPC untuk menghitung waktu yang dibutuhkan untuk proses RPC
        t_rpc0 = time.time()
        # Panggil RPC method "pay" pada node base_url dengan parameter order_id, amount, dan correlation_id yang diperlukan untuk proses pembayaran
        resp = rpc_call(base_url, "pay", {
            "order_id": order_id,
            "amount": o["amount"],
            "correlation_id": corr_id
        })
        # Catat waktu setelah mendapatkan response dari RPC untuk menghitung waktu yang dibutuhkan untuk proses RPC
        t_rpc1 = time.time()
        return resp, int((t_rpc1 - t_rpc0) * 1000)

    # 1) coba node mana saja
    try:
        # Coba melakukan pembayaran pada node yang dipilih dengan memanggil fungsi try_pay.
        # Jika berhasil, maka simpan response dan waktu yang dibutuhkan untuk proses RPC.
        resp, rpc_ms = try_pay(chosen)
    except Exception as e:
        # Jika terjadi error saat mencoba melakukan pembayaran pada node yang dipilih (misalnya karena node tersebut tidak responsif atau terjadi timeout), 
        # maka kembalikan error 503 (Service Unavailable) dengan detail error dan node yang dipilih
        return jsonify({"error": "payment node unreachable", "detail": str(e), "chosen": chosen}), 503

    # 2) kalau bukan leader, retry ke leader
    if resp.get("error", {}).get("code") == "NOT_LEADER":
        # Jika response dari RPC menunjukkan bahwa node yang dipilih bukanlah leader (dengan kode error "NOT_LEADER"),
        # maka ambil informasi leader dari response tersebut (leader_id dan leader_url)
        leader_url = resp["error"].get("leader_url")
        leader_id = resp["error"].get("leader_id")

        # Jika response tidak menyertakan informasi leader (leader_url atau leader_id), 
        # maka panggil fungsi find_leader untuk mencari leader di antara node-node yang tersedia, 
        # dan ambil informasi leader tersebut jika ditemukan.
        if not leader_url:
            leader = find_leader()
            leader_url = leader["leader_url"] if leader else None
            leader_id = leader["leader_id"] if leader else None

        # Jika setelah mencoba mencari leader masih tidak ditemukan (leader_url masih None), 
        # maka kembalikan error 503 (Service Unavailable) dengan pesan bahwa belum ada leader yang diketahui 
        # dan minta client untuk mencoba lagi nanti.
        if not leader_url:
            return jsonify({"error": "no leader known yet, retry in a moment"}), 503

        # Jika sudah mendapatkan leader_url, maka coba melakukan pembayaran lagi dengan memanggil fungsi try_pay pada leader_url tersebut,
        # dan simpan response serta waktu yang dibutuhkan untuk proses RPC pada leader.
        resp2, rpc_ms2 = try_pay(leader_url)
        rpc_ms += rpc_ms2
        resp = resp2
        chosen = f"{chosen} -> leader({leader_id})"

    # Jika response dari RPC pada akhirnya berhasil (tidak ada error), maka update status order menjadi "PAID" 
    # dan simpan receipt pembayaran yang diterima dari response ke dalam detail order.
    if "result" in resp:
        o["status"] = "PAID"
        o["receipt"] = resp["result"]
    else:
        o["status"] = "FAILED"

    # Hitung total waktu yang dibutuhkan untuk proses pembayaran end-to-end, yaitu dari saat request diterima hingga response siap dikirimkan kembali ke client, 
    # dengan cara menghitung selisih waktu saat ini dengan waktu mulai yang sudah dicatat sebelumnya.
    total_ms = int((time.time() - t0) * 1000)

    return jsonify({
        "order": o,
        "metrics": {
            "chosen_path": chosen,
            "rpc_total_ms": rpc_ms,
            "end_to_end_ms": total_ms,
            "correlation_id": corr_id
        }
    })

# Main entry point untuk menjalankan Flask app pada port 8000 dengan host "0.0.0.0" 
# sehingga dapat diakses dari luar container, dan dengan opsi threaded=True untuk 
# memungkinkan Flask menangani multiple request secara bersamaan dalam thread yang berbeda.
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)