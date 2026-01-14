const API_URL = '/api';

const getAuthHeaders = () => {
    const token = localStorage.getItem('jwt');
    return token ? {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    } : {
        'Content-Type': 'application/json'
    };
};

// Helper to handle Strapi's { data: [...] } structure and flattening
const normalize = (data) => {
    if (!data) return null;
    if (Array.isArray(data)) {
        return data.map(item => ({
            id: item.id,
            ...item,
            ...(item.attributes || {})
        }));
    }
    return {
        id: data.id,
        ...(data.attributes || data)
    };
};

const unwrap = async (response) => {
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || 'API Error');
    }
    if (response.status === 204) {
        return null;
    }
    const json = await response.json();
    return normalize(json.data || json); // Login returns { jwt, user }, not { data: ... } sometimes
};

export const api = {
    auth: {
        login: async (identifier, password) => {
            const res = await fetch(`${API_URL}/auth/local`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ identifier, password })
            });
            // Strapi Login response: { jwt: "...", user: { ... } }
            // It doesn't follow { data: ... } wrapper usually
            if (!res.ok) {
                const error = await res.json();
                throw new Error(error.error?.message || 'Login Failed');
            }
            return res.json();
        }
    },
    projects: {
        list: async () => {
            const res = await fetch(`${API_URL}/projects?sort=createdAt:desc&populate=*`, {
                headers: getAuthHeaders()
            });
            return unwrap(res);
        },
        create: async (data) => {
            const res = await fetch(`${API_URL}/projects`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ data })
            });
            return unwrap(res);
        },
        update: async (documentId, data) => {
            const res = await fetch(`${API_URL}/projects/${documentId}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ data })
            });
            return unwrap(res);
        },
        delete: async (documentId) => {
            const res = await fetch(`${API_URL}/projects/${documentId}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            return unwrap(res);
        }
    },
    machines: {
        list: async () => {
            const res = await fetch(`${API_URL}/machines?sort=createdAt:asc`, {
                headers: getAuthHeaders()
            });
            return unwrap(res);
        },
        create: async (data) => {
            const res = await fetch(`${API_URL}/machines`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ data })
            });
            return unwrap(res);
        },
        update: async (id, data) => {
            const res = await fetch(`${API_URL}/machines/${id}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ data })
            });
            return unwrap(res);
        },
        delete: async (id) => {
            const res = await fetch(`${API_URL}/machines/${id}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            return unwrap(res);
        }
    },
    processes: {
        list: async () => {
            const res = await fetch(`${API_URL}/processes?populate=*`, {
                headers: getAuthHeaders()
            });
            return unwrap(res);
        },
        launch: async (machineId, projectId) => {
            const res = await fetch(`${API_URL}/processes/launch`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ machineId, projectId })
            });
            return unwrap(res);
        },
        kill: async (machineId) => {
            const res = await fetch(`${API_URL}/processes/kill`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ machineId })
            });
            return unwrap(res);
        },
        batchKill: async (machineIds) => {
            const res = await fetch(`${API_URL}/processes/batch-kill`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ machineIds })
            });
            return unwrap(res);
        },
        killAll: async () => {
            const res = await fetch(`${API_URL}/processes/kill-all`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            return unwrap(res);
        },
        executePython: async (ip, port, code) => {
            const res = await fetch(`${API_URL}/processes/execute-python`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ ip, port, code })
            });
            return unwrap(res);
        }
    }
};
