import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    X, Users, Plus, PhoneOff, Link2, Unlink,
    Mic, MicOff, Monitor, Glasses
} from 'lucide-react';
import { api } from '../services/api';
import { THEME_COLOR } from '../constants';
import MeetingParticipantModal from './MeetingParticipantModal';

const INPUT_CLS =
    'w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]';

const MeetingPanel = ({ onClose, addNotification, currentUser }) => {
    const [activeMeeting, setActiveMeeting] = useState(null);
    const [projects, setProjects] = useState([]);
    const [machines, setMachines] = useState([]);
    const [title, setTitle] = useState('');
    const [projectId, setProjectId] = useState('');
    const [hostMachineId, setHostMachineId] = useState('');
    const [creating, setCreating] = useState(false);
    const [showAddParticipant, setShowAddParticipant] = useState(false);
    const [ending, setEnding] = useState(false);
    const pollRef = useRef(null);

    const currentUserId = currentUser?.appUser?.id;
    const isHost = activeMeeting?.host?.id === currentUserId;
    const isManager = currentUser?.isManager;

    const refreshMeeting = useCallback(async () => {
        if (!activeMeeting?.id) return;
        try {
            const data = await api.meetings.findOne(activeMeeting.id);
            if (data && data.status !== 'ended') {
                setActiveMeeting(data);
            } else {
                setActiveMeeting(null);
                clearInterval(pollRef.current);
            }
        } catch {
            clearInterval(pollRef.current);
        }
    }, [activeMeeting?.id]);

    useEffect(() => {
        if (activeMeeting?.id) {
            pollRef.current = setInterval(refreshMeeting, 5000);
            return () => clearInterval(pollRef.current);
        }
    }, [activeMeeting?.id, refreshMeeting]);

    useEffect(() => {
        Promise.all([
            api.projects.list(1, 100),
            api.machines.list(),
            api.meetings.findActive(),
        ])
            .then(([projRes, machinesData, activeData]) => {
                setProjects(projRes?.data || []);
                setMachines(
                    (Array.isArray(machinesData) ? machinesData : []).filter(
                        (m) => m.status === 'idle'
                    )
                );
                if (activeData && activeData.status !== 'ended') {
                    setActiveMeeting(activeData);
                }
            })
            .catch((err) => {
                addNotification('加载数据失败: ' + err.message, 'error');
            });
    }, []);

    const handleCreate = async () => {
        if (!title.trim() || !projectId || !hostMachineId) {
            addNotification('请填写完整信息', 'error');
            return;
        }
        setCreating(true);
        try {
            const meeting = await api.meetings.create({
                title: title.trim(),
                projectId,
                hostMachineId,
            });
            setActiveMeeting(meeting);
            setTitle('');
            setProjectId('');
            setHostMachineId('');
            addNotification('会议已创建', 'success');
        } catch (e) {
            addNotification('创建会议失败: ' + e.message, 'error');
        } finally {
            setCreating(false);
        }
    };

    const handleEnd = async () => {
        if (!window.confirm('确定要结束会议吗？')) return;
        setEnding(true);
        try {
            await api.meetings.end(activeMeeting.id);
            setActiveMeeting(null);
            clearInterval(pollRef.current);
            addNotification('会议已结束', 'success');
        } catch (e) {
            addNotification('结束会议失败: ' + e.message, 'error');
        } finally {
            setEnding(false);
        }
    };

    const toggleJoin = async (p) => {
        try {
            await api.meetings.updateParticipant(activeMeeting.id, p.id, {
                action: p.status === 'joined' ? 'leave' : 'join',
            });
            refreshMeeting();
        } catch (e) {
            addNotification('操作失败: ' + e.message, 'error');
        }
    };

    const toggleMic = async (p) => {
        try {
            await api.meetings.updateParticipant(activeMeeting.id, p.id, {
                micEnabled: !p.micEnabled,
            });
            refreshMeeting();
        } catch (e) {
            addNotification('操作失败: ' + e.message, 'error');
        }
    };

    const toggleVr = async (p) => {
        try {
            await api.meetings.updateParticipant(activeMeeting.id, p.id, {
                vrModeEnabled: !p.vrModeEnabled,
            });
            refreshMeeting();
        } catch (e) {
            addNotification('操作失败: ' + e.message, 'error');
        }
    };

    const getVisibleParticipants = () => {
        if (!activeMeeting?.participants) return [];
        if (isHost || isManager) return activeMeeting.participants;
        return activeMeeting.participants.filter(
            (p) => p.user?.id === currentUserId
        );
    };

    const renderCreationForm = () => (
        <div className="flex-1 overflow-y-auto p-6">
            <div className="max-w-lg mx-auto space-y-5">
                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        会议标题
                    </label>
                    <input
                        type="text"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="请输入会议标题"
                        className={INPUT_CLS}
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        选择项目
                    </label>
                    <select
                        value={projectId}
                        onChange={(e) => setProjectId(e.target.value)}
                        className={INPUT_CLS}
                    >
                        <option value="">请选择项目</option>
                        {projects.map((p) => (
                            <option key={p.id} value={p.id}>
                                {p.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        主持人机器
                    </label>
                    <select
                        value={hostMachineId}
                        onChange={(e) => setHostMachineId(e.target.value)}
                        className={INPUT_CLS}
                    >
                        <option value="">请选择机器</option>
                        {machines.map((m) => (
                            <option key={m.id} value={m.id}>
                                {m.name} ({m.ip}:{m.port})
                            </option>
                        ))}
                    </select>
                </div>

                <div className="flex gap-3 pt-4">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-xl font-medium transition-colors text-sm"
                    >
                        取消
                    </button>
                    <button
                        onClick={handleCreate}
                        disabled={creating || !title.trim() || !projectId || !hostMachineId}
                        className="flex-1 px-4 py-2 rounded-xl text-white font-bold text-sm transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                        style={{ backgroundColor: THEME_COLOR }}
                    >
                        {creating ? '创建中...' : '创建会议'}
                    </button>
                </div>
            </div>
        </div>
    );

    const renderActiveMeeting = () => {
        const participants = getVisibleParticipants();

        const statusBadge = (status) => {
            const map = {
                active: 'bg-green-50 text-green-600',
                pending: 'bg-yellow-50 text-yellow-600',
                joined: 'bg-emerald-50 text-emerald-600',
                left: 'bg-gray-50 text-gray-500',
            };
            return (
                <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        map[status] || 'bg-gray-50 text-gray-500'
                    }`}
                >
                    {status === 'active'
                        ? '进行中'
                        : status === 'pending'
                        ? '待加入'
                        : status === 'joined'
                        ? '已加入'
                        : status === 'left'
                        ? '已离开'
                        : status}
                </span>
            );
        };

        const iconBtn = (onClick, IconOn, IconOff, isOn, colorKey) => {
            const colors = {
                mic: isOn
                    ? 'bg-blue-50 text-blue-500'
                    : 'bg-gray-50 text-gray-400',
                vr: isOn
                    ? 'bg-purple-50 text-purple-500'
                    : 'bg-gray-50 text-gray-400',
                join: isOn
                    ? 'bg-emerald-50 text-emerald-500'
                    : 'bg-gray-50 text-gray-400',
            };
            const Icon = isOn ? IconOn : IconOff;
            return (
                <button
                    onClick={onClick}
                    className={`p-1.5 rounded-lg transition-colors ${colors[colorKey]}`}
                >
                    <Icon size={14} />
                </button>
            );
        };

        const renderParticipantRow = (p) => {
            const displayName = p.user?.displayName || p.user?.username || '未知';
            const headsetName = p.headset?.name || '-';
            const machineInfo = p.headset?.machine
                ? `${p.headset.machine.ip}:${p.headset.machine.port}`
                : '-';

            return (
                <div
                    key={p.id}
                    className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors"
                >
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold bg-gray-200 text-gray-700 shrink-0">
                        {displayName[0].toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-gray-800 truncate">
                            {displayName}
                            {p.user?.id === activeMeeting?.host?.id && (
                                <span className="ml-1.5 text-xs text-orange-500 font-normal">
                                    主持人
                                </span>
                            )}
                        </div>
                        <div className="text-xs text-gray-400 truncate">
                            {headsetName} · {machineInfo}
                        </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                        {iconBtn(
                            () => toggleJoin(p),
                            Link2,
                            Unlink,
                            p.status === 'joined',
                            'join'
                        )}
                        {iconBtn(
                            () => toggleMic(p),
                            Mic,
                            MicOff,
                            p.micEnabled,
                            'mic'
                        )}
                        {iconBtn(
                            () => toggleVr(p),
                            Glasses,
                            Monitor,
                            p.vrModeEnabled,
                            'vr'
                        )}
                    </div>
                </div>
            );
        };

        return (
            <div className="flex-1 overflow-y-auto flex flex-col">
                <div className="px-6 py-4 border-b border-gray-100 bg-gray-50/50">
                    <div className="flex items-center justify-between">
                        <div>
                            <div className="flex items-center gap-2">
                                <h3 className="text-base font-bold text-gray-800">
                                    {activeMeeting.title}
                                </h3>
                                {statusBadge(activeMeeting.status)}
                            </div>
                            <div className="text-xs text-gray-400 mt-0.5">
                                {activeMeeting.project?.name || '未知项目'} · 主持人:{' '}
                                {activeMeeting.host?.displayName ||
                                    activeMeeting.host?.username ||
                                    '未知'}
                            </div>
                        </div>
                        {(isHost || isManager) && (
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setShowAddParticipant(true)}
                                    className="px-4 py-2 rounded-xl text-white font-bold text-sm transition-colors inline-flex items-center gap-1.5"
                                    style={{ backgroundColor: THEME_COLOR }}
                                >
                                    <Plus size={14} /> 添加参会者
                                </button>
                                <button
                                    onClick={handleEnd}
                                    disabled={ending}
                                    className="px-4 py-2 rounded-xl text-red-500 bg-red-50 hover:bg-red-100 font-bold text-sm transition-colors inline-flex items-center gap-1.5 disabled:opacity-60"
                                >
                                    <PhoneOff size={14} /> {ending ? '结束中...' : '结束会议'}
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto">
                    <div className="px-4 py-2 bg-gray-50 border-b border-gray-100">
                        <span className="text-xs font-medium text-gray-500">
                            参会者 ({participants.length})
                        </span>
                    </div>
                    {participants.length === 0 ? (
                        <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
                            暂无参会者
                        </div>
                    ) : (
                        participants.map(renderParticipantRow)
                    )}
                </div>
            </div>
        );
    };

    return (
        <div
            className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
            onClick={onClose}
        >
            <div
                className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-5 border-b border-gray-100 shrink-0">
                    <div className="flex items-center gap-3">
                        <div
                            className="w-9 h-9 rounded-xl flex items-center justify-center text-white"
                            style={{ backgroundColor: THEME_COLOR }}
                        >
                            <Users size={18} />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-gray-800">
                                会议管理
                            </h2>
                            <p className="text-xs text-gray-400">
                                {activeMeeting ? '会议进行中' : '创建新会议'}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-400 hover:bg-gray-100 rounded-xl transition-colors shrink-0"
                    >
                        <X size={18} />
                    </button>
                </div>

                {activeMeeting ? renderActiveMeeting() : renderCreationForm()}
            </div>

            {showAddParticipant && (
                <MeetingParticipantModal
                    onClose={() => setShowAddParticipant(false)}
                    onAdded={async (userId, headsetId) => {
                        try {
                            await api.meetings.addParticipant(activeMeeting.id, {
                                userId,
                                headsetId,
                            });
                            addNotification('参会者已添加', 'success');
                            refreshMeeting();
                        } catch (e) {
                            addNotification('添加参会者失败: ' + e.message, 'error');
                        }
                    }}
                    addNotification={addNotification}
                />
            )}
        </div>
    );
};

export default MeetingPanel;
