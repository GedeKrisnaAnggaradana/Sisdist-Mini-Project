# api_gateway.py — REST API Gateway untuk Helpdesk Ticketing
#
# Service ini menyediakan REST API yang bisa diakses oleh klien (GUI/curl).
# Semua request diteruskan ke Ticket Service Node via RPC (HTTP POST /rpc).
#
# Gateway menangani:
# - Routing request ke node yang tepat (round-robin)
# - Retry otomatis ke leader jika mendapat respons NOT_LEADER
# - Serving file statis untuk GUI (HTML/CSS/JS)

import os
import time
import uuid

import requests
from flask import Flask, request, jsonify, send_from_directory

# ============================================================
# Inisialisasi Flask
# ============================================================
app = Flask(__name__)

# ============================================================
# Konfigurasi Ticket Service Nodes
# ============================================================
TICKET_NODES = [
    x.strip()
    for x in os.getenv(
        "TICKET_NODES",
        "http://ticket-1:9000,http://ticket-2:9000,http://ticket-3:9000",
    ).split(",")
    if x.strip()
]

# Counter round-robin untuk distribusi request ke node
_rr = 0


def log(msg: str):
    """Cetak log dengan prefix [api-gateway]."""
    gw_id = os.getenv("GW_ID", "1")
    print(f"[api-gateway-{gw_id}] {msg}", flush=True)


# ============================================================
# RPC Helper: komunikasi dengan Ticket Service Nodes
# ============================================================
def rpc_call(base_url: str, method: str, params: dict, timeout=3.0):
    """Panggil RPC method pada Ticket Service Node.

    Args:
        base_url: URL dasar node (misal: http://ticket-1:9000)
        method: Nama RPC method
        params: Parameter untuk method
        timeout: Timeout request dalam detik

    Returns:
        Dictionary response dari node
    """
    payload = {"method": method, "params": params}
    r = requests.post(f"{base_url}/rpc", json=payload, timeout=timeout)
    try:
        data = r.json()
        if isinstance(data, dict) and ("error" in data or "result" in data):
            return data
    except Exception:
        pass
    r.raise_for_status()
    return r.json()


def pick_node() -> str:
    """Pilih Ticket Service Node secara round-robin."""
    global _rr
    _rr = (_rr + 1) % len(TICKET_NODES)
    return TICKET_NODES[_rr]


def find_leader():
    """Tanya ke setiap node: siapa leader saat ini?

    Mengembalikan info leader pertama yang valid ditemukan.
    """
    for n in TICKET_NODES:
        try:
            out = rpc_call(n, "who_is_leader", {}, timeout=1.0).get("result") or {}
            if out.get("leader_id"):
                return out
        except Exception:
            continue
    return None


def rpc_with_leader_retry(method: str, params: dict):
    """Panggil RPC method dengan otomatis retry ke leader.

    Alur:
    1. Pilih node secara round-robin
    2. Kirim RPC call
    3. Jika respons NOT_LEADER → ambil leader_url dari respons → retry ke leader
    4. Jika node tidak bisa dihubungi → coba cari leader dari node lain

    Args:
        method: Nama RPC method
        params: Parameter

    Returns:
        Tuple (response_dict, metrics_dict)
    """
    t0 = time.time()
    chosen = pick_node()
    corr_id = str(uuid.uuid4())[:8]

    # 1) Coba ke node yang dipilih
    try:
        resp = rpc_call(chosen, method, params)
    except Exception as e:
        return {"error": {"code": "NODE_UNREACHABLE", "detail": str(e)}}, 503

    # 2) Jika NOT_LEADER, retry ke leader
    if resp.get("error", {}).get("code") == "NOT_LEADER":
        leader_url = resp["error"].get("leader_url")
        leader_id = resp["error"].get("leader_id")

        if not leader_url:
            leader_info = find_leader()
            if leader_info:
                leader_url = leader_info.get("leader_url")
                leader_id = leader_info.get("leader_id")

        if not leader_url:
            return {"error": "No leader available, try again later"}, 503

        try:
            resp = rpc_call(leader_url, method, params)
            chosen = f"{chosen} → leader(node-{leader_id})"
        except Exception as e:
            return {"error": {"code": "LEADER_UNREACHABLE", "detail": str(e)}}, 503

    total_ms = int((time.time() - t0) * 1000)
    metrics = {
        "routed_via": chosen,
        "end_to_end_ms": total_ms,
        "correlation_id": corr_id,
    }

    return resp, 200, metrics


# ============================================================
# REST API Endpoints
# ============================================================




# --- Tickets ---
@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    """Buat tiket baru.

    Request Body:
        {"title": "...", "description": "...", "priority": "MEDIUM", "created_by": "..."}
    """
    body = request.get_json(force=True, silent=True) or {}
    result = rpc_with_leader_retry("create_ticket", body)

    if isinstance(result, tuple) and len(result) == 3:
        resp, status, metrics = result
        if "result" in resp:
            log(f"POST /api/tickets → {resp['result'].get('ticket_id', '?')} [{metrics['routed_via']}]")
            return jsonify({"data": resp["result"], "metrics": metrics}), 201
        return jsonify(resp), status
    return jsonify(result[0]), result[1]


@app.route("/api/tickets", methods=["GET"])
def list_tickets():
    """Daftar tiket dengan filter opsional.

    Query Params:
        status: Filter berdasarkan status (OPEN, IN_PROGRESS, RESOLVED, CLOSED)
        priority: Filter berdasarkan prioritas (LOW, MEDIUM, HIGH, CRITICAL)
        limit: Jumlah tiket per halaman (default: 50)
        offset: Offset pagination (default: 0)
    """
    params = {
        "status": request.args.get("status"),
        "priority": request.args.get("priority"),
        "limit": request.args.get("limit", 50),
        "offset": request.args.get("offset", 0),
    }
    # Hapus parameter yang None
    params = {k: v for k, v in params.items() if v is not None}

    chosen = pick_node()
    try:
        resp = rpc_call(chosen, "get_tickets", params)
        return jsonify({"data": resp.get("result", [])})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/tickets/<ticket_id>", methods=["GET"])
