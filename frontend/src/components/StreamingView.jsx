import React, { useState } from 'react';
import { ArrowLeft, Activity, Glasses, SplitSquareHorizontal, ImageIcon, Headset, FolderOpen, Monitor } from 'lucide-react';
import ProjectThumbnail from './ProjectThumbnail';
import { api } from '../services/api';

const StreamingView = ({ 
    streamingMachineId, 
    setStreamingMachineId, 
    machines, 
    projects, 
    runningMachines
}) => {
    const machine = machines.find(m => m.id === streamingMachineId);
    const project = projects.find(p => p.id === runningMachines[streamingMachineId]);
    const THEME_COLOR = '#39C5BB';
    
    const [streamParams, setStreamParams] = useState({
        hmdIp: '',
        hmdPort: '8888',
        trackingInterval: '1.0',
        isTracking: false,
        schemeIp: '',
        schemePort: '8888',
        schemeCompareActive: false,
        liveRefFolder: '',
        realtimeRefActive: false,
        displayMode: 'standard', // 'standard', 'immersive'
        immersiveType: 'xr', // 'xr', 'mr'
        showCalibration: false
    });

    const updateStreamParam = (key, value) => setStreamParams(prev => ({ ...prev, [key]: value }));

    const handleOneTimeTracking = () => {
        console.log('Trigger one-time tracking');
    };

    const handleAutoTracking = (enabled) => {
        updateStreamParam('isTracking', enabled);
    };

    const sendPython = async (code) => {
        if (!machine) return;
        try {
            await api.processes.executePython(machine.ip, machine.port || 8888, code);
        } catch (e) {
            console.error('Python Exec Error:', e);
        }
    };

    const handleStandardDisplay = () => {
        updateStreamParam('displayMode', 'standard');
        sendPython('setDisplayMode(VR_DISPLAY_STANDARD)');
    };

    const handleEnterXR = () => {
        updateStreamParam('displayMode', 'immersive');
        sendPython('setDisplayMode(VR_DISPLAY_OPEN_VR)');
    };

    const handleToggleMode = () => {
        if (streamParams.displayMode !== 'immersive') return;
        const newType = streamParams.immersiveType === 'xr' ? 'mr' : 'xr';
        updateStreamParam('immersiveType', newType);
        
        if (newType === 'mr') {
            // Switch to MR (Varjo/Passthrough)
            sendPython('setDisplayMode(VR_DISPLAY_VARJO)');
        } else {
            // Switch back to VR (OpenXR)
            sendPython('setDisplayMode(VR_DISPLAY_OPEN_VR)');
        }
    };

    const handleStartCompare = async () => {
        if (!streamParams.schemeIp) return;
        
        updateStreamParam('schemeCompareActive', true);
        
        try {
            // Tell the secondary node (Right) to join the primary node (Left) session
            const pythonCode = `vrSessionService.joinSession("${machine.ip}")`;
            console.log('Sending Python to Secondary Node:', streamParams.schemeIp, pythonCode);
            
            await api.processes.executePython(
                streamParams.schemeIp, 
                streamParams.schemePort, 
                pythonCode
            );
        } catch (e) {
            console.error('Failed to start comparison sync:', e);
        }
    };

    const handleStopCompare = async () => {
        updateStreamParam('schemeCompareActive', false);
        try {
            const pythonCode = `vrSessionService.leaveSession()`;
             await api.processes.executePython(
                streamParams.schemeIp, 
                streamParams.schemePort, 
                pythonCode
            );
        } catch (e) {
             console.error('Failed to stop comparison sync:', e);
        }
    };

    const [iframeLoading, setIframeLoading] = useState(true);

    const onIframeLoad = () => {
        setIframeLoading(false);
    };

    const goBack = () => setStreamingMachineId(null);

    const vredUrl = machine ? `http://${machine.ip}:${machine.port || 8888}/apps/VREDStreamApp/index.html` : '';

    return (
        <div className="absolute inset-0 z-30 bg-gray-900 flex flex-col animate-in fade-in duration-300">
            {/* Streaming Header */}
            <div className="h-16 flex items-center justify-between px-6 bg-gray-900 border-b border-gray-800 text-white shrink-0">
                <div className="flex items-center gap-4">
                    <button onClick={goBack} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors text-sm">
                        <ArrowLeft size={16} />退出预览
                    </button>
                    <div className="h-6 w-[1px] bg-gray-700"></div>
                    <div>
                        <h2 className="text-lg font-bold flex items-center gap-2">
                            <Activity size={18} className="text-[#39C5BB] animate-pulse" />
                            实时串流: {machine?.name}
                        </h2>
                        <p className="text-xs text-gray-400">Project: {project?.name}</p>
                    </div>
                </div>
                <div className="flex gap-4 text-xs font-mono text-gray-500">
                    {streamParams.isTracking && <span className="text-[#39C5BB] flex items-center gap-1"><Glasses size={12}/> HMD TRACKING</span>}
                    {streamParams.schemeCompareActive && <span className="text-[#39C5BB] flex items-center gap-1"><SplitSquareHorizontal size={12}/> COMPARING</span>}
                    {streamParams.realtimeRefActive && <span className="text-[#39C5BB] flex items-center gap-1"><ImageIcon size={12}/> REF ACTIVE</span>}
                    {streamParams.displayMode === 'immersive' && streamParams.immersiveType === 'xr' && (
                        <span className="text-[#39C5BB] flex items-center gap-1 bg-[#39C5BB]/10 px-2 py-0.5 rounded border border-[#39C5BB]/20"><Glasses size={12}/> XR ACTIVE</span>
                    )}
                    {streamParams.displayMode === 'immersive' && streamParams.immersiveType === 'mr' && (
                        <span className="text-[#39C5BB] flex items-center gap-1 bg-[#39C5BB]/10 px-2 py-0.5 rounded border border-[#39C5BB]/20"><Headset size={12}/> MR ACTIVE</span>
                    )}
                </div>
            </div>

            {/* Streaming Content */}
            <div className="flex-1 flex overflow-hidden">
                <div className="flex-1 bg-black relative flex items-center justify-center overflow-hidden">
                        {iframeLoading && (
                            <div className="absolute inset-0 flex items-center justify-center z-10">
                                <ProjectThumbnail project={project} className="w-full h-full opacity-80" />
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#39C5BB]"></div>
                                </div>
                            </div>
                        )}
                        
                        {/* Primary Stream (Left) */}
                        <div className={`relative h-full transition-all duration-300 ${streamParams.schemeCompareActive ? 'w-1/2 border-r border-gray-800' : 'w-full'}`}>
                            <iframe 
                                src={vredUrl} 
                                frameBorder="0" 
                                width="100%" 
                                height="100%"
                                onLoad={onIframeLoad}
                                style={{ opacity: iframeLoading ? 0 : 1 }}
                                allow="autoplay; fullscreen"
                            ></iframe>
                            {streamParams.schemeCompareActive && (
                                <div className="absolute bottom-4 left-4 text-white font-bold text-shadow bg-black/30 px-2 rounded z-20 pointer-events-none">方案 A (Main)</div>
                            )}
                        </div>

                        {/* Secondary Stream (Right) */}
                        {streamParams.schemeCompareActive && (
                            <div className="w-1/2 h-full relative animate-in fade-in slide-in-from-right-10 duration-500">
                                <iframe 
                                    src={`http://${streamParams.schemeIp}:${streamParams.schemePort || 8888}/apps/VREDStreamApp/index.html`}
                                    frameBorder="0" 
                                    width="100%" 
                                    height="100%"
                                    allow="autoplay; fullscreen"
                                ></iframe>
                                <div className="absolute bottom-4 right-4 text-white font-bold text-shadow bg-black/30 px-2 rounded z-20 pointer-events-none">方案 B ({streamParams.schemeIp})</div>
                            </div>
                        )}

                        {streamParams.showCalibration && <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: 'linear-gradient(rgba(57, 197, 187, 0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(57, 197, 187, 0.3) 1px, transparent 1px)', backgroundSize: '50px 50px' }}></div>}
                </div>
                <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col p-6 overflow-y-auto custom-scrollbar">
                    {/* 1. HMD View Tracking */}
                    <div className="mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                        <h3 className="text-sm font-bold text-gray-300 mb-3 flex items-center gap-2"><Glasses size={16} className="text-[#39C5BB]"/>HMD 视角追踪</h3>
                        <div className="space-y-3">
                            <div className="grid grid-cols-3 gap-2">
                                <div className="col-span-2">
                                    <label className="block text-[10px] text-gray-500 mb-1">HMD IP</label>
                                    <input type="text" placeholder="192.168.x.x" value={streamParams.hmdIp} onChange={(e) => updateStreamParam('hmdIp', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                </div>
                                <div>
                                    <label className="block text-[10px] text-gray-500 mb-1">Port</label>
                                    <input type="text" placeholder="8888" value={streamParams.hmdPort} onChange={(e) => updateStreamParam('hmdPort', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                </div>
                            </div>
                            <div>
                                <label className="block text-[10px] text-gray-500 mb-1">追踪间隔 (s)</label>
                                <input type="number" placeholder="1.0" value={streamParams.trackingInterval} onChange={(e) => updateStreamParam('trackingInterval', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                            </div>
                            
                            <button onClick={handleOneTimeTracking} className="w-full py-2 rounded text-xs font-bold bg-gray-700 text-white hover:bg-gray-600 transition-colors border border-gray-600">一次性追踪</button>
                            
                            <div className="flex items-center justify-between mt-1">
                                <span className="text-xs text-gray-400">自动追踪:</span>
                                <div className="flex rounded-lg overflow-hidden border border-gray-700">
                                    <button 
                                        onClick={() => handleAutoTracking(true)} 
                                        className={`px-3 py-1.5 text-xs font-bold transition-colors ${streamParams.isTracking ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                    >
                                        开启
                                    </button>
                                    <div className="w-[1px] bg-gray-700"></div>
                                    <button 
                                        onClick={() => handleAutoTracking(false)} 
                                        className={`px-3 py-1.5 text-xs font-bold transition-colors ${!streamParams.isTracking ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                    >
                                        停止
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* 2. Scheme Compare */}
                    <div className="mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                        <h3 className="text-sm font-bold text-gray-300 mb-3 flex items-center gap-2"><SplitSquareHorizontal size={16} className="text-[#39C5BB]"/>方案对比</h3>
                        <div className="space-y-3">
                            <div className="grid grid-cols-3 gap-2"><div className="col-span-2"><label className="block text-[10px] text-gray-500 mb-1">Node IP</label><input type="text" placeholder="192.168.x.x" value={streamParams.schemeIp} onChange={(e) => updateStreamParam('schemeIp', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" /></div><div><label className="block text-[10px] text-gray-500 mb-1">Port</label><input type="text" placeholder="8888" value={streamParams.schemePort} onChange={(e) => updateStreamParam('schemePort', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" /></div></div>
                            
                            <div className="flex rounded-lg overflow-hidden border border-gray-700 w-full">
                                <button 
                                    onClick={handleStartCompare} 
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.schemeCompareActive ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    开启对比
                                </button>
                                <div className="w-[1px] bg-gray-700"></div>
                                <button 
                                    onClick={handleStopCompare} 
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.schemeCompareActive ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    关闭对比
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* 3. Realtime Reference */}
                    <div className="mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                        <h3 className="text-sm font-bold text-gray-300 mb-3 flex items-center gap-2"><ImageIcon size={16} className="text-[#39C5BB]"/>实时参照</h3>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-[10px] text-gray-500 mb-1">参照图片目录</label>
                                <div className="flex gap-2">
                                    <input type="text" placeholder="C:/Reference/..." value={streamParams.liveRefFolder} onChange={(e) => updateStreamParam('liveRefFolder', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                    <button className="px-2 bg-gray-700 hover:bg-gray-600 rounded text-white border border-gray-600"><FolderOpen size={14}/></button>
                                </div>
                            </div>
                            
                            <div className="flex rounded-lg overflow-hidden border border-gray-700 w-full">
                                <button 
                                    onClick={() => updateStreamParam('realtimeRefActive', true)} 
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.realtimeRefActive ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    开启参照
                                </button>
                                <div className="w-[1px] bg-gray-700"></div>
                                <button 
                                    onClick={() => updateStreamParam('realtimeRefActive', false)} 
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.realtimeRefActive ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    关闭参照
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="mt-auto pt-4 border-t border-gray-800 space-y-3">
                        <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">显示模式</h3>
                        <div className="grid grid-cols-2 gap-2">
                            <button 
                                onClick={handleStandardDisplay} 
                                className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'standard' ? `text-white shadow-lg` : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'}`}
                                style={{ backgroundColor: streamParams.displayMode === 'standard' ? THEME_COLOR : '' }}
                            >
                                <Monitor size={18} /> 标准显示
                            </button>
                            
                            <button 
                                onClick={handleEnterXR} 
                                className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'immersive' ? `text-white shadow-lg` : 'bg-gray-800 border border-gray-700 text-gray-400 hover:bg-gray-700 hover:text-white'}`}
                                style={{ backgroundColor: streamParams.displayMode === 'immersive' ? THEME_COLOR : '' }}
                            >
                                <Glasses size={18} /> OpenXR
                            </button>
                        </div>
                        <button 
                            onClick={handleToggleMode} 
                            disabled={streamParams.displayMode !== 'immersive'}
                            className={`w-full py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'immersive' ? `bg-purple-600 text-white hover:bg-purple-500 shadow-lg cursor-pointer` : 'bg-gray-800/50 border border-gray-700 text-gray-600 cursor-not-allowed'}`}
                        >
                            {streamParams.displayMode !== 'immersive' 
                                ? <><Headset size={18} /> 切换模式 (需先进入XR)</> 
                                : (streamParams.immersiveType === 'xr' 
                                    ? <><Headset size={18} /> 切换为 MR</> 
                                    : <><Glasses size={18} /> 切换为 VR</>
                                )
                            }
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StreamingView;