import React, { useState, useMemo, useRef, useEffect } from 'react';
import LoginScreen from './components/LoginScreen';
import { THEME_COLOR, MR_TOOLS } from './constants';
import { RADIAL_MENU_CORE, TOOL_IMPLEMENTATIONS } from './utils/vredPy';
import { api } from './services/api';
import { uploadFile, TUSD_PATH_PREFIX } from './services/upload';

// Components
import MonitorWall from './components/MonitorWall';
import StreamingView from './components/StreamingView';
import MachineList from './components/MachineList';
import Header from './components/Header';
import ProjectWorkspace from './components/ProjectWorkspace';
import ScriptToolsPanel from './components/ScriptToolsPanel';
import NotificationToast from './components/NotificationToast';
import MachineModal from './components/MachineModal';
import ProjectModal from './components/ProjectModal';
import { 
    KillConfirmModal, 
    GlobalKillConfirmModal, 
    ClearNodesConfirmModal, 
    DeleteNodeConfirmModal 
} from './components/ConfirmationModals';

const App = () => {
    // --- State: Auth ---
    const [isLoggedIn, setIsLoggedIn] = useState(() => !!localStorage.getItem('jwt'));
    const [loginForm, setLoginForm] = useState({ username: '', password: '' });
    const [currentUser, setCurrentUser] = useState(() => {
        const saved = localStorage.getItem('currentUser');
        return saved ? JSON.parse(saved) : null;
    });

    // --- State: Data ---
    const [projects, setProjects] = useState([]);
    const [machines, setMachines] = useState([]);

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

    // --- State: Upload Progress ---
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);

    // --- State: Process & Streaming ---
    const [runningMachines, setRunningMachines] = useState({}); // { machineId: projectId }
    const [bootingMachines, setBootingMachines] = useState(new Set()); // Set<machineId>
    const [pendingLaunches, setPendingLaunches] = useState({}); // { machineId: projectId } (Staged for batch launch)
    const [streamingMachineId, setStreamingMachineId] = useState(null);
    const [machineScripts, setMachineScripts] = useState({}); // { machineId: Set<scriptId> }
    const [showScriptTools, setShowScriptTools] = useState(false);

    // --- State: Modals ---
    const [showProjectModal, setShowProjectModal] = useState(false);
    const [showMachineModal, setShowMachineModal] = useState(false);
    const [showClearNodesModal, setShowClearNodesModal] = useState(false);
    const [showGlobalKillModal, setShowGlobalKillModal] = useState(false);
    
    const [killCandidate, setKillCandidate] = useState(null);
    const [nodeToDelete, setNodeToDelete] = useState(null);
    const [editingNode, setEditingNode] = useState(null);
    const [replacingProject, setReplacingProject] = useState(null);

    // --- State: Forms ---
    const [newProjectForm, setNewProjectForm] = useState({ name: '', type: 'VRED', fileName: '', size: '', thumbnail: null, tags: '', file: null });
    const [newMachineForm, setNewMachineForm] = useState({ name: '', ip: '', port: '' });
    const fileInputRef = useRef(null);
    const thumbnailInputRef = useRef(null);
    const replaceFileInputRef = useRef(null);

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

    // --- Effect: Load Data ---
    useEffect(() => {
        if (isLoggedIn) {
            loadData();
            const interval = setInterval(loadData, 2000);
            return () => clearInterval(interval);
        }
    }, [isLoggedIn]);

    const loadData = async () => {
        try {
            const [p, m, procs] = await Promise.all([
                api.projects.list(), 
                api.machines.list(),
                api.processes.list()
            ]);
            setProjects(p || []);
            
            const mappedMachines = (m || []).map(mach => ({
                ...mach,
                currentProject: mach.current_project?.id || null
            }));
            setMachines(mappedMachines);

            // Sync runningMachines from processes
            const running = {};
            const booting = new Set();
            
            if (procs && Array.isArray(procs)) {
                procs.forEach(proc => {
                    if (proc.machine?.id && proc.project?.id) {
                        if (proc.status === 'running') {
                            running[proc.machine.id] = proc.project.id;
                        } else if (proc.status === 'starting') {
                            booting.add(proc.machine.id);
                            // Optionally also track project for starting
                            running[proc.machine.id] = proc.project.id; // Treat as running for UI binding? 
                            // Or better to separate? 
                            // If I put it in running, it shows as running.
                            // But I want to show it as booting.
                            // The UI logic uses runningMachines to determine if it's "occupied".
                        }
                    }
                });
            }
            setRunningMachines(running);
            // Merge backend booting with local pending booting, but remove those that are now running or stopped/error
            setBootingMachines(prev => {
                const next = new Set(prev);
                // Add confirmed starting
                booting.forEach(id => next.add(id));
                
                // Remove confirmed running/stopped/error
                if (procs && Array.isArray(procs)) {
                    procs.forEach(proc => {
                        if (proc.machine?.id && proc.status !== 'starting') {
                            next.delete(proc.machine.id);
                        }
                    });
                }
                return next;
            });
        } catch (e) {
            console.error("Failed to load data", e);
            // Don't show error immediately on load to avoid spam if server is down initially
        }
    };

    // --- Handlers: Auth ---
    const handleLogin = async (e) => {
        e.preventDefault();
        if (loginForm.username && loginForm.password) {
            try {
                const { jwt, user } = await api.auth.login(loginForm.username, loginForm.password);
                
                setIsLoggedIn(true);
                setCurrentUser(user);
                
                localStorage.setItem('jwt', jwt);
                localStorage.setItem('currentUser', JSON.stringify(user));
                
                addNotification('登录成功', 'success');
            } catch (e) {
                console.error(e);
                addNotification(e.message || '登录失败，请检查账号密码', 'error');
            }
        }
    };

    const handleLogout = () => {
        setIsLoggedIn(false);
        setCurrentUser(null);
        setLoginForm({ username: '', password: '' });
        localStorage.removeItem('jwt');
        localStorage.removeItem('currentUser');
    };

    // --- Handlers: Projects ---
    const handleAddProject = async () => {
        const projectName = newProjectForm.name || newProjectForm.fileName;
        if (!projectName || !newProjectForm.fileName) return;
        
        try {
            let filePath = '';
            if (newProjectForm.file) {
                setIsUploading(true);
                setUploadProgress(0);
                await uploadFile(newProjectForm.file, (bytesUploaded, bytesTotal) => {
                    const percentage = Math.round((bytesUploaded / bytesTotal) * 100);
                    setUploadProgress(percentage);
                });
                filePath = TUSD_PATH_PREFIX + newProjectForm.fileName;
                addNotification('文件上传成功', 'success');
            }

            const newProjectData = {
                name: projectName,
                type: newProjectForm.type,
                thumbnail: newProjectForm.thumbnail,
                size: newProjectForm.size,
                date: new Date().toISOString().split('T')[0],
                tags: newProjectForm.tags ? newProjectForm.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
                fileName: newProjectForm.fileName,
                filePath: filePath
            };
            
            const created = await api.projects.create(newProjectData);
            setProjects([created, ...projects]);
            setShowProjectModal(false);
            setNewProjectForm({ name: '', type: 'VRED', fileName: '', size: '', thumbnail: null, tags: '', file: null });
            addNotification(`项目 "${created.name}" 已添加`, 'success');
        } catch (e) {
            console.error(e);
            addNotification('添加项目失败: ' + (e.message || e), 'error');
        } finally {
            setIsUploading(false);
            setUploadProgress(0);
        }
    };

    const handleDeleteProject = async (projectId) => {
        const project = projects.find(p => p.id === projectId);
        if (!project) return;
        
        if (window.confirm('确定要删除该项目吗？')) {
            try {
                await api.projects.delete(project.documentId);
                setProjects(projects.filter(p => p.id !== projectId));
                if (activeProject === projectId) setActiveProject(null);
                addNotification('项目已删除', 'info');
            } catch (e) {
                console.error(e);
                addNotification('删除失败', 'error');
            }
        }
    };

    const handleRenameProject = async (projectId, newName) => {
        const project = projects.find(p => p.id === projectId);
        if (!project || !newName.trim()) return;

        try {
            const updated = await api.projects.update(project.documentId, { name: newName });
            setProjects(projects.map(p => p.id === projectId ? { ...p, name: updated.name } : p));
            addNotification(`项目已重命名为 "${newName}"`, 'success');
        } catch (e) {
            console.error(e);
            addNotification('重命名失败', 'error');
        }
    };

    const handleReplaceClick = (e, project) => {
        e.stopPropagation();
        setReplacingProject(project);
        if (replaceFileInputRef.current) {
            replaceFileInputRef.current.click();
        }
    };

    const handleReplaceFileSelect = async (e) => {
        const file = e.target.files[0];
        if (file && replacingProject) {
             let size = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
            if (file.size > 1024 * 1024 * 1024) size = (file.size / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
            
            let type = 'Unknown';
            if (file.name.endsWith('.vpb')) type = 'VRED';
            else if (file.name.endsWith('.wire')) type = 'Alias';

            try {
                setIsUploading(true);
                setUploadProgress(0);
                await uploadFile(file, (bytesUploaded, bytesTotal) => {
                     const percentage = Math.round((bytesUploaded / bytesTotal) * 100);
                     setUploadProgress(percentage);
                });
                const filePath = TUSD_PATH_PREFIX + file.name;
                addNotification('文件上传成功', 'success');

                const updateData = {
                    fileName: file.name,
                    size: size,
                    type: type !== 'Unknown' ? type : replacingProject.type,
                    filePath: filePath
                };

                const updated = await api.projects.update(replacingProject.documentId, updateData);
                setProjects(projects.map(p => p.id === replacingProject.id ? { 
                    ...p, 
                    ...updated
                } : p));
                
                addNotification(`项目 "${replacingProject.name}" 文件已替换`, 'success');
            } catch (e) {
                console.error(e);
                addNotification('替换文件失败: ' + (e.message || e), 'error');
            } finally {
                setIsUploading(false);
                setUploadProgress(0);
                setReplacingProject(null);
                if (replaceFileInputRef.current) replaceFileInputRef.current.value = '';
            }
        }
    };

    const handleFileSelect = (e) => {
        const file = e.target.files[0];
        if (file) {
            let size = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
            if (file.size > 1024 * 1024 * 1024) size = (file.size / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
            
            let type = 'Unknown';
            if (file.name.endsWith('.vpb')) type = 'VRED';
            else if (file.name.endsWith('.wire')) type = 'Alias';

            setNewProjectForm({ ...newProjectForm, fileName: file.name, size, type, file });
        }
    };
    
    const clearFile = (e) => {
        e.stopPropagation();
        setNewProjectForm({ ...newProjectForm, fileName: '', size: '' });
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const handleThumbnailSelect = async (e) => {
        const file = e.target.files[0];
        if (file) {
            try {
                addNotification('正在上传封面图...', 'info');
                const uploadedFiles = await api.upload(file);
                if (uploadedFiles && uploadedFiles.length > 0) {
                    const url = uploadedFiles[0].url;
                    setNewProjectForm({ ...newProjectForm, thumbnail: url });
                    addNotification('封面图上传成功', 'success');
                }
            } catch (e) {
                console.error(e);
                addNotification('封面图上传失败', 'error');
            }
        }
    };

    const clearThumbnail = (e) => {
        e.stopPropagation();
        setNewProjectForm({ ...newProjectForm, thumbnail: null });
        if (thumbnailInputRef.current) thumbnailInputRef.current.value = '';
    };

    // --- Handlers: Machines ---
    const handleSaveMachine = async () => {
        if (!newMachineForm.name || !newMachineForm.ip) return;
        
        try {
            if (editingNode) {
                const updated = await api.machines.update(editingNode.documentId, newMachineForm);
                setMachines(machines.map(m => m.id === editingNode.id ? { ...m, ...updated, currentProject: m.currentProject } : m));
                addNotification(`节点 "${newMachineForm.name}" 更新成功`, 'success');
            } else {
                const newMachineData = {
                    ...newMachineForm,
                    status: 'idle',
                    health: 'good'
                };
                const created = await api.machines.create(newMachineData);
                setMachines([...machines, { ...created, currentProject: null }]);
                addNotification(`节点 "${newMachineForm.name}" 已添加`, 'success');
            }
            setShowMachineModal(false);
            setNewMachineForm({ name: '', ip: '', port: '' });
            setEditingNode(null);
        } catch (e) {
            console.error(e);
            addNotification('保存节点失败', 'error');
        }
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

    const confirmDeleteNode = async () => {
        if (nodeToDelete) {
            try {
                await api.machines.delete(nodeToDelete.id);
                setMachines(machines.filter(m => m.id !== nodeToDelete.id));
                // Also cleanup states
                if (activeMachineId === nodeToDelete.id) setActiveMachineId(null);
                setNodeToDelete(null);
                addNotification('节点已删除', 'info');
            } catch (e) {
                console.error(e);
                addNotification('删除失败', 'error');
            }
        }
    };
    
    const confirmClearAllNodes = async () => {
        // Warning: This is a heavy operation, doing it client-side one by one
        try {
            await Promise.all(machines.map(m => api.machines.delete(m.id)));
            setMachines([]);
            setActiveMachineId(null);
            setStreamingMachineId(null);
            setShowClearNodesModal(false);
            addNotification('所有节点已清空', 'warning');
        } catch (e) {
            console.error(e);
            addNotification('清空失败', 'error');
        }
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

    const openScriptTools = (machine) => {
        setActiveMachineId(machine.id);
        setStreamingMachineId(null);
        setShowMonitorWall(false);
        setIsBatchMode(false);
        setShowScriptTools(true);

        // Inject Radial Menu Core (Async)
        api.processes.executePython(machine.ip, machine.port, RADIAL_MENU_CORE)
            .then(() => console.log('Radial Menu Core Injected'))
            .catch(e => console.error('Radial Menu Core Injection Failed', e));
    };

    const handleInjectScripts = (scriptIds) => {
        // Prepare Python Code
        let pythonCode = "";
        scriptIds.forEach(id => {
            const impl = TOOL_IMPLEMENTATIONS[id];
            if (impl) {
                pythonCode += impl + "\n";
                const tool = MR_TOOLS.find(t => t.id === id);
                if (tool) {
                     pythonCode += `if 'radial_menu_instance' in globals(): radial_menu_instance.add_tool("${id}", "${tool.name}", tool_${id})\n`;
                }
            }
        });

        if (isBatchMode && selectedBatchIds.size > 0) {
            // Batch injection
            setMachineScripts(prev => {
                const next = { ...prev };
                selectedBatchIds.forEach(id => {
                    const current = next[id] ? new Set(next[id]) : new Set();
                    scriptIds.forEach(s => current.add(s));
                    next[id] = current;
                });
                return next;
            });

            // Execute on all selected machines
            const targets = machines.filter(m => selectedBatchIds.has(m.id));
            targets.forEach(m => {
                 api.processes.executePython(m.ip, m.port, pythonCode)
                    .catch(e => console.error(`Failed to inject on ${m.name}`, e));
            });

            addNotification(`已向 ${selectedBatchIds.size} 台机器注入 ${scriptIds.length} 个脚本`, 'success');
        } else if (activeMachineId) {
            // Single injection
            setMachineScripts(prev => {
                const current = prev[activeMachineId] ? new Set(prev[activeMachineId]) : new Set();
                scriptIds.forEach(s => current.add(s));
                return { ...prev, [activeMachineId]: current };
            });

            // Execute
            const machine = machines.find(m => m.id === activeMachineId);
            if (machine) {
                api.processes.executePython(machine.ip, machine.port, pythonCode)
                   .catch(e => console.error(`Failed to inject on ${machine.name}`, e));
            }

            addNotification(`脚本注入成功`, 'success');
        }
    };

    const handleResetScripts = () => {
        if (isBatchMode && selectedBatchIds.size > 0) {
            setMachineScripts(prev => {
                const next = { ...prev };
                selectedBatchIds.forEach(id => {
                    delete next[id];
                });
                return next;
            });
            addNotification('已清除选中机器的脚本工具', 'info');
        } else if (activeMachineId) {
            setMachineScripts(prev => {
                const next = { ...prev };
                delete next[activeMachineId];
                return next;
            });
            addNotification('已清除当前机器的脚本工具', 'info');
        }
    };

    // --- Handlers: Process Control ---
    const commitLaunches = async () => {
        const machineIds = Object.keys(pendingLaunches);
        if (machineIds.length === 0) return;

        // Move to booting
        const newBooting = new Set(bootingMachines);
        machineIds.forEach(id => newBooting.add(id));
        setBootingMachines(newBooting);

        // Store launches to process locally to optimize UI
        const launchesToProcess = { ...pendingLaunches };
        setPendingLaunches({});

        // Clear selections
        setActiveProject(null);
        setActiveMachineId(null);
        setSelectedBatchIds(new Set());

        addNotification(`正在启动 ${machineIds.length} 个任务...`, 'info');

        // Execute Launches
        try {
            await Promise.all(machineIds.map(async (machineId) => {
                const projectId = launchesToProcess[machineId];
                try {
                    await api.processes.launch(machineId, projectId);
                    
                    // Success: Update UI
                    setBootingMachines(prev => {
                        const next = new Set(prev);
                        next.delete(machineId);
                        return next;
                    });
                    setRunningMachines(prev => ({ ...prev, [machineId]: projectId }));
                    addNotification(`节点 ${machines.find(m => m.id === machineId)?.name || machineId} 启动完成`, 'success');
                    
                    // Reload machines to get updated status/PID
                    // loadData(); // Optional, might cause UI flicker
                } catch (e) {
                    console.error(`Failed to launch on ${machineId}`, e);
                    setBootingMachines(prev => {
                        const next = new Set(prev);
                        next.delete(machineId);
                        return next;
                    });
                    addNotification(`节点 ${machineId} 启动失败: ${e.message}`, 'error');
                }
            }));
        } catch (e) {
            console.error(e);
        }
    };

    const restartNode = (machine, e) => {
        e.stopPropagation();
        if (!runningMachines[machine.id]) return;
        
        // This would require a restart API or stop+launch. 
        // For now, let's just use the current flow which is mostly visual in original code.
        // Implementing proper restart:
        // 1. Stop
        // 2. Launch
        
        const projectId = runningMachines[machine.id];
        
        // Optimistic UI updates
        setRunningMachines(prev => {
            const next = { ...prev };
            delete next[machine.id];
            return next;
        });
        setBootingMachines(prev => new Set(prev).add(machine.id));
        
        // Async restart
        (async () => {
            try {
                // await api.processes.stop(machine.id); // Assuming we can find process ID
                // For now, we launch directly which might fail if port used.
                // Ideally, backend handles restart.
                
                await api.processes.launch(machine.id, projectId);
                
                setBootingMachines(prev => {
                    const next = new Set(prev);
                    next.delete(machine.id);
                    return next;
                });
                setRunningMachines(prev => ({ ...prev, [machine.id]: projectId }));
                addNotification(`${machine.name} 重启完成`, 'success');
            } catch (e) {
                 setBootingMachines(prev => {
                    const next = new Set(prev);
                    next.delete(machine.id);
                    return next;
                });
                addNotification(`${machine.name} 重启失败`, 'error');
            }
        })();
    };

    const killProcess = async (target) => {
        if (Array.isArray(target)) {
            // Batch Kill
            try {
                // Call batch kill API
                await api.processes.batchKill(target);
                
                setRunningMachines(prev => {
                    const next = { ...prev };
                    target.forEach(id => delete next[id]);
                    return next;
                });
                if (target.includes(streamingMachineId)) setStreamingMachineId(null);
                addNotification(`${target.length} 个进程已终止`, 'success');
            } catch (e) {
                console.error(e);
                addNotification('批量终止失败', 'error');
            }
        } else {
            // Single Kill
            const machineId = target;
            try {
                await api.processes.kill(machineId);
                
                setRunningMachines(prev => {
                    const next = { ...prev };
                    delete next[machineId];
                    return next;
                });
                setKillCandidate(null);
                if (streamingMachineId === machineId) setStreamingMachineId(null);
                addNotification('进程已终止', 'success');
            } catch (e) {
                console.error(e);
                addNotification('终止进程失败', 'error');
            }
        }
    };
    
    const confirmGlobalKill = async () => {
        try {
            await api.processes.killAll();
            setRunningMachines({});
            setStreamingMachineId(null);
            setShowGlobalKillModal(false);
            addNotification('所有进程已终止', 'success');
        } catch (e) {
            console.error(e);
            addNotification('一键终止失败', 'error');
        }
        setBootingMachines(new Set());
        setPendingLaunches({});
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
            (p.tags && p.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase())))
        );

        if (selectedFilterTags.size > 0) {
             result = result.filter(p => p.tags && p.tags.some(t => selectedFilterTags.has(t)));
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

    if (!isLoggedIn) {
        return <LoginScreen handleLogin={handleLogin} loginForm={loginForm} setLoginForm={setLoginForm} />;
    }

    return (
        <div className="flex items-center justify-center h-screen w-screen bg-gray-100 p-4 font-sans select-none relative text-sm text-gray-600">
            {/* Notification Toast */}
            <NotificationToast notifications={notifications} />

            {/* Top Header */}
            <div className="w-full h-full bg-white shadow-2xl rounded-2xl overflow-hidden flex flex-col relative border border-gray-200">
                {streamingMachineId && runningMachines[streamingMachineId] && (
                    <StreamingView 
                        streamingMachineId={streamingMachineId}
                        setStreamingMachineId={setStreamingMachineId}
                        machines={machines}
                        projects={projects}
                        runningMachines={runningMachines}
                        setKillCandidate={setKillCandidate}
                    />
                )}
                <Header currentUser={currentUser} handleLogout={handleLogout} />

                <div className="flex-1 flex overflow-hidden bg-gray-50">
                    {showMonitorWall ? (
                        <MonitorWall 
                            machines={machines}
                            runningMachines={runningMachines}
                            projects={projects}
                            setShowMonitorWall={setShowMonitorWall}
                            setStreamingMachineId={setStreamingMachineId}
                            handleGlobalKillClick={handleGlobalKillClick}
                            setKillCandidate={setKillCandidate}
                        />
                    ) : showScriptTools ? (
                        <ScriptToolsPanel 
                            machine={machines.find(m => m.id === activeMachineId)}
                            isBatchMode={isBatchMode}
                            selectedBatchCount={selectedBatchIds.size}
                            onBack={() => setShowScriptTools(false)}
                            onInject={handleInjectScripts}
                            onReset={handleResetScripts}
                            onKill={() => killProcess(isBatchMode ? Array.from(selectedBatchIds) : activeMachineId)}
                        />
                    ) : (
                        /* Main Content Area */
                        <ProjectWorkspace 
                            setShowMonitorWall={setShowMonitorWall}
                            searchQuery={searchQuery}
                            setSearchQuery={setSearchQuery}
                            sortBy={sortBy}
                            setSortBy={setSortBy}
                            sortOrder={sortOrder}
                            setSortOrder={setSortOrder}
                            showTagFilter={showTagFilter}
                            setShowTagFilter={setShowTagFilter}
                            selectedFilterTags={selectedFilterTags}
                            setSelectedFilterTags={setSelectedFilterTags}
                            viewMode={viewMode}
                            setViewMode={setViewMode}
                            setShowProjectModal={setShowProjectModal}
                            allAvailableTags={allAvailableTags}
                            projects={projects}
                            filteredProjects={filteredProjects}
                            activeProject={activeProject}
                            handleProjectClick={handleProjectClick}
                            runningMachines={runningMachines}
                            handleDeleteProject={handleDeleteProject}
                            handleRenameProject={handleRenameProject}
                            handleReplaceClick={handleReplaceClick}
                            isUploading={isUploading}
                            uploadProgress={uploadProgress}
                        />
                    )}
                    
                    {/* Right Sidebar: Machine List */}
                    <MachineList 
                        machines={machines}
                        isBatchMode={isBatchMode}
                        selectedBatchIds={selectedBatchIds}
                        selectAllIdleNodes={selectAllIdleNodes}
                        selectAllRunningNodes={selectAllRunningNodes}
                        toggleBatchMode={toggleBatchMode}
                        handleGlobalKillClick={handleGlobalKillClick}
                        setShowClearNodesModal={setShowClearNodesModal}
                        openAddModal={openAddModal}
                        runningMachines={runningMachines}
                        bootingMachines={bootingMachines}
                        pendingLaunches={pendingLaunches}
                        projects={projects}
                        activeMachineId={activeMachineId}
                        handleMachineClick={handleMachineClick}
                        commitLaunches={commitLaunches}
                        restartNode={restartNode}
                        setKillCandidate={setKillCandidate}
                        openEditModal={openEditModal}
                        promptDeleteNode={promptDeleteNode}
                        setStreamingMachineId={setStreamingMachineId}
                        setActiveMachineId={setActiveMachineId}
                        setShowMonitorWall={setShowMonitorWall}
                        setIsBatchMode={setIsBatchMode}
                        openScriptTools={openScriptTools}
                    />
                </div>
            </div>

            {/* Hidden Input for Replace */}
            <input type="file" ref={replaceFileInputRef} onChange={handleReplaceFileSelect} className="hidden" />

            {/* Modals */}
            <KillConfirmModal 
                killCandidate={killCandidate} 
                setKillCandidate={setKillCandidate} 
                killProcess={killProcess} 
            />
            
            <GlobalKillConfirmModal 
                showGlobalKillModal={showGlobalKillModal} 
                setShowGlobalKillModal={setShowGlobalKillModal} 
                confirmGlobalKill={confirmGlobalKill} 
            />
            
            <ClearNodesConfirmModal 
                showClearNodesModal={showClearNodesModal} 
                setShowClearNodesModal={setShowClearNodesModal} 
                confirmClearAllNodes={confirmClearAllNodes} 
            />
            
            <MachineModal 
                showMachineModal={showMachineModal} 
                setShowMachineModal={setShowMachineModal} 
                editingNode={editingNode} 
                newMachineForm={newMachineForm} 
                setNewMachineForm={setNewMachineForm} 
                handleSaveMachine={handleSaveMachine} 
            />

            <ProjectModal 
                showProjectModal={showProjectModal} 
                setShowProjectModal={setShowProjectModal} 
                newProjectForm={newProjectForm} 
                setNewProjectForm={setNewProjectForm} 
                handleFileSelect={handleFileSelect} 
                clearFile={clearFile} 
                fileInputRef={fileInputRef} 
                handleThumbnailSelect={handleThumbnailSelect} 
                clearThumbnail={clearThumbnail} 
                thumbnailInputRef={thumbnailInputRef} 
                handleAddProject={handleAddProject} 
                isUploading={isUploading}
                uploadProgress={uploadProgress}
            />
            
            <DeleteNodeConfirmModal 
                nodeToDelete={nodeToDelete} 
                setNodeToDelete={setNodeToDelete} 
                confirmDeleteNode={confirmDeleteNode} 
            />
        </div>
    );
};

export default App;
