import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit3, RefreshCw, Check, X, AlertTriangle, Shield, Lock } from 'lucide-react';
import { THEME_COLOR } from '../../constants';
import { api } from '../../services/api';

const RoleView = ({ addNotification }) => {
    const [roles, setRoles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const [newName, setNewName] = useState('');
    const [newCanManage, setNewCanManage] = useState(false);

    const [editingId, setEditingId] = useState(null);
    const [editForm, setEditForm] = useState({ name: '', canManage: false });

    const reload = async () => {
        setLoading(true);
        try {
            const r = await api.appRoles.list();
            setRoles(Array.isArray(r) ? r : []);
        } catch (e) {
            addNotification('加载失败：' + e.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { reload(); }, []);

    const handleAdd = async (e) => {
        e.preventDefault();
        setError(null);
        if (!newName.trim()) return;
        try {
            await api.appRoles.create({ name: newName.trim(), canManage: newCanManage });
            setNewName('');
            setNewCanManage(false);
            reload();
            addNotification('角色已创建', 'success');
        } catch (e) {
            setError(e.message || '创建失败');
        }
    };

    const handleSaveEdit = async (role) => {
        try {
            await api.appRoles.update(role.id, {
                name: editForm.name.trim() || role.name,
                canManage: editForm.canManage,
            });
            setEditingId(null);
            reload();
        } catch (e) {
            addNotification('保存失败：' + e.message, 'error');
        }
    };

    const handleDelete = async (role) => {
        if (role.isSystem) {
            addNotification('系统内置角色不可删除', 'error');
            return;
        }
        if (!window.confirm(`确认删除角色 "${role.name}"？`)) return;
        try {
            await api.appRoles.delete(role.id);
            addNotification('已删除', 'success');
            reload();
        } catch (e) {
            addNotification(e.message || '删除失败', 'error');
        }
    };

    return (
        <div className="h-full flex flex-col">
            <div className="px-5 py-3 border-b border-gray-50 shrink-0">
                <form className="flex gap-2 items-center" onSubmit={handleAdd}>
                    <input
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        placeholder="新角色名称"
                        className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                    />
                    <label className="flex items-center gap-1 text-xs text-gray-600 whitespace-nowrap">
                        <input type="checkbox" checked={newCanManage} onChange={(e) => setNewCanManage(e.target.checked)} />
                        可管理
                    </label>
                    <button type="submit" className="px-3 py-2 rounded-xl text-white text-sm font-bold flex items-center gap-1" style={{ backgroundColor: THEME_COLOR }}>
                        <Plus size={14} /> 新建
                    </button>
                    <button type="button" onClick={reload} className="p-2 text-gray-400 hover:bg-gray-100 rounded-xl">
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                    </button>
                </form>
                {error && (
                    <div className="bg-red-50 text-red-600 px-3 py-2 rounded-lg text-sm flex items-center gap-2 mt-2">
                        <AlertTriangle size={14} /> {error}
                    </div>
                )}
            </div>

            <div className="flex-1 overflow-auto px-5 py-3">
                {loading ? (
                    <div className="text-center text-gray-400 py-10">加载中...</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                                <th className="py-2 px-2 font-medium">角色名称</th>
                                <th className="py-2 px-2 font-medium">权限</th>
                                <th className="py-2 px-2 font-medium">用户数</th>
                                <th className="py-2 px-2 font-medium text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {roles.map((r) => {
                                const isEditing = editingId === r.id;
                                return (
                                    <tr key={r.id} className="hover:bg-gray-50/50">
                                        <td className="py-3 px-2">
                                            {isEditing ? (
                                                <input
                                                    value={editForm.name}
                                                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                                    className="px-2 py-1 border border-gray-200 rounded text-sm focus:outline-none focus:border-[#39C5BB]"
                                                    autoFocus
                                                />
                                            ) : (
                                                <span className="font-medium text-gray-800 inline-flex items-center gap-1.5">
                                                    {r.isSystem && <Lock size={11} className="text-gray-400" />}
                                                    {r.name}
                                                </span>
                                            )}
                                        </td>
                                        <td className="py-3 px-2">
                                            {isEditing && !r.isSystem ? (
                                                <label className="flex items-center gap-1 text-xs">
                                                    <input
                                                        type="checkbox"
                                                        checked={editForm.canManage}
                                                        onChange={(e) => setEditForm({ ...editForm, canManage: e.target.checked })}
                                                    />
                                                    可管理
                                                </label>
                                            ) : r.canManage ? (
                                                <span className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-orange-50 text-orange-600 border border-orange-100">
                                                    <Shield size={10} /> 可管理
                                                </span>
                                            ) : (
                                                <span className="text-xs text-gray-400">普通</span>
                                            )}
                                        </td>
                                        <td className="py-3 px-2 text-gray-500">{r.userCount ?? 0}</td>
                                        <td className="py-3 px-2 text-right whitespace-nowrap">
                                            {isEditing ? (
                                                <>
                                                    <button onClick={() => handleSaveEdit(r)} className="text-green-500 hover:text-green-600 mr-2 text-xs">
                                                        <Check size={13} className="inline mr-1" />保存
                                                    </button>
                                                    <button onClick={() => setEditingId(null)} className="text-gray-400 hover:text-gray-600 text-xs">
                                                        <X size={13} className="inline mr-1" />取消
                                                    </button>
                                                </>
                                            ) : (
                                                <>
                                                    <button
                                                        onClick={() => { setEditingId(r.id); setEditForm({ name: r.name, canManage: r.canManage }); }}
                                                        className="text-blue-500 hover:text-blue-600 mr-3 text-xs"
                                                    >
                                                        <Edit3 size={13} className="inline mr-1" />编辑
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(r)}
                                                        disabled={r.isSystem}
                                                        className="text-red-500 hover:text-red-600 text-xs disabled:opacity-30 disabled:cursor-not-allowed"
                                                        title={r.isSystem ? '系统内置角色不可删除' : ''}
                                                    >
                                                        <Trash2 size={13} className="inline mr-1" />删除
                                                    </button>
                                                </>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                            {roles.length === 0 && (
                                <tr><td colSpan={4} className="text-center text-gray-400 py-10">暂无角色</td></tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};

export default RoleView;
