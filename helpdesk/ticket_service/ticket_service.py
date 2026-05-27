# ticket_service.py — Ticket Service Node dengan Ring-based Leader Election
#
# Service ini adalah inti dari sistem Helpdesk Ticketing terdistribusi.
# Setiap instance (node) dari service ini membentuk topologi ring logis
# dan menggunakan algoritma Chang-Roberts untuk memilih leader.
#
# Hanya leader yang boleh melakukan operasi WRITE (create, update, delete tiket).
# Semua node boleh melakukan operasi READ (get tiket, list tiket).
#
# Komunikasi antar-node menggunakan RPC melalui HTTP POST ke endpoint /rpc.

import os
import time
import uuid
import json
import threading
import logging
from typing import Dict, Optional
from datetime import datetime

import requests
import pika
from flask import Flask, request, jsonify

import db

# ============================================================
# Inisialisasi Flask dan Konfigurasi Logging
# ============================================================
app = Flask(__name__)

# Kurangi verbosity log werkzeug agar output lebih bersih
log_werkzeug = logging.getLogger("werkzeug")
log_werkzeug.setLevel(logging.ERROR)

# ============================================================
# Konfigurasi Node (dari environment variable docker-compose)
# ============================================================
NODE_NAME = os.getenv("NODE_NAME", "ticket-1")
NODE_ID = int(os.getenv("NODE_ID", "1"))

# ALL_NODES berformat "ticket-1:1,ticket-2:2,ticket-3:3"
ALL_NODES_RAW = os.getenv("ALL_NODES", "ticket-1:1,ticket-2:2,ticket-3:3")

# Parse ALL_NODES menjadi dictionary {node_id: hostname}
NODES: Dict[int, str] = {}
for item in [x.strip() for x in ALL_NODES_RAW.split(",") if x.strip()]:
    host, sid = item.split(":")
    NODES[int(sid)] = host

# URL service ini sendiri
SELF_URL = f"http://{NODE_NAME}:9000"

# Konfigurasi RabbitMQ
RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")

# ============================================================
# State Global untuk Leader Election (Thread-safe)
# ============================================================
state_lock = threading.Lock()
leader_id: Optional[int] = None
leader_url: Optional[str] = None
is_leader = False
election_in_progress = False
last_heartbeat = time.time()

# Flag participant: apakah node ini sudah berpartisipasi
# dalam election round yang sedang berjalan
is_participant = False


# ============================================================
# Fungsi Utilitas
# ============================================================
def log(msg: str):
    """Cetak log dengan prefix nama dan ID node."""
    print(f"[{NODE_NAME} id={NODE_ID}] {msg}", flush=True)


def rpc_call(url: str, method: str, params: dict, timeout=1.5):
    """Panggil RPC method pada node lain via HTTP POST."""
    r = requests.post(
        f"{url}/rpc", json={"method": method, "params": params}, timeout=timeout
    )
    r.raise_for_status()
    return r.json()


def get_successor_id() -> int:
    """Dapatkan ID dari successor (tetangga berikutnya) dalam ring.

    Ring disusun berdasarkan urutan ID ascending, lalu kembali ke awal.
    Contoh: jika ada Node 1, 2, 3 maka:
      - Successor dari 1 adalah 2
      - Successor dari 2 adalah 3
      - Successor dari 3 adalah 1 (kembali ke awal)
    """
    sorted_ids = sorted(NODES.keys())
    my_index = sorted_ids.index(NODE_ID)
    next_index = (my_index + 1) % len(sorted_ids)
    return sorted_ids[next_index]


def send_to_successor(method: str, params: dict, skip_ids: set = None):
    """Kirim pesan RPC ke successor dalam ring.

    Jika successor tidak dapat dijangkau (crash/down), lompati ke
    successor berikutnya. Ini memastikan ring tetap berfungsi
    meskipun ada node yang mati.

    Args:
        method: Nama RPC method yang akan dipanggil.
        params: Parameter untuk RPC call.
        skip_ids: Set node ID yang sudah dicoba dan gagal (untuk menghindari loop).

    Returns:
        True jika pesan berhasil dikirim, False jika semua node gagal.
    """
    if skip_ids is None:
        skip_ids = set()

    sorted_ids = sorted(NODES.keys())
    my_index = sorted_ids.index(NODE_ID)

    # Coba kirim ke setiap node dalam urutan ring dimulai dari successor
    for i in range(1, len(sorted_ids)):
        next_index = (my_index + i) % len(sorted_ids)
        next_id = sorted_ids[next_index]

        # Jangan kirim ke diri sendiri atau node yang sudah di-skip
        if next_id == NODE_ID or next_id in skip_ids:
            continue

        next_host = NODES[next_id]
        next_url = f"http://{next_host}:9000"

        try:
            rpc_call(next_url, method, params, timeout=1.0)
            log(f"  -> Sent {method} to Node {next_id} ({next_host})")
            return True
        except Exception:
            log(f"  -> Node {next_id} ({next_host}) unreachable, skipping...")
            skip_ids.add(next_id)
            continue

    log(f"  -> WARN: Could not send {method} to any node in ring!")
    return False


