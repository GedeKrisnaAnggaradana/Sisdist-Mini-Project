import React, { useState, useEffect } from 'react';
import { apiFetch } from '../api';

export default function RingMonitor({ showToast }) {
    const [nodes, setNodes] = useState([]);
    
    const loadNodes = async () => {
        const resp = await apiFetch("/api/leader");
        if (resp.data) setNodes(resp.data);
    };

    useEffect(() => {
        loadNodes();
        const interval = setInterval(loadNodes, 3000);
        return () => clearInterval(interval);
    }, []);

    const triggerElection = async () => {
        if (!window.confirm("Trigger election baru? (untuk demo)")) return;
        await apiFetch("/api/election/trigger", { method: "POST" });
        showToast("Election triggered! Refreshing...", "info");
        setTimeout(loadNodes, 2000);
    };

    // Render SVG Ring Topology
    const renderRing = () => {
        if (nodes.length === 0) return null;
        const centerX = 300;
        const centerY = 150;
        const radius = 120;
        const nodeCount = nodes.length;

        const positions = nodes.map((_, i) => {
            const angle = (i * 2 * Math.PI / nodeCount) - Math.PI / 2;
            return {
                x: centerX + radius * Math.cos(angle),
                y: centerY + radius * Math.sin(angle)
            };
        });

        return (
            <div className="ring-visualization" style={{ position: 'relative', width: '600px', margin: '0 auto' }}>
                <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 1 }} viewBox="0 0 600 320">
                    <defs>
                        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="var(--text-secondary)" />
                        </marker>
                    </defs>
                    {positions.map((from, i) => {
                        const to = positions[(i + 1) % nodeCount];
                        return (
                            <line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                                stroke="var(--text-secondary)" strokeWidth="2" strokeDasharray="6,4"
                                markerEnd="url(#arrowhead)" />
                        );
                    })}
                </svg>

                {nodes.map((n, i) => {
                    const pos = positions[i];
                    const role = !n.reachable ? "offline" : n.i_am_leader ? "leader" : "follower";
                    const roleLabel = !n.reachable ? "OFFLINE" : n.i_am_leader ? "👑 LEADER" : "FOLLOWER";
                    const nodeId = n.node_id || (i + 1);

                    return (
                        <div key={nodeId} className={`ring-node ${role}`} style={{ left: pos.x - 50, top: pos.y - 50 }}>
                            <span className="ring-node-id">{nodeId}</span>
                            <span className="ring-node-label">{n.node_name || `Node ${nodeId}`}</span>
                            <span className="ring-node-role">{roleLabel}</span>
                        </div>
                    );
                })}

                <div className="ring-center-label" style={{ left: centerX - 60, top: centerY - 12, width: 120 }}>
                    Ring Topology<br />
                    <strong style={{ color: 'var(--accent-primary)' }}>Chang-Roberts</strong>
                </div>
            </div>
        );
    };

    return (
        <div className="page active">
            <div className="card">
                <div className="card-header">
                    <h2>🔗 Ring Election Monitor</h2>
                    <button className="btn btn-danger btn-sm" onClick={triggerElection}>⚡ Trigger Election</button>
                </div>
                <div className="card-body">
                    {renderRing()}
                    <div className="ring-legend">
                        <span className="legend-item"><span className="legend-dot leader"></span> Leader</span>
                        <span className="legend-item"><span className="legend-dot follower"></span> Follower</span>
                        <span className="legend-item"><span className="legend-dot offline"></span> Offline</span>
                    </div>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <h2>📡 Status Node</h2>
                </div>
                <div className="card-body">
                    <div className="table-container">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Node</th>
                                    <th>ID</th>
                                    <th>URL</th>
                                    <th>Role</th>
                                    <th>Leader yang Diketahui</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {nodes.length > 0 ? nodes.map((n, i) => {
                                    const role = !n.reachable ? "OFFLINE" : n.i_am_leader ? "LEADER" : "FOLLOWER";
                                    const roleClass = role.toLowerCase();
                                    return (
                                        <tr key={i}>
                                            <td>{n.node_name || "—"}</td>
                                            <td>{n.node_id || "—"}</td>
                                            <td><code>{n.url}</code></td>
                                            <td><span className={`badge badge-${roleClass === "leader" ? "open" : roleClass === "follower" ? "in_progress" : "closed"}`}>{role}</span></td>
                                            <td>{n.leader_id ? `Node ${n.leader_id}` : "—"}</td>
                                            <td>{n.reachable 
                                                ? <span className="badge badge-open">Online</span>
                                                : <span className="badge badge-closed">Offline</span>
                                            }</td>
                                        </tr>
                                    );
                                }) : (
                                    <tr><td colSpan="6" className="empty-state">Memuat data...</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
