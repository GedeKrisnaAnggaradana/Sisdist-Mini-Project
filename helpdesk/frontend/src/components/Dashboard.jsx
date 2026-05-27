import React, { useState, useEffect } from 'react';
import { apiFetch, formatDate } from '../api';

export default function Dashboard({ onViewTicket }) {
    const [stats, setStats] = useState({});
    const [leader, setLeader] = useState(null);
    const [recentTickets, setRecentTickets] = useState([]);
    const [activeNodes, setActiveNodes] = useState({ active: 0, total: 0 });

    const loadData = async () => {
        // Fetch stats
        const sResp = await apiFetch("/api/stats");
        if (sResp.data) setStats(sResp.data);

        // Fetch leader
        const lResp = await apiFetch("/api/leader");
        if (lResp.data) {
            const activeCount = lResp.data.filter(n => n.reachable).length;
            setActiveNodes({ active: activeCount, total: lResp.data.length });
            const currLeader = lResp.data.find(n => n.i_am_leader && n.reachable);
            setLeader(currLeader);
        }

        // Fetch recent tickets
        const tResp = await apiFetch("/api/tickets?limit=5");
        if (tResp.data) setRecentTickets(tResp.data);
    };

    useEffect(() => {
        loadData();
        const interval = setInterval(loadData, 5000);
        return () => clearInterval(interval);
    }, []);

    const priorityBadge = (priority) => {
        const cls = (priority || "").toLowerCase();
        return <span className={`badge badge-${cls}`}>{priority || "—"}</span>;
    };

    const statusBadge = (status) => {
        const cls = (status || "").toLowerCase().replace(" ", "_");
        const label = (status || "—").replace("_", " ");
        return <span className={`badge badge-${cls}`}>{label}</span>;
    };

    return (
        <div className="page active">
            <div className="stats-grid">
                <div className="stat-card stat-total">
                    <div className="stat-icon">📋</div>
                    <div className="stat-info">
                        <span className="stat-value">{stats.total ?? "—"}</span>
                        <span className="stat-label">Total Tiket</span>
                    </div>
                </div>
                <div className="stat-card stat-open">
                    <div className="stat-icon">🟢</div>
                    <div className="stat-info">
                        <span className="stat-value">{stats.open ?? "—"}</span>
                        <span className="stat-label">Open</span>
                    </div>
                </div>
                <div className="stat-card stat-progress">
                    <div className="stat-icon">🔵</div>
                    <div className="stat-info">
                        <span className="stat-value">{stats.in_progress ?? "—"}</span>
                        <span className="stat-label">In Progress</span>
                    </div>
                </div>
                <div className="stat-card stat-resolved">
                    <div className="stat-icon">✅</div>
                    <div className="stat-info">
                        <span className="stat-value">{stats.resolved ?? "—"}</span>
                        <span className="stat-label">Resolved</span>
                    </div>
                </div>
                <div className="stat-card stat-closed">
                    <div className="stat-icon">🔒</div>
                    <div className="stat-info">
                        <span className="stat-value">{stats.closed ?? "—"}</span>
                        <span className="stat-label">Closed</span>
                    </div>
                </div>
            </div>

            <div className="card leader-card">
                <div className="card-header">
                    <h2>👑 Leader Saat Ini</h2>
                </div>
                <div className="card-body">
                    {leader ? (
                        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                            <div className="leader-info-item">
                                <div className="label">Leader Node</div>
                                <div className="value">Node {leader.leader_id} ({leader.node_name})</div>
                            </div>
                            <div className="leader-info-item">
                                <div className="label">Leader URL</div>
                                <div className="value">{leader.leader_url}</div>
                            </div>
                            <div className="leader-info-item">
                                <div className="label">Node Aktif</div>
                                <div className="value">{activeNodes.active} / {activeNodes.total}</div>
                            </div>
                        </div>
                    ) : (
                        <div className="empty-state">Belum ada leader yang terpilih atau sistem offline</div>
                    )}
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <h2>🕐 Tiket Terbaru</h2>
                </div>
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
                                    <th>Dibuat</th>
                                </tr>
                            </thead>
                            <tbody>
                                {recentTickets.length > 0 ? recentTickets.map(t => (
                                    <tr key={t.ticket_id}>
                                        <td>
                                            <a 
                                                href={`#ticket-${t.ticket_id}`} 
                                                onClick={(e) => { e.preventDefault(); onViewTicket(t.ticket_id); }}
                                                style={{ fontWeight: '600' }}
                                            >
                                                <code>{t.ticket_id}</code>
                                            </a>
                                        </td>
                                        <td>
                                            <a 
                                                href={`#ticket-${t.ticket_id}`} 
                                                onClick={(e) => { e.preventDefault(); onViewTicket(t.ticket_id); }}
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
                                        <td>{formatDate(t.created_at)}</td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan="6" className="empty-state">Belum ada tiket</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
