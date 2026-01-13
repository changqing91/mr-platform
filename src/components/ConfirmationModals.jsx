import React from 'react';
import { AlertTriangle, Power, Trash2 } from 'lucide-react';

export const KillConfirmModal = ({ killCandidate, setKillCandidate, killProcess }) => {
    if (!killCandidate) return null;
    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-red-100 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-2 bg-red-500"></div>
                <div className="flex flex-col items-center text-center mb-6">
                    <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4 text-red-500">
                        <AlertTriangle size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-gray-800">终止进程确认</h3>
                    <p className="text-gray-500 mt-2 text-sm">
                        您确定要强制关闭 <span className="font-bold text-gray-800">{killCandidate.name}</span> 的进程吗？<br />
                        <span className="text-red-500 font-bold text-xs">未保存的数据将会丢失。</span>
                    </p>
                </div>
                <div className="flex gap-3">
                    <button onClick={() => setKillCandidate(null)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button>
                    <button onClick={() => killProcess(killCandidate.id)} className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold shadow-lg shadow-red-500/30 transition-all flex items-center justify-center gap-2">
                        <Power size={18} />确认终止
                    </button>
                </div>
            </div>
        </div>
    );
};

export const GlobalKillConfirmModal = ({ showGlobalKillModal, setShowGlobalKillModal, confirmGlobalKill }) => {
    if (!showGlobalKillModal) return null;
    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-red-100 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-2 bg-red-500"></div>
                <div className="flex flex-col items-center text-center mb-6">
                    <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4 text-red-500">
                        <AlertTriangle size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-gray-800">紧急停止确认</h3>
                    <p className="text-gray-500 mt-2 text-sm">
                        您即将强制关闭所有运行中的机器进程。<br />
                        <span className="text-red-500 font-bold">所有未保存的数据将会丢失。</span>
                    </p>
                </div>
                <div className="flex gap-3">
                    <button onClick={() => setShowGlobalKillModal(false)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button>
                    <button onClick={confirmGlobalKill} className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold shadow-lg shadow-red-500/30 transition-all flex items-center justify-center gap-2">
                        <Power size={18} />确认全部停止
                    </button>
                </div>
            </div>
        </div>
    );
};

export const ClearNodesConfirmModal = ({ showClearNodesModal, setShowClearNodesModal, confirmClearAllNodes }) => {
    if (!showClearNodesModal) return null;
    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-orange-200 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-2 bg-orange-500"></div>
                <div className="flex flex-col items-center text-center mb-6">
                    <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mb-4 text-orange-500">
                        <Trash2 size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-gray-800">清空列表确认</h3>
                    <p className="text-gray-500 mt-2 text-sm">
                        您确定要清空所有计算节点吗？<br />
                        <span className="text-orange-600 font-bold text-xs">此操作不可撤销。</span>
                    </p>
                </div>
                <div className="flex gap-3">
                    <button onClick={() => setShowClearNodesModal(false)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button>
                    <button onClick={confirmClearAllNodes} className="flex-1 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-bold shadow-lg shadow-orange-500/30 transition-all flex items-center justify-center gap-2">
                        <Trash2 size={18} />确认清空
                    </button>
                </div>
            </div>
        </div>
    );
};

export const DeleteNodeConfirmModal = ({ nodeToDelete, setNodeToDelete, confirmDeleteNode }) => {
    if (!nodeToDelete) return null;
    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-red-100 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-full h-2 bg-red-500"></div>
                <div className="flex flex-col items-center text-center mb-6">
                    <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4 text-red-500">
                        <AlertTriangle size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-gray-800">删除节点确认</h3>
                    <p className="text-gray-500 mt-2 text-sm">
                        您确定要删除节点 <span className="font-bold text-gray-800">{nodeToDelete.name}</span> 吗？<br />
                        此操作无法撤销。
                    </p>
                </div>
                <div className="flex gap-3">
                    <button onClick={() => setNodeToDelete(null)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button>
                    <button onClick={confirmDeleteNode} className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold shadow-lg shadow-red-500/30 transition-all flex items-center justify-center gap-2">
                        <Trash2 size={18} />确认删除
                    </button>
                </div>
            </div>
        </div>
    );
};
