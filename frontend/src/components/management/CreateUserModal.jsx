import React, { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { THEME_COLOR } from '../../constants';
import { api } from '../../services/api';

const CreateUserModal = ({ roles, groups, onClose, onCreated, addNotification }) => {
    const [form, setForm] = useState({
        username: '',
        email: '',
        password: '',
        displayName: '',
        appRoleId: '',
        projectGroupIds: [],
        temporaryPassword: false,
    });
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    const toggleGroup = (id) => {
        setForm((f) => ({
            ...f,
            projectGroupIds: f.projectGroupIds.includes(id)
                ? f.projectGroupIds.filter((g) => g !== id)
                : [...f.projectGroupIds, id],
        }));
    };

    const submit = async (e) => {
        e.preventDefault();
        setError(null);
        if (!form.username.trim()) return setError('用户名必填');
        if (form.password.length < 6) return setError('初始密码至少 6 位');

        setSaving(true);
        try {
            await api.appUsers.create({
                username: form.username.trim(),
                email: form.email.trim() || null,
                password: form.password,
                displayName: form.displayName.trim() || form.username.trim(),
                appRoleId: form.appRoleId || null,
                projectGroupIds: form.projectGroupIds,
                temporaryPassword: form.temporaryPassword,
            });
            addNotification('成员创建成功', 'success');
            onCreated();
        } catch (e) {
            setError(e.message || '创建失败');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <form
                className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-5"
                onClick={(e) => e.stopPropagation()}
                onSubmit={submit}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-gray-800">新建成员</h3>
                    <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600">
                        <X size={18} />
                    </button>
                </div>

                {error && (
                    <div className="bg-red-50 text-red-600 px-3 py-2 rounded-lg text-sm flex items-center gap-2 mb-3">
                        <AlertTriangle size={14} /> {error}
                    </div>
                )}

                <div className="space-y-3">
                    <Field label="用户名（账号）" required>
                        <input
                            value={form.username}
                            onChange={(e) => setForm({ ...form, username: e.target.value })}
                            className={inputCls}
                            placeholder="如 zhangsan"
                            autoFocus
                        />
                    </Field>
                    <Field label="真实姓名">
                        <input
                            value={form.displayName}
                            onChange={(e) => setForm({ ...form, displayName: e.target.value })}
                            className={inputCls}
                            placeholder="默认与账号相同"
                        />
                    </Field>
                    <Field label="邮箱">
                        <input
                            type="email"
                            value={form.email}
                            onChange={(e) => setForm({ ...form, email: e.target.value })}
                            className={inputCls}
                        />
                    </Field>
                    <Field label="初始密码" required>
                        <input
                            type="password"
                            value={form.password}
                            onChange={(e) => setForm({ ...form, password: e.target.value })}
                            className={inputCls}
                            placeholder="至少 6 位"
                        />
                    </Field>
                    <label className="flex items-center gap-2 text-xs text-gray-600">
                        <input
                            type="checkbox"
                            checked={form.temporaryPassword}
                            onChange={(e) => setForm({ ...form, temporaryPassword: e.target.checked })}
                        />
                        要求用户首次登录时修改密码
                    </label>
                    <Field label="角色">
                        <select
                            value={form.appRoleId}
                            onChange={(e) => setForm({ ...form, appRoleId: e.target.value })}
                            className={inputCls}
                        >
                            <option value="">未分配</option>
                            {roles.map((r) => (
                                <option key={r.id} value={r.id}>
                                    {r.name}{r.canManage ? '（可管理）' : ''}
                                </option>
                            ))}
                        </select>
                    </Field>
                    <Field label={`所属项目组（已选 ${form.projectGroupIds.length}）`}>
                        <div className="border border-gray-200 rounded-lg max-h-32 overflow-auto p-2 space-y-1">
                            {groups.length === 0 && <div className="text-xs text-gray-400 text-center py-2">暂无项目组</div>}
                            {groups.map((g) => (
                                <label key={g.id} className="flex items-center gap-2 text-sm text-gray-700 hover:bg-gray-50 px-2 py-1 rounded cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={form.projectGroupIds.includes(g.id)}
                                        onChange={() => toggleGroup(g.id)}
                                    />
                                    {g.name}
                                </label>
                            ))}
                        </div>
                    </Field>
                </div>

                <div className="flex gap-2 mt-5">
                    <button type="button" onClick={onClose} className="flex-1 py-2 rounded-xl border border-gray-200 text-sm font-bold text-gray-600 hover:bg-gray-50">
                        取消
                    </button>
                    <button
                        type="submit"
                        disabled={saving}
                        className="flex-1 py-2 rounded-xl text-white text-sm font-bold disabled:opacity-60"
                        style={{ backgroundColor: THEME_COLOR }}
                    >
                        {saving ? '创建中...' : '创建'}
                    </button>
                </div>
            </form>
        </div>
    );
};

const Field = ({ label, required, children }) => (
    <div>
        <label className="block text-xs font-bold text-gray-600 mb-1">
            {required && <span className="text-red-500">*</span>} {label}
        </label>
        {children}
    </div>
);

const inputCls = 'w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]';

export default CreateUserModal;
