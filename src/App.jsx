import React, { useState, useMemo, useRef } from 'react';
import LoginScreen from './components/LoginScreen';
import { INITIAL_PROJECTS, INITIAL_MACHINES, THEME_COLOR } from './constants';

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
    const [newProjectForm, setNewProjectForm] = useState({ name: '', type: 'VRED', fileName: '', size: '', thumbnail: null });
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

    const handleDeleteProject = (projectId) => {
        if (window.confirm('确定要删除该项目吗？')) {
            setProjects(projects.filter(p => p.id !== projectId));
            if (activeProject === projectId) setActiveProject(null);
            addNotification('项目已删除', 'info');
        }
    };

    const handleRenameProject = (projectId, newName) => {
        if (!newName.trim()) return;
        setProjects(projects.map(p => p.id === projectId ? { ...p, name: newName } : p));
        addNotification(`项目已重命名为 "${newName}"`, 'success');
    };

    const handleReplaceClick = (e, project) => {
        e.stopPropagation();
        setReplacingProject(project);
        if (replaceFileInputRef.current) {
            replaceFileInputRef.current.click();
        }
    };

    const handleReplaceFileSelect = (e) => {
        const file = e.target.files[0];
        if (file && replacingProject) {
             let size = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
            if (file.size > 1024 * 1024 * 1024) size = (file.size / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
            
            let type = 'Unknown';
            if (file.name.endsWith('.vpb')) type = 'VRED';
            else if (file.name.endsWith('.wire')) type = 'Alias';

            setProjects(projects.map(p => p.id === replacingProject.id ? { 
                ...p, 
                fileName: file.name,
                size: size,
                type: type !== 'Unknown' ? type : p.type // Update type if detected
            } : p));
            
            addNotification(`项目 "${replacingProject.name}" 文件已替换`, 'success');
            setReplacingProject(null);
            if (replaceFileInputRef.current) replaceFileInputRef.current.value = '';
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

    const openScriptTools = (machine) => {
        setActiveMachineId(machine.id);
        setStreamingMachineId(null);
        setShowMonitorWall(false);
        setIsBatchMode(false);
        setShowScriptTools(true);
    };

    const handleInjectScripts = (scriptIds) => {
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
            addNotification(`已向 ${selectedBatchIds.size} 台机器注入 ${scriptIds.length} 个脚本`, 'success');
        } else if (activeMachineId) {
            // Single injection
            setMachineScripts(prev => {
                const current = prev[activeMachineId] ? new Set(prev[activeMachineId]) : new Set();
                scriptIds.forEach(s => current.add(s));
                return { ...prev, [activeMachineId]: current };
            });
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

    const killProcess = (target) => {
        if (Array.isArray(target)) {
            // Batch Kill
            setRunningMachines(prev => {
                const next = { ...prev };
                target.forEach(id => delete next[id]);
                return next;
            });
            if (target.includes(streamingMachineId)) setStreamingMachineId(null);
            addNotification(`${target.length} 个进程已终止`, 'warning');
        } else {
            // Single Kill
            const machineId = target;
            setRunningMachines(prev => {
                const next = { ...prev };
                delete next[machineId];
                return next;
            });
            setKillCandidate(null);
            if (streamingMachineId === machineId) setStreamingMachineId(null);
            addNotification('进程已终止', 'warning');
        }
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
