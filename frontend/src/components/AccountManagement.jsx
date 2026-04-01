import React, { useState, useEffect } from 'react';
import { Users, Lock, X, AlertTriangle, CheckCircle, Search, RefreshCw } from 'lucide-react';
import { THEME_COLOR } from '../constants';
import { api } from '../services/api';

const AccountManagement = ({ onClose, addNotification }) => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [changingPasswordFor, setChangingPasswordFor] = useState(null); // userId
    const [passwordForm, setPasswordForm] = useState({ password: '', confirmPassword: '' });
    const [passwordError, setPasswordError] = useState(null);
    const [saving, setSaving] = useState(false);

    const loadUsers = async () => {
        setLoading(true);
        try {
            const data = await api.userAdmin.listUsers();
            setUsers(Array.isArray(data) ? data : []);
        } catch (e) {
            addNotification('加载用户列表失败: ' + (e.message || e), 'error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadUsers();
    }, []);

    const openPasswordModal = (userId) => {
        setChangingPasswordFor(userId);
        setPasswordForm({ password: '', confirmPassword: '' });
        setPasswordError(null);
    };

    const closePasswordModal = () => {
        setChangingPasswordFor(null);
        setPasswordForm({ password: '', confirmPassword: '' });
        setPasswordError(null);
    };

    const handleChangePassword = async (e) => {
        e.preventDefault();
        setPasswordError(null);

        if (passwordForm.password.length < 6) {
            setPasswordError('密码长度至少为6位');
            return;
        }
        if (passwordForm.password !== passwordForm.confirmPassword) {
            setPasswordError('两次输入的密码不一致');
            return;
        }

        setSaving(true);
        try {
            await api.userAdmin.changePassword(changingPasswordFor, passwordForm.password);
            addNotification('密码修改成功', 'success');
            closePasswordModal();
        } catch (e) {
            setPasswordError(e.message || '修改失败，请重试');
        } finally {
            setSaving(false);
        }
    };

    const filteredUsers = users.filter(u =>
        u.username?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.email?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div
                className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-gray-100 shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center text-white" style={{ backgroundColor: THEME_COLOR }}>
                            <Users size={18} />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-gray-800">账户管理</h2>
                            <p className="text-xs text-gray-400">管理所有注册用户</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-400 hover:bg-gray-100 rounded-xl transition-colors"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Search & Refresh */}
                <div className="px-6 py-3 border-b border-gray-50 flex gap-2 shrink-0">
                    <div className="relative flex-1">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <Search size={16} />
                        </div>
                        <input
                            type="text"
                            className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all"
                            placeholder="搜索用户名或邮箱..."
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                        />
                    </div>
                    <button
                        onClick={loadUsers}
                        disabled={loading}
                        className="p-2 text-gray-400 hover:bg-gray-100 rounded-xl transition-colors disabled:opacity-50"
                        title="刷新"
                    >
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>

                {/* User List */}
                <div className="flex-1 overflow-y-auto p-4">
                    {loading ? (
                        <div className="flex items-center justify-center py-16 text-gray-400">
                            <RefreshCw size={20} className="animate-spin mr-2" />
                            加载中...
                        </div>
                    ) : filteredUsers.length === 0 ? (
                        <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
                            {searchQuery ? '未找到匹配的用户' : '暂无注册用户'}
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {filteredUsers.map(user => (
                                <div
                                    key={user.id}
                                    className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100 hover:border-gray-200 transition-all"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-9 h-9 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 font-bold text-sm shrink-0">
                                            {user.username?.charAt(0).toUpperCase()}
                                        </div>
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="font-bold text-gray-800 text-sm">{user.username}</span>
                                                {user.username === 'admin' && (
                                                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md text-white" style={{ backgroundColor: THEME_COLOR }}>
                                                        管理员
                                                    </span>
                                                )}
                                                {user.blocked && (
                                                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-red-100 text-red-600">
                                                        已锁定
                                                    </span>
                                                )}
                                            </div>
                                            <div className="text-xs text-gray-400 mt-0.5">{user.email}</div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => openPasswordModal(user.id)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold text-gray-600 hover:bg-white border border-gray-200 hover:border-gray-300 rounded-lg transition-all"
                                    >
                                        <Lock size={13} />
                                        修改密码
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="px-6 py-3 border-t border-gray-100 text-xs text-gray-400 shrink-0">
                    共 {filteredUsers.length} 个用户{searchQuery && `（过滤自 ${users.length} 个）`}
                </div>
            </div>

            {/* Change Password Modal */}
            {changingPasswordFor !== null && (
                <div className="fixed inset-0 z-60 bg-black/50 flex items-center justify-center p-4" onClick={closePasswordModal}>
                    <div
                        className="bg-white rounded-2xl shadow-2xl w-full max-w-sm"
                        onClick={e => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between p-5 border-b border-gray-100">
                            <div className="flex items-center gap-2 font-bold text-gray-800">
                                <Lock size={18} style={{ color: THEME_COLOR }} />
                                修改密码
                            </div>
                            <button onClick={closePasswordModal} className="text-gray-400 hover:text-gray-600 text-xl font-bold leading-none">×</button>
                        </div>

                        <form onSubmit={handleChangePassword} className="p-5 space-y-4">
                            <div className="text-xs text-gray-500 bg-gray-50 rounded-xl p-3">
                                正在修改用户 <span className="font-bold text-gray-700">
                                    {users.find(u => u.id === changingPasswordFor)?.username}
                                </span> 的密码
                            </div>

                            {passwordError && (
                                <div className="bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm flex items-center gap-2">
                                    <AlertTriangle size={15} />
                                    {passwordError}
                                </div>
                            )}

                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2 ml-1">新密码</label>
                                <div className="relative">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                        <Lock size={16} />
                                    </div>
                                    <input
                                        type="password"
                                        className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all"
                                        placeholder="至少6位"
                                        value={passwordForm.password}
                                        onChange={e => setPasswordForm({ ...passwordForm, password: e.target.value })}
                                        autoFocus
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-bold text-gray-700 mb-2 ml-1">确认新密码</label>
                                <div className="relative">
                                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                        <Lock size={16} />
                                    </div>
                                    <input
                                        type="password"
                                        className="w-full pl-9 pr-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all"
                                        placeholder="再次输入新密码"
                                        value={passwordForm.confirmPassword}
                                        onChange={e => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="flex gap-2 pt-1">
                                <button
                                    type="button"
                                    onClick={closePasswordModal}
                                    className="flex-1 py-2.5 border border-gray-200 text-gray-600 rounded-xl font-bold text-sm hover:bg-gray-50 transition-all"
                                >
                                    取消
                                </button>
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="flex-1 py-2.5 text-white rounded-xl font-bold text-sm hover:opacity-90 transition-all disabled:opacity-60 flex items-center justify-center gap-1.5"
                                    style={{ backgroundColor: THEME_COLOR }}
                                >
                                    {saving ? (
                                        <><RefreshCw size={14} className="animate-spin" /> 保存中...</>
                                    ) : (
                                        <><CheckCircle size={14} /> 确认修改</>
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AccountManagement;
