import React from 'react';
import { LayoutDashboard, Activity, Power, Monitor, Eye } from 'lucide-react';
import ProjectThumbnail from './ProjectThumbnail';

const MonitorWall = ({ 
    machines, 
    runningMachines, 
    projects, 
    setShowMonitorWall, 
    setStreamingMachineId, 
    handleGlobalKillClick,
    setKillCandidate
}) => {
    const wallMachines = machines.filter(m => runningMachines[m.id]);
    
    return (
        <div className="flex-1 flex flex-col bg-gray-50 animate-in fade-in duration-500 overflow-hidden">
            {/* UPDATED: Changed padding to p-6 to match Project List header */}
            <div className="p-6 border-b border-gray-200 flex justify-between items-center bg-white shrink-0">
                {/* New Navigation Group */}
                <div className="flex items-center gap-6">
                    <button onClick={() => setShowMonitorWall(false)} className="text-xl font-bold text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-2">
                        <LayoutDashboard size={20} />
                        项目资源库
                    </button>
                    <div className="w-[1px] h-6 bg-gray-300"></div>
                    {/* UPDATED: Aligned text size and icon size */}
                    <button onClick={() => setShowMonitorWall(true)} className="text-2xl font-bold text-gray-800 transition-colors flex items-center gap-2">
                        <Activity size={24} className="text-[#39C5BB]" />
                        全局监控墙
                    </button>
                    <span className="px-2 py-0.5 rounded text-xs bg-[#39C5BB]/10 text-[#39C5BB] font-mono border border-[#39C5BB]/20 ml-2">LIVE FEED</span>
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-4 text-sm text-gray-500 mr-4 border-r border-gray-200 pr-6">
                        <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>{wallMachines.length} 运行中</div>
                        <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-gray-300"></div>{machines.length - wallMachines.length} 空闲/离线</div>
                    </div>
                    
                    <button 
                        onClick={handleGlobalKillClick}
                        className="flex items-center gap-2 px-4 py-2 bg-red-50 text-red-600 border border-red-200 rounded-lg hover:bg-red-600 hover:text-white hover:shadow-md transition-all text-sm font-bold group"
                    >
                        <Power size={16} className="group-hover:scale-110 transition-transform"/> 关闭所有进程
                    </button>
                </div>
            </div>
            
            <div className="flex-1 p-8 overflow-y-auto custom-scrollbar monitor-grid-bg">
                {wallMachines.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-400">
                        <Monitor size={64} className="mb-4 opacity-20" />
                        <p className="text-xl font-medium text-gray-600">当前没有运行中的项目</p>
                        <p className="text-sm mt-2">请从左侧列表启动节点</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-6"> 
                        {wallMachines.map(machine => {
                            const proj = projects.find(p => p.id === runningMachines[machine.id]);
                            return (
                                <div key={machine.id} className="bg-white rounded-xl overflow-hidden border border-gray-200 hover:border-[#39C5BB] transition-all group shadow-sm hover:shadow-lg relative flex flex-col">
                                    <div 
                                        onClick={() => { setStreamingMachineId(machine.id); setShowMonitorWall(false); }}
                                        className="aspect-[4/3] bg-gray-100 relative cursor-pointer shrink-0 w-full" 
                                    >
                                        <ProjectThumbnail project={proj} className="absolute inset-0 w-full h-full object-cover opacity-90 group-hover:opacity-100 transition-opacity" />
                                        <iframe 
                                            src={`http://${machine.ip}:${machine.port || 8888}/apps/VREDStream/index.html?width=auto&height=auto`}
                                            className="absolute inset-0 w-full h-full pointer-events-none"
                                            frameBorder="0"
                                            scrolling="no"
                                            allow="autoplay; fullscreen"
                                        ></iframe>
                                        <div className="absolute top-3 left-3 z-10"><span className={`px-2 py-1 rounded-md text-xs font-bold text-white shadow-sm backdrop-blur-md ${proj?.type === 'VRED' ? 'bg-orange-500/80' : 'bg-blue-500/80'}`}>{proj?.type}</span></div>
                                        <div className="absolute top-2 right-2 flex gap-1 z-10">
                                            <span className="bg-red-500/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1 animate-pulse"><div className="w-1.5 h-1.5 bg-white rounded-full"></div>REC</span>
                                        </div>
                                        <div className="absolute bottom-2 left-2 right-2 flex justify-between items-end z-10">
                                            <div className="bg-black/60 backdrop-blur-sm px-2 py-1 rounded text-xs font-mono text-white">FPS: 59.9</div>
                                        </div>
                                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 backdrop-blur-[1px] z-20">
                                            <div className="bg-[#39C5BB] text-white px-4 py-2 rounded-lg font-bold flex items-center gap-2 transform scale-95 group-hover:scale-100 transition-transform shadow-lg">
                                                <Eye size={18} /> 进入控制
                                            </div>
                                        </div>
                                    </div>
                                    <div className="p-4 flex items-center justify-between bg-white relative z-10 border-t border-gray-50 shrink-0">
                                        <div className="flex-1 min-w-0 mr-2"> 
                                            <div className="flex items-center gap-2 mb-1">
                                                <h3 className="font-bold text-gray-800 truncate" title={machine.name}>{machine.name}</h3>
                                            </div>
                                            <p className="text-xs text-gray-400 font-mono truncate">{machine.ip}</p>
                                            <p className="text-xs text-gray-500 truncate mt-0.5" title={proj?.name}>{proj?.name}</p>
                                        </div>
                                        
                                        <div className="flex flex-col items-end gap-1 shrink-0">
                                            <label className="relative inline-flex items-center cursor-pointer" title="点击停止进程">
                                                <input 
                                                    type="checkbox" 
                                                    className="sr-only peer" 
                                                    checked={true} 
                                                    onChange={() => setKillCandidate(machine)} 
                                                />
                                                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#39C5BB] hover:peer-checked:bg-[#2dbdb3]"></div>
                                            </label>
                                            <span className="text-[10px] text-green-500 font-bold tracking-wide">运行中</span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default MonitorWall;
