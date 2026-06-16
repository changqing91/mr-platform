import { getAccessToken, login as oidcLogin, logout as oidcLogout, userManager } from './auth';

const API_URL = '/api';

const buildHeaders = async (extra = {}) => {
    const token = await getAccessToken();
    const headers = { 'Content-Type': 'application/json', ...extra };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
};

const buildHeadersNoBody = async () => {
    const token = await getAccessToken();
    const headers = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
};

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

const handle401 = async () => {
    // Token may be revoked or expired; try silent refresh, fall back to redirect.
    try {
        await userManager.signinSilent();
    } catch (_) {
        oidcLogin();
    }
};

const unwrap = async (response) => {
    if (response.status === 401) {
        await handle401();
        throw new Error('UNAUTHENTICATED');
    }
    if (!response.ok) {
        let msg = 'API Error';
        try {
            const j = await response.json();
            msg = j.error?.message || j.message || msg;
        } catch (_) { /* ignore */ }
        throw new Error(msg);
    }
    if (response.status === 204) return null;
    const json = await response.json();
    return normalize(json.data || json);
};

const unwrapPaginated = async (response) => {
    if (response.status === 401) {
        await handle401();
        throw new Error('UNAUTHENTICATED');
    }
    if (!response.ok) {
        let msg = 'API Error';
        try {
            const j = await response.json();
            msg = j.error?.message || j.message || msg;
        } catch (_) { /* ignore */ }
        throw new Error(msg);
    }
    const json = await response.json();
    return {
        data: normalize(json.data || []),
        pagination: json.meta?.pagination || { page: 1, pageSize: 20, pageCount: 1, total: 0 },
    };
};

const get = async (path) => {
    const res = await fetch(`${API_URL}${path}`, { headers: await buildHeaders() });
    return unwrap(res);
};

const send = async (method, path, body) => {
    const res = await fetch(`${API_URL}${path}`, {
        method,
        headers: await buildHeaders(),
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    return unwrap(res);
};

export const api = {
    auth: {
        login: oidcLogin,
        logout: oidcLogout,
        me: () => get('/me'),
    },
    appUsers: {
        list:           ()                        => get('/app-users'),
        create:         (data)                    => send('POST',   '/app-users', data),
        update:         (id, data)                => send('PUT',    `/app-users/${id}`, data),
        delete:         (id)                      => send('DELETE', `/app-users/${id}`),
        resetPassword:  (id, password, temporary) => send('PUT',    `/app-users/${id}/password`, { password, temporary }),
    },
    appRoles: {
        list:    ()         => get('/app-roles'),
        create:  (data)     => send('POST',   '/app-roles', data),
        update:  (id, data) => send('PUT',    `/app-roles/${id}`, data),
        delete:  (id)       => send('DELETE', `/app-roles/${id}`),
    },
    projectGroups: {
        list:    async () => {
            const res = await fetch(`${API_URL}/project-groups`, { headers: await buildHeaders() });
            if (res.status === 401) { await handle401(); throw new Error('UNAUTHENTICATED'); }
            if (!res.ok) throw new Error('Failed to load project groups');
            const json = await res.json();
            return { data: normalize(json.data || []), meta: json.meta || {} };
        },
        create:  (data)     => send('POST',   '/project-groups', data),
        update:  (id, data) => send('PUT',    `/project-groups/${id}`, data),
        delete:  (id)       => send('DELETE', `/project-groups/${id}`),
    },
    projects: {
        list: async (page = 1, pageSize = 20, groupDocId = null) => {
            const params = new URLSearchParams({ sort: 'createdAt:desc', 'pagination[page]': page, 'pagination[pageSize]': pageSize });
            if (groupDocId) params.set('filters[projectGroup]', groupDocId);
            const res = await fetch(`${API_URL}/projects?${params}`, { headers: await buildHeaders() });
            return unwrapPaginated(res);
        },
        create: (data)            => send('POST',   '/projects', { data }),
        update: (documentId, data) => send('PUT',    `/projects/${documentId}`, { data }),
        delete: (documentId)      => send('DELETE', `/projects/${documentId}`),
    },
    machines: {
        list:   ()                 => get('/machines?sort=createdAt:asc'),
        create: (data)             => send('POST',   '/machines', { data }),
        update: (documentId, data) => send('PUT',    `/machines/${documentId}`, { data }),
        delete: (documentId)       => send('DELETE', `/machines/${documentId}`),
    },
    processes: {
        list: () => get('/processes'),
        create: (data)             => send('POST', '/processes', { data }),
        update: (documentId, data) => send('PUT',  `/processes/${documentId}`, { data }),
        launch:    (machineId, projectId) => send('POST', '/processes/launch',    { machineId, projectId }),
        kill:      (machineId)            => send('POST', '/processes/kill',      { machineId }),
        killAll:   ()                     => send('POST', '/processes/kill-all'),
        batchKill: (machineIds)           => send('POST', '/processes/batch-kill', { machineIds }),
        executePython:    (ip, port, code) => send('POST', '/processes/execute-python', { ip, port, code }),
        getScriptConfig:  ()              => get('/processes/script-config'),
        saveScriptConfig: (config)        => send('PUT',  '/processes/script-config', config),
    },
    upload: async (file) => {
        const formData = new FormData();
        formData.append('files', file);
        const res = await fetch(`${API_URL}/upload`, {
            method: 'POST',
            headers: await buildHeadersNoBody(),
            body: formData,
        });
        if (res.status === 401) {
            await handle401();
            throw new Error('UNAUTHENTICATED');
        }
        if (!res.ok) {
            let msg = 'Upload Failed';
            try { const j = await res.json(); msg = j.error?.message || msg; } catch (_) { /* ignore */ }
            throw new Error(msg);
        }
        return res.json();
    },
};
