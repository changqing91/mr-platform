import React, { useState } from 'react';
import { ArrowLeft, RotateCcw, CheckSquare, Play, Square, AlertTriangle } from 'lucide-react';
import { MR_TOOLS, THEME_COLOR } from '../constants';

const ScriptToolsPanel = ({
    machine,
    isBatchMode,
    selectedBatchCount,
    onBack,
    onInject,
    onReset,
    onKill
}) => {
    const [selectedScriptIds, setSelectedScriptIds] = useState(new Set());
    const [isConfirmingKill, setIsConfirmingKill] = useState(false);

    const handleScriptClick = (tool) => {
        if (selectedScriptIds.has(tool.id)) {
            setSelectedScriptIds(new Set());
            return;
        }
        setSelectedScriptIds(new Set([tool.id]));
    };

    const handleExecute = () => {
        const [selectedId] = Array.from(selectedScriptIds);
        if (selectedId) {
            onInject([selectedId]);
            setSelectedScriptIds(new Set());
        }
    };

    return (
        <div className="flex-1 flex flex-col animate-in fade-in zoom-in duration-300 bg-white relative h-full">
            <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-gray-50/50 shrink-0">
                <div className="flex items-center gap-4">
                    <button 
                        onClick={onBack} 
                        className="flex items-center gap-2 px-3 py-2 rounded-lg text-gray-600 hover:bg-gray-200 transition-colors font-medium text-sm"
                    >
                        <ArrowLeft size={18} />
                        返回资源库
                    </button>
                    <div className="h-6 w-[1px] bg-gray-300"></div>
                    <div>
                        <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-3">
                            <span className="w-3 h-8 rounded-full" style={{ backgroundColor: THEME_COLOR }}></span>
                            {isBatchMode ? 'MR 工具面板 (批量)' : 'MR 工具面板'}
                        </h2>
                        <p className="text-gray-500 mt-1 text-xs">
                            {isBatchMode 
                                ? `已选中 ${selectedBatchCount} 台机器进行同步控制` 
                                : `已连接: ${machine?.name} (${machine?.ip})`
                            }
                        </p>
                    </div>
                </div>
            </div>

            <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">
                        MR 功能脚本 {isBatchMode && '(批量注入)'}
                    </h3>
                    <button 
                        onClick={onReset}
                        className="text-xs px-3 py-1.5 rounded-lg border border-red-200 text-red-500 bg-red-50 hover:bg-red-100 hover:border-red-300 transition-all font-bold flex items-center gap-2"
                    >
                        <RotateCcw size={14} /> 清除工具注入
                    </button>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-6 mb-8">
                    {MR_TOOLS.map(tool => {
                        const isSelected = selectedScriptIds.has(tool.id);
                        return (
                            <button 
                                key={tool.id} 
                                onClick={() => handleScriptClick(tool)} 
                                className={`
                                    flex flex-col items-center p-6 bg-white border rounded-2xl shadow-sm hover:shadow-lg transition-all group relative 
                                    ${isSelected ? `border-[${THEME_COLOR}] ring-1 ring-[${THEME_COLOR}] bg-[#39C5BB]/5` : 'border-gray-200 hover:border-[#39C5BB] hover:-translate-y-1'}
                                `}
                                style={{ 
                                    borderColor: isSelected ? THEME_COLOR : undefined,
                                    backgroundColor: isSelected ? 'rgba(57, 197, 187, 0.05)' : undefined
                                }}
                            >
                                {/* Selection Checkmark */}
                                <div 
                                    className={`absolute top-3 right-3 w-5 h-5 rounded-full border flex items-center justify-center transition-colors`}
                                    style={{
                                        backgroundColor: isSelected ? THEME_COLOR : 'white',
                                        borderColor: isSelected ? 'transparent' : '#D1D5DB'
                                    }}
                                >
                                    {isSelected && <CheckSquare size={12} className="text-white" />}
                                </div>
                                
                                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-colors ${isSelected ? 'bg-white' : 'bg-gray-50 group-hover:bg-[#39C5BB]/10'}`}>
                                    <tool.icon 
                                        size={32} 
                                        className="transition-colors"
                                        style={{ color: isSelected ? THEME_COLOR : undefined }} 
                                    />
                                </div>
                                <span 
                                    className="font-bold mb-1"
                                    style={{ color: isSelected ? THEME_COLOR : '#374151' }}
                                >
                                    {tool.name}
                                </span>
                                <span className="text-xs text-center text-gray-400">{tool.description}</span>
                            </button>
                        )
                    })}
                </div>

                {/* Confirm Injection Button - Shows when any script selected */}
                {selectedScriptIds.size > 0 && (
                    <div className="mb-10 animate-in fade-in slide-in-from-bottom-2">
                        <button 
                            onClick={handleExecute}
                            className="w-full py-4 rounded-xl text-white font-bold shadow-lg flex items-center justify-center gap-2 hover:opacity-90 transition-opacity hover:-translate-y-0.5"
                            style={{ backgroundColor: THEME_COLOR }}
                        >
                            <Play size={20} fill="currentColor"/> 
                            确认注入 {selectedScriptIds.size} 个脚本
                        </button>
                    </div>
                )}

                <div className="border-t border-gray-100 pt-8">
                    <h3 className="text-sm font-bold text-red-400 uppercase tracking-wider mb-4">危险操作区</h3>
                    <div className="bg-red-50 border border-red-100 rounded-xl p-6 flex items-center justify-between">
                        <div>
                            <h4 className="font-bold text-red-800">{isBatchMode ? '批量终止进程' : '终止进程'}</h4>
                            <p className="text-sm text-red-600/70">
                                {isBatchMode 
                                    ? `将强制关闭选中的 ${selectedBatchCount} 台机器的所有进程` 
                                    : '将强制关闭 VRED/Alias 进程并断开MR连接'
                                }
                            </p>
                        </div>
                        {isConfirmingKill ? (
                            <div className="flex items-center gap-3">
                                <span className="text-sm text-red-500 font-bold animate-pulse">确定要关闭吗?</span>
                                <button 
                                    onClick={onKill} 
                                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold shadow-lg transition-all"
                                >
                                    确定关闭
                                </button>
                                <button 
                                    onClick={() => setIsConfirmingKill(false)} 
                                    className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg font-bold transition-all"
                                >
                                    取消
                                </button>
                            </div>
                        ) : (
                            <button 
                                onClick={() => setIsConfirmingKill(true)} 
                                className="px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold shadow-lg shadow-red-500/30 transition-all flex items-center gap-2"
                            >
                                <Square size={18} fill="currentColor" />
                                强制关闭
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ScriptToolsPanel;