# ============================================================
# Ring-based Leader Election (Chang-Roberts Algorithm)
# ============================================================
def become_leader():
    """Tetapkan node ini sebagai leader baru.

    Dipanggil ketika pesan ELECTION berputar penuh kembali ke
    node ini (candidate_id == NODE_ID), yang berarti node ini
    memiliki ID tertinggi di antara node yang aktif.
    """
    global leader_id, leader_url, is_leader, election_in_progress
    global last_heartbeat, is_participant

    with state_lock:
        leader_id = NODE_ID
        leader_url = SELF_URL
        is_leader = True
        election_in_progress = False
        is_participant = False
        last_heartbeat = time.time()

    log("★ BECOME LEADER → sending COORDINATOR around ring")

    # Kirim pesan COORDINATOR searah ring agar semua node tahu
    # siapa leader baru
    send_to_successor(
        "coordinator", {"leader_id": NODE_ID, "leader_url": SELF_URL}
    )



def start_election():
    """Mulai proses Ring-based Leader Election.

    Node ini mengirim pesan ELECTION dengan candidate_id = NODE_ID
    ke successor-nya. Pesan ini akan beredar di ring:
    - Jika node penerima memiliki ID lebih tinggi → ganti candidate_id
    - Jika node penerima memiliki ID lebih rendah → teruskan apa adanya
    - Jika candidate_id == my_id → pesan sudah berputar penuh, saya leader
    """
    global election_in_progress, is_participant

    with state_lock:
        if election_in_progress:
            return
        election_in_progress = True
        is_participant = True

    log("⚡ ELECTION started (Ring-based / Chang-Roberts)")
    log(f"  -> Sending ELECTION(candidate={NODE_ID}) to successor")

    # Kirim pesan election dengan candidate_id = ID node ini
    send_to_successor("election", {"candidate_id": NODE_ID})

    # Safety timer: jika dalam 6 detik tidak ada COORDINATOR diterima,
    # reset dan ulangi election
    def wait_and_reset():
        global election_in_progress, is_participant
        time.sleep(6.0)
        with state_lock:
            still_in_progress = election_in_progress
        if still_in_progress:
            log("⏰ Election timeout → resetting for retry")
            with state_lock:
                election_in_progress = False
                is_participant = False
            start_election()

    threading.Thread(target=wait_and_reset, daemon=True).start()


# ============================================================
# Heartbeat: Leader mengirim heartbeat ke semua node secara
# periodik untuk memberitahu bahwa leader masih hidup
# ============================================================
def heartbeat_loop():
    """Loop heartbeat yang dijalankan oleh leader.

    Leader mengirim heartbeat setiap 1 detik ke successor-nya
    dalam ring. Heartbeat mengandung informasi leader_id dan
    leader_url sehingga semua node selalu up-to-date.
    """
    while True:
        time.sleep(1.0)
        with state_lock:
            if not is_leader:
                continue
            hb = {"leader_id": leader_id, "leader_url": leader_url}

        # Broadcast heartbeat ke semua node (bukan hanya successor)
        # agar semua node langsung mendapat info terbaru
        for nid, host in NODES.items():
            if nid == NODE_ID:
                continue
            try:
                rpc_call(f"http://{host}:9000", "heartbeat", hb, timeout=2.0)
            except Exception:
                pass


def monitor_loop():
    """Monitor heartbeat dari leader.

    Jika node ini bukan leader dan tidak menerima heartbeat
    dalam 10 detik terakhir, mulai election baru karena
    kemungkinan leader sudah crash.
    """
    while True:
        time.sleep(0.5)
        with state_lock:
            if is_leader:
                continue
            lh = last_heartbeat
        # Jika sudah lebih dari 10 detik tanpa heartbeat → leader mungkin crash
        if (time.time() - lh) > 10:
            log("💀 Heartbeat timeout! Leader may be down → starting election")
            start_election()


