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
