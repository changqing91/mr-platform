import React, { useState, useRef, useEffect } from 'react';
import { LayoutDashboard, Activity, Search, Calendar, Check, Edit2, Upload, Trash2, Link } from 'lucide-react';
import ResourceDetail from './ResourceDetail';
import ProjectThumbnail from './ProjectThumbnail';
import { THEME_COLOR } from '../constants';

const ProjectWorkspace = ({
    setShowMonitorWall,
    searchQuery,
    setSearchQuery,
    sortBy,
    setSortBy,
    sortOrder,
    setSortOrder,
    showTagFilter,
    setShowTagFilter,
    selectedFilterTags,
    setSelectedFilterTags,
    viewMode,
    setViewMode,
    setShowProjectModal,
    allAvailableTags,
    projects,
    filteredProjects,
    activeProject,
    handleProjectClick,
    runningMachines,
    handleDeleteProject,
    handleRenameProject,
    handleReplaceClick
}) => {
    // --- Inline Rename State ---
    const [editingProjectId, setEditingProjectId] = useState(null);
    const [editName, setEditName] = useState('');
    const editInputRef = useRef(null);

    const startEditing = (project, e) => {
        e.stopPropagation();
        setEditingProjectId(project.id);
        setEditName(project.name);
    };

    const cancelEditing = () => {
        setEditingProjectId(null);
        setEditName('');
    };

    const saveEditing = () => {
        if (editingProjectId && editName.trim()) {
            handleRenameProject(editingProjectId, editName.trim());
        }
        cancelEditing();
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            saveEditing();
        } else if (e.key === 'Escape') {
            cancelEditing();
        }
    };

    // Auto-focus input when editing starts
    useEffect(() => {
        if (editingProjectId && editInputRef.current) {
            editInputRef.current.focus();
            editInputRef.current.select();
        }
    }, [editingProjectId]);

    return (
        <main className="flex-1 flex flex-col min-w-0 bg-gray-50">
            {/* Sub Header / Toolbar */}
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
            <div className="flex-1 p-6 overflow-y-auto custom-scrollbar">
                {viewMode === 'grid' ? (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-6">
                        {filteredProjects.map(project => {
                            const isSelected = activeProject === project.id;
                            const isRunning = Object.values(runningMachines).includes(project.id);
                            // eslint-disable-next-line no-unused-vars
                            const runningCount = Object.values(runningMachines).filter(id => id === project.id).length;
                            
                            return (
                                <div 
                                    key={project.id} 
                                    onClick={() => handleProjectClick(project)}
                                    className={`group bg-white rounded-2xl transition-all duration-200 cursor-pointer flex flex-col overflow-hidden relative ${isSelected ? `border border-transparent shadow-xl z-10` : 'border border-gray-200 shadow-sm hover:shadow-lg hover:translate-y-[-2px]'}`}
                                >
                                    {/* Selection Border Overlay */}
                                    {isSelected && <div className="absolute inset-0 border-[6px] border-[#39C5BB] rounded-2xl pointer-events-none z-50 -m-[1px]"></div>}

                                    {/* Thumbnail */}
                                    <div className="aspect-[4/3] bg-gray-100 relative overflow-hidden rounded-t-2xl">
                                        <ProjectThumbnail project={project} className="w-full h-full transition-transform duration-500 group-hover:scale-105" />
                                        <div className="absolute top-3 left-3"><span className={`px-2 py-1 rounded-md text-xs font-bold text-white shadow-sm backdrop-blur-md ${project.type === 'VRED' ? 'bg-orange-500/80' : 'bg-blue-500/80'}`}>{project.type}</span></div>
                                        
                                        {/* Date Overlay */}
                                        <div className="absolute bottom-3 left-3 right-3 flex justify-between items-end text-white text-xs opacity-80">
                                            <div className="flex gap-1 items-center bg-black/30 px-1.5 py-0.5 rounded backdrop-blur-sm"><Calendar size={10} /> {project.date || 'N/A'}</div>
                                        </div>

                                        {/* Selection Indicator Overlay */}
                                        {isSelected && (
                                            <div className="absolute inset-0 bg-[#39C5BB]/90 backdrop-blur-sm flex flex-col items-center justify-center text-white animate-in fade-in duration-200 z-10">
                                                <div className="bg-white text-[#39C5BB] rounded-full p-2 mb-2 shadow-lg"><Link size={32} /></div>
                                                <span className="font-bold text-lg tracking-wide">已选中项目</span>
                                                <span className="text-xs opacity-90 mt-1 mb-4">请点击右侧节点绑定</span>
                                            </div>
                                        )}

                                        {/* Action Buttons (Hover or Selected) */}
                                        <div className={`absolute top-3 right-3 flex items-center gap-2 z-20 transition-opacity duration-200 ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                                            <button 
                                                onClick={(e) => handleReplaceClick(e, project)} 
                                                className="p-1.5 bg-black/40 hover:bg-[#39C5BB] rounded-lg text-white/80 hover:text-white backdrop-blur-md transition-colors" 
                                                title="替换项目文件"
                                            >
                                                <Upload size={14} />
                                            </button>
                                            <button 
                                                onClick={(e) => { e.stopPropagation(); handleDeleteProject(project.id); }} 
                                                className="p-1.5 bg-black/40 hover:bg-red-500 rounded-lg text-white/80 hover:text-white backdrop-blur-md transition-colors" 
                                                title="删除项目"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </div>
                                    
                                    {/* Info */}
                                    <div className="p-4 flex flex-col bg-white relative z-10 border-t border-gray-50">
                                        <div className="mb-2 flex items-center justify-between h-7">
                                            {editingProjectId === project.id ? (
                                                <input 
                                                    ref={editInputRef}
                                                    type="text" 
                                                    value={editName}
                                                    onChange={(e) => setEditName(e.target.value)}
                                                    onKeyDown={handleKeyDown}
                                                    onBlur={saveEditing}
                                                    onClick={(e) => e.stopPropagation()}
                                                    className="w-full px-2 py-1 text-sm font-bold text-gray-800 border border-[#39C5BB] rounded focus:outline-none focus:ring-1 focus:ring-[#39C5BB]"
                                                />
                                            ) : (
                                                <>
                                                    <h3 className="font-bold text-gray-800 truncate" title={project.name}>{project.name}</h3>
                                                    <button 
                                                        onClick={(e) => startEditing(project, e)} 
                                                        className={`text-gray-400 hover:text-[#39C5BB] transition-opacity p-1 shrink-0 ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} 
                                                        title="重命名"
                                                    >
                                                        <Edit2 size={14} />
                                                    </button>
                                                </>
                                            )}
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
                                            className={`cursor-pointer hover:bg-gray-50 transition-colors ${isSelected ? 'bg-blue-50/50' : ''}`}
                                        >
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-10 h-8 rounded bg-gray-100 overflow-hidden shrink-0">
                                                        <ProjectThumbnail project={project} className="w-full h-full" />
                                                    </div>
                                                    {editingProjectId === project.id ? (
                                                        <input 
                                                            ref={editInputRef}
                                                            type="text" 
                                                            value={editName}
                                                            onChange={(e) => setEditName(e.target.value)}
                                                            onKeyDown={handleKeyDown}
                                                            onBlur={saveEditing}
                                                            onClick={(e) => e.stopPropagation()}
                                                            className="px-2 py-1 text-sm font-bold text-gray-800 border border-[#39C5BB] rounded focus:outline-none focus:ring-1 focus:ring-[#39C5BB]"
                                                        />
                                                    ) : (
                                                        <div className="font-bold text-gray-800">{project.name}</div>
                                                    )}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-gray-500">{project.type}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-gray-500 font-mono">{project.size}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-gray-500">{project.date}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    <button 
                                                        onClick={(e) => startEditing(project, e)}
                                                        className="p-1.5 text-gray-400 hover:text-[#39C5BB] hover:bg-gray-100 rounded-lg transition-colors"
                                                        title="重命名"
                                                    >
                                                        <Edit2 size={16} />
                                                    </button>
                                                    <button 
                                                        onClick={(e) => handleReplaceClick(e, project)}
                                                        className="p-1.5 text-gray-400 hover:text-[#39C5BB] hover:bg-gray-100 rounded-lg transition-colors"
                                                        title="替换文件"
                                                    >
                                                        <Upload size={16} />
                                                    </button>
                                                    <button 
                                                        onClick={(e) => { e.stopPropagation(); handleDeleteProject(project.id); }}
                                                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                                                        title="删除"
                                                    >
                                                        <Trash2 size={16} />
                                                    </button>
                                                </div>
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
    );
};

export default ProjectWorkspace;
