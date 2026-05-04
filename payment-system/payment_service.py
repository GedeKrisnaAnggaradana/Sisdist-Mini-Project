# Distributed Payment Service sederhana dengan mekanisme leader election (bully algorithm) dan RPC untuk proses pembayaran.
# Service ini akan menerima request pembayaran dari order service, kemudian mencoba untuk memproses pembayaran tersebut dengan memanggil RPC method "pay" pada node payment service yang dipilih secara round-robin.
# Jika node yang dipilih bukanlah leader, maka service ini akan mencoba untuk memanggil RPC method "pay" pada node leader yang diketahui. 
# Jika pembayaran berhasil, maka service ini akan mengembalikan receipt pembayaran kepada order service.
import os, time, uuid, threading, logging
from typing import Dict, Optional

import requests
from flask import Flask, request, jsonify

# Inisialisasi Flask app untuk payment service
app = Flask(__name__)

# Konfigurasi logging untuk mengurangi verbosity log dari werkzeug (Flask) agar output log lebih bersih dan fokus pada log yang kita buat sendiri.
log_werkzeug = logging.getLogger('werkzeug')
log_werkzeug.setLevel(logging.ERROR)

# Konfigurasi node payment service, termasuk nama node, ID node, dan daftar semua node yang tersedia dalam format "host:node_id"
# Nilai ini akan diambil dari environment variable (docker-compose.yml), dengan nilai default jika tidak disediakan
NODE_NAME = os.getenv("NODE_NAME", "payment-1")
NODE_ID = int(os.getenv("NODE_ID", "1"))
ALL_NODES_RAW = os.getenv("ALL_NODES", "payment-1:1,payment-2:2,payment-3:3")

# Buat dictionary NODES yang memetakan node_id ke host berdasarkan konfigurasi ALL_NODES_RAW
NODES: Dict[int, str] = {}
for item in [x.strip() for x in ALL_NODES_RAW.split(",") if x.strip()]:
    host, sid = item.split(":")
    # Isi dictionary NODES dengan key berupa node_id (dalam bentuk integer) dan value berupa host dari node tersebut
    NODES[int(sid)] = host

# URL untuk mengakses node payment service ini, yang akan digunakan untuk proses RPC dan komunikasi antar node
# Cara kerjanya adalah dengan menggunakan nama node (NODE_NAME) yang sudah dikonfigurasi untuk membentuk URL lengkap, 
# misalnya "http://payment-1:9000"
SELF_URL = f"http://{NODE_NAME}:9000"

# Variabel global untuk menyimpan state dari payment service, termasuk informasi tentang leader saat ini, status election, dan data pembayaran yang sudah diproses
state_lock = threading.Lock()
leader_id: Optional[int] = None
leader_url: Optional[str] = None
is_leader = False
election_in_progress = False
last_heartbeat = time.time()

# Dictionary untuk menyimpan data pembayaran yang sudah diproses, dengan key berupa order_id dan value berupa receipt pembayaran.
PAYMENTS: Dict[str, dict] = {}  # order_id -> receipt (idempotent)

# Fungsi untuk mencatat log dengan format yang mencakup nama node dan ID node, 
# sehingga dapat memantau aktivitas service
def log(msg: str):
    print(f"[{NODE_NAME} id={NODE_ID}] {msg}", flush=True)

# Fungsi untuk melakukan RPC call ke node payment service dengan method dan parameter yang diberikan, serta timeout untuk request tersebut
def rpc_call(url: str, method: str, params: dict, timeout=1.0):
    r = requests.post(f"{url}/rpc", json={"method": method, "params": params}, timeout=timeout)
    r.raise_for_status()
    return r.json()

# Menyebarkan (broadcast) pesan ke semua node Payment Service lain
# Best-effort: jika ada node yang down / timeout, error diabaikan.
def broadcast(method: str, params: dict):
    for nid, host in NODES.items():
        if nid == NODE_ID:
            continue
        try:
            rpc_call(f"http://{host}:9000", method, params, timeout=0.8)
        except Exception:
            pass

