import React, { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { THEME_COLOR } from '../../constants';
import { api } from '../../services/api';

const TYPES = ['Vive', 'Oculus', 'Pico', 'Other'];

const HeadsetModal = ({ headset, machines, onClose, onSaved, addNotification }) => {
    const isEdit = !!headset;
    const [form, setForm] = useState({
        name: headset?.name || '',
        type: headset?.type || '',
        serialNumber: headset?.serialNumber || '',
        machineId: headset?.machineId || '',
    });
    const [error, setError] = useState(null);
    const [saving, setSaving] = useState(false);

    const eligibleMachines = machines.filter((m) =>
        !m.vrHeadsetId || m.vrHeadsetId === headset?.id
    );

    const submit = async (e) => {
        e.preventDefault();
        setError(null);
        if (!form.name.trim()) return setError('名称必填');

        setSaving(true);
        try {
            const payload = {
                name: form.name.trim(),
                type: form.type || null,
                serialNumber: form.serialNumber.trim() || null,
                machineId: form.machineId || null,
            };
            if (isEdit) {
                await api.vrHeadsets.update(headset.id, payload);
                addNotification('头盔更新成功', 'success');
            } else {
                await api.vrHeadsets.create(payload);
                addNotification('头盔创建成功', 'success');
            }
            onSaved();
        } catch (e) {
            setError(e.message || '保存失败');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <form
                className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-5"
                onClick={(e) => e.stopPropagation()}
                onSubmit={submit}
            >
                <div className="flex items-center justify-between mb-4">
                    <h3 className="font-bold text-gray-800">{isEdit ? '编辑头盔' : '新建头盔'}</h3>
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
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            <span className="text-red-500">*</span> 名称
                        </label>
                        <input
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                            placeholder="如 Vive Pro 2 #1"
                            autoFocus
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">品牌/型号</label>
                        <select
                            value={form.type}
                            onChange={(e) => setForm({ ...form, type: e.target.value })}
                            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                        >
                            <option value="">请选择</option>
                            {TYPES.map((t) => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">序列号</label>
                        <input
                            value={form.serialNumber}
                            onChange={(e) => setForm({ ...form, serialNumber: e.target.value })}
                            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                            placeholder="可选"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">绑定机器</label>
                        <select
                            value={form.machineId}
                            onChange={(e) => setForm({ ...form, machineId: e.target.value })}
                            className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:bg-white focus:border-[#39C5BB]"
                        >
                            <option value="">不绑定机器</option>
                            {eligibleMachines.map((m) => (
                                <option key={m.id} value={m.id}>
                                    {m.name} ({m.ip}:{m.port})
                                </option>
                            ))}
                        </select>
                    </div>
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
                        {saving ? '保存中...' : isEdit ? '保存' : '创建'}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default HeadsetModal;
