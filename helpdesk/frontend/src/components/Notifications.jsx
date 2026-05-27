import React, { useState, useEffect } from 'react';
import { apiFetch, formatDate } from '../api';

export default function Notifications() {
    const [notifications, setNotifications] = useState([]);

    useEffect(() => {
        const loadNotifs = async () => {
            const resp = await apiFetch("/api/notifications");
            if (resp.data) setNotifications(resp.data);
        };
        loadNotifs();
        const interval = setInterval(loadNotifs, 5000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="page active">
            <div className="card">
                <div className="card-header">
                    <h2>🔔 Notifikasi Sistem</h2>
                </div>
                <div className="card-body">
                    <div className="notifications-list">
                        {notifications.length > 0 ? notifications.map(n => {
                            const isAssigned = n.type === "ASSIGNED";
                            return (
                                <div key={n.id || n.created_at} className="notif-item">
                                    <div className={`notif-icon ${isAssigned ? "assigned" : "updated"}`}>
                                        {isAssigned ? "👤" : "🔄"}
                                    </div>
                                    <div className="notif-content">
                                        <div className="notif-message">{n.message}</div>
                                        <div className="notif-time">{formatDate(n.created_at)}</div>
                                    </div>
                                </div>
                            );
                        }) : (
                            <div className="empty-state">Belum ada notifikasi</div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