# Menetapkan node ini sebagai leader baru pada Payment Service cluster.
# - Mengupdate state leader (leader_id, leader_url, is_leader) secara thread-safe dengan lock.
# - Mengakhiri status election dan me-reset heartbeat timestamp untuk menyatakan "leader masih hidup".
# - Mengumumkan hasil election ke semua node lain dengan mengirim RPC "coordinator"
#   berisi informasi leader (ID dan URL) agar replika nodel lain menyinkronkan state leader-nya.
def become_leader():
    global leader_id, leader_url, is_leader, election_in_progress, last_heartbeat
    with state_lock:
        leader_id = NODE_ID
        leader_url = SELF_URL
        is_leader = True
        election_in_progress = False
        last_heartbeat = time.time()
    # Catat log bahwa node ini menjadi leader dan akan mengumumkan ke node lain
    log("BECOME LEADER -> broadcast coordinator")
    # Broadcast ke node lain bahwa node ini menjadi leader dengan mengirim RPC "coordinator" yang berisi informasi leader (ID dan URL)
    broadcast("coordinator", {"leader_id": leader_id, "leader_url": leader_url})


# Memulai proses leader election menggunakan algoritma: Bully Algorithm.
# - Mencegah election ganda dengan flag `election_in_progress` (menggunakan lock).
# - Mendaftar node dengan ID lebih tinggi dari node saat ini.
#   * Jika tidak ada node yang lebih tinggi, maka node ini langsung menjadi leader (`become_leader()`).
# - Mengirim RPC `election` ke semua node yang lebih tinggi:
#   * Jika ada minimal satu node membalas "OK", artinya ada kandidat node lebih kuat yang aktif,
#     sehingga node ini hanya akan menunggu pengumuman leader baru (RPC `coordinator`).
#   * Jika tidak ada balasan "OK" (semua node lebih tinggi down/tidak reachable),
#     maka node ini akan mendeklarasikan diri sebagai leader.
# - Menjalankan timer `wait_and_retry`: jika dalam batas waktu tidak menerima `coordinator`
#   (leader_id masih None), election diulang untuk recovery dari lost message/timeout.
def start_election():
    # Gunakan variabel global untuk melacak status election dan informasi leader, 
    # serta lock untuk memastikan operasi thread-safe
    global election_in_progress

    # Cek dan set flag election_in_progress untuk mencegah election ganda, dengan menggunakan lock untuk memastikan thread-safe
    with state_lock:
        if election_in_progress:
            return
        election_in_progress = True

    # Catat log bahwa proses election dimulai dengan algoritma bully
    log("ELECTION started (bully)")
    # Cari node dengan ID lebih tinggi dari node saat ini (NODE_ID) untuk menentukan kandidat leader yang lebih kuat
    higher = [nid for nid in NODES.keys() if nid > NODE_ID]

    # Jika tidak ada node dengan ID lebih tinggi, maka node ini langsung menjadi leader dengan memanggil fungsi `become_leader()`
    if not higher:
        become_leader()
        return

    # Kirim RPC `election` ke semua node yang lebih tinggi untuk menanyakan apakah mereka aktif dan siap menjadi leader
    any_ok = False
    for nid in sorted(higher):
        host = NODES[nid]
        try:
            # Panggil RPC method "election" pada node dengan ID lebih tinggi untuk menanyakan apakah mereka aktif dan siap menjadi leader, dengan parameter "from_id" yang berisi ID node saat ini
            resp = rpc_call(f"http://{host}:9000", "election", {"from_id": NODE_ID}, timeout=0.8)
            # Jika ada minimal satu node yang membalas dengan "OK", artinya ada kandidat node lebih kuat yang aktif, sehingga node ini hanya akan menunggu pengumuman leader baru (RPC `coordinator`).
            if resp.get("result") == "OK":
                any_ok = True
        except Exception:
            continue

    # Jika tidak ada balasan "OK" dari node yang lebih tinggi (semua node lebih tinggi down/tidak reachable), maka node ini akan mendeklarasikan diri sebagai leader dengan memanggil fungsi `become_leader()`
    if not any_ok:
        become_leader()
        return

    # Jalankan timer `wait_and_retry`: jika dalam batas waktu tidak menerima `coordinator` (leader_id masih None), election diulang untuk recovery dari lost message/timeout.
    def wait_and_retry():
        global election_in_progress
        time.sleep(2.0)
        with state_lock:
            still_waiting = election_in_progress and (leader_id is None)
            election_in_progress = False
        if still_waiting:
            start_election()

    # Jalankan fungsi `wait_and_retry` dalam thread terpisah untuk menunggu pengumuman leader baru, 
    # dan jika tidak menerima pengumuman dalam batas waktu, maka akan memulai election ulang untuk recovery dari lost message/timeout.
    threading.Thread(target=wait_and_retry, daemon=True).start()

