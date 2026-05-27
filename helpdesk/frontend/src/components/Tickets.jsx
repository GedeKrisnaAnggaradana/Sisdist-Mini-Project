import React, { useState, useEffect } from 'react';
import { apiFetch, updateTicket, deleteTicket, formatDate } from '../api';

export default function Tickets({ showToast }) {
    const [tickets, setTickets] = useState([]);
    const [agents, setAgents] = useState([]);
    const [status, setStatus] = useState('');
    const [priority, setPriority] = useState('');
    
    // Modal Edit State
    const [editingTicket, setEditingTicket] = useState(null);
    const [editForm, setEditForm] = useState({ title: '', description: '', status: '', priority: '' });
    const [isDeleting, setIsDeleting] = useState(null); // ticket_id

    const loadData = async () => {
        let url = `/api/tickets?limit=50`;
        if (status) url += `&status=${status}`;
        if (priority) url += `&priority=${priority}`;
        
        const [tResp, aResp] = await Promise.all([
            apiFetch(url),
            apiFetch('/api/agents')
        ]);
        
        if (tResp.data) setTickets(tResp.data);
        if (aResp.data) setAgents(aResp.data);
    };

    useEffect(() => {
        loadData();
    }, [status, priority]);

    const handleDelete = async (id) => {
        if (!window.confirm(`Yakin ingin menghapus tiket ${id}?`)) return;
        
        setIsDeleting(id);
        const resp = await deleteTicket(id);
        setIsDeleting(null);
        
        if (resp.error) {
            showToast(`Gagal menghapus tiket: ${resp.error.detail || resp.error.code}`, 'error');
        } else {
            showToast('Tiket berhasil dihapus!', 'success');
            loadData();
        }
    };

    const handleEditClick = (ticket) => {
        setEditingTicket(ticket.ticket_id);
        setEditForm({
            title: ticket.title,
            description: ticket.description,
            status: ticket.status,
            priority: ticket.priority
        });
    };

    const handleEditSubmit = async (e) => {
        e.preventDefault();
        const resp = await updateTicket(editingTicket, editForm);
        if (resp.error) {
            showToast(`Gagal update tiket: ${resp.error.detail || resp.error.code}`, 'error');
        } else {
            showToast('Tiket berhasil diupdate!', 'success');
            setEditingTicket(null);
            loadData();
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
                <button className="btn btn-primary btn-sm" onClick={loadData}>🔍 Filter</button>
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
                                {tickets.length > 0 ? tickets.map(t => {
                                    const agent = agents.find(a => a.agent_id === t.assigned_to);
                                    const agentName = agent ? agent.name : (t.assigned_to ? `Agent #${t.assigned_to}` : "—");
                                    return (
                                        <tr key={t.ticket_id}>
                                            <td><code>{t.ticket_id}</code></td>
                                            <td>{t.title}</td>
                                            <td>{priorityBadge(t.priority)}</td>
                                            <td>{statusBadge(t.status)}</td>
                                            <td>{agentName}</td>
                                            <td>
                                                <div style={{ display: 'flex', gap: '8px' }}>
                                                    <button className="icon-btn" title="Edit Tiket" onClick={() => handleEditClick(t)}>
                                                        ✏️
                                                    </button>
                                                    <button className="icon-btn" title="Hapus Tiket" onClick={() => handleDelete(t.ticket_id)} disabled={isDeleting === t.ticket_id}>
                                                        🗑️
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                }) : (
                                    <tr><td colSpan="6" className="empty-state">Tidak ada tiket ditemukan</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Modal Edit */}
            {editingTicket && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
                    backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <div className="card" style={{ width: '400px', margin: '0', maxHeight: '90vh', overflowY: 'auto' }}>
                        <div className="card-header">
                            <h2>Edit Tiket: <code>{editingTicket}</code></h2>
                            <button className="icon-btn" onClick={() => setEditingTicket(null)}>✖</button>
                        </div>
                        <div className="card-body">
                            <form onSubmit={handleEditSubmit}>
                                <div className="form-group">
                                    <label>Judul Tiket</label>
                                    <input type="text" className="form-input" required
                                        value={editForm.title} onChange={e => setEditForm({...editForm, title: e.target.value})} />
                                </div>
                                <div className="form-group">
                                    <label>Deskripsi Masalah</label>
                                    <textarea className="form-input" rows="3" required
                                        value={editForm.description} onChange={e => setEditForm({...editForm, description: e.target.value})}></textarea>
                                </div>
                                <div className="form-row">
                                    <div className="form-group">
                                        <label>Status</label>
                                        <select className="form-input" value={editForm.status} onChange={e => setEditForm({...editForm, status: e.target.value})}>
                                            <option value="OPEN">Open</option>
                                            <option value="IN_PROGRESS">In Progress</option>
                                            <option value="RESOLVED">Resolved</option>
                                            <option value="CLOSED">Closed</option>
                                        </select>
                                    </div>
                                    <div className="form-group">
                                        <label>Prioritas</label>
                                        <select className="form-input" value={editForm.priority} onChange={e => setEditForm({...editForm, priority: e.target.value})}>
                                            <option value="LOW">Low</option>
                                            <option value="MEDIUM">Medium</option>
                                            <option value="HIGH">High</option>
                                            <option value="CRITICAL">Critical</option>
                                        </select>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                                    <button type="button" className="btn" onClick={() => setEditingTicket(null)}>Batal</button>
                                    <button type="submit" className="btn btn-primary">Simpan Perubahan</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
