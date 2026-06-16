import React, { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { THEME_COLOR } from '../../constants';
import { api } from '../../services/api';

const ResetPasswordModal = ({ user, onClose, addNotification }) => {
    const [form, setForm] = useState({ password: '', confirm: '', temporary: true });
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    const submit = async (e) => {
        e.preventDefault();
        setError(null);
        if (form.password.length < 6) return setError('密码至少 6 位');
        if (form.password !== form.confirm) return setError('两次密码不一致');
        setSaving(true);
        try {
            await api.appUsers.resetPassword(user.id, form.password, form.temporary);
            addNotification('密码已重置', 'success');
            onClose();
        } catch (e) {
            setError(e.message || '重置失败');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <form
                className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-5"
                onClick={(e) => e.stopPropagation()}
                onSubmit={submit}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-gray-800">重置密码 · {user.username}</h3>
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
                    <input
                        type="password"
                        value={form.password}
                        onChange={(e) => setForm({ ...form, password: e.target.value })}
                        placeholder="新密码（至少 6 位）"
                        className={inputCls}
                        autoFocus
                    />
                    <input
                        type="password"
                        value={form.confirm}
                        onChange={(e) => setForm({ ...form, confirm: e.target.value })}
                        placeholder="再次输入新密码"
                        className={inputCls}
                    />
                    <label className="flex items-center gap-2 text-xs text-gray-600">
                        <input
                            type="checkbox"
                            checked={form.temporary}
                            onChange={(e) => setForm({ ...form, temporary: e.target.checked })}
                        />
                        要求该用户下次登录时修改密码
                    </label>
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
                        {saving ? '保存中...' : '确认'}
                    </button>
                </div>
            </form>
        </div>
    );
};

const inputCls = 'w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]';

export default ResetPasswordModal;
