import React, { useState, useEffect } from 'react';
import { X, Search } from 'lucide-react';
import { api } from '../services/api';
import { THEME_COLOR } from '../constants';

const MeetingParticipantModal = ({ onClose, onAdded, addNotification }) => {
    const [users, setUsers] = useState([]);
    const [headsets, setHeadsets] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedUserId, setSelectedUserId] = useState(null);
    const [selectedHeadsetId, setSelectedHeadsetId] = useState(null);

    useEffect(() => {
        Promise.all([api.meetings.visibleUsers(), api.vrHeadsets.list()])
            .then(([usersData, headsetsData]) => {
                setUsers(Array.isArray(usersData) ? usersData : []);
                setHeadsets(
                    (Array.isArray(headsetsData) ? headsetsData : []).filter(
                        (h) => h.status === 'idle' && h.machine
                    )
                );
            })
            .catch((err) => {
                addNotification?.('加载失败: ' + (err.message || '未知错误'), 'error');
            })
            .finally(() => setLoading(false));
    }, []);

    const filteredUsers = users.filter((u) => {
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        return (
            (u.displayName || '').toLowerCase().includes(q) ||
            (u.username || '').toLowerCase().includes(q)
        );
    });

    const handleAdd = () => {
        if (!selectedUserId || !selectedHeadsetId) return;
        onAdded(selectedUserId, selectedHeadsetId);
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col">
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                    <h2 className="text-lg font-bold text-gray-800">添加参会者</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {loading ? (
                    <div className="flex-1 flex items-center justify-center py-12 text-gray-400 text-sm">
                        加载中...
                    </div>
                ) : (
                    <div className="flex-1 overflow-hidden flex gap-4 p-6">
                        <div className="flex-1 flex flex-col min-w-0">
                            <h3 className="text-sm font-semibold text-gray-600 mb-2">选择用户</h3>
                            <div className="relative mb-3">
                                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="搜索用户..."
                                    className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                                />
                            </div>
                            <div className="flex-1 overflow-y-auto space-y-1">
                                {filteredUsers.map((u) => {
                                    const isSelected = selectedUserId === u.id;
                                    return (
                                        <div
                                            key={u.id}
                                            onClick={() => setSelectedUserId(u.id)}
                                            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
                                                isSelected ? 'text-white' : 'hover:bg-gray-50'
                                            }`}
                                            style={isSelected ? { backgroundColor: THEME_COLOR } : undefined}
                                        >
                                            <div
                                                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                                                    isSelected ? 'bg-white/20 text-white' : 'bg-gray-200 text-gray-700'
                                                }`}
                                            >
                                                {(u.displayName || u.username || '?')[0].toUpperCase()}
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium truncate">{u.displayName || u.username}</div>
                                                {u.username && u.displayName && (
                                                    <div className={`text-xs truncate ${isSelected ? 'text-white/70' : 'text-gray-400'}`}>
                                                        @{u.username}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                                {filteredUsers.length === 0 && (
                                    <div className="text-center text-gray-400 text-sm py-8">无匹配用户</div>
                                )}
                            </div>
                        </div>

                        <div className="w-px bg-gray-100" />

                        <div className="flex-1 flex flex-col min-w-0">
                            <h3 className="text-sm font-semibold text-gray-600 mb-2">选择头显</h3>
                            <div className="flex-1 overflow-y-auto space-y-1 mt-[52px]">
                                {headsets.map((h) => {
                                    const isSelected = selectedHeadsetId === h.id;
                                    return (
                                        <div
                                            key={h.id}
                                            onClick={() => setSelectedHeadsetId(h.id)}
                                            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
                                                isSelected ? 'text-white' : 'hover:bg-gray-50'
                                            }`}
                                            style={isSelected ? { backgroundColor: THEME_COLOR } : undefined}
                                        >
                                            <div className="min-w-0 flex-1">
                                                <div className="text-sm font-medium truncate">{h.name}</div>
                                                <div className={`text-xs truncate ${isSelected ? 'text-white/70' : 'text-gray-400'}`}>
                                                    {h.type || 'VR'} · {h.machine.ip}:{h.machine.port}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {headsets.length === 0 && (
                                    <div className="text-center text-gray-400 text-sm py-8">无可用头显</div>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                <div className="flex gap-3 px-6 py-4 border-t border-gray-100">
                    <button
                        onClick={onClose}
                        className="flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-medium transition-colors text-sm"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleAdd}
                        disabled={!selectedUserId || !selectedHeadsetId}
                        className="flex-1 py-2 text-white rounded-xl font-medium transition-colors text-sm disabled:opacity-60 disabled:cursor-not-allowed"
                        style={{ backgroundColor: selectedUserId && selectedHeadsetId ? THEME_COLOR : '#9CA3AF' }}
                    >
                        添加参会者
                    </button>
                </div>
            </div>
        </div>
    );
};

export default MeetingParticipantModal;
