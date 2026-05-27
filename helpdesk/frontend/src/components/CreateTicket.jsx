import React, { useState, useRef } from 'react';
import { apiFetch, uploadAttachment } from '../api';

export default function CreateTicket({ showToast }) {
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [priority, setPriority] = useState('MEDIUM');
    const [author, setAuthor] = useState('');
    const [attachmentFile, setAttachmentFile] = useState(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const fileInputRef = useRef(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setResult(null);

        const payload = { title, description, priority, created_by: author };
        const resp = await apiFetch("/api/tickets", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        setLoading(false);
        if (resp.data) {
            const newTicketId = resp.data.ticket_id;
            let uploadSuccess = true;
            let uploadErrorMsg = '';

            // Handle optional file upload
            if (attachmentFile) {
                // Validasi ukuran
                const MAX_SIZE = 5 * 1024 * 1024;
                if (attachmentFile.size > MAX_SIZE) {
                    showToast("Tiket dibuat, tetapi lampiran gagal diunggah: Ukuran melebihi 5 MB", "warning");
                    uploadSuccess = false;
                } else {
                    const formData = new FormData();
                    formData.append('file', attachmentFile);
                    formData.append('uploaded_by', author);
                    
                    const uploadResp = await uploadAttachment(newTicketId, formData);
                    if (uploadResp.error) {
                        uploadSuccess = false;
                        uploadErrorMsg = uploadResp.error.detail || "Gagal mengunggah berkas";
                        showToast(`Tiket dibuat, tetapi gagal mengunggah lampiran: ${uploadErrorMsg}`, "warning");
                    }
                }
            }

            setResult({ 
                success: true, 
                data: resp.data, 
                metrics: resp.metrics,
                uploadStatus: attachmentFile ? (uploadSuccess ? 'success' : 'failed') : 'none'
            });

            if (uploadSuccess || !attachmentFile) {
                showToast("Tiket berhasil dibuat!", "success");
            }
            
            setTitle('');
            setDescription('');
            setAuthor('');
            setAttachmentFile(null);
            if (fileInputRef.current) fileInputRef.current.value = '';
            
        } else {
            setResult({ success: false, error: resp.error || "Gagal membuat tiket" });
            showToast("Gagal membuat tiket", "error");
        }
    };

    return (
        <div className="page active">
            <div className="card form-card">
                <div className="card-header">
                    <h2>📝 Buat Tiket Baru</h2>
                </div>
                <div className="card-body">
                    <form onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label>Judul Tiket</label>
                            <input type="text" className="form-input" required 
                                value={title} onChange={e => setTitle(e.target.value)}
                                placeholder="Contoh: Tidak bisa login ke sistem" />
                        </div>
                        <div className="form-group">
                            <label>Deskripsi</label>
                            <textarea className="form-input form-textarea" rows="4"
                                value={description} onChange={e => setDescription(e.target.value)}
                                placeholder="Jelaskan masalah secara detail..."></textarea>
                        </div>
                        <div className="form-row">
                            <div className="form-group">
                                <label>Prioritas</label>
                                <select className="form-input" value={priority} onChange={e => setPriority(e.target.value)}>
                                    <option value="LOW">Low</option>
                                    <option value="MEDIUM">Medium</option>
                                    <option value="HIGH">High</option>
                                    <option value="CRITICAL">Critical</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Nama Pelapor</label>
                                <input type="text" className="form-input" required
                                    value={author} onChange={e => setAuthor(e.target.value)}
                                    placeholder="Nama Anda" />
                            </div>
                        </div>
                        <div className="form-group" style={{ marginTop: '16px', marginBottom: '24px' }}>
                            <label>Lampiran Opsional (Maks. 5 MB)</label>
                            <input type="file" className="form-input" 
                                ref={fileInputRef}
                                onChange={e => setAttachmentFile(e.target.files[0] || null)}
                                style={{ padding: '8px 10px', backgroundColor: 'var(--bg-secondary)' }}
                            />
                        </div>
                        <button type="submit" className="btn btn-primary" disabled={loading}>
                            {loading ? "⏳ Mengirim..." : "🚀 Kirim Tiket"}
                        </button>
                    </form>
                    
                    {result && result.success && (
                        <div className="form-result success" style={{ display: 'block' }}>
                            ✅ Tiket berhasil dibuat!<br/>
                            <strong>ID:</strong> {result.data.ticket_id}<br/>
                            <strong>Diproses oleh:</strong> Node {result.data.processed_by_node}<br/>
                            {result.metrics && <span><strong>Routing:</strong> {result.metrics.routed_via} ({result.metrics.end_to_end_ms}ms)</span>}<br/>
                            {result.uploadStatus === 'success' && <span style={{ color: 'var(--color-primary)' }}>📎 Lampiran berhasil diunggah</span>}
                            {result.uploadStatus === 'failed' && <span style={{ color: 'var(--color-warning)' }}>⚠️ Tiket dibuat, namun lampiran gagal diunggah</span>}
                        </div>
                    )}
                    {result && !result.success && (
                        <div className="form-result error" style={{ display: 'block' }}>
                            ❌ {JSON.stringify(result.error)}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
