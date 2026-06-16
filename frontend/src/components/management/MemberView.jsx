import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit3, Lock, RefreshCw, Search, Shield } from 'lucide-react';
import { THEME_COLOR } from '../../constants';
import { api } from '../../services/api';
import CreateUserModal from './CreateUserModal';
import EditUserModal from './EditUserModal';
import ResetPasswordModal from './ResetPasswordModal';

const MemberView = ({ addNotification, currentUser }) => {
    const [users, setUsers] = useState([]);
    const [roles, setRoles] = useState([]);
    const [groups, setGroups] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    const [showCreate, setShowCreate] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [pwdUser, setPwdUser] = useState(null);

    const reload = async () => {
        setLoading(true);
        try {
            const [u, r, g] = await Promise.all([
                api.appUsers.list(),
                api.appRoles.list(),
                api.projectGroups.list(),
            ]);
            setUsers(Array.isArray(u) ? u : []);
            setRoles(Array.isArray(r) ? r : []);
            setGroups(Array.isArray(g) ? g : []);
        } catch (e) {
            addNotification('加载失败：' + e.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { reload(); }, []);

    const filtered = users.filter((u) =>
        (u.username || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (u.displayName || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (u.email || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleDelete = async (user) => {
        if (currentUser?.appUser?.id === user.id) {
            addNotification('不能删除自己', 'error');
            return;
        }
        if (!window.confirm(`确定删除用户 ${user.username}？该操作会同时从 Keycloak 中移除账号。`)) return;
        try {
            await api.appUsers.delete(user.id);
            addNotification('删除成功', 'success');
            reload();
        } catch (e) {
            addNotification('删除失败：' + e.message, 'error');
        }
    };

    return (
        <div className="h-full flex flex-col">
            <div className="px-5 py-3 border-b border-gray-50 flex items-center gap-2 shrink-0">
                <div className="relative flex-1">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="搜索姓名 / 账号 / 邮箱"
                        className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                    />
                </div>
                <button onClick={reload} className="p-2 text-gray-400 hover:bg-gray-100 rounded-xl" title="刷新">
                    <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                </button>
                <button
                    onClick={() => setShowCreate(true)}
                    className="px-3 py-2 rounded-xl text-white text-sm font-bold flex items-center gap-1"
                    style={{ backgroundColor: THEME_COLOR }}
                >
                    <Plus size={14} /> 新建成员
                </button>
            </div>

            <div className="flex-1 overflow-auto px-5 py-3">
                {loading ? (
                    <div className="text-center text-gray-400 py-10">加载中...</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                                <th className="py-2 px-2 font-medium">用户信息</th>
                                <th className="py-2 px-2 font-medium">角色</th>
                                <th className="py-2 px-2 font-medium">所属项目组</th>
                                <th className="py-2 px-2 font-medium text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {filtered.map((u) => (
                                <tr key={u.id} className="hover:bg-gray-50/50">
                                    <td className="py-3 px-2">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-700 text-xs font-bold">
                                                {(u.displayName || u.username || '?').charAt(0).toUpperCase()}
                                            </div>
                                            <div>
                                                <div className="font-medium text-gray-800">{u.displayName || u.username}</div>
                                                <div className="text-xs text-gray-400">@{u.username}{u.email ? ` · ${u.email}` : ''}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="py-3 px-2">
                                        {u.appRole?.name ? (
                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] bg-gray-50 border-gray-200 text-gray-700">
                                                {u.appRole.name}
                                                {u.appRole.canManage && <Shield size={10} style={{ color: THEME_COLOR }} />}
                                            </span>
                                        ) : (
                                            <span className="text-gray-400 text-xs">未分配</span>
                                        )}
                                    </td>
                                    <td className="py-3 px-2">
                                        <div className="flex flex-wrap gap-1">
                                            {(u.projectGroups || []).map((g) => (
                                                <span key={g.id} className="text-[10px] bg-gray-100 border border-gray-200 px-1.5 py-0.5 rounded">{g.name}</span>
                                            ))}
                                            {(!u.projectGroups || u.projectGroups.length === 0) && (
                                                <span className="text-xs text-gray-400">-</span>
                                            )}
                                        </div>
                                    </td>
                                    <td className="py-3 px-2 text-right whitespace-nowrap">
                                        <button onClick={() => setEditingUser(u)} className="text-blue-500 hover:text-blue-600 mr-3 text-xs">
                                            <Edit3 size={13} className="inline mr-1" />编辑
                                        </button>
                                        <button onClick={() => setPwdUser(u)} className="text-gray-500 hover:text-gray-700 mr-3 text-xs">
                                            <Lock size={13} className="inline mr-1" />重置密码
                                        </button>
                                        <button onClick={() => handleDelete(u)} className="text-red-500 hover:text-red-600 text-xs">
                                            <Trash2 size={13} className="inline mr-1" />删除
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {filtered.length === 0 && (
                                <tr>
                                    <td colSpan={4} className="text-center text-gray-400 py-10">无匹配的成员</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>

            {showCreate && (
                <CreateUserModal
                    roles={roles}
                    groups={groups}
                    onClose={() => setShowCreate(false)}
                    onCreated={() => { setShowCreate(false); reload(); }}
                    addNotification={addNotification}
                />
            )}
            {editingUser && (
                <EditUserModal
                    user={editingUser}
                    roles={roles}
                    groups={groups}
                    onClose={() => setEditingUser(null)}
                    onSaved={() => { setEditingUser(null); reload(); }}
                    addNotification={addNotification}
                />
            )}
            {pwdUser && (
                <ResetPasswordModal
                    user={pwdUser}
                    onClose={() => setPwdUser(null)}
                    addNotification={addNotification}
                />
            )}
        </div>
    );
};

export default MemberView;
