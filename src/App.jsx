import React, { useState, useMemo, useRef } from 'react';
import { 
    Search, Plus, Box, Monitor, Wifi, Power, RefreshCw, X, Play, Square, 
    Settings, Server, Activity, Clock, Trash2, Edit2, AlertTriangle, 
    FileText, Upload, Check, CheckSquare, RotateCcw, Rocket, Link, FilePlus, LogOut, Bell, ArrowLeft,
    LayoutDashboard, Layers2, Copy, Eye, Calendar
} from 'lucide-react';
import LoginScreen from './components/LoginScreen';
import ProjectThumbnail from './components/ProjectThumbnail';
import ResourceDetail from './components/ResourceDetail';
import { INITIAL_PROJECTS, INITIAL_MACHINES, MR_TOOLS, THEME_COLOR } from './constants';

const App = () => {
    // --- State: Auth ---
    const [isLoggedIn, setIsLoggedIn] = useState(() => localStorage.getItem('isLoggedIn') === 'true');
    const [loginForm, setLoginForm] = useState({ username: '', password: '' });
    const [currentUser, setCurrentUser] = useState(() => {
        const saved = localStorage.getItem('currentUser');
        return saved ? JSON.parse(saved) : null;
    });

    // --- State: Data ---
    const [projects, setProjects] = useState(INITIAL_PROJECTS);
    const [machines, setMachines] = useState(INITIAL_MACHINES);

    // --- State: UI & Selection ---
    const [activeProject, setActiveProject] = useState(null);
    const [activeMachineId, setActiveMachineId] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'list'
    const [showMonitorWall, setShowMonitorWall] = useState(false);
    
    // --- State: Sorting & Filtering ---
    const [sortBy, setSortBy] = useState('date');
    const [sortOrder, setSortOrder] = useState('desc');
    const [showTagFilter, setShowTagFilter] = useState(false);
    const [selectedFilterTags, setSelectedFilterTags] = useState(new Set());

    // --- State: Batch Operations ---
    const [isBatchMode, setIsBatchMode] = useState(false);
    const [selectedBatchIds, setSelectedBatchIds] = useState(new Set());

    // --- State: Process & Streaming ---
    const [runningMachines, setRunningMachines] = useState({}); // { machineId: projectId }
    const [bootingMachines, setBootingMachines] = useState(new Set()); // Set<machineId>
    const [pendingLaunches, setPendingLaunches] = useState({}); // { machineId: projectId } (Staged for batch launch)
    const [streamingMachineId, setStreamingMachineId] = useState(null);

    // --- State: Modals ---
    const [showProjectModal, setShowProjectModal] = useState(false);
    const [showMachineModal, setShowMachineModal] = useState(false);
    const [showClearNodesModal, setShowClearNodesModal] = useState(false);
    const [showGlobalKillModal, setShowGlobalKillModal] = useState(false);
    const [killCandidate, setKillCandidate] = useState(null);
    const [nodeToDelete, setNodeToDelete] = useState(null);
    const [editingNode, setEditingNode] = useState(null);

    // --- State: Forms ---
    const [newProjectForm, setNewProjectForm] = useState({ name: '', type: 'VRED', fileName: '', size: '', thumbnail: null });
    const [newMachineForm, setNewMachineForm] = useState({ name: '', ip: '', port: '' });
    const fileInputRef = useRef(null);
    const thumbnailInputRef = useRef(null);

    // --- State: Notifications ---
    const [notifications, setNotifications] = useState([]);

    // --- Helper: Notifications ---
    const addNotification = (message, type = 'info') => {
        const id = Date.now();
        setNotifications(prev => [...prev, { id, message, type }]);
        setTimeout(() => {
            setNotifications(prev => prev.filter(n => n.id !== id));
        }, 3000);
    };

    // --- Handlers: Auth ---
    const handleLogin = (e) => {
        e.preventDefault();
        if (loginForm.username && loginForm.password) {
            const user = { name: loginForm.username, id: '8902' };
            setIsLoggedIn(true);
            setCurrentUser(user);
            localStorage.setItem('isLoggedIn', 'true');
            localStorage.setItem('currentUser', JSON.stringify(user));
            addNotification('登录成功', 'success');
        }
    };

    const handleLogout = () => {
        setIsLoggedIn(false);
        setCurrentUser(null);
        setLoginForm({ username: '', password: '' });
        localStorage.removeItem('isLoggedIn');
        localStorage.removeItem('currentUser');
    };

    // --- Handlers: Projects ---
    const handleAddProject = () => {
        if (!newProjectForm.name || !newProjectForm.fileName) return;
        const newProject = {
            id: Date.now(),
            name: newProjectForm.name,
            type: newProjectForm.type,
            thumbnail: newProjectForm.thumbnail,
            size: newProjectForm.size,
            date: new Date().toISOString().split('T')[0],
            tags: ['New']
        };
        setProjects([newProject, ...projects]);
        setShowProjectModal(false);
        setNewProjectForm({ name: '', type: 'VRED', fileName: '', size: '', thumbnail: null });
        addNotification(`项目 "${newProject.name}" 已添加`, 'success');
    };

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) {
            let size = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
            if (file.size > 1024 * 1024 * 1024) size = (file.size / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
            
            let type = 'Unknown';
            if (file.name.endsWith('.vpb')) type = 'VRED';
            else if (file.name.endsWith('.wire')) type = 'Alias';

            setNewProjectForm({ ...newProjectForm, fileName: file.name, size, type });
        }
    };
    
    const clearFile = (e) => {
        e.stopPropagation();
        setNewProjectForm({ ...newProjectForm, fileName: '', size: '' });
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const handleThumbnailSelect = (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onloadend = () => {
                setNewProjectForm({ ...newProjectForm, thumbnail: reader.result });
            };
            reader.readAsDataURL(file);
        }
    };

    const clearThumbnail = (e) => {
        e.stopPropagation();
        setNewProjectForm({ ...newProjectForm, thumbnail: null });
        if (thumbnailInputRef.current) thumbnailInputRef.current.value = '';
    };

    // --- Handlers: Machines ---
    const handleSaveMachine = () => {
        if (!newMachineForm.name || !newMachineForm.ip) return;
        
        if (editingNode) {
            setMachines(machines.map(m => m.id === editingNode.id ? { ...m, ...newMachineForm } : m));
            addNotification(`节点 "${newMachineForm.name}" 更新成功`, 'success');
        } else {
            const newMachine = {
                id: `m${Date.now()}`,
                ...newMachineForm,
                status: 'idle',
                currentProject: null,
                health: 'good'
            };
            setMachines([...machines, newMachine]);
            addNotification(`节点 "${newMachineForm.name}" 已添加`, 'success');
        }
        setShowMachineModal(false);
        setNewMachineForm({ name: '', ip: '', port: '' });
        setEditingNode(null);
    };

    const openEditModal = (machine, e) => {
        e.stopPropagation();
        setEditingNode(machine);
        setNewMachineForm({ name: machine.name, ip: machine.ip, port: machine.port });
        setShowMachineModal(true);
    };

    const promptDeleteNode = (machine, e) => {
        e.stopPropagation();
        setNodeToDelete(machine);
    };

    const confirmDeleteNode = () => {
        if (nodeToDelete) {
            setMachines(machines.filter(m => m.id !== nodeToDelete.id));
            // Also cleanup states
            if (activeMachineId === nodeToDelete.id) setActiveMachineId(null);
            setNodeToDelete(null);
            addNotification('节点已删除', 'info');
        }
    };
    
    const confirmClearAllNodes = () => {
        // Only keep running nodes? No, "Clear List" usually means remove all configuration
        // But here we might want to prevent deleting running nodes? 
        // The modal text says "running nodes will also be removed".
        setMachines([]);
        setActiveMachineId(null);
        setStreamingMachineId(null);
        setShowClearNodesModal(false);
        addNotification('所有节点已清空', 'warning');
    };

    // --- Handlers: Interaction ---
    const handleProjectClick = (project) => {
        setActiveProject(project.id === activeProject ? null : project.id);
        
        // If we are in batch mode and have selected nodes, assign this project to them as PENDING
        if (isBatchMode && selectedBatchIds.size > 0) {
            const newPending = { ...pendingLaunches };
            selectedBatchIds.forEach(mid => {
                // Only if not already running/booting
                if (!runningMachines[mid] && !bootingMachines.has(mid)) {
                    newPending[mid] = project.id;
                }
            });
            setPendingLaunches(newPending);
            setSelectedBatchIds(new Set());
            addNotification(`已为 ${selectedBatchIds.size} 个节点预设项目: ${project.name}`, 'info');
        } else if (activeMachineId && !isBatchMode) {
             // Single mode assignment
             if (!runningMachines[activeMachineId] && !bootingMachines.has(activeMachineId)) {
                 setPendingLaunches(prev => ({ ...prev, [activeMachineId]: project.id }));
             }
        }
    };

    const toggleBatchMode = () => {
        setIsBatchMode(!isBatchMode);
        setSelectedBatchIds(new Set());
        // If exiting batch mode, maybe clear pending if not committed? 
        // We keep pending launches even if mode changes, until committed or cleared.
    };

    const selectAllIdleNodes = () => {
        const idleIds = machines
            .filter(m => !runningMachines[m.id] && !bootingMachines.has(m.id) && m.status !== 'offline')
            .map(m => m.id);
        setSelectedBatchIds(new Set(idleIds));
    };

    const selectAllRunningNodes = () => {
        const runningIds = machines
            .filter(m => runningMachines[m.id])
            .map(m => m.id);
        setSelectedBatchIds(new Set(runningIds));
    };

    const handleGlobalKillClick = () => {
        setShowGlobalKillModal(true);
    };

    const openAddModal = () => setShowMachineModal(true);

    const handleMachineClick = (machine) => {
        if (machine.status === 'offline') return;

        if (isBatchMode) {
            // Batch Selection Toggle
            const newSet = new Set(selectedBatchIds);
            if (newSet.has(machine.id)) {
                newSet.delete(machine.id);
            } else {
                newSet.add(machine.id);
            }
            setSelectedBatchIds(newSet);
        } else {
            // Single Mode Selection
            if (activeMachineId === machine.id) {
                setActiveMachineId(null);
                // Also clear pending launch for this machine if it was set
                setPendingLaunches(prev => {
                    const next = { ...prev };
                    delete next[machine.id];
                    return next;
                });
            } else {
                setActiveMachineId(machine.id);
                
                // Auto-assign active project if one is selected
                if (activeProject && !runningMachines[machine.id] && !bootingMachines.has(machine.id)) {
                    setPendingLaunches(prev => ({ ...prev, [machine.id]: activeProject }));
                }
            }
        }
    };

    // --- Handlers: Process Control ---
    const commitLaunches = () => {
        const machineIds = Object.keys(pendingLaunches);
        if (machineIds.length === 0) return;

        // Move to booting
        const newBooting = new Set(bootingMachines);
        machineIds.forEach(id => newBooting.add(id));
        setBootingMachines(newBooting);

        // Clear pending
        const launchesToProcess = { ...pendingLaunches };
        setPendingLaunches({});

        // Simulate boot delays
        machineIds.forEach(id => {
            setTimeout(() => {
                setBootingMachines(prev => {
                    const next = new Set(prev);
                    next.delete(id);
                    return next;
                });
                setRunningMachines(prev => ({ ...prev, [id]: launchesToProcess[id] }));
                addNotification(`节点 ${machines.find(m => m.id === id)?.name || id} 启动完成`, 'success');
            }, 2000 + Math.random() * 2000);
        });
        
        addNotification(`正在启动 ${machineIds.length} 个任务...`, 'info');
    };

    const restartNode = (machine, e) => {
        e.stopPropagation();
        if (!runningMachines[machine.id]) return;
        
        const projectId = runningMachines[machine.id];
        // Kill then restart
        setRunningMachines(prev => {
            const next = { ...prev };
            delete next[machine.id];
            return next;
        });
        
        setBootingMachines(prev => new Set(prev).add(machine.id));
        
        setTimeout(() => {
            setBootingMachines(prev => {
                const next = new Set(prev);
                next.delete(machine.id);
                return next;
            });
            setRunningMachines(prev => ({ ...prev, [machine.id]: projectId }));
            addNotification(`${machine.name} 重启完成`, 'success');
        }, 3000);
    };

    const killProcess = (machineId) => {
        setRunningMachines(prev => {
            const next = { ...prev };
            delete next[machineId];
            return next;
        });
        setKillCandidate(null);
        if (streamingMachineId === machineId) setStreamingMachineId(null);
        addNotification('进程已终止', 'warning');
    };
    
    const confirmGlobalKill = () => {
        setRunningMachines({});
        setBootingMachines(new Set());
        setPendingLaunches({});
        setStreamingMachineId(null);
        setShowGlobalKillModal(false);
        addNotification('所有进程已紧急停止', 'error');
    };

    // --- Derived State ---
    const allAvailableTags = useMemo(() => {
        const tags = new Set();
        projects.forEach(p => p.tags && p.tags.forEach(t => tags.add(t)));
        return Array.from(tags);
    }, [projects]);

    const filteredProjects = useMemo(() => {
        let result = projects.filter(p => 
            p.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
            p.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))
        );

        if (selectedFilterTags.size > 0) {
             result = result.filter(p => p.tags.some(t => selectedFilterTags.has(t)));
        }

        return result.sort((a, b) => {
            let valA = a[sortBy];
            let valB = b[sortBy];
            
            // Handle date string comparison
            if (sortBy === 'date') {
                valA = new Date(valA).getTime();
                valB = new Date(valB).getTime();
            } else if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }
            
            if (valA < valB) return sortOrder === 'asc' ? -1 : 1;
            if (valA > valB) return sortOrder === 'asc' ? 1 : -1;
            return 0;
        });
    }, [projects, searchQuery, selectedFilterTags, sortBy, sortOrder]);

    const pendingCount = Object.keys(pendingLaunches).length;

    // --- Sub-components ---
    // Defined here to access closure state easily
    
    const MonitorWall = () => {
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
                                            <ProjectThumbnail project={proj} className="w-full h-full opacity-90 group-hover:opacity-100 transition-opacity" />
                                            <div className="absolute top-3 left-3"><span className={`px-2 py-1 rounded-md text-xs font-bold text-white shadow-sm backdrop-blur-md ${proj?.type === 'VRED' ? 'bg-orange-500/80' : 'bg-blue-500/80'}`}>{proj?.type}</span></div>
                                            <div className="absolute top-2 right-2 flex gap-1">
                                                <span className="bg-red-500/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1 animate-pulse"><div className="w-1.5 h-1.5 bg-white rounded-full"></div>REC</span>
                                            </div>
                                            <div className="absolute bottom-2 left-2 right-2 flex justify-between items-end">
                                                <div className="bg-black/60 backdrop-blur-sm px-2 py-1 rounded text-xs font-mono text-white">FPS: 59.9</div>
                                            </div>
                                            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 backdrop-blur-[1px]">
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

    const StreamingView = () => {
        const machine = machines.find(m => m.id === streamingMachineId);
        const project = projects.find(p => p.id === runningMachines[streamingMachineId]);
        
        // Mock Streaming State
        const [streamParams, setStreamParams] = useState({
            fps: 60,
            latency: 12,
            bitrate: 45,
            resolution: '4K',
            displayMode: 'standard', // 'standard', 'immersive'
            immersiveType: 'xr'
        });

        const updateStreamParam = (key, value) => setStreamParams(prev => ({ ...prev, [key]: value }));

        return (
            <div className="flex-1 bg-black relative flex flex-col">
                {/* Stream Header */}
                <div className="h-12 bg-gray-900/90 backdrop-blur border-b border-gray-800 flex items-center justify-between px-4 z-20">
                    <div className="flex items-center gap-4">
                        <button onClick={() => setStreamingMachineId(null)} className="text-gray-400 hover:text-white flex items-center gap-1 text-sm font-medium transition-colors">
                            <ArrowLeft size={16} /> 返回
                        </button>
                        <div className="h-4 w-px bg-gray-700"></div>
                        <div className="flex items-center gap-2">
                            <span className="text-white font-bold">{machine?.name}</span>
                            <span className="text-gray-500 text-sm">•</span>
                            <span className="text-primary text-sm">{project?.name}</span>
                        </div>
                    </div>
                    
                    {/* Stream Stats */}
                    <div className="flex items-center gap-6 text-xs font-mono">
                        <div className="flex items-center gap-1.5 text-green-400">
                            <Activity size={12} />
                            <span>{streamParams.fps} FPS</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-blue-400">
                            <Clock size={12} />
                            <span>{streamParams.latency}ms</span>
                        </div>
                        <div className="flex items-center gap-1.5 text-purple-400">
                            <Wifi size={12} />
                            <span>{streamParams.bitrate} Mbps</span>
                        </div>
                    </div>
                </div>

                {/* Stream Content Area */}
                <div className="flex-1 relative overflow-hidden group">
                     {/* Placeholder Stream Image */}
                     <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
                        <ProjectThumbnail project={project} className="w-full h-full opacity-60 blur-sm scale-105" />
                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
                        <div className="z-10 text-center">
                            <div className="text-white text-2xl font-bold mb-2">Streaming Active</div>
                            <div className="text-primary font-mono">{streamParams.resolution} • H.265 • 10bit</div>
                        </div>
                     </div>
                     
                     {/* MR Overlay UI (Simulated) */}
                     <div className="absolute top-4 right-4 flex flex-col gap-2">
                        {MR_TOOLS.map(tool => (
                            <button key={tool.id} className="w-10 h-10 bg-black/50 backdrop-blur border border-white/10 rounded-lg flex items-center justify-center text-white/70 hover:text-white hover:bg-primary hover:border-primary transition-all" title={tool.name}>
                                <tool.icon size={20} />
                            </button>
                        ))}
                     </div>
                </div>

                {/* Bottom Control Bar */}
                <div className="h-16 bg-gray-900 border-t border-gray-800 px-6 flex items-center justify-between z-20">
                    <div className="flex items-center gap-2">
                         <button className="p-2 rounded-lg bg-primary/10 text-primary border border-primary/30 hover:bg-primary hover:text-white transition-all">
                            <Settings size={20} />
                         </button>
                         <div className="h-8 w-px bg-gray-700 mx-2"></div>
                         <div className="flex gap-2">
                            <button 
                                onClick={() => updateStreamParam('displayMode', 'standard')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${streamParams.displayMode === 'standard' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}`}
                            >标准显示</button>
                            <button 
                                onClick={() => updateStreamParam('displayMode', 'immersive')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${streamParams.displayMode === 'immersive' ? 'bg-purple-600/20 text-purple-400 border border-purple-500/30' : 'text-gray-400 hover:text-white'}`}
                            >XR 沉浸模式</button>
                         </div>
                    </div>
                    
                    <button onClick={() => setKillCandidate(machine)} className="px-4 py-2 bg-red-500/10 text-red-500 border border-red-500/30 rounded-lg hover:bg-red-500 hover:text-white transition-all font-bold flex items-center gap-2">
                        <Power size={18} /> 停止进程
                    </button>
                </div>
            </div>
        );
    };

    if (!isLoggedIn) {
        return <LoginScreen handleLogin={handleLogin} loginForm={loginForm} setLoginForm={setLoginForm} />;
    }

    if (streamingMachineId && runningMachines[streamingMachineId]) {
        return <StreamingView />;
    }

    return (
        <div className="flex items-center justify-center h-screen w-screen bg-gray-100 p-4 font-sans select-none relative text-sm text-gray-600">
            {/* Notification Toast */}
            <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] flex flex-col gap-2 pointer-events-none">
                {notifications.map(n => (
                    <div key={n.id} className={`pointer-events-auto px-4 py-3 rounded-lg shadow-xl flex items-center gap-3 animate-in slide-in-from-top-4 fade-in ${n.type === 'success' ? 'bg-white border-l-4 border-green-500 text-gray-800' : (n.type === 'error' ? 'bg-red-50 text-red-800 border-l-4 border-red-500' : 'bg-gray-800 text-white border-l-4 border-primary')}`}>
                        {n.type === 'success' && <Check size={18} className="text-green-500" />}
                        {n.type === 'error' && <AlertTriangle size={18} className="text-red-500" />}
                        {n.type === 'info' && <Bell size={18} className="text-primary" />}
                        <span className="font-medium">{n.message}</span>
                    </div>
                ))}
            </div>

            {/* Top Header */}
            <div className="w-full h-full bg-white shadow-2xl rounded-2xl overflow-hidden flex flex-col relative border border-gray-200">
            <header className="h-16 border-b border-gray-100 flex items-center justify-between px-8 bg-white z-20 shrink-0">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white shadow-lg shadow-[#39C5BB]/30" style={{ backgroundColor: THEME_COLOR }}>
                            <Box size={20} strokeWidth={3} />
                        </div>
                        <h1 className="text-xl font-bold text-gray-800 tracking-tight">WhatTech <span style={{ color: THEME_COLOR }}>MR</span></h1>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="text-right mr-2 hidden sm:block">
                            <div className="text-sm font-bold text-gray-700">{currentUser?.name}</div>
                            <div className="text-[10px] text-gray-400 font-mono">ID: {currentUser?.id}</div>
                        </div>
                        <div className="w-9 h-9 rounded-full bg-gray-200 border border-gray-200 flex items-center justify-center text-gray-500 font-bold">
                            {currentUser?.name?.charAt(0).toUpperCase()}
                        </div>
                        <button onClick={handleLogout} className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors ml-2" title="退出登录">
                            <LogOut size={18} />
                        </button>
                    </div>
                </header>

            <div className="flex-1 flex overflow-hidden bg-gray-50">
                {showMonitorWall ? (
                    <MonitorWall />
                ) : (
                        /* Main Content Area */
                        <main className="flex-1 flex flex-col min-w-0 bg-gray-50">
                            {/* Sub Header / Toolbar */}
                            {/* Sub Header / Toolbar - REPLACED */}
                            <div className="p-6 pb-4 shrink-0">
                                {/* Top Nav & Search */}
                                <div className="flex items-center justify-between mb-6">
                                    {/* Left: Page Nav */}
                                    <div className="flex items-center gap-6">
                                        <button onClick={() => setShowMonitorWall(false)} className="text-2xl font-bold text-gray-800 transition-colors flex items-center gap-2 cursor-default">
                                            <LayoutDashboard size={24} style={{ color: THEME_COLOR }} />
                                            项目资源库
                                        </button>
                                        <div className="w-[1px] h-6 bg-gray-300"></div>
                                        <button onClick={() => setShowMonitorWall(true)} className="text-xl font-bold text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-2">
                                            <Activity size={20} />
                                            全局监控墙
                                        </button>
                                    </div>

                                    {/* Right: Search */}
                                    <div className="relative group w-80">
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 group-focus-within:text-primary transition-colors" size={18} />
                                        <input 
                                            type="text" 
                                            placeholder="搜索 VRED / Alias 资产..." 
                                            value={searchQuery} 
                                            onChange={(e) => setSearchQuery(e.target.value)} 
                                            className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all" 
                                        />
                                    </div>
                                </div>

                                {/* Toolbar */}
                                <ResourceDetail 
                                    sortBy={sortBy}
                                    setSortBy={setSortBy}
                                    sortOrder={sortOrder}
                                    setSortOrder={setSortOrder}
                                    showTagFilter={showTagFilter}
                                    setShowTagFilter={setShowTagFilter}
                                    selectedFilterTags={selectedFilterTags}
                                    setSelectedFilterTags={setSelectedFilterTags}
                                    projectViewMode={viewMode}
                                    setProjectViewMode={setViewMode}
                                    setShowProjectModal={setShowProjectModal}
                                    allAvailableTags={allAvailableTags}
                                    projectCount={projects.length}
                                />
                            </div>

                            {/* Content Grid/List */}
                                {/* Project Area */}
                                <div className="flex-1 p-6 overflow-y-auto custom-scrollbar">
                            {viewMode === 'grid' ? (
                                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-6">
                                    {filteredProjects.map(project => {
                                        const isSelected = activeProject === project.id;
                                        const isRunning = Object.values(runningMachines).includes(project.id);
                                        const runningCount = Object.values(runningMachines).filter(id => id === project.id).length;
                                        
                                        return (
                                            <div 
                                                key={project.id} 
                                                onClick={() => handleProjectClick(project)}
                                                className={`group bg-white rounded-xl border transition-all duration-200 cursor-pointer flex flex-col overflow-hidden relative ${isSelected ? `border-[#39C5BB] ring-2 ring-[#39C5BB] shadow-xl translate-y-[-4px]` : 'border-gray-200 hover:border-[#39C5BB] shadow-sm hover:shadow-lg hover:translate-y-[-2px]'}`}
                                            >
                                                {/* Thumbnail */}
                                                <div className="aspect-[4/3] bg-gray-100 relative overflow-hidden">
                                                    <ProjectThumbnail project={project} className="w-full h-full transition-transform duration-500 group-hover:scale-105" />
                                                    <div className="absolute top-3 left-3"><span className={`px-2 py-1 rounded-md text-xs font-bold text-white shadow-sm backdrop-blur-md ${project.type === 'VRED' ? 'bg-orange-500/80' : 'bg-blue-500/80'}`}>{project.type}</span></div>
                                                    
                                                    {/* Date Overlay */}
                                                    <div className="absolute bottom-3 left-3 right-3 flex justify-between items-end text-white text-xs opacity-80">
                                                        <div className="flex gap-1 items-center bg-black/30 px-1.5 py-0.5 rounded backdrop-blur-sm"><Calendar size={10} /> {project.date || 'N/A'}</div>
                                                    </div>

                                                    {/* Selection Indicator Overlay */}
                                                    {isSelected && (
                                                        <div className="absolute inset-0 rounded-none pointer-events-none z-10">
                                                            <div className="absolute top-3 right-3 bg-[#39C5BB] text-white p-1 rounded-full shadow-lg">
                                                                <Check size={14} strokeWidth={3} />
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                                
                                                {/* Info */}
                                                <div className="p-4 flex flex-col bg-white relative z-10 border-t border-gray-50">
                                                    <div className="mb-2">
                                                        <h3 className="font-bold text-gray-800 truncate" title={project.name}>{project.name}</h3>
                                                    </div>
                                                    
                                                    {/* Tags */}
                                                    <div className="flex items-center gap-1 mb-3 overflow-hidden">
                                                        {project.tags && project.tags.map((tag, idx) => (
                                                            <span key={idx} className="px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded text-[10px] font-medium tracking-tight border border-gray-200 whitespace-nowrap">{tag}</span>
                                                        ))}
                                                    </div>
                                                    
                                                    {/* Footer: Size & Status */}
                                                    <div className="flex items-center justify-between text-xs text-gray-400 font-mono pt-3 border-t border-gray-100">
                                                        <div className="flex items-center gap-1">
                                                            {/* We don't have HardDrive imported, using FileText or simple text */}
                                                            <span>{project.size}</span>
                                                        </div>
                                                        
                                                        <div className="flex items-center gap-1">
                                                            <div className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`}></div>
                                                            <span className={`${isRunning ? 'text-green-500' : 'text-gray-400'} font-bold`}>{isRunning ? '运行中' : '离线'}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
                                    <table className="w-full">
                                        <thead className="bg-gray-50 border-b border-gray-200">
                                            <tr>
                                                <th className="px-6 py-4 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">项目名称</th>
                                                <th className="px-6 py-4 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">类型</th>
                                                <th className="px-6 py-4 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">大小</th>
                                                <th className="px-6 py-4 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">修改日期</th>
                                                <th className="px-6 py-4 text-right text-xs font-bold text-gray-500 uppercase tracking-wider">操作</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100">
                                            {filteredProjects.map(project => {
                                                const isSelected = activeProject === project.id;
                                                return (
                                                    <tr 
                                                        key={project.id} 
                                                        onClick={() => handleProjectClick(project)}
                                                        className={`cursor-pointer transition-colors ${isSelected ? 'bg-primary/5' : 'hover:bg-gray-50'}`}
                                                    >
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <div className="flex items-center gap-3">
                                                                <div className="w-10 h-10 rounded-lg overflow-hidden shrink-0">
                                                                    <ProjectThumbnail project={project} className="w-full h-full" />
                                                                </div>
                                                                <span className={`font-medium ${isSelected ? 'text-primary' : 'text-gray-800'}`}>{project.name}</span>
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500">{project.type}</td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500 font-mono">{project.size}</td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-gray-500">{project.date}</td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                                            {isSelected && <Check size={18} className="inline-block text-primary" />}
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                </main>
                )}
                        {/* Right Sidebar: Machine List */}
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
                                </div>

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
                                     
                                     const isSelectedInBatch = isBatchMode && selectedBatchIds.has(machine.id);
                                     const isActiveInSingle = !isBatchMode && activeMachineId === machine.id;
                                     
                                     let borderClass = 'border-white';
                                     let ringClass = '';
                                     let bgClass = 'bg-white';
                                     
                                     if (isSelectedInBatch) {
                                         bgClass = 'bg-blue-50';
                                     }
                                     if (pendingProject && !isBooting && !isRunning) {
                                         borderClass = 'border-yellow-400 border-dashed';
                                         bgClass = 'bg-yellow-50';
                                     }
                                     
                                     let isClickable = !isOffline;
                                     if (isRunning && !isBatchMode) isClickable = false;

                                     return (
                                         <div 
                                            key={machine.id}
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
                                             {/* Left Side: Thumbnail/Icon */}
                                             <div className="flex gap-3">
                                                 <div className={`w-36 h-24 rounded-lg overflow-hidden relative flex items-center justify-center transition-colors shrink-0 ${isRunning ? 'bg-black' : 'bg-gray-100'}`}>
                                                     {isRunning ? (
                                                         <div className="w-full h-full relative group/thumb">
                                                            <ProjectThumbnail project={currentProject} className="w-full h-full opacity-80 group-hover/thumb:opacity-60 transition-opacity" />
                                                            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover/thumb:opacity-100 transition-opacity">
                                                                <Play size={24} className="text-white fill-current" />
                                                            </div>
                                                            <div className="absolute top-1 left-1 bg-black/60 text-white text-[9px] px-1 rounded backdrop-blur-sm">{currentProject?.type}</div>
                                                            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-2 pt-6">
                                                                <div className="text-[10px] font-bold text-white leading-tight truncate">{currentProject?.name}</div>
                                                            </div>
                                                         </div>
                                                     ) : isBooting ? (
                                                         <div className="w-full h-full flex flex-col items-center justify-center bg-gray-50">
                                                             <RefreshCw size={24} className="text-primary animate-spin mb-1" />
                                                             <span className="text-[10px] text-gray-500 font-bold">启动中...</span>
                                                         </div>
                                                     ) : (
                                                         <div className="w-full h-full flex flex-col items-center justify-center text-gray-400 gap-1">
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
                                                 
                                                 {/* Right: Info */}
                                                 <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5 border-l border-gray-100 pl-3">
                                                     <div>
                                                         <div className="flex justify-between items-start mb-1">
                                                             <h3 className="font-bold text-gray-800 text-sm truncate pr-2" title={machine.name}>{machine.name}</h3>
                                                             {/* Status Dot */}
                                                             <div className={`shrink-0 w-2 h-2 rounded-full ${isOffline ? 'bg-gray-300' : (isBooting || isRunning ? 'bg-green-500 animate-pulse' : (pendingProject ? 'bg-yellow-400 animate-pulse' : 'bg-slate-300'))}`}></div>
                                                         </div>
                                                         <div className="text-xs text-gray-400 font-mono tracking-tight flex items-center gap-1">
                                                             <Server size={10} />
                                                             {machine.ip}<span className="text-gray-300">:</span>{machine.port}
                                                         </div>
                                                     </div>

                                                     {/* Actions */}
                                                     <div className="flex items-center justify-end gap-1.5 mt-2">
                                                         {!isBatchMode && (
                                                             isRunning ? (
                                                                 <>
                                                                    <button onClick={(e) => restartNode(machine, e)} className="p-1.5 bg-blue-50 text-blue-500 rounded hover:bg-blue-100 transition-colors" title="重启"><RotateCcw size={14} /></button>
                                                                    <button onClick={(e) => { e.stopPropagation(); setKillCandidate(machine); }} className="p-1.5 bg-red-50 text-red-500 rounded hover:bg-red-100 transition-colors" title="停止"><Square size={14} fill="currentColor" /></button>
                                                                 </>
                                                             ) : !isBooting && (
                                                                 <>
                                                                     <button onClick={(e) => openEditModal(machine, e)} className="p-1.5 hover:bg-gray-100 text-gray-400 hover:text-gray-600 rounded transition-colors" title="编辑"><Edit2 size={14} /></button>
                                                                     <button onClick={(e) => promptDeleteNode(machine, e)} className="p-1.5 hover:bg-red-50 text-gray-400 hover:text-red-500 rounded transition-colors" title="删除"><Trash2 size={14} /></button>
                                                                 </>
                                                             )
                                                         )}
                                                     </div>
                                                 </div>
                                             </div>
                                         </div>
                                     );
                                 })}
                             </div>
                             
                             {/* Batch Action Bar */}
                             {pendingCount > 0 && (
                                 <div className="absolute bottom-6 left-6 right-6 z-20 animate-in slide-in-from-bottom-4 fade-in">
                                     <button onClick={commitLaunches} className="w-full py-4 rounded-xl shadow-xl flex items-center justify-center gap-3 text-white font-bold text-lg hover:scale-[1.02] active:scale-[0.98] transition-all" style={{ backgroundColor: THEME_COLOR }}>
                                         <Rocket size={24} className="animate-pulse" />
                                         执行启动计划 ({pendingCount})
                                     </button>
                                 </div>
                             )}
                        </aside>
    </div>
    </div>

            {/* Modals */}
            {killCandidate && ( <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in"><div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-red-100 relative overflow-hidden"><div className="absolute top-0 left-0 w-full h-2 bg-red-500"></div><div className="flex flex-col items-center text-center mb-6"><div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4 text-red-500"><AlertTriangle size={32} /></div><h3 className="text-xl font-bold text-gray-800">终止进程确认</h3><p className="text-gray-500 mt-2 text-sm">您确定要强制关闭 <span className="font-bold text-gray-800">{killCandidate.name}</span> 的进程吗？<br /><span className="text-red-500 font-bold text-xs">未保存的数据将会丢失。</span></p></div><div className="flex gap-3"><button onClick={() => setKillCandidate(null)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button><button onClick={() => killProcess(killCandidate.id)} className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold shadow-lg shadow-red-500/30 transition-all flex items-center justify-center gap-2"><Power size={18} />确认终止</button></div></div></div> )}
            
            {showGlobalKillModal && ( <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in"><div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-red-100 relative overflow-hidden"><div className="absolute top-0 left-0 w-full h-2 bg-red-500"></div><div className="flex flex-col items-center text-center mb-6"><div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4 text-red-500"><AlertTriangle size={32} /></div><h3 className="text-xl font-bold text-gray-800">紧急停止确认</h3><p className="text-gray-500 mt-2 text-sm">您即将强制关闭所有运行中的机器进程。<br /><span className="text-red-500 font-bold">所有未保存的数据将会丢失。</span></p></div><div className="flex gap-3"><button onClick={() => setShowGlobalKillModal(false)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button><button onClick={confirmGlobalKill} className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold shadow-lg shadow-red-500/30 transition-all flex items-center justify-center gap-2"><Power size={18} />确认全部停止</button></div></div></div> )}
            
            {showClearNodesModal && ( <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in"><div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-orange-200 relative overflow-hidden"><div className="absolute top-0 left-0 w-full h-2 bg-orange-500"></div><div className="flex flex-col items-center text-center mb-6"><div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mb-4 text-orange-500"><Trash2 size={32} /></div><h3 className="text-xl font-bold text-gray-800">清空列表确认</h3><p className="text-gray-500 mt-2 text-sm">您确定要清空所有计算节点吗？<br /><span className="text-orange-600 font-bold text-xs">此操作不可撤销。</span></p></div><div className="flex gap-3"><button onClick={() => setShowClearNodesModal(false)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button><button onClick={confirmClearAllNodes} className="flex-1 py-3 bg-orange-500 hover:bg-orange-600 text-white rounded-lg font-bold shadow-lg shadow-orange-500/30 transition-all flex items-center justify-center gap-2"><Trash2 size={18} />确认清空</button></div></div></div> )}
            
            {showMachineModal && ( <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in"><div className="bg-white p-8 rounded-2xl shadow-2xl w-96 border border-gray-100 transform transition-all scale-100"><h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-gray-800"><Server size={24} style={{ color: THEME_COLOR }} />{editingNode ? '编辑计算节点' : '添加新计算节点'}</h3><div className="space-y-4"><div><label className="block text-sm font-medium text-gray-700 mb-1">机器名称</label><input type="text" value={newMachineForm.name} onChange={e => setNewMachineForm({...newMachineForm, name: e.target.value})} className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" placeholder="例如: Render Node 05" /></div><div><label className="block text-sm font-medium text-gray-700 mb-1">IP 地址</label><input type="text" value={newMachineForm.ip} onChange={e => setNewMachineForm({...newMachineForm, ip: e.target.value})} className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" placeholder="192.168.1.XXX" /></div><div><label className="block text-sm font-medium text-gray-700 mb-1">端口 (Port)</label><input type="text" value={newMachineForm.port} onChange={e => setNewMachineForm({...newMachineForm, port: e.target.value})} className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" placeholder="例如: 8888" /></div><div className="flex gap-3 pt-4"><button onClick={() => setShowMachineModal(false)} className="flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors">取消</button><button onClick={handleSaveMachine} className="flex-1 py-2 text-white rounded-lg font-medium transition-colors shadow-lg hover:shadow-xl hover:-translate-y-0.5" style={{ backgroundColor: THEME_COLOR }}>保存</button></div></div></div></div> )}

            {showProjectModal && ( <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in"><div className="bg-white p-8 rounded-2xl shadow-2xl w-[500px] border border-gray-100 transform transition-all scale-100"><h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-gray-800"><FilePlus size={24} style={{ color: THEME_COLOR }} />上传项目资源</h3><div className="space-y-4"><div><label className="block text-sm font-medium text-gray-700 mb-1">项目文件 (支持 .vpb, .wire)</label>{!newProjectForm.fileName ? (<div className="flex items-center justify-center w-full"><label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors"><div className="flex flex-col items-center justify-center pt-5 pb-6"><Upload className="w-8 h-8 mb-3 text-gray-400" /><p className="mb-2 text-sm text-gray-500"><span className="font-semibold">点击上传</span> 或拖拽文件</p><p className="text-xs text-gray-400">自动识别 VRED (.vpb) 或 Alias (.wire)</p></div><input type="file" ref={fileInputRef} className="hidden" onChange={handleFileSelect} accept=".vpb,.wire,.sb" /></label></div>) : (<div className="w-full p-4 border border-primary bg-primary/5 rounded-lg flex items-center justify-between"><div className="flex items-center gap-3"><div className="p-2 bg-white rounded-md shadow-sm text-primary"><FileText size={20} /></div><div><div className="text-sm font-bold text-gray-800 truncate max-w-[200px]">{newProjectForm.fileName}</div><div className="flex gap-2 text-xs text-gray-500"><span className="font-mono">{newProjectForm.size}</span><span>•</span><span className="font-bold text-primary">{newProjectForm.type || '未知格式'}</span></div></div></div><button onClick={clearFile} className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors" title="移除文件"><Trash2 size={18} /></button></div>)}</div><div><label className="block text-sm font-medium text-gray-700 mb-1">项目封面 (可选)</label>{!newProjectForm.thumbnail ? (<div className="flex items-center justify-center w-full"><label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors"><div className="flex flex-col items-center justify-center pt-5 pb-6"><Upload className="w-8 h-8 mb-3 text-gray-400" /><p className="mb-2 text-sm text-gray-500"><span className="font-semibold">点击上传</span> 或拖拽图片</p><p className="text-xs text-gray-400">支持 JPG, PNG</p></div><input type="file" ref={thumbnailInputRef} className="hidden" onChange={handleThumbnailSelect} accept="image/*" /></label></div>) : (<div className="w-full p-4 border border-primary bg-primary/5 rounded-lg flex items-center justify-between"><div className="flex items-center gap-3"><img src={newProjectForm.thumbnail} alt="Thumbnail" className="w-16 h-12 object-cover rounded-md border border-gray-200" /><div><div className="text-sm font-bold text-gray-800">封面已上传</div><div className="text-xs text-gray-500">点击右侧按钮移除</div></div></div><button onClick={clearThumbnail} className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors" title="移除封面"><Trash2 size={18} /></button></div>)}</div><div><label className="block text-sm font-medium text-gray-700 mb-1">项目显示名称</label><input type="text" value={newProjectForm.name} onChange={e => setNewProjectForm({...newProjectForm, name: e.target.value})} className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" placeholder="例如: Audi E-Tron Concept" /></div><div className="flex gap-3 pt-4"><button onClick={() => setShowProjectModal(false)} className="flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors">取消</button><button onClick={handleAddProject} disabled={!newProjectForm.fileName || !newProjectForm.name} className="flex-1 py-2 text-white rounded-lg font-medium transition-colors shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed" style={{ backgroundColor: THEME_COLOR }}>添加项目</button></div></div></div></div> )}
            
            {nodeToDelete && ( <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in"><div className="bg-white p-8 rounded-2xl shadow-2xl w-[400px] border border-red-100 relative overflow-hidden"><div className="absolute top-0 left-0 w-full h-2 bg-red-500"></div><div className="flex flex-col items-center text-center mb-6"><div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4 text-red-500"><AlertTriangle size={32} /></div><h3 className="text-xl font-bold text-gray-800">删除节点确认</h3><p className="text-gray-500 mt-2 text-sm">您确定要删除节点 <span className="font-bold text-gray-800">{nodeToDelete.name}</span> 吗？<br />此操作无法撤销。</p></div><div className="flex gap-3"><button onClick={() => setNodeToDelete(null)} className="flex-1 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-bold transition-colors">取消</button><button onClick={confirmDeleteNode} className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold shadow-lg shadow-red-500/30 transition-all flex items-center justify-center gap-2"><Trash2 size={18} />确认删除</button></div></div></div> )}
        </div>
    );
};

export default App;
