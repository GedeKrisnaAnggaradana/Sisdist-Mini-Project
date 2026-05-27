import React, { useState, useEffect } from 'react';
import { 
    getTicket, 
    getTicketHistory, 
    getComments, 
    addComment, 
    updateTicket, 
    formatDate,
    uploadAttachment,
    getAttachments,
    getAttachmentDownloadUrl
} from '../api';

export default function TicketDetailModal({ ticketId, initialEditMode = false, onClose, showToast }) {
    const [ticket, setTicket] = useState(null);
    const [history, setHistory] = useState([]);
    const [comments, setComments] = useState([]);
    const [isEditMode, setIsEditMode] = useState(initialEditMode);
    
    // Forms state
    const [editForm, setEditForm] = useState({ title: '', description: '', status: '', priority: '' });
    const [commentForm, setCommentForm] = useState({ commenter: '', comment_text: '' });
    
    // Load state
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isAddingComment, setIsAddingComment] = useState(false);

    // Attachments state
    const [attachments, setAttachments] = useState([]);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadName, setUploadName] = useState('');

    const loadAllData = async () => {
        setIsLoading(true);
        try {
            const [tResp, hResp, cResp, aResp] = await Promise.all([
                getTicket(ticketId),
                getTicketHistory(ticketId),
                getComments(ticketId),
                getAttachments(ticketId)
            ]);

            if (tResp.data) {
                setTicket(tResp.data);
                setEditForm({
                    title: tResp.data.title,
                    description: tResp.data.description,
                    status: tResp.data.status,
                    priority: tResp.data.priority
                });
            }
            if (hResp.data) setHistory(hResp.data);
            if (cResp.data) setComments(cResp.data);
            if (aResp.data) setAttachments(aResp.data);
        } catch (err) {
            console.error("Error loading ticket detail data:", err);
            showToast("Gagal memuat detail tiket", "error");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        if (ticketId) {
            loadAllData();
            setIsEditMode(initialEditMode);
        }
    }, [ticketId, initialEditMode]);

    const handleEditSubmit = async (e) => {
        e.preventDefault();
        setIsSaving(true);
        const resp = await updateTicket(ticketId, editForm);
        setIsSaving(false);

        if (resp.error) {
            showToast(`Gagal mengupdate tiket: ${resp.error.detail || resp.error.code}`, 'error');
        } else {
            showToast('Tiket berhasil diperbarui!', 'success');
            setIsEditMode(false);
            loadAllData(); // Reload to get updated history and metadata
        }
    };

    const handleCommentSubmit = async (e) => {
        e.preventDefault();
        if (!commentForm.commenter.trim() || !commentForm.comment_text.trim()) return;

        setIsAddingComment(true);
        const resp = await addComment(ticketId, commentForm);
        setIsAddingComment(false);

        if (resp.error) {
            showToast(`Gagal mengirim komentar: ${resp.error.detail || resp.error.code}`, 'error');
        } else {
            showToast('Komentar berhasil ditambahkan!', 'success');
            setCommentForm({ ...commentForm, comment_text: '' });
            
            // Reload comments
            const cResp = await getComments(ticketId);
            if (cResp.data) setComments(cResp.data);
        }
    };

    const handleFileUpload = async (e) => {
        e.preventDefault();
        const fileInput = e.target.querySelector('input[type="file"]');
        const file = fileInput?.files?.[0];
        if (!file) return;

        // Validasi ukuran klien (maks 5 MB)
        const MAX_SIZE = 5 * 1024 * 1024;
        if (file.size > MAX_SIZE) {
            showToast('Ukuran file melebihi batas 5 MB', 'error');
            return;
        }

        setIsUploading(true);
        const formData = new FormData();
        formData.append('file', file);
        formData.append('uploaded_by', uploadName.trim() || 'anonymous');

        const resp = await uploadAttachment(ticketId, formData);
        setIsUploading(false);

        if (resp.error) {
            showToast(`Gagal mengunggah: ${resp.error.detail || resp.error.code || resp.error}`, 'error');
        } else {
            showToast('Berkas berhasil diunggah!', 'success');
            fileInput.value = '';
            // Reload attachments
            const aResp = await getAttachments(ticketId);
            if (aResp.data) setAttachments(aResp.data);
        }
    };

    const formatFileSize = (bytes) => {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
    };

    if (isLoading) {
        return (
            <div style={modalOverlayStyle}>
                <div className="card" style={{ width: '400px', padding: '32px', textAlign: 'center', margin: '0' }}>
                    <div style={{ fontSize: '1.25rem', marginBottom: '16px' }}>⏳ Memuat detail tiket...</div>
                    <div className="empty-state" style={{ padding: 0 }}>Silakan tunggu sebentar</div>
                </div>
            </div>
        );
    }

    if (!ticket) {
        return (
            <div style={modalOverlayStyle}>
                <div className="card" style={{ width: '400px', padding: '32px', textAlign: 'center', margin: '0' }}>
                    <div style={{ fontSize: '1.25rem', marginBottom: '16px', color: 'var(--color-warning)' }}>⚠️ Tiket Tidak Ditemukan</div>
                    <button className="btn btn-primary" onClick={onClose}>Tutup</button>
                </div>
            </div>
        );
    }

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
        <div style={modalOverlayStyle}>
            <div className="card" style={modalCardStyle}>
                {/* Header */}
                <div className="card-header" style={{ flexShrink: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <span style={{ fontSize: '1.2rem' }}>🎫</span>
                        <h2 style={{ fontSize: '1.1rem', margin: 0 }}>
                            Tiket: <code>{ticket.ticket_id}</code>
                        </h2>
                        {statusBadge(ticket.status)}
                        {priorityBadge(ticket.priority)}
                    </div>
                    <button className="icon-btn" onClick={onClose} title="Tutup Modal">✖</button>
                </div>

                {/* Body Split layout */}
                <div className="card-body" style={modalBodyStyle}>
                    
                    {/* LEFT COLUMN: Info or Edit */}
                    <div style={leftColStyle}>
                        {isEditMode ? (
                            <div>
                                <h3 style={colHeaderStyle}>✏️ Edit Informasi Tiket</h3>
                                <form onSubmit={handleEditSubmit}>
                                    <div className="form-group">
                                        <label>Judul Tiket</label>
                                        <input 
                                            type="text" 
                                            className="form-input" 
                                            required
                                            value={editForm.title} 
                                            onChange={e => setEditForm({...editForm, title: e.target.value})} 
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label>Deskripsi Masalah</label>
                                        <textarea 
                                            className="form-input" 
                                            rows="5" 
                                            required
                                            value={editForm.description} 
                                            onChange={e => setEditForm({...editForm, description: e.target.value})}
                                        ></textarea>
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>Status</label>
                                            <select 
                                                className="form-input" 
                                                value={editForm.status} 
                                                onChange={e => setEditForm({...editForm, status: e.target.value})}
                                            >
                                                <option value="OPEN">Open</option>
                                                <option value="IN_PROGRESS">In Progress</option>
                                                <option value="RESOLVED">Resolved</option>
                                                <option value="CLOSED">Closed</option>
                                            </select>
                                        </div>
                                        <div className="form-group">
                                            <label>Prioritas</label>
                                            <select 
                                                className="form-input" 
                                                value={editForm.priority} 
                                                onChange={e => setEditForm({...editForm, priority: e.target.value})}
                                            >
                                                <option value="LOW">Low</option>
                                                <option value="MEDIUM">Medium</option>
                                                <option value="HIGH">High</option>
                                                <option value="CRITICAL">Critical</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '24px' }}>
                                        <button 
                                            type="button" 
                                            className="btn" 
                                            onClick={() => setIsEditMode(false)}
                                            disabled={isSaving}
                                        >
                                            Batal
                                        </button>
                                        <button 
                                            type="submit" 
                                            className="btn btn-primary"
                                            disabled={isSaving}
                                        >
                                            {isSaving ? 'Menyimpan...' : 'Simpan Perubahan'}
                                        </button>
                                    </div>
                                </form>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                                <div style={{ flex: '0 0 auto', marginBottom: '20px' }}>
                                    <h1 style={{ fontSize: '1.3rem', fontWeight: '700', marginBottom: '12px', color: 'var(--text-primary)' }}>
                                        {ticket.title}
                                    </h1>
                                    
                                    <div style={{ 
                                        backgroundColor: 'var(--hover-overlay)', 
                                        padding: '14px', 
                                        borderRadius: 'var(--radius)', 
                                        marginBottom: '16px',
                                        fontSize: '0.95rem',
                                        color: 'var(--text-primary)',
                                        whiteSpace: 'pre-wrap',
                                        border: '1px solid var(--border-color)',
                                        lineHeight: '1.5'
                                    }}>
                                        {ticket.description || <span style={{ fontStyle: 'italic', color: '#999' }}>Tidak ada deskripsi</span>}
                                    </div>

                                    {/* Meta grid */}
                                    <div style={metaGridStyle}>
                                        <div style={metaItemStyle}>
                                            <span style={metaLabelStyle}>Dibuat Oleh</span>
                                            <span style={metaValStyle}>👤 {ticket.created_by}</span>
                                        </div>
                                        <div style={metaItemStyle}>
                                            <span style={metaLabelStyle}>Ditugaskan Ke</span>
                                            <span style={metaValStyle}>🛠️ {ticket.assigned_to_name || "Belum Ditugaskan"}</span>
                                        </div>
                                        <div style={metaItemStyle}>
                                            <span style={metaLabelStyle}>Node Pemroses</span>
                                            <span style={metaValStyle}>🖥️ Node {ticket.processed_by_node || "—"}</span>
                                        </div>
                                        <div style={metaItemStyle}>
                                            <span style={metaLabelStyle}>Tanggal Dibuat</span>
                                            <span style={metaValStyle}>📅 {formatDate(ticket.created_at)}</span>
                                        </div>
                                    </div>
                                </div>

                                {/* History Audit Trail */}
                                <div style={{ flex: '1 1 auto', display: 'flex', flexDirection: 'column', minHeight: '150px' }}>
                                    <h4 style={{ fontSize: '0.9rem', marginBottom: '8px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        🕒 Riwayat Perubahan Status (Audit Trail)
                                    </h4>
                                    <div style={historyContainerStyle}>
                                        {history.length > 0 ? (
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                                {history.map((h, idx) => (
                                                    <div key={h.id || idx} style={historyItemStyle}>
                                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                                            <span>
                                                                <strong>{h.changed_by}</strong> mengubah status: {h.old_status ? statusBadge(h.old_status) : <span className="badge badge-low" style={{textTransform:'none'}}>OPEN</span>} ➡️ {statusBadge(h.new_status)}
                                                            </span>
                                                            <span>{formatDate(h.changed_at)}</span>
                                                        </div>
                                                        {h.note && (
                                                            <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginTop: '4px', fontStyle: 'italic' }}>
                                                                ↳ Catatan: "{h.note}"
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        ) : (
                                            <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '16px', fontSize: '0.85rem', fontStyle: 'italic' }}>
                                                Belum ada riwayat perubahan.
                                            </div>
                                        )}
                                    </div>
                                </div>

                                <div style={{ flex: '0 0 auto', display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '16px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                                    <button className="btn" onClick={onClose}>Tutup</button>
                                    <button className="btn btn-primary" onClick={() => setIsEditMode(true)}>✏️ Edit Tiket</button>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* RIGHT COLUMN: Comments */}
                    <div style={rightColStyle}>
                        <h3 style={colHeaderStyle}>💬 Diskusi / Komentar</h3>
                        
                        {/* Comments List */}
                        <div style={commentsContainerStyle}>
                            {comments.length > 0 ? comments.map(c => (
                                <div key={c.comment_id} style={commentItemStyle}>
                                    <div style={commentMetaStyle}>
                                        <strong>👤 {c.commenter}</strong>
                                        <span>{formatDate(c.created_at)}</span>
                                    </div>
                                    <div style={{ color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: '1.4' }}>
                                        {c.comment_text}
                                    </div>
                                </div>
                            )) : (
                                <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '48px 0', fontSize: '0.9rem', fontStyle: 'italic' }}>
                                    Belum ada komentar untuk tiket ini.
                                </div>
                            )}
                        </div>

                        {/* Comment Form */}
                        <form onSubmit={handleCommentSubmit} style={commentFormStyle}>
                            <div className="form-group" style={{ marginBottom: '8px' }}>
                                <input 
                                    type="text" 
                                    className="form-input" 
                                    placeholder="Nama Anda..." 
                                    required
                                    value={commentForm.commenter} 
                                    onChange={e => setCommentForm({...commentForm, commenter: e.target.value})}
                                    style={{ padding: '8px 10px', fontSize: '0.85rem' }}
                                />
                            </div>
                            <div className="form-group" style={{ marginBottom: '8px' }}>
                                <textarea 
                                    className="form-input" 
                                    placeholder="Tulis komentar..." 
                                    rows="2" 
                                    required
                                    value={commentForm.comment_text} 
                                    onChange={e => setCommentForm({...commentForm, comment_text: e.target.value})}
                                    style={{ padding: '8px 10px', fontSize: '0.85rem', resize: 'none' }}
                                ></textarea>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                                <button type="submit" className="btn btn-primary btn-sm" disabled={isAddingComment}>
                                    {isAddingComment ? 'Mengirim...' : '🚀 Kirim Komentar'}
                                </button>
                            </div>
                        </form>

                        {/* Attachments Section */}
                        <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                            <h3 style={colHeaderStyle}>📎 Lampiran</h3>
                            
                            {/* Attachments List */}
                            <div style={{ marginBottom: '12px', maxHeight: '160px', overflowY: 'auto' }}>
                                {attachments.length > 0 ? attachments.map(a => (
                                    <div key={a.attachment_id} style={attachmentItemStyle}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                                            <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>
                                                {a.content_type?.startsWith('image/') ? '🖼️' : 
                                                 a.content_type === 'application/pdf' ? '📄' : '📁'}
                                            </span>
                                            <div style={{ minWidth: 0, flex: 1 }}>
                                                <div style={{ fontWeight: '600', fontSize: '0.85rem', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                    {a.filename}
                                                </div>
                                                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                                    {formatFileSize(a.file_size)} • {a.uploaded_by} • {formatDate(a.created_at)}
                                                </div>
                                            </div>
                                        </div>
                                        <a 
                                            href={getAttachmentDownloadUrl(a.attachment_id)} 
                                            className="btn btn-sm"
                                            style={{ flexShrink: 0, fontSize: '0.75rem', padding: '4px 10px', textDecoration: 'none' }}
                                            download
                                        >
                                            ⬇️ Unduh
                                        </a>
                                    </div>
                                )) : (
                                    <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '16px 0', fontSize: '0.85rem', fontStyle: 'italic' }}>
                                        Belum ada lampiran.
                                    </div>
                                )}
                            </div>

                            {/* Upload Form */}
                            <form onSubmit={handleFileUpload} style={{ 
                                backgroundColor: 'var(--hover-overlay)', 
                                padding: '12px', 
                                borderRadius: 'var(--radius)', 
                                border: '1px solid var(--border-color)' 
                            }}>
                                <div className="form-group" style={{ marginBottom: '8px' }}>
                                    <input 
                                        type="text" 
                                        className="form-input" 
                                        placeholder="Nama pengunggah..." 
                                        value={uploadName} 
                                        onChange={e => setUploadName(e.target.value)}
                                        style={{ padding: '6px 10px', fontSize: '0.85rem' }}
                                    />
                                </div>
                                <div className="form-group" style={{ marginBottom: '8px' }}>
                                    <input 
                                        type="file" 
                                        className="form-input"
                                        required
                                        style={{ padding: '6px 10px', fontSize: '0.85rem' }}
                                    />
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Maks. 5 MB</span>
                                    <button type="submit" className="btn btn-primary btn-sm" disabled={isUploading}>
                                        {isUploading ? 'Mengunggah...' : '📎 Unggah Berkas'}
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
}

// Inline Styles to maintain beautiful UI across pages & theme modes
const modalOverlayStyle = {
    position: 'fixed', 
    top: 0, 
    left: 0, 
    right: 0, 
    bottom: 0, 
    backgroundColor: 'rgba(0,0,0,0.5)', 
    zIndex: 1000,
    display: 'flex', 
    alignItems: 'center', 
    justifyContent: 'center',
    padding: '20px'
};

const modalCardStyle = {
    width: '900px', 
    maxWidth: '100%', 
    margin: '0', 
    height: '80vh', 
    maxHeight: '750px',
    display: 'flex', 
    flexDirection: 'column'
};

const modalBodyStyle = {
    display: 'flex', 
    gap: '24px', 
    overflow: 'hidden', 
    flex: 1, 
    padding: '24px'
};

const leftColStyle = {
    flex: 1.1, 
    paddingRight: '20px', 
    borderRight: '1px solid var(--border-color)',
    display: 'flex',
    flexDirection: 'column',
    overflowY: 'auto',
    height: '100%'
};

const rightColStyle = {
    flex: 0.9, 
    display: 'flex', 
    flexDirection: 'column', 
    height: '100%',
    overflow: 'hidden'
};

const colHeaderStyle = {
    fontSize: '1rem', 
    marginBottom: '16px', 
    color: 'var(--color-primary)',
    fontWeight: '600'
};

const metaGridStyle = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
    backgroundColor: 'var(--hover-overlay)',
    padding: '12px',
    borderRadius: 'var(--radius)',
    border: '1px solid var(--border-color)',
    fontSize: '0.85rem'
};

const metaItemStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px'
};

const metaLabelStyle = {
    color: 'var(--text-secondary)',
    fontSize: '0.75rem',
    textTransform: 'uppercase'
};

const metaValStyle = {
    fontWeight: '600',
    color: 'var(--text-primary)'
};

const historyContainerStyle = {
    flex: 1,
    overflowY: 'auto',
    backgroundColor: 'var(--hover-overlay)',
    border: '1px solid var(--border-color)',
    borderRadius: 'var(--radius)',
    padding: '12px',
    fontSize: '0.85rem',
    maxHeight: '180px'
};

const historyItemStyle = {
    paddingBottom: '8px',
    borderBottom: '1px solid var(--border-color)',
    marginBottom: '4px'
};

const commentsContainerStyle = {
    flex: 1, 
    overflowY: 'auto', 
    marginBottom: '16px', 
    paddingRight: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px'
};

const commentItemStyle = {
    backgroundColor: 'var(--hover-overlay)', 
    padding: '12px', 
    borderRadius: 'var(--radius)', 
    borderLeft: '4px solid var(--color-primary)',
    fontSize: '0.9rem',
    borderTop: '1px solid var(--border-color)',
    borderRight: '1px solid var(--border-color)',
    borderBottom: '1px solid var(--border-color)'
};

const commentMetaStyle = {
    display: 'flex', 
    justifyContent: 'space-between', 
    fontSize: '0.75rem', 
    color: 'var(--text-secondary)', 
    marginBottom: '6px'
};

const commentFormStyle = {
    borderTop: '1px solid var(--border-color)', 
    paddingTop: '16px', 
    flexShrink: 0
};

const attachmentItemStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
    padding: '8px 10px',
    backgroundColor: 'var(--hover-overlay)',
    borderRadius: 'var(--radius)',
    border: '1px solid var(--border-color)',
    marginBottom: '6px',
    fontSize: '0.85rem'
};
