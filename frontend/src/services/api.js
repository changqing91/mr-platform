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
                const msg = error.error?.message || '';
                // Translate common Strapi auth error messages to Chinese
                if (msg.toLowerCase().includes('identifier') || msg.toLowerCase().includes('password') || msg.toLowerCase().includes('invalid')) {
                    throw new Error('账号或密码错误');
                }
                if (msg.toLowerCase().includes('blocked')) {
                    throw new Error('账户已被锁定，请联系管理员');
                }
                if (msg.toLowerCase().includes('confirmed')) {
                    throw new Error('账户尚未激活');
                }
                throw new Error(msg || '登录失败');
            }
            return res.json();
        },
        register: async (username, email, password) => {
            const res = await fetch(`${API_URL}/auth/local/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });
            if (!res.ok) {
                const error = await res.json();
                const msg = error.error?.message || '';
                if (msg.toLowerCase().includes('already taken') || msg.toLowerCase().includes('unique')) {
                    throw new Error('用户名或邮箱已被注册');
                }
                if (msg.toLowerCase().includes('email')) {
                    throw new Error('邮箱格式无效');
                }
                throw new Error(msg || '注册失败');
            }
            return res.json();
        }
    },
    userAdmin: {
        listUsers: async () => {
            const res = await fetch(`${API_URL}/user-admin/users`, {
                headers: getAuthHeaders()
            });
            return unwrap(res);
        },
        changePassword: async (userId, password) => {
            const res = await fetch(`${API_URL}/user-admin/users/${userId}/password`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ password })
            });
            return unwrap(res);
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
        update: async (documentId, data) => {
            const res = await fetch(`${API_URL}/machines/${documentId}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ data })
            });
            return unwrap(res);
        },
        delete: async (documentId) => {
            const res = await fetch(`${API_URL}/machines/${documentId}`, {
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
        create: async (data) => {
            const res = await fetch(`${API_URL}/processes`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ data })
            });
            return unwrap(res);
        },
        update: async (documentId, data) => {
            const res = await fetch(`${API_URL}/processes/${documentId}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ data })
            });
            return unwrap(res);
        },
        // Custom endpoints
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
            return res.json();
        },
        killAll: async () => {
            const res = await fetch(`${API_URL}/processes/kill-all`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            return res.json();
        },
        batchKill: async (machineIds) => {
            const res = await fetch(`${API_URL}/processes/batch-kill`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ machineIds })
            });
            return res.json();
        },
        executePython: async (ip, port, code) => {
            const res = await fetch(`${API_URL}/processes/execute-python`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ ip, port, code })
            });
            return unwrap(res);
        }
    },
    upload: async (file) => {
        const formData = new FormData();
        formData.append('files', file);

        const token = localStorage.getItem('jwt');
        const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

        const res = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            headers: headers,
            body: formData
        });

        if (!res.ok) {
            const error = await res.json();
            throw new Error(error.error?.message || 'Upload Failed');
        }
        return res.json();
    }
};
