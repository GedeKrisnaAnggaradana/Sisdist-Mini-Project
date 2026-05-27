// api.js
// Base URL dikosongkan karena Nginx akan proxy /api ke API Gateway
const API_BASE = "";

export async function apiFetch(url, options = {}) {
    try {
        const resp = await fetch(API_BASE + url, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        return await resp.json();
    } catch (err) {
        console.error(`API Error (${url}):`, err);
        return { error: err.message };
    }
}

export const updateTicket = async (id, payload) => {
    return await apiFetch(`/api/tickets/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload)
    });
};

export const deleteTicket = async (id) => {
    return await apiFetch(`/api/tickets/${id}`, {
        method: 'DELETE'
    });
};

export const formatDate = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleString('id-ID', { 
        year: 'numeric', month: 'short', day: 'numeric', 
        hour: '2-digit', minute:'2-digit', second:'2-digit' 
    });
};

export const getComments = async (ticketId) => {
    return await apiFetch(`/api/tickets/${ticketId}/comments`);
};

export const addComment = async (ticketId, payload) => {
    return await apiFetch(`/api/tickets/${ticketId}/comments`, {
        method: 'POST',
        body: JSON.stringify(payload)
    });
};

export const getTicket = async (id) => {
    return await apiFetch(`/api/tickets/${id}`);
};

export const getTicketHistory = async (id) => {
    return await apiFetch(`/api/tickets/${id}/history`);
};

export const uploadAttachment = async (ticketId, formData) => {
    try {
        const resp = await fetch(`/api/tickets/${ticketId}/attachments`, {
            method: 'POST',
            body: formData,
            // Jangan set Content-Type header — browser akan otomatis set
            // multipart/form-data dengan boundary yang benar
        });
        return await resp.json();
    } catch (err) {
        console.error(`API Error (upload attachment):`, err);
        return { error: err.message };
    }
};

export const getAttachments = async (ticketId) => {
    return await apiFetch(`/api/tickets/${ticketId}/attachments`);
};

export const getAttachmentDownloadUrl = (attachmentId) => {
    return `/api/attachments/${attachmentId}/download`;
};
