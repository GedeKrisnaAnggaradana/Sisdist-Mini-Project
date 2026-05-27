import React, { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import Tickets from './components/Tickets';
import CreateTicket from './components/CreateTicket';
import Agents from './components/Agents';
import RingMonitor from './components/RingMonitor';
import Notifications from './components/Notifications';
import TicketDetailModal from './components/TicketDetailModal';
import './index.css';

export default function App() {
    const [activePage, setActivePage] = useState('dashboard');
    const [isSidebarOpen, setSidebarOpen] = useState(false);
    const [toast, setToast] = useState(null);
    const [selectedTicket, setSelectedTicket] = useState(null); // { id: '...', edit: boolean }
    
    // Theme state, default to light
    const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(theme === 'light' ? 'dark' : 'light');
    };

    const pages = {
        dashboard: { label: 'Dashboard', icon: '📊', component: Dashboard },
        tickets: { label: 'Tiket', icon: '🎫', component: Tickets },
        create: { label: 'Buat Tiket', icon: '➕', component: CreateTicket },
        agents: { label: 'Agen', icon: '👤', component: Agents },
        monitoring: { label: 'Ring Monitor', icon: '🔗', component: RingMonitor },
        notifications: { label: 'Notifikasi', icon: '🔔', component: Notifications }
    };

    const showToast = (message, type = 'info') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    const ActiveComponent = pages[activePage].component;

    return (
        <div className="app-container">
            <aside className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
                <div className="sidebar-header">
                    <div className="logo">
                        <span className="logo-icon">🎫</span>
                        <span className="logo-text">Helpdesk</span>
                    </div>
                    <span className="logo-subtitle">Distributed System</span>
                </div>
                <nav className="sidebar-nav">
                    {Object.entries(pages).map(([key, { label, icon }]) => (
                        <a 
                            key={key} 
                            href={`#${key}`}
                            className={`nav-item ${activePage === key ? 'active' : ''}`}
                            onClick={(e) => { e.preventDefault(); setActivePage(key); setSidebarOpen(false); }}
                        >
                            <span className="nav-icon">{icon}</span>
                            <span className="nav-label">{label}</span>
                        </a>
                    ))}
                </nav>
            </aside>

            <main className="main-content">
                <header className="topbar">
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                        <button className="menu-toggle" onClick={() => setSidebarOpen(!isSidebarOpen)}>☰</button>
                        <h1 className="page-title">{pages[activePage].label}</h1>
                    </div>
                    <div className="topbar-actions">
                        <button className="icon-btn" onClick={toggleTheme} title="Toggle Dark/Light Mode">
                            {theme === 'light' ? '🌙' : '☀️'}
                        </button>
                    </div>
                </header>
                <div className="page-container">
                    <ActiveComponent 
                        showToast={showToast} 
                        onViewTicket={(id, edit = false) => setSelectedTicket({ id, edit })} 
                    />
                </div>
            </main>

            {selectedTicket && (
                <TicketDetailModal
                    ticketId={selectedTicket.id}
                    initialEditMode={selectedTicket.edit}
                    onClose={() => setSelectedTicket(null)}
                    showToast={showToast}
                />
            )}

            {toast && (
                <div className="toast-container">
                    <div className={`toast ${toast.type}`}>
                        {toast.message}
                    </div>
                </div>
            )}
        </div>
    );
}
