import React from 'react';
import { Server, X } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const MachineModal = ({
    showMachineModal,
    setShowMachineModal,
    editingNode,
    newMachineForm,
    setNewMachineForm,
    handleSaveMachine
}) => {
    if (!showMachineModal) return null;

    return (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white p-8 rounded-2xl shadow-2xl w-96 border border-gray-100 transform transition-all scale-100 relative">
                <h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-gray-800">
                    <Server size={24} style={{ color: THEME_COLOR }} />
                    {editingNode ? '编辑计算节点' : '添加新计算节点'}
                </h3>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">机器名称</label>
                        <input 
                            type="text" 
                            value={newMachineForm.name} 
                            onChange={e => setNewMachineForm({...newMachineForm, name: e.target.value})} 
                            className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" 
                            placeholder="例如: Render Node 05" 
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">IP 地址</label>
                        <input 
                            type="text" 
                            value={newMachineForm.ip} 
                            onChange={e => setNewMachineForm({...newMachineForm, ip: e.target.value})} 
                            className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" 
                            placeholder="192.168.1.XXX" 
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">端口 (Port)</label>
                        <input 
                            type="text" 
                            value={newMachineForm.port} 
                            onChange={e => setNewMachineForm({...newMachineForm, port: e.target.value})} 
                            className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" 
                            placeholder="例如: 8888" 
                        />
                    </div>
                    <div className="flex gap-3 pt-4">
                        <button 
                            onClick={() => setShowMachineModal(false)} 
                            className="flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors"
                        >
                            取消
                        </button>
                        <button 
                            onClick={handleSaveMachine} 
                            className="flex-1 py-2 text-white rounded-lg font-medium transition-colors shadow-lg hover:shadow-xl hover:-translate-y-0.5" 
                            style={{ backgroundColor: THEME_COLOR }}
                        >
                            保存
                        </button>
                    </div>
                </div>
                <button 
                    onClick={() => setShowMachineModal(false)} 
                    className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
                >
                    <X size={20} />
                </button>
            </div>
        </div>
    );
};

export default MachineModal;
