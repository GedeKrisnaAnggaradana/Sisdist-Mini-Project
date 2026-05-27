import React, { useState, useEffect } from 'react';
import { apiFetch, deleteTicket, formatDate } from '../api';

export default function Tickets({ showToast, onViewTicket }) {
    const [tickets, setTickets] = useState([]);
    const [status, setStatus] = useState('');
    const [priority, setPriority] = useState('');
    const [isDeleting, setIsDeleting] = useState(null); // ticket_id

    const loadTickets = async () => {
        let url = `/api/tickets?limit=50`;
        if (status) url += `&status=${status}`;
        if (priority) url += `&priority=${priority}`;
        
        const resp = await apiFetch(url);
        if (resp.data) setTickets(resp.data);
    };

    useEffect(() => {
        loadTickets();
        
        // Polling daftar tiket untuk real-time update
        const interval = setInterval(loadTickets, 5000);
        return () => clearInterval(interval);
    }, [status, priority]);

    const handleDelete = async (e, id) => {
        e.stopPropagation(); // mencegah modal detail terbuka saat mengklik hapus
        if (!window.confirm(`Yakin ingin menghapus tiket ${id}?`)) return;
        
        setIsDeleting(id);
        const resp = await deleteTicket(id);
        setIsDeleting(null);
        
        if (resp.error) {
            showToast(`Gagal menghapus tiket: ${resp.error.detail || resp.error.code}`, 'error');
        } else {
            showToast('Tiket berhasil dihapus!', 'success');
            loadTickets();
        }
    };

    const priorityBadge = (pri) => {
        const cls = (pri || "").toLowerCase();
        return <span className={`badge badge-${cls}`}>{pri || "—"}</span>;
    };

    const statusBadge = (stat) => {
        const cls = (stat || "").toLowerCase().replace(" ", "_");
        const label = (stat || "—").replace("_", " ");
        return <span className={`badge badge-${cls}`}>{label}</span>;
    };

    return (
        <div className="page active">
            <div className="filter-bar">
                <select className="select-input" value={status} onChange={e => setStatus(e.target.value)}>
                    <option value="">Semua Status</option>
                    <option value="OPEN">Open</option>
                    <option value="IN_PROGRESS">In Progress</option>
                    <option value="RESOLVED">Resolved</option>
                    <option value="CLOSED">Closed</option>
                </select>
                <select className="select-input" value={priority} onChange={e => setPriority(e.target.value)}>
                    <option value="">Semua Prioritas</option>
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="CRITICAL">Critical</option>
                </select>
                <button className="btn btn-primary btn-sm" onClick={loadTickets}>🔍 Filter</button>
            </div>

            <div className="card">
                <div className="card-body">
                    <div className="table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Judul</th>
                                    <th>Prioritas</th>
                                    <th>Status</th>
                                    <th>Assigned</th>
                                    <th>Aksi</th>
                                </tr>
                            </thead>
                            <tbody>
                                {tickets.length > 0 ? tickets.map(t => (
                                    <tr key={t.ticket_id}>
                                        <td>
                                            <a 
                                                href={`#ticket-${t.ticket_id}`} 
                                                onClick={(e) => { e.preventDefault(); onViewTicket(t.ticket_id, false); }}
                                                style={{ fontWeight: '600' }}
                                            >
                                                <code>{t.ticket_id}</code>
                                            </a>
                                        </td>
                                        <td>
                                            <a 
                                                href={`#ticket-${t.ticket_id}`} 
                                                onClick={(e) => { e.preventDefault(); onViewTicket(t.ticket_id, false); }}
                                                style={{ color: 'var(--text-primary)', fontWeight: '500', textDecoration: 'none' }}
                                                onMouseEnter={(e) => e.target.style.textDecoration = 'underline'}
                                                onMouseLeave={(e) => e.target.style.textDecoration = 'none'}
                                            >
                                                {t.title}
                                            </a>
                                        </td>
                                        <td>{priorityBadge(t.priority)}</td>
                                        <td>{statusBadge(t.status)}</td>
                                        <td>{t.assigned_to_name || "—"}</td>
                                        <td>
                                            <div style={{ display: 'flex', gap: '8px' }} onClick={(e) => e.stopPropagation()}>
                                                <button 
                                                    className="icon-btn" 
                                                    title="Buka & Edit" 
                                                    onClick={() => onViewTicket(t.ticket_id, true)}
                                                >
                                                    ✏️
                                                </button>
                                                <button 
                                                    className="icon-btn" 
                                                    title="Hapus Tiket" 
                                                    onClick={(e) => handleDelete(e, t.ticket_id)} 
                                                    disabled={isDeleting === t.ticket_id}
                                                >
                                                    🗑️
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan="6" className="empty-state">Tidak ada tiket ditemukan</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
