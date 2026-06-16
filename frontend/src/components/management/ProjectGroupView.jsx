import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit3, RefreshCw, Check, X, AlertTriangle, FolderKanban } from 'lucide-react';
import { THEME_COLOR } from '../../constants';
import { api } from '../../services/api';

const ProjectGroupView = ({ addNotification }) => {
    const [groups, setGroups] = useState([]);
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);

    const [newName, setNewName] = useState('');
    const [editingId, setEditingId] = useState(null);
    const [editingName, setEditingName] = useState('');
    const [error, setError] = useState(null);

    const [memberPickerGroup, setMemberPickerGroup] = useState(null);

    const reload = async () => {
        setLoading(true);
        try {
            const [g, u] = await Promise.all([api.projectGroups.list(), api.appUsers.list()]);
            setGroups(Array.isArray(g) ? g : []);
            setUsers(Array.isArray(u) ? u : []);
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
            await api.projectGroups.create({ name: newName.trim() });
            setNewName('');
            reload();
            addNotification('项目组已创建', 'success');
        } catch (e) {
            setError(e.message || '创建失败');
        }
    };

    const handleSaveName = async (group) => {
        if (!editingName.trim()) return;
        try {
            await api.projectGroups.update(group.id, { name: editingName.trim() });
            setEditingId(null);
            reload();
        } catch (e) {
            addNotification('保存失败：' + e.message, 'error');
        }
    };

    const handleDelete = async (group) => {
        if (!window.confirm(`确认删除项目组 "${group.name}"？`)) return;
        try {
            await api.projectGroups.delete(group.id);
            addNotification('已删除', 'success');
            reload();
        } catch (e) {
            addNotification(e.message || '删除失败', 'error');
        }
    };

    return (
        <div className="h-full flex flex-col">
            <div className="px-5 py-3 border-b border-gray-50 shrink-0">
                <form className="flex gap-2" onSubmit={handleAdd}>
                    <input
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        placeholder="新项目组名称"
                        className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                    />
                    <button
                        type="submit"
                        className="px-3 py-2 rounded-xl text-white text-sm font-bold flex items-center gap-1"
                        style={{ backgroundColor: THEME_COLOR }}
                    >
                        <Plus size={14} /> 新建
                    </button>
                    <button type="button" onClick={reload} className="p-2 text-gray-400 hover:bg-gray-100 rounded-xl" title="刷新">
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
                ) : groups.length === 0 ? (
                    <div className="flex flex-col items-center text-gray-400 py-10">
                        <FolderKanban size={32} className="mb-2 text-gray-300" />
                        <div className="text-sm">暂无项目组</div>
                    </div>
                ) : (
                    <div className="space-y-2">
                        {groups.map((g) => {
                            const memberCount = (g.users || []).length;
                            return (
                                <div key={g.id} className="border border-gray-100 rounded-xl p-3 hover:border-gray-200 transition-colors">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="flex-1 flex items-center gap-2">
                                            {editingId === g.id ? (
                                                <>
                                                    <input
                                                        value={editingName}
                                                        onChange={(e) => setEditingName(e.target.value)}
                                                        autoFocus
                                                        className="flex-1 px-2 py-1 border border-gray-200 rounded text-sm focus:outline-none focus:border-[#39C5BB]"
                                                        onKeyDown={(e) => e.key === 'Enter' && handleSaveName(g)}
                                                    />
                                                    <button onClick={() => handleSaveName(g)} className="text-green-500 p-1 hover:bg-green-50 rounded">
                                                        <Check size={14} />
                                                    </button>
                                                    <button onClick={() => setEditingId(null)} className="text-gray-400 p-1 hover:bg-gray-100 rounded">
                                                        <X size={14} />
                                                    </button>
                                                </>
                                            ) : (
                                                <>
                                                    <div className="font-bold text-gray-800 text-sm">{g.name}</div>
                                                    <span className="text-xs text-gray-400">
                                                        · {memberCount} 名成员 · {g.projectCount ?? 0} 个项目
                                                    </span>
                                                </>
                                            )}
                                        </div>
                                        {editingId !== g.id && (
                                            <div className="flex gap-1">
                                                <button
                                                    onClick={() => setMemberPickerGroup(g)}
                                                    className="text-xs px-2 py-1 rounded text-gray-600 hover:bg-gray-100"
                                                >
                                                    成员
                                                </button>
                                                <button
                                                    onClick={() => { setEditingId(g.id); setEditingName(g.name); }}
                                                    className="text-blue-500 hover:text-blue-600 p-1.5 rounded hover:bg-blue-50"
                                                >
                                                    <Edit3 size={14} />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(g)}
                                                    className="text-red-500 hover:text-red-600 p-1.5 rounded hover:bg-red-50"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                    {(g.users || []).length > 0 && editingId !== g.id && (
                                        <div className="flex flex-wrap gap-1 mt-2">
                                            {(g.users || []).map((u) => (
                                                <span key={u.id} className="text-[10px] bg-gray-100 border border-gray-200 px-1.5 py-0.5 rounded">
                                                    {u.displayName || u.username}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {memberPickerGroup && (
                <GroupMemberPicker
                    group={memberPickerGroup}
                    allUsers={users}
                    onClose={() => setMemberPickerGroup(null)}
                    onSaved={() => { setMemberPickerGroup(null); reload(); }}
                    addNotification={addNotification}
                />
            )}
        </div>
    );
};

const GroupMemberPicker = ({ group, allUsers, onClose, onSaved, addNotification }) => {
    const [selected, setSelected] = useState(() => new Set((group.users || []).map((u) => u.id)));
    const [saving, setSaving] = useState(false);

    const toggle = (id) => {
        const next = new Set(selected);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        setSelected(next);
    };

    const save = async () => {
        setSaving(true);
        try {
            await api.projectGroups.update(group.id, { users: Array.from(selected) });
            addNotification('项目组成员已更新', 'success');
            onSaved();
        } catch (e) {
            addNotification('保存失败：' + e.message, 'error');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-5 flex flex-col max-h-[80vh]" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-4 shrink-0">
                    <h3 className="font-bold text-gray-800">{group.name} · 成员</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                        <X size={18} />
                    </button>
                </div>
                <div className="flex-1 overflow-auto border border-gray-100 rounded-xl p-2 space-y-1">
                    {allUsers.length === 0 && <div className="text-center text-gray-400 text-sm py-4">暂无可分配的用户</div>}
                    {allUsers.map((u) => (
                        <label key={u.id} className="flex items-center gap-2 hover:bg-gray-50 px-2 py-1.5 rounded cursor-pointer">
                            <input type="checkbox" checked={selected.has(u.id)} onChange={() => toggle(u.id)} />
                            <span className="text-sm text-gray-700">{u.displayName || u.username}</span>
                            <span className="text-xs text-gray-400">@{u.username}</span>
                        </label>
                    ))}
                </div>
                <div className="flex gap-2 mt-4 shrink-0">
                    <button onClick={onClose} className="flex-1 py-2 rounded-xl border border-gray-200 text-sm font-bold text-gray-600 hover:bg-gray-50">
                        取消
                    </button>
                    <button onClick={save} disabled={saving} className="flex-1 py-2 rounded-xl text-white text-sm font-bold disabled:opacity-60" style={{ backgroundColor: THEME_COLOR }}>
                        {saving ? '保存中...' : '保存'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ProjectGroupView;
