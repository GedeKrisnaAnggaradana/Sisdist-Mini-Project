import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function Agents() {
    const [agents, setAgents] = useState([]);

    useEffect(() => {
        const loadAgents = async () => {
            const resp = await apiFetch("/api/agents");
            if (resp.data) setAgents(resp.data);
        };
        loadAgents();
    }, []);

    return (
        <div className="page active">
            <div className="card">
                <div className="card-header">
                    <h2>👥 Daftar Agen Helpdesk</h2>
                </div>
                <div className="card-body">
                    <div className="table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Nama</th>
                                    <th>Email</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {agents.length > 0 ? agents.map(a => (
                                    <tr key={a.agent_id}>
                                        <td>{a.agent_id}</td>
                                        <td>{a.name}</td>
                                        <td>{a.email}</td>
                                        <td>{a.is_available 
                                            ? <span className="badge badge-open">Available</span>
                                            : <span className="badge badge-closed">Unavailable</span>
                                        }</td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan="4" className="empty-state">Memuat data...</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