def bootstrap():
    """Bootstrap: tunggu sebentar lalu mulai election pertama.

    Delay berbeda untuk setiap node (berdasarkan NODE_ID) untuk
    mengurangi kemungkinan election simultaneous saat startup.
    """
    time.sleep(1.5 + 0.3 * NODE_ID)
    start_election()


# ============================================================
# Publish Event ke RabbitMQ
# ============================================================
def publish_event(queue: str, event: dict):
    """Publish event ke RabbitMQ queue tertentu.

    Args:
        queue: Nama queue tujuan (misal: 'ticket_created').
        event: Dictionary berisi data event yang akan dikirim.
    """
    try:
        conn = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBIT_HOST)
        )
        ch = conn.channel()
        ch.queue_declare(queue=queue, durable=True)
        ch.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(event, default=str).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )
        conn.close()
        log(f"📤 Published event to '{queue}': {event.get('event', '')}")
    except Exception as e:
        log(f"⚠️ Failed to publish to '{queue}': {e}")


# ============================================================
# Serialisasi datetime untuk JSON response
# ============================================================
def serialize_row(row: dict) -> dict:
    """Konversi objek datetime dalam row menjadi string ISO format."""
    if row is None:
        return None
    result = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ============================================================
# RPC Endpoint — Satu endpoint untuk semua method
# ============================================================
@app.post("/rpc")
def rpc():
    """Endpoint RPC utama.

    Menerima request JSON dengan format:
        {"method": "nama_method", "params": {...}}

    Method yang tersedia:
    - who_is_leader: Tanya siapa leader saat ini
    - heartbeat: Terima heartbeat dari leader
    - coordinator: Terima pengumuman leader baru (Ring Election)
    - election: Terima pesan election (Ring Election)
    - create_ticket: Buat tiket baru (LEADER ONLY)
    - get_tickets: Ambil daftar tiket
    - get_ticket: Ambil detail satu tiket
    - update_ticket: Update tiket (LEADER ONLY)
    - delete_ticket: Hapus tiket (LEADER ONLY)
    - get_agents: Ambil daftar agen
    - get_stats: Ambil statistik tiket
    - get_ticket_history: Ambil riwayat perubahan tiket
    - get_notifications: Ambil daftar notifikasi
    """
    global last_heartbeat, leader_id, leader_url, is_leader
    global election_in_progress, is_participant

    body = request.get_json(force=True, silent=True) or {}
    method = body.get("method")
    params = body.get("params") or {}

    # ----------------------------------------------------------
    # ELECTION METHODS (Ring-based / Chang-Roberts)
    # ----------------------------------------------------------

    if method == "who_is_leader":
        with state_lock:
            return jsonify(
                {
                    "result": {
                        "leader_id": leader_id,
                        "leader_url": leader_url,
                        "i_am_leader": is_leader,
                        "node_id": NODE_ID,
                        "node_name": NODE_NAME,
                    }
                }
            )

    if method == "heartbeat":
        with state_lock:
            leader_id = int(params.get("leader_id"))
            leader_url = params.get("leader_url")
            is_leader = leader_id == NODE_ID
            last_heartbeat = time.time()
            election_in_progress = False
            is_participant = False
        return jsonify({"result": "OK"})

    if method == "coordinator":
        # Pesan COORDINATOR berputar di ring untuk memberitahu
        # semua node siapa leader baru.
        new_leader_id = int(params.get("leader_id"))
        new_leader_url = params.get("leader_url")

        with state_lock:
            leader_id = new_leader_id
            leader_url = new_leader_url
            is_leader = new_leader_id == NODE_ID
            last_heartbeat = time.time()
            election_in_progress = False
            is_participant = False

        log(f"📢 COORDINATOR received: leader_id={new_leader_id}")

        # Teruskan pesan COORDINATOR ke successor KECUALI jika
        # pesan sudah kembali ke node pengirim asli (leader)
        if new_leader_id != NODE_ID:
            send_to_successor(
                "coordinator",
                {"leader_id": new_leader_id, "leader_url": new_leader_url},
            )

        return jsonify({"result": "OK"})

    if method == "election":
        # Pesan ELECTION berputar di ring dengan candidate_id.
        # Setiap node membandingkan candidate_id dengan ID-nya sendiri.
        candidate_id = int(params.get("candidate_id"))

        log(f"📩 ELECTION received: candidate_id={candidate_id}")

        if candidate_id > NODE_ID:
            # Candidate lebih tinggi dari saya → teruskan apa adanya
            log(f"  -> {candidate_id} > {NODE_ID}, forwarding unchanged")
            with state_lock:
                is_participant = True
            send_to_successor("election", {"candidate_id": candidate_id})

        elif candidate_id < NODE_ID:
            # Candidate lebih rendah dari saya → ganti dengan ID saya
            log(f"  -> {candidate_id} < {NODE_ID}, replacing with my ID")
            with state_lock:
                is_participant = True
                election_in_progress = True
            send_to_successor("election", {"candidate_id": NODE_ID})

        else:
            # candidate_id == NODE_ID → pesan sudah berputar penuh!
            # Saya adalah node dengan ID tertinggi → saya jadi leader
            log(f"  -> {candidate_id} == {NODE_ID}, message completed full circle!")
            become_leader()

        return jsonify({"result": "OK"})

    # ----------------------------------------------------------
    # TICKET CRUD METHODS
    # ----------------------------------------------------------

    if method == "create_ticket":
        # Hanya leader yang boleh membuat tiket baru
        with state_lock:
            local_is_leader = is_leader
            l_id = leader_id
            l_url = leader_url

        if not local_is_leader:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "NOT_LEADER",
                            "leader_id": l_id,
                            "leader_url": l_url,
                        }
                    }
                ),
                409,
            )

        # Buat tiket baru
        ticket_id = str(uuid.uuid4())[:8]
        title = params.get("title", "Untitled")
        description = params.get("description", "")
        priority = params.get("priority", "MEDIUM")
        created_by = params.get("created_by", "anonymous")

        try:
            row = db.execute(
                """
                INSERT INTO tickets (ticket_id, title, description, priority,
                                     status, created_by, processed_by_node)
                VALUES (%s, %s, %s, %s, 'OPEN', %s, %s)
                RETURNING *
                """,
                (ticket_id, title, description, priority, created_by, NODE_ID),
                returning=True,
            )

            # Catat di ticket_history
            db.execute(
                """
                INSERT INTO ticket_history (ticket_id, old_status, new_status, note, changed_by)
                VALUES (%s, NULL, 'OPEN', 'Tiket dibuat', %s)
                """,
                (ticket_id, created_by),
            )

            # Publish event ke RabbitMQ untuk diproses oleh Assignment Worker
            publish_event(
                "ticket_created",
                {
                    "event": "ticket_created",
                    "ticket_id": ticket_id,
                    "title": title,
                    "priority": priority,
                    "created_by": created_by,
                    "processed_by_node": NODE_ID,
                    "timestamp": time.time(),
                },
            )

            log(f"✅ Ticket created: {ticket_id} by leader (node {NODE_ID})")
            return jsonify({"result": serialize_row(row)})

        except Exception as e:
            log(f"❌ Error creating ticket: {e}")
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "update_ticket":
        # Hanya leader yang boleh mengupdate tiket
        with state_lock:
            local_is_leader = is_leader
            l_id = leader_id
            l_url = leader_url

        if not local_is_leader:
            return jsonify({"error": {"code": "NOT_LEADER", "leader_id": l_id, "leader_url": l_url}}), 409

        ticket_id = params.get("ticket_id")
        title = params.get("title")
        description = params.get("description")
        status = params.get("status")
        priority = params.get("priority")
        updated_by = params.get("updated_by", "anonymous")

        try:
            # Dapatkan data lama untuk notifikasi
            old_row = db.query("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,), fetch_one=True)
            if not old_row:
                return jsonify({"error": {"code": "NOT_FOUND", "detail": "Ticket not found"}}), 404

            row = db.execute(
                """
                UPDATE tickets SET title = %s, description = %s, status = %s, priority = %s, processed_by_node = %s
                WHERE ticket_id = %s
                RETURNING *
                """,
                (title, description, status, priority, NODE_ID, ticket_id),
                returning=True,
            )

            # Catat histori jika status berubah
            if old_row['status'] != status:
                db.execute(
                    """
                    INSERT INTO ticket_history (ticket_id, old_status, new_status, note, changed_by)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (ticket_id, old_row['status'], status, 'Tiket diupdate manual', updated_by),
                )

            publish_event(
                "ticket_updated",
                {
                    "event": "ticket_updated",
                    "ticket_id": ticket_id,
                    "title": title,
                    "status": status,
                    "updated_by": updated_by,
                    "processed_by_node": NODE_ID,
                    "timestamp": time.time(),
                },
            )

            log(f"✅ Ticket updated: {ticket_id} by leader (node {NODE_ID})")
            return jsonify({"result": serialize_row(row)})
        except Exception as e:
            log(f"❌ Error updating ticket: {e}")
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "delete_ticket":
        # Hanya leader yang boleh menghapus tiket
        with state_lock:
            local_is_leader = is_leader
            l_id = leader_id
            l_url = leader_url

        if not local_is_leader:
            return jsonify({"error": {"code": "NOT_LEADER", "leader_id": l_id, "leader_url": l_url}}), 409

        ticket_id = params.get("ticket_id")

        try:
            row = db.execute(
                "DELETE FROM tickets WHERE ticket_id = %s RETURNING *",
                (ticket_id,),
                returning=True,
            )
            
            if not row:
                return jsonify({"error": {"code": "NOT_FOUND", "detail": "Ticket not found"}}), 404

            # Hapus histori juga (karena foreign key on delete cascade belum diset)
            db.execute("DELETE FROM ticket_history WHERE ticket_id = %s", (ticket_id,))

            publish_event(
                "ticket_deleted",
                {
                    "event": "ticket_deleted",
                    "ticket_id": ticket_id,
                    "processed_by_node": NODE_ID,
                    "timestamp": time.time(),
                },
            )

            log(f"✅ Ticket deleted: {ticket_id} by leader (node {NODE_ID})")
            return jsonify({"result": {"deleted": True, "ticket_id": ticket_id}})
        except Exception as e:
            log(f"❌ Error deleting ticket: {e}")
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "get_tickets":
        # Semua node bisa membaca tiket dari database
        status_filter = params.get("status")
        priority_filter = params.get("priority")
        limit = int(params.get("limit", 50))
        offset = int(params.get("offset", 0))

        sql = "SELECT t.*, a.name AS assigned_to_name FROM tickets t LEFT JOIN agents a ON t.assigned_to = a.agent_id WHERE 1=1"
        sql_params = []

        if status_filter:
            sql += " AND t.status = %s"
            sql_params.append(status_filter)
        if priority_filter:
            sql += " AND t.priority = %s"
            sql_params.append(priority_filter)

        sql += " ORDER BY t.created_at DESC LIMIT %s OFFSET %s"
        sql_params.extend([limit, offset])

        try:
            rows = db.query(sql, tuple(sql_params))
            return jsonify({"result": [serialize_row(r) for r in rows]})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "get_ticket":
        ticket_id = params.get("ticket_id")
        try:
            row = db.query(
                "SELECT t.*, a.name AS assigned_to_name FROM tickets t LEFT JOIN agents a ON t.assigned_to = a.agent_id WHERE t.ticket_id = %s",
                (ticket_id,),
                fetch_one=True,
            )
            if not row:
                return jsonify({"error": {"code": "NOT_FOUND"}}), 404
            return jsonify({"result": serialize_row(row)})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "update_ticket":
        # Hanya leader yang boleh mengupdate tiket
        with state_lock:
            local_is_leader = is_leader
            l_id = leader_id
            l_url = leader_url

        if not local_is_leader:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "NOT_LEADER",
                            "leader_id": l_id,
                            "leader_url": l_url,
                        }
                    }
                ),
                409,
            )

        ticket_id = params.get("ticket_id")
        new_status = params.get("status")
        note = params.get("note", "")

        try:
            # Ambil status lama
            old = db.query(
                "SELECT status FROM tickets WHERE ticket_id = %s",
                (ticket_id,),
                fetch_one=True,
            )
            if not old:
                return jsonify({"error": {"code": "NOT_FOUND"}}), 404

            old_status = old["status"]

            # Update tiket
            row = db.execute(
                """
                UPDATE tickets SET status = %s, updated_at = NOW()
                WHERE ticket_id = %s RETURNING *
                """,
                (new_status, ticket_id),
                returning=True,
            )

            # Catat di history
            db.execute(
                """
                INSERT INTO ticket_history (ticket_id, old_status, new_status, note, changed_by)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (ticket_id, old_status, new_status, note, f"node-{NODE_ID}"),
            )

            # Publish event
            publish_event(
                "ticket_updated",
                {
                    "event": "ticket_updated",
                    "ticket_id": ticket_id,
                    "old_status": old_status,
                    "new_status": new_status,
                    "note": note,
                    "timestamp": time.time(),
                },
            )

            log(f"✅ Ticket updated: {ticket_id} ({old_status} → {new_status})")
            return jsonify({"result": serialize_row(row)})

        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "delete_ticket":
        # Hanya leader yang boleh menghapus tiket
        with state_lock:
            local_is_leader = is_leader
            l_id = leader_id
            l_url = leader_url

        if not local_is_leader:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "NOT_LEADER",
                            "leader_id": l_id,
                            "leader_url": l_url,
                        }
                    }
                ),
                409,
            )

        ticket_id = params.get("ticket_id")

        try:
            row = db.query(
                "SELECT * FROM tickets WHERE ticket_id = %s",
                (ticket_id,),
                fetch_one=True,
            )
            if not row:
                return jsonify({"error": {"code": "NOT_FOUND"}}), 404

            db.execute("DELETE FROM tickets WHERE ticket_id = %s", (ticket_id,))
            log(f"🗑️ Ticket deleted: {ticket_id}")
            return jsonify({"result": {"deleted": ticket_id}})

        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "get_agents":
        try:
            rows = db.query("SELECT * FROM agents ORDER BY agent_id")
            return jsonify({"result": [serialize_row(r) for r in rows]})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "get_stats":
        try:
            stats = db.query(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'OPEN') AS open,
                    COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') AS in_progress,
                    COUNT(*) FILTER (WHERE status = 'RESOLVED') AS resolved,
                    COUNT(*) FILTER (WHERE status = 'CLOSED') AS closed
                FROM tickets
                """,
                fetch_one=True,
            )
            return jsonify({"result": serialize_row(stats)})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "get_ticket_history":
        ticket_id = params.get("ticket_id")
        try:
            rows = db.query(
                "SELECT * FROM ticket_history WHERE ticket_id = %s ORDER BY changed_at DESC",
                (ticket_id,),
            )
            return jsonify({"result": [serialize_row(r) for r in rows]})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "get_notifications":
        try:
            rows = db.query(
                "SELECT * FROM notifications ORDER BY created_at DESC LIMIT 50"
            )
            return jsonify({"result": [serialize_row(r) for r in rows]})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "get_comments":
        ticket_id = params.get("ticket_id")
        try:
            rows = db.query(
                "SELECT * FROM ticket_comments WHERE ticket_id = %s ORDER BY created_at ASC",
                (ticket_id,),
            )
            return jsonify({"result": [serialize_row(r) for r in rows]})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    if method == "add_comment":
        # Hanya leader yang boleh menambahkan komentar baru
        with state_lock:
            local_is_leader = is_leader
            l_id = leader_id
            l_url = leader_url

        if not local_is_leader:
            return (
                jsonify(
                    {
                        "error": {
                            "code": "NOT_LEADER",
                            "leader_id": l_id,
                            "leader_url": l_url,
                        }
                    }
                ),
                409,
            )

        ticket_id = params.get("ticket_id")
        commenter = params.get("commenter", "anonymous")
        comment_text = params.get("comment_text")

        if not comment_text:
            return jsonify({"error": {"code": "BAD_REQUEST", "detail": "Comment text is required"}}), 400

        try:
            row = db.execute(
                """
                INSERT INTO ticket_comments (ticket_id, commenter, comment_text)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (ticket_id, commenter, comment_text),
                returning=True,
            )
            return jsonify({"result": serialize_row(row)})
        except Exception as e:
            return jsonify({"error": {"code": "DB_ERROR", "detail": str(e)}}), 500

    # Method tidak dikenali
    return jsonify({"error": {"code": "NO_SUCH_METHOD"}}), 400


# ============================================================
# Health Check Endpoint
# ============================================================
@app.get("/health")
def health():
    """Endpoint health check untuk monitoring."""
    with state_lock:
        return jsonify(
            {
                "status": "ok",
                "node_id": NODE_ID,
                "node_name": NODE_NAME,
                "is_leader": is_leader,
                "leader_id": leader_id,
            }
        )


# ============================================================
# Main Entry Point
# ============================================================
if __name__ == "__main__":
    # Jalankan thread-thread background
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=bootstrap, daemon=True).start()

    log("🚀 Starting Ticket Service on :9000")
    log(f"   Ring topology: {' → '.join(NODES[k] for k in sorted(NODES.keys()))} → (loop)")
    log(f"   Successor: Node {get_successor_id()}")

    app.run(host="0.0.0.0", port=9000, threaded=True)