# Method RPC yang akan dipanggil oleh order service untuk memproses pembayaran pada order yang sudah dibuat.
@app.post("/rpc")
def rpc():
    global last_heartbeat, leader_id, leader_url, is_leader, election_in_progress

    body = request.get_json(force=True, silent=True) or {}
    method = body.get("method")
    params = body.get("params") or {}

    # Handle method RPC yang berbeda berdasarkan nilai "method" yang diterima dalam request body.
    if method == "who_is_leader":
        # Jika method adalah "who_is_leader", maka service ini akan mengembalikan informasi tentang leader saat ini, 
        # termasuk leader_id, leader_url, dan apakah node ini adalah leader (is_leader), 
        # dengan menggunakan lock untuk memastikan thread-safe saat mengakses state leader.
        with state_lock:
            return jsonify({"result": {"leader_id": leader_id, "leader_url": leader_url, "i_am_leader": is_leader}})

    # Bagian ini dipanggil secara periodeik untuk memberitahu ke semua node lain bahwa node ini masih hidup, sekaligus menyebarkan informasi siapa leader saat ini.
    if method == "heartbeat":        
        # Jika method adalah "heartbeat", maka service ini akan memperbarui informasi leader berdasarkan parameter yang diterima (leader_id dan leader_url), 
        # serta mengupdate timestamp heartbeat untuk menandakan bahwa node ini masih hidup, dengan menggunakan lock untuk memastikan thread-safe saat mengupdate state leader.
        with state_lock:
            leader_id = int(params.get("leader_id"))
            leader_url = params.get("leader_url")
            is_leader = (leader_id == NODE_ID)
            last_heartbeat = time.time()
            election_in_progress = False
        return jsonify({"result": "OK"})

    # Bagian ini dipanggil sekali pada saat election telah selesai untuk memberitahu ke semua node lain siapa yang menjadi leader baru.
    if method == "coordinator":
        # Jika method adalah "coordinator", maka service ini akan memperbarui informasi leader berdasarkan parameter yang diterima (leader_id dan leader_url),
        # serta mengupdate timestamp heartbeat untuk menandakan bahwa node ini masih hidup, dengan menggunakan lock untuk memastikan thread-safe saat mengupdate state leader.
        with state_lock:
            leader_id = int(params.get("leader_id"))
            leader_url = params.get("leader_url")
            is_leader = (leader_id == NODE_ID)
            last_heartbeat = time.time()
            election_in_progress = False
        log(f"COORDINATOR received: leader_id={leader_id}")
        return jsonify({"result": "OK"})

    # Bagian ini dipanggil saat terjadi election. Jika node pemanggil memiliki ID lebih rendah, 
    # maka node ini akan membalas dengan "OK" dan memulai elaction terpisah untuk menentukan apakah ada node lain yang lebih tinggi yang aktif.
    if method == "election":
        from_id = int(params.get("from_id"))
        if NODE_ID > from_id:
            threading.Thread(target=start_election, daemon=True).start()
            return jsonify({"result": "OK"})
        return jsonify({"result": "IGNORED"})

    # Bagian ini dipanggil oleh order service untuk memproses pembayaran pada order yang sudah dibuat.
    if method == "pay":
        order_id = str(params.get("order_id"))
        amount = int(params.get("amount", 0))
        corr = str(params.get("correlation_id", ""))

        # Jika method adalah "pay", maka service ini akan mencoba untuk memproses pembayaran pada order yang diberikan dengan memeriksa apakah node ini adalah leader.
        with state_lock:
            local_is_leader = is_leader
            l_id = leader_id
            l_url = leader_url

        # Jika node ini bukan leader, maka service ini akan mengembalikan error dengan kode "NOT_LEADER" beserta informasi leader yang diketahui (leader_id dan leader_url) agar order service dapat mencoba melakukan pembayaran pada node leader.
        if not local_is_leader:
            return jsonify({"error": {"code": "NOT_LEADER", "leader_id": l_id, "leader_url": l_url}}), 409

        # Service ini juga akan memastikan bahwa pembayaran bersifat idempotent (hanya boleh ada satu pembayaran yang sukses) dengan memeriksa apakah order_id sudah ada dalam dictionary PAYMENTS sebelum memproses pembayaran, dan jika sudah ada maka akan mengembalikan receipt yang sudah ada tanpa memproses pembayaran lagi.
        if order_id in PAYMENTS:  # idempotent
            return jsonify({"result": PAYMENTS[order_id]})

        time.sleep(0.12)  # simulasi proses

        # Jika node ini adalah leader, maka service ini akan memproses pembayaran dengan membuat receipt pembayaran yang berisi detail order, amount, node yang memproses pembayaran, leader_id, correlation_id, receipt_id, dan timestamp pembayaran.
        receipt = {
            "order_id": order_id,
            "amount": amount,
            "charged_by": NODE_NAME,
            "leader_id": NODE_ID,
            "correlation_id": corr,
            "receipt_id": str(uuid.uuid4())[:8],
            "charged_at": time.time(),
        }
        PAYMENTS[order_id] = receipt
        log(f"I am the leader processing the payment={leader_id}")
        return jsonify({"result": receipt})

    return jsonify({"error": {"code": "NO_SUCH_METHOD"}}), 400

