import React, { useState } from 'react';
import { ArrowLeft, RotateCcw, CheckSquare, Play, Square, AlertTriangle, Zap, Power } from 'lucide-react';
import { MR_TOOLS, THEME_COLOR } from '../constants';

const ScriptToolsPanel = ({
    machine,
    isBatchMode,
    selectedBatchCount,
    onBack,
    onSwitchTool,
    onReset,
    onKill,
    activeTool,
    isToolsInjected
}) => {
    const [isConfirmingKill, setIsConfirmingKill] = useState(false);

    const handleToolClick = (tool) => {
        if (onSwitchTool) {
            onSwitchTool(tool.id);
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
                {isToolsInjected && (
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-50 border border-green-200">
                        <Zap size={14} className="text-green-500" />
                        <span className="text-xs font-bold text-green-600">工具已注入</span>
                    </div>
                )}
            </div>

            <div className="flex-1 p-8 overflow-y-auto custom-scrollbar">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">
                        MR 功能工具 {isBatchMode && '(批量控制)'} — 点击即可切换
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
                        const isActive = activeTool === tool.id;
                        return (
                            <button 
                                key={tool.id} 
                                onClick={() => handleToolClick(tool)} 
                                className={`
                                    flex flex-col items-center p-6 bg-white border rounded-2xl shadow-sm hover:shadow-lg transition-all group relative 
                                    ${isActive ? 'ring-2 shadow-lg' : 'border-gray-200 hover:border-[#39C5BB] hover:-translate-y-1'}
                                `}
                                style={{ 
                                    borderColor: isActive ? THEME_COLOR : undefined,
                                    backgroundColor: isActive ? 'rgba(57, 197, 187, 0.08)' : undefined,
                                    ringColor: isActive ? THEME_COLOR : undefined
                                }}
                            >
                                {/* Active indicator */}
                                {isActive && (
                                    <div 
                                        className="absolute top-3 right-3 w-5 h-5 rounded-full flex items-center justify-center animate-pulse"
                                        style={{ backgroundColor: THEME_COLOR }}
                                    >
                                        <Power size={10} className="text-white" />
                                    </div>
                                )}
                                
                                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center mb-4 transition-colors ${isActive ? 'bg-white shadow-sm' : 'bg-gray-50 group-hover:bg-[#39C5BB]/10'}`}>
                                    <tool.icon 
                                        size={32} 
                                        className="transition-colors"
                                        style={{ color: isActive ? THEME_COLOR : undefined }} 
                                    />
                                </div>
                                <span 
                                    className="font-bold mb-1"
                                    style={{ color: isActive ? THEME_COLOR : '#374151' }}
                                >
                                    {tool.name}
                                </span>
                                <span className="text-xs text-center text-gray-400">
                                    {isActive ? '当前生效' : tool.description}
                                </span>
                            </button>
                        )
                    })}
                </div>

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