def get_ticket(ticket_id):
    """Ambil detail satu tiket."""
    chosen = pick_node()
    try:
        resp = rpc_call(chosen, "get_ticket", {"ticket_id": ticket_id})
        if "error" in resp:
            return jsonify(resp), 404
        return jsonify({"data": resp.get("result")})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/tickets/<ticket_id>", methods=["PUT"])
def update_ticket(ticket_id):
    """Update status tiket.

    Request Body:
        {"status": "RESOLVED", "note": "Masalah sudah diperbaiki"}
    """
    body = request.get_json(force=True, silent=True) or {}
    body["ticket_id"] = ticket_id

    result = rpc_with_leader_retry("update_ticket", body)

    if isinstance(result, tuple) and len(result) == 3:
        resp, status, metrics = result
        if "result" in resp:
            log(f"PUT /api/tickets/{ticket_id} [{metrics['routed_via']}]")
            return jsonify({"data": resp["result"], "metrics": metrics})
        return jsonify(resp), status
    return jsonify(result[0]), result[1]


@app.route("/api/tickets/<ticket_id>", methods=["DELETE"])
def delete_ticket(ticket_id):
    """Hapus tiket."""
    result = rpc_with_leader_retry("delete_ticket", {"ticket_id": ticket_id})

    if isinstance(result, tuple) and len(result) == 3:
        resp, status, metrics = result
        if "result" in resp:
            log(f"DELETE /api/tickets/{ticket_id} [{metrics['routed_via']}]")
            return jsonify({"data": resp["result"], "metrics": metrics})
        return jsonify(resp), status
    return jsonify(result[0]), result[1]


@app.route("/api/tickets/<ticket_id>/history", methods=["GET"])
def get_ticket_history(ticket_id):
    """Ambil riwayat perubahan tiket."""
    chosen = pick_node()
    try:
        resp = rpc_call(chosen, "get_ticket_history", {"ticket_id": ticket_id})
        return jsonify({"data": resp.get("result", [])})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# --- Comments ---
@app.route("/api/tickets/<ticket_id>/comments", methods=["POST"])
def add_comment(ticket_id):
    """Tambah komentar baru ke tiket."""
    body = request.get_json(force=True, silent=True) or {}
    body["ticket_id"] = ticket_id
    result = rpc_with_leader_retry("add_comment", body)

    if isinstance(result, tuple) and len(result) == 3:
        resp, status, metrics = result
        if "result" in resp:
            log(f"POST /api/tickets/{ticket_id}/comments [{metrics['routed_via']}]")
            return jsonify({"data": resp["result"], "metrics": metrics}), 201
        return jsonify(resp), status
    return jsonify(result[0]), result[1]


@app.route("/api/tickets/<ticket_id>/comments", methods=["GET"])
def get_comments(ticket_id):
    """Ambil daftar komentar tiket."""
    chosen = pick_node()
    try:
        resp = rpc_call(chosen, "get_comments", {"ticket_id": ticket_id})
        return jsonify({"data": resp.get("result", [])})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# --- Agents ---
@app.route("/api/agents", methods=["GET"])
def list_agents():
    """Daftar agen helpdesk."""
    chosen = pick_node()
    try:
        resp = rpc_call(chosen, "get_agents", {})
        return jsonify({"data": resp.get("result", [])})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# --- Stats ---
@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Statistik tiket (jumlah per status)."""
    chosen = pick_node()
    try:
        resp = rpc_call(chosen, "get_stats", {})
        return jsonify({"data": resp.get("result", {})})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# --- Notifications ---
@app.route("/api/notifications", methods=["GET"])
def list_notifications():
    """Daftar notifikasi terbaru."""
    chosen = pick_node()
    try:
        resp = rpc_call(chosen, "get_notifications", {})
        return jsonify({"data": resp.get("result", [])})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# --- Leader Info ---
@app.route("/api/leader", methods=["GET"])
def get_leader():
    """Info leader saat ini dari semua node."""
    nodes_status = []
    for n in TICKET_NODES:
        try:
            resp = rpc_call(n, "who_is_leader", {}, timeout=1.0)
            info = resp.get("result", {})
            info["url"] = n
            info["reachable"] = True
            nodes_status.append(info)
        except Exception:
            nodes_status.append({"url": n, "reachable": False})

    return jsonify({"data": nodes_status})


# --- Election Trigger (untuk demo) ---
@app.route("/api/election/trigger", methods=["POST"])
def trigger_election():
    """Trigger election pada node tertentu (untuk keperluan demo).

    Query Params:
        node: URL node yang akan di-trigger (opsional, default: node pertama)
    """
    target = request.args.get("node", TICKET_NODES[0])
    try:
        # Kita kirim pesan election manual ke node target
        # Node akan memulai proses election
        resp = rpc_call(target, "election", {"candidate_id": 0}, timeout=2.0)
        return jsonify({"message": "Election triggered", "target": target, "response": resp})
    except Exception as e:
        return jsonify({"error": str(e)}), 503


# ============================================================
# Main Entry Point
# ============================================================
if __name__ == "__main__":
    gw_id = os.getenv("GW_ID", "1")
    log(f"🚀 Starting API Gateway (instance {gw_id}) on :8000")
    log(f"   Ticket nodes: {TICKET_NODES}")
    app.run(host="0.0.0.0", port=8000, threaded=True)
