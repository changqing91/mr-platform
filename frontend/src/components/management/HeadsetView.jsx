import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Edit3, RefreshCw, Search } from 'lucide-react';
import { THEME_COLOR } from '../../constants';
import { api } from '../../services/api';
import HeadsetModal from './HeadsetModal';

const STATUS_BADGE = {
    idle: 'bg-green-50 text-green-700 border-green-200',
    'in-use': 'bg-blue-50 text-blue-700 border-blue-200',
    offline: 'bg-gray-50 text-gray-500 border-gray-200',
};

const STATUS_LABEL = {
    idle: '空闲',
    'in-use': '使用中',
    offline: '离线',
};

const HeadsetView = ({ addNotification }) => {
    const [headsets, setHeadsets] = useState([]);
    const [machines, setMachines] = useState([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [editingHeadset, setEditingHeadset] = useState(null);
    const [showCreate, setShowCreate] = useState(false);

    const reload = async () => {
        setLoading(true);
        try {
            const [h, m] = await Promise.all([
                api.vrHeadsets.list(),
                api.machines.list(),
            ]);
            setHeadsets(Array.isArray(h) ? h : []);
            setMachines(Array.isArray(m) ? m : []);
        } catch (e) {
            addNotification('加载失败：' + e.message, 'error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { reload(); }, []);

    const filtered = headsets.filter((hs) =>
        (hs.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (hs.serialNumber || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (hs.type || '').toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleDelete = async (hs) => {
        if (!window.confirm(`确定删除头盔 ${hs.name}？`)) return;
        try {
            await api.vrHeadsets.delete(hs.id);
            addNotification('删除成功', 'success');
            reload();
        } catch (e) {
            addNotification('删除失败：' + e.message, 'error');
        }
    };

    const getBoundMachine = (hs) => {
        if (!hs.machineId) return null;
        return machines.find((m) => m.id === hs.machineId);
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
                        placeholder="搜索名称 / 序列号 / 型号"
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
                    <Plus size={14} /> 新建头盔
                </button>
            </div>

            <div className="flex-1 overflow-auto px-5 py-3">
                {loading ? (
                    <div className="text-center text-gray-400 py-10">加载中...</div>
                ) : (
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                                <th className="py-2 px-2 font-medium">名称</th>
                                <th className="py-2 px-2 font-medium">品牌/型号</th>
                                <th className="py-2 px-2 font-medium">序列号</th>
                                <th className="py-2 px-2 font-medium">状态</th>
                                <th className="py-2 px-2 font-medium">绑定机器</th>
                                <th className="py-2 px-2 font-medium text-right">操作</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-50">
                            {filtered.map((hs) => {
                                const boundMachine = getBoundMachine(hs);
                                return (
                                    <tr key={hs.id} className="hover:bg-gray-50/50">
                                        <td className="py-3 px-2 font-medium text-gray-800">{hs.name || '-'}</td>
                                        <td className="py-3 px-2 text-gray-600">{hs.type || '-'}</td>
                                        <td className="py-3 px-2 text-gray-500 font-mono text-xs">{hs.serialNumber || '-'}</td>
                                        <td className="py-3 px-2">
                                            <span className={`inline-flex px-2 py-0.5 rounded border text-[11px] ${STATUS_BADGE[hs.status] || STATUS_BADGE.offline}`}>
                                                {STATUS_LABEL[hs.status] || hs.status}
                                            </span>
                                        </td>
                                        <td className="py-3 px-2">
                                            {boundMachine ? (
                                                <span className="text-xs text-gray-700">{boundMachine.ip}:{boundMachine.port}</span>
                                            ) : (
                                                <span className="text-xs text-gray-400">未绑定</span>
                                            )}
                                        </td>
                                        <td className="py-3 px-2 text-right whitespace-nowrap">
                                            <button onClick={() => setEditingHeadset(hs)} className="text-blue-500 hover:text-blue-600 mr-3 text-xs">
                                                <Edit3 size={13} className="inline mr-1" />编辑
                                            </button>
                                            {hs.status === 'idle' && (
                                                <button onClick={() => handleDelete(hs)} className="text-red-500 hover:text-red-600 text-xs">
                                                    <Trash2 size={13} className="inline mr-1" />删除
                                                </button>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                            {filtered.length === 0 && (
                                <tr>
                                    <td colSpan={6} className="text-center text-gray-400 py-10">无匹配的头盔</td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>

            {showCreate && (
                <HeadsetModal
                    machines={machines}
                    onClose={() => setShowCreate(false)}
                    onSaved={() => { setShowCreate(false); reload(); }}
                    addNotification={addNotification}
                />
            )}
            {editingHeadset && (
                <HeadsetModal
                    headset={editingHeadset}
                    machines={machines}
                    onClose={() => setEditingHeadset(null)}
                    onSaved={() => { setEditingHeadset(null); reload(); }}
                    addNotification={addNotification}
                />
            )}
        </div>
    );
};

export default HeadsetView;
