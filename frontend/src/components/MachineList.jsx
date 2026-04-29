import React, { useState } from 'react';
import { 
    Monitor, Layers2, Copy, CheckSquare, Power, Trash2, Plus, 
    Play, RefreshCw, Link, Rocket, Server, RotateCcw, Square, Edit2, Sliders
} from 'lucide-react';
import ProjectThumbnail from './ProjectThumbnail';
import { THEME_COLOR } from '../constants';

const MachineList = ({
    machines,
    isBatchMode,
    selectedBatchIds,
    selectAllIdleNodes,
    selectAllRunningNodes,
    toggleBatchMode,
    handleGlobalKillClick,
    setShowClearNodesModal,
    openAddModal,
    runningMachines,
    bootingMachines,
    pendingLaunches,
    projects,
    activeMachineId,
    handleMachineClick,
    commitLaunches,
    restartNode,
    setKillCandidate,
    openEditModal,
    promptDeleteNode,
    setStreamingMachineId,
    setActiveMachineId,
    setShowMonitorWall,
    setIsBatchMode,
    collaborationMachineIds,
    toggleMachineCollaboration,
    globalScriptConfig,
    onScriptConfigChange,
}) => {
    const pendingCount = Object.keys(pendingLaunches).length;
    const [showScriptPanel, setShowScriptPanel] = useState(false);

    const updateGlobalConfig = (updates) => {
        const next = { ...globalScriptConfig, ...updates };
        onScriptConfigChange(next);
    };
    const hasScriptConfig = (globalScriptConfig?.dlssQuality !== undefined && globalScriptConfig?.dlssQuality !== null) || !!globalScriptConfig?.customScript?.trim();

    return (
        <aside className="w-[320px] lg:w-[30%] max-w-[480px] bg-gray-50 border-l border-gray-200 flex flex-col relative shrink-0">
             {/* Header */}
             <div className="p-6 pb-4 shrink-0 border-b border-gray-100">
                <div className="flex justify-between items-center mb-6">
                    <div className="flex-1">
                        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                            <Monitor size={20} className="text-gray-400" />
                            节点列表
                        </h2>
                        <p className="text-xs text-gray-400 mt-1">
                            {isBatchMode ? `批量模式: 已选 ${selectedBatchIds.size} 个节点` : '选择项目以进行绑定，或管理现有节点'}
                        </p>
                    </div>
                    <button
                        onClick={() => setShowScriptPanel(v => !v)}
                        className={`p-2 rounded-lg transition-colors ${showScriptPanel || hasScriptConfig ? 'bg-violet-100 text-violet-600' : 'text-gray-400 hover:bg-gray-100 hover:text-violet-500'}`}
                        title="全局启动脚本配置"
                    >
                        <Sliders size={18} />
                    </button>
                </div>

                {/* Global Script Config Panel */}
                {showScriptPanel && (
                    <div className="mb-4 rounded-xl border border-violet-200 bg-violet-50/60 p-3 space-y-3">
                        <div className="text-xs font-bold text-violet-500 uppercase tracking-wider flex items-center gap-1.5">
                            <Sliders size={12} />
                            全局启动脚本配置
                        </div>

                        {/* DLSS */}
                        <div className="space-y-2 pb-2 border-b border-violet-200">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-medium text-gray-700">DLSS</span>
                                <select
                                    value={globalScriptConfig?.dlssQuality ?? ''}
                                    onChange={e => updateGlobalConfig({ dlssQuality: e.target.value === '' ? null : Number(e.target.value) })}
                                    className="text-xs border border-violet-200 rounded px-2 py-0.5 bg-white focus:outline-none focus:border-violet-400"
                                >
                                    <option value={''}>不设置</option>
                                    <option value={0}>关闭 (VR_DLSS_OFF)</option>
                                    <option value={2}>性能 (VR_DLSS_PERFORMANCE)</option>
                                    <option value={3}>均衡 (VR_DLSS_BALANCED)</option>
                                    <option value={4}>质量 (VR_DLSS_QUALITY)</option>
                                    <option value={5}>超高性能 (VR_DLSS_ULTRA_PERFORMANCE)</option>
                                </select>
                            </div>
                        </div>

                        {/* Custom Script */}
                        <div className="space-y-1.5">
                            <div className="text-xs font-medium text-gray-700">自定义 Python 脚本</div>
                            <textarea
                                value={globalScriptConfig?.customScript || ''}
                                onChange={e => updateGlobalConfig({ customScript: e.target.value })}
                                placeholder="# 项目加载后执行..."
                                className="w-full text-xs font-mono border border-violet-200 rounded-lg p-2 resize-none focus:outline-none focus:border-violet-400 bg-white placeholder-gray-300"
                                rows={3}
                            />
                        </div>

                        {hasScriptConfig && (
                            <button
                                onClick={() => onScriptConfigChange({})}
                                className="text-xs text-gray-400 hover:text-red-400 transition-colors"
                            >
                                清除配置
                            </button>
                        )}
                    </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                    {/* Contextual Row */}
                    {isBatchMode && (
                        <>
                            <button onClick={selectAllIdleNodes} className="flex items-center justify-center gap-2 px-3 py-2.5 bg-white border border-gray-200 rounded-lg hover:border-primary hover:text-primary transition-colors shadow-sm text-xs font-bold text-gray-600" title="全选空闲节点">
                                <div className="w-3.5 h-3.5 border-2 border-current rounded-sm"></div> 全选空闲
                            </button>
                            <button onClick={selectAllRunningNodes} className="flex items-center justify-center gap-2 px-3 py-2.5 bg-white border border-gray-200 rounded-lg hover:border-primary hover:text-primary transition-colors shadow-sm text-xs font-bold text-gray-600" title="全选运行中节点">
                                <Layers2 size={16} /> 全选运行
                            </button>
                        </>
                    )}

                    {/* Persistent Control Row */}
                    <button onClick={toggleBatchMode} className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg transition-all shadow-sm text-xs font-bold ${isBatchMode ? `bg-gray-800 text-white` : 'bg-white border border-gray-200 text-gray-600 hover:border-primary hover:text-primary'}`} title="批量控制模式">
                        {isBatchMode ? <CheckSquare size={16} /> : <Copy size={16} />} {isBatchMode ? '退出批量' : '批量模式'}
                    </button>

                    <button onClick={handleGlobalKillClick} className="flex items-center justify-center gap-2 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 hover:border-red-300 hover:text-red-700 text-red-600 transition-colors shadow-sm text-xs font-bold" title="一键停止所有进程">
                        <Power size={16} /> 一键停止
                    </button>

                    {/* Footer Row */}
                    <button onClick={() => setShowClearNodesModal(true)} className="flex items-center justify-center gap-2 px-3 py-2.5 bg-white border border-gray-200 rounded-lg hover:bg-orange-50 hover:border-orange-500 hover:text-orange-500 transition-colors shadow-sm text-xs font-bold text-gray-600" title="清空所有节点列表">
                        <Trash2 size={16} /> 清空节点
                    </button>

                    <button onClick={openAddModal} className="flex items-center justify-center gap-2 px-3 py-2.5 bg-white border border-gray-200 rounded-lg hover:border-primary hover:text-primary transition-colors shadow-sm text-xs font-bold text-gray-600" title="添加新节点">
                        <Plus size={16} /> 添加节点
                    </button>
                </div>
             </div>

             {/* Machine List */}
             <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar pb-24">
                 {machines.map(machine => {
                     const isRunning = !!runningMachines[machine.id];
                     const isBooting = bootingMachines.has(machine.id);
                     const isOffline = machine.status === 'offline';
                     const isIdle = !isRunning && !isBooting && !isOffline;
                     const pendingProject = pendingLaunches[machine.id] ? projects.find(p => p.id === pendingLaunches[machine.id]) : null;
                     const currentProject = isRunning ? projects.find(p => p.id === runningMachines[machine.id]) : null;
                     const project = pendingProject || currentProject;
                     
                     const isSelectedInBatch = isBatchMode && selectedBatchIds.has(machine.id);
                     const isActiveInSingle = !isBatchMode && activeMachineId === machine.id;
                     const isInCollaboration = collaborationMachineIds?.has(machine.id);
                     
                     let borderClass = 'border-white';
                     let ringClass = '';
                     let bgClass = 'bg-white';
                     
                     if (isSelectedInBatch) {
                         bgClass = 'bg-blue-50';
                     }
                     if (isBooting) {
                         borderClass = 'border-blue-400 border-dashed animate-pulse';
                         bgClass = 'bg-blue-50';
                     } else if (pendingProject && !isRunning) {
                         borderClass = 'border-yellow-400 border-dashed';
                         bgClass = 'bg-yellow-50';
                     }
                     
                     // 离线节点不可点击，其他情况都可以点击
                     let isClickable = !isOffline;

                     return (
                         <React.Fragment key={machine.id}>
                         <div 
                            onClick={() => { if(isClickable) handleMachineClick(machine); }}
                            className={`
                                relative p-3 rounded-xl border-2 transition-all duration-200 group shadow-sm hover:shadow-md flex gap-3 
                                ${borderClass} ${ringClass} ${bgClass}
                                ${!isClickable && isBatchMode ? 'opacity-40 cursor-not-allowed grayscale' : ''}
                                ${isOffline ? 'opacity-60 grayscale cursor-not-allowed' : ''}
                                ${isClickable ? 'cursor-pointer' : ''}
                            `}
                            style={{ borderColor: (isActiveInSingle || isSelectedInBatch) ? THEME_COLOR : ((pendingProject && !isBooting && !isRunning) ? '#FBBF24' : 'transparent') }}
                         >
                             {/* Left Side: Project Info */}
                             <div 
                                 className={`flex gap-3 ${isRunning && !isBatchMode ? 'cursor-pointer group/thumb' : ''}`}
                                 onClick={(e) => {
                                     if (isRunning && !isBatchMode) {
                                         e.stopPropagation();
                                         setStreamingMachineId(machine.id);
                                         setActiveMachineId(null);
                                     }
                                 }}
                             >
                                 {/* Scripts Column could go here if we had scripts data */}

                                 {/* Thumbnail Container */}
                                 <div className={`w-36 h-24 rounded-lg overflow-hidden relative flex items-center justify-center transition-colors shrink-0 ${isRunning ? 'bg-black' : 'bg-gray-100'}`}>
                                     {(isRunning || isBooting) && project ? (
                                         <>
                                            <ProjectThumbnail project={project} className={`w-full h-full opacity-80 transition-opacity ${!isBatchMode ? 'group-hover/thumb:opacity-60' : ''}`} />
                                            {!isBatchMode && (
                                                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover/thumb:opacity-100 transition-opacity">
                                                    <Play size={24} className="text-white fill-current" />
                                                </div>
                                            )}
                                            <div className="absolute top-1 left-1 bg-black/60 text-white text-[9px] px-1 rounded backdrop-blur-sm">{project.type}</div>
                                            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-2 pt-6">
                                                <div className="text-[10px] font-bold text-white leading-tight truncate">{project.name}</div>
                                            </div>
                                         </>
                                     ) : (
                                         <div className="flex flex-col items-center justify-center text-gray-400 gap-1">
                                             {isOffline ? <Power size={24} /> : <Monitor size={24} />}
                                             <span className="text-[10px] font-bold uppercase">{isOffline ? 'OFFLINE' : 'IDLE'}</span>
                                         </div>
                                     )}
                                     
                                     {/* Pending Overlay */}
                                     {pendingProject && !isBooting && !isRunning && (
                                         <div className="absolute inset-0 z-10 bg-yellow-50 flex flex-col items-center justify-center border-2 border-yellow-400 border-dashed rounded-lg animate-in fade-in">
                                             <Link size={18} className="text-yellow-500 mb-1" />
                                             <span className="text-[10px] font-bold text-yellow-700 truncate max-w-[90%] px-1">{pendingProject.name}</span>
                                             <span className="text-[9px] text-yellow-600/80">待启动...</span>
                                         </div>
                                     )}
                                     
                                    {/* Batch Selection Overlay */}
                                     {isBatchMode && isClickable && (
                                         <div className={`absolute inset-0 bg-white/50 backdrop-blur-[1px] flex items-center justify-center transition-opacity ${isSelectedInBatch ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                                             <div className={`w-8 h-8 rounded-full flex items-center justify-center shadow-lg transform transition-transform ${isSelectedInBatch ? `bg-primary scale-110` : 'bg-white scale-100'}`} style={{ backgroundColor: isSelectedInBatch ? THEME_COLOR : undefined }}>
                                                 {isSelectedInBatch ? <CheckSquare size={18} className="text-white" /> : <div className="w-4 h-4 border-2 border-gray-300 rounded-sm"></div>}
                                             </div>
                                         </div>
                                     )}
                                 </div>
                             </div>

                             {/* Right Side: Node Info & Actions */}
                             <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5 border-l border-gray-100 pl-3">
                                 <div>
                                     <div className="flex justify-between items-start mb-1">
                                         <h3 className="font-bold text-gray-800 text-sm truncate pr-2" title={machine.name}>{machine.name}</h3>
                                         {/* Status Dot */}
                                         {pendingProject && !isBooting && !isRunning ? (
                                             <div className="shrink-0 w-2 h-2 rounded-full bg-yellow-400 animate-pulse" title="等待启动"></div>
                                         ) : (
                                             <div className={`shrink-0 w-2 h-2 rounded-full ${isOffline ? 'bg-gray-300' : (isIdle ? 'bg-slate-300' : `bg-green-500 shadow-sm shadow-green-200 animate-pulse`)}`} title={isIdle ? '空闲' : (isRunning ? '运行中' : (isOffline ? '离线' : '启动中'))}></div>
                                         )}
                                     </div>
                                     <div className="text-xs text-gray-400 font-mono tracking-tight flex items-center gap-1">
                                         <Server size={10} />
                                         {machine.ip}<span className="text-gray-300">:</span>{machine.port}
                                     </div>
                                 </div>

                                 <div className="flex items-center justify-end gap-2 mt-2">
                                     {!isBatchMode && (
                                         <>
                                             {isRunning && (
                                                 <label 
                                                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors text-sm font-bold cursor-pointer"
                                                    onClick={(e) => e.stopPropagation()}
                                                    title="加入VRED协作"
                                                 >
                                                    <input
                                                        type="checkbox"
                                                        className="w-4 h-4 accent-emerald-500"
                                                        checked={!!isInCollaboration}
                                                        onChange={(e) => toggleMachineCollaboration(machine, e.target.checked)}
                                                    />
                                                    协作
                                                 </label>
                                             )}
                                             {isRunning ? (
                                                 <>
                                                     <button onClick={(e) => restartNode(machine, e)} className="p-2.5 bg-blue-50 text-blue-500 rounded-lg hover:bg-blue-100 transition-colors" title="重启项目"><RotateCcw size={18} /></button>
                                                     <button onClick={(e) => { e.stopPropagation(); setKillCandidate(machine); }} className="p-2.5 bg-red-50 text-red-500 rounded-lg hover:bg-red-100 transition-colors" title="停止进程"><Square size={18} fill="currentColor" /></button>
                                                 </>
                                             ) : (
                                                 !isBooting && (
                                                     <>
                                                         <button onClick={(e) => openEditModal(machine, e)} className="p-2.5 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded-lg transition-colors" title="编辑"><Edit2 size={18} /></button>
                                                         <button onClick={(e) => promptDeleteNode(machine, e)} className="p-2.5 hover:bg-red-50 text-gray-400 hover:text-red-500 rounded-lg transition-colors" title="删除"><Trash2 size={18} /></button>
                                                     </>
                                                 )
                                             )}
                                         </>
                                     )}
                                 </div>
                             </div>
                         </div>

                         </React.Fragment>
                     );
                 })}
             </div>

            {/* Launch Action Bar */}
            {pendingCount > 0 && (
                <div className="absolute bottom-6 left-6 right-6 z-20 animate-in slide-in-from-bottom-4 fade-in">
                    <button 
                        onClick={commitLaunches} 
                        className="w-full py-4 rounded-xl shadow-xl flex items-center justify-center gap-3 text-white font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all" 
                        style={{ backgroundColor: THEME_COLOR }}
                    >
                        <Rocket size={24} className="animate-pulse" />
                        执行启动计划 ({pendingCount} 个节点)
                    </button>
                </div>
            )}
        </aside>
    );
};

export default MachineList;
