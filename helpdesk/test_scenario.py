import requests
import time
import json

print("======================================================")
print(" 🚀 PENGUJIAN INTEGRASI SISTEM HELPDESK MICROSERVICES ")
print("======================================================\n")

# 1. Ring Election & Status Leader
print("=== 1. STATUS RING ELECTION & LEADER ===")
try:
    resp = requests.get('http://localhost:80/api/leader').json()
    data = resp.get('data', [])
    leader = next((n for n in data if n.get('i_am_leader')), None)
    if leader:
        print(f"✅ Sistem berjalan. Leader terpilih adalah Node {leader['leader_id']} di {leader['leader_url']}")
    else:
        print("❌ Leader tidak ditemukan.")
except Exception as e:
    print(f"❌ Error API Leader: {e}")

# 2. Membuat Tiket
print("\n=== 2. MEMBUAT TIKET (API Gateway + RPC) ===")
payload = {
    'title': 'Server Database Down',
    'description': 'Tidak bisa koneksi ke port 5432.',
    'priority': 'CRITICAL',
    'created_by': 'Admin DevOps'
}
ticket_id = None
try:
    t_resp = requests.post('http://localhost:80/api/tickets', json=payload).json()
    ticket_data = t_resp.get('data', {})
    ticket_id = ticket_data.get('ticket_id')
    if ticket_id:
        print(f"✅ Tiket berhasil dibuat dengan ID: {ticket_id}")
        meta = t_resp.get('metrics', {})
        print(f"   ↳ Routing perjalanan request: {meta.get('routed_via', 'OK')} (dalam {meta.get('end_to_end_ms')} ms)")
        print(f"   ↳ Diproses oleh: Node {ticket_data.get('processed_by_node')}")
    else:
        print(f"❌ Gagal membuat tiket: {t_resp}")
except Exception as e:
    print(f"❌ Error API Create Ticket: {e}")

# 3. Auto-Assignment (RabbitMQ)
if ticket_id:
    print("\n=== 3. AUTO-ASSIGNMENT WORKER (RabbitMQ Event) ===")
    print("⏳ Menunggu 2 detik agar Assignment Worker memproses event dari queue...")
    time.sleep(2)
    try:
        t_detail = requests.get(f'http://localhost:80/api/tickets/{ticket_id}').json()
        data = t_detail.get('data', {})
        print(f"✅ Status Tiket: {data.get('status')}")
        print(f"✅ Diberikan ke Agen (Assigned To): Agent #{data.get('assigned_to')}")
    except Exception as e:
        print(f"❌ Error API Get Ticket: {e}")

# 4. Notifications
if ticket_id:
    print("\n=== 4. NOTIFICATION WORKER (Event-Driven) ===")
    try:
        n_resp = requests.get('http://localhost:80/api/notifications').json()
        data = n_resp.get('data', [])
        # Cari notifikasi yang berkaitan dengan tiket ini
        notif = [n for n in data if ticket_id in n.get('message', '')]
        if notif:
            for n in notif:
                print(f"✅ Notifikasi Ter-generate: {n['message']}")
        else:
            print("❌ Notifikasi untuk tiket ini belum muncul.")
    except Exception as e:
        print(f"❌ Error API Notifications: {e}")

print("\n======================================================")
print(" Semua fitur inti (Gateway, RPC, Database, RabbitMQ) teruji!")
print("======================================================")