# Fungsi untuk mengirim heartbeat secara periodik ke semua node lain untuk memberitahu bahwa node ini masih hidup, sekaligus menyebarkan informasi siapa leader saat ini.
# Fungsi ini akan berjalan dalam thread terpisah dan jika node ini merupakan leader akan mengirimkan heartbeat saat itu.
def heartbeat_loop():
    while True:
        time.sleep(1.0)
        with state_lock:
            if not is_leader:
                continue
            hb = {"leader_id": leader_id, "leader_url": leader_url}
        for nid, host in NODES.items():
            if nid == NODE_ID:
                continue
            try:
                rpc_call(f"http://{host}:9000", "heartbeat", hb, timeout=2.0)
            except Exception:
                pass

# Fungsi untuk memonitor heartbeat dari leader dan memulai election jika tidak menerima heartbeat 
# dalam batas waktu tertentu (misalnya 2.5 detik), yang menandakan bahwa leader mungkin sudah down atau tidak responsif.
def monitor_loop():
    while True:
        time.sleep(0.5)
        with state_lock:
            if is_leader:
                continue
            lh = last_heartbeat
        if (time.time() - lh) > 10:
            start_election()

# Fungsi bootstrap untuk memulai proses election setelah service ini dijalankan, 
# dengan delay yang bervariasi berdasarkan NODE_ID untuk mengurangi kemungkinan terjadinya election ganda saat semua node memulai secara bersamaan.
def bootstrap():
    time.sleep(0.8 + 0.15 * NODE_ID)
    start_election()

# Main entry point untuk menjalankan Flask app pada port 9000, serta memulai thread untuk heartbeat loop, monitor loop, dan bootstrap process.
if __name__ == "__main__":
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=bootstrap, daemon=True).start()

    log("starting payment service on :9000")
    app.run(host="0.0.0.0", port=9000, threaded=True)