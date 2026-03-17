import React, { useState, useRef } from 'react';
import { LayoutDashboard, Activity, Search, Calendar, Edit2, Trash2, Link, X, Tag, Save, Upload, Image as ImageIcon } from 'lucide-react';
import ResourceDetail from './ResourceDetail';
import ProjectThumbnail from './ProjectThumbnail';
import { THEME_COLOR } from '../constants';
import { api } from '../services/api';

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
    handleUpdateProject,
    handleReplaceClick
}) => {
    const [editingProject, setEditingProject] = useState(null);
    const [editForm, setEditForm] = useState({ name: '', tags: '', thumbnail: undefined });
    const [isUploadingThumb, setIsUploadingThumb] = useState(false);
    const thumbInputRef = useRef(null);

    const openEdit = (e, project) => {
        e.stopPropagation();
        setEditingProject(project);
        setEditForm({
            name: project.name,
            tags: Array.isArray(project.tags) ? project.tags.join(', ') : (project.tags || ''),
            thumbnail: undefined // undefined = not changed
        });
    };

    const closeEdit = () => {
        setEditingProject(null);
        setIsUploadingThumb(false);
    };

    const handleThumbSelect = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setIsUploadingThumb(true);
        try {
            const uploaded = await api.upload(file);
            if (uploaded && uploaded.length > 0) {
                setEditForm(f => ({ ...f, thumbnail: uploaded[0].url }));
            }
        } catch (err) {
            console.error('封面图上传失败', err);
        } finally {
            setIsUploadingThumb(false);
            if (thumbInputRef.current) thumbInputRef.current.value = '';
        }
    };

    const saveEdit = async () => {
        if (!editForm.name.trim()) return;
        await handleUpdateProject(editingProject.id, {
            name: editForm.name,
            tags: editForm.tags,
            ...(editForm.thumbnail !== undefined && { thumbnail: editForm.thumbnail })
        });
        closeEdit();
    };

    return (
        <main className="flex-1 flex flex-col min-w-0 bg-gray-50">
            {/* Sub Header / Toolbar */}
            <div className="p-6 pb-4 shrink-0">
                {/* Top Nav & Search */}
                <div className="flex items-center justify-between mb-6">
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

                            return (
                                <div
                                    key={project.id}
                                    onClick={() => handleProjectClick(project)}
                                    className={`group bg-white rounded-2xl transition-all duration-200 cursor-pointer flex flex-col overflow-hidden relative ${isSelected ? 'border border-transparent shadow-xl z-10' : 'border border-gray-200 shadow-sm hover:shadow-lg hover:translate-y-[-2px]'}`}
                                >
                                    {/* Selection Border Overlay */}
                                    {isSelected && <div className="absolute inset-0 border-[6px] border-[#39C5BB] rounded-2xl pointer-events-none z-50 -m-[1px]"></div>}

                                    {/* Thumbnail */}
                                    <div className="aspect-[4/3] bg-gray-100 relative overflow-hidden rounded-t-2xl">
                                        <ProjectThumbnail project={project} className="w-full h-full transition-transform duration-500 group-hover:scale-105" />
                                        <div className="absolute top-3 left-3">
                                            <span className={`px-2 py-1 rounded-md text-xs font-bold text-white shadow-sm backdrop-blur-md ${project.type === 'VRED' ? 'bg-orange-500/80' : 'bg-blue-500/80'}`}>{project.type}</span>
                                        </div>

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

                                        {/* Delete Button (hover) */}
                                        <div className={`absolute top-3 right-3 z-20 transition-opacity duration-200 ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>
                                            <button
                                                onClick={(e) => { e.stopPropagation(); handleDeleteProject(project.id); }}
                                                className="p-1.5 bg-black/40 hover:bg-red-500 rounded-lg text-white/80 hover:text-white backdrop-blur-md transition-colors"
                                                title="删除项目"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>

                                        {/* Edit Button — always visible top-right corner */}
                                        <button
                                            onClick={(e) => openEdit(e, project)}
                                            className="absolute top-3 right-10 z-20 p-1.5 bg-black/40 hover:bg-[#39C5BB] rounded-lg text-white/80 hover:text-white backdrop-blur-md transition-colors opacity-0 group-hover:opacity-100"
                                            title="编辑项目"
                                        >
                                            <Edit2 size={14} />
                                        </button>
                                    </div>

                                    {/* Info */}
                                    <div className="p-4 flex flex-col bg-white relative z-10 border-t border-gray-50">
                                        <div className="mb-2 h-7 flex items-center">
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
                                            <span>{project.size}</span>
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
                                                    <div className="font-bold text-gray-800">{project.name}</div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-gray-500">{project.type}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-gray-500 font-mono">{project.size}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-gray-500">{project.date}</td>
                                            <td className="px-6 py-4 whitespace-nowrap text-right">
                                                <div className="flex items-center justify-end gap-2">
                                                    <button
                                                        onClick={(e) => openEdit(e, project)}
                                                        className="p-1.5 text-gray-400 hover:text-[#39C5BB] hover:bg-gray-100 rounded-lg transition-colors"
                                                        title="编辑项目"
                                                    >
                                                        <Edit2 size={16} />
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

            {/* Project Edit Modal */}
            {editingProject && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in" onClick={closeEdit}>
                    <div className="bg-white rounded-2xl shadow-2xl w-[460px] border border-gray-100 overflow-hidden" onClick={(e) => e.stopPropagation()}>
                        {/* Modal Header */}
                        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100">
                            <h3 className="text-base font-bold text-gray-800">编辑项目</h3>
                            <button onClick={closeEdit} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                                <X size={18} />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div className="px-6 py-5 space-y-4">
                            {/* Thumbnail */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
                                    <ImageIcon size={14} /> 封面图
                                </label>
                                <input
                                    ref={thumbInputRef}
                                    type="file"
                                    accept="image/png,image/jpeg,image/webp"
                                    className="hidden"
                                    onChange={handleThumbSelect}
                                />
                                <button
                                    type="button"
                                    onClick={() => thumbInputRef.current?.click()}
                                    disabled={isUploadingThumb}
                                    className="w-full relative rounded-xl overflow-hidden border-2 border-dashed border-gray-200 hover:border-[#39C5BB] transition-colors group/thumb"
                                    style={{ aspectRatio: '16/7' }}
                                >
                                    {/* Preview */}
                                    <div className="absolute inset-0">
                                        {editForm.thumbnail !== undefined ? (
                                            <img src={editForm.thumbnail} alt="封面预览" className="w-full h-full object-cover" />
                                        ) : (
                                            <ProjectThumbnail project={editingProject} className="w-full h-full" />
                                        )}
                                    </div>
                                    {/* Overlay */}
                                    <div className={`absolute inset-0 flex flex-col items-center justify-center transition-opacity ${isUploadingThumb ? 'opacity-100 bg-black/50' : 'opacity-0 group-hover/thumb:opacity-100 bg-black/40'}`}>
                                        {isUploadingThumb ? (
                                            <div className="animate-spin rounded-full h-6 w-6 border-2 border-white border-t-transparent" />
                                        ) : (
                                            <>
                                                <Upload size={20} className="text-white mb-1" />
                                                <span className="text-white text-xs font-bold">点击更换封面</span>
                                            </>
                                        )}
                                    </div>
                                </button>
                            </div>

                            {/* Name */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5">项目名称</label>
                                <input
                                    type="text"
                                    value={editForm.name}
                                    onChange={(e) => setEditForm(f => ({ ...f, name: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#39C5BB]/50 focus:border-[#39C5BB] transition-all"
                                    placeholder="输入项目名称"
                                    autoFocus
                                />
                            </div>

                            {/* Tags */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
                                    <Tag size={14} /> 项目标签
                                </label>
                                <input
                                    type="text"
                                    value={editForm.tags}
                                    onChange={(e) => setEditForm(f => ({ ...f, tags: e.target.value }))}
                                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#39C5BB]/50 focus:border-[#39C5BB] transition-all"
                                    placeholder="用逗号分隔，例如: Concept, SUV"
                                />
                            </div>

                            {/* Replace File */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1.5">项目文件</label>
                                <button
                                    onClick={(e) => handleReplaceClick(e, editingProject)}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-600 hover:border-[#39C5BB] hover:text-[#39C5BB] hover:bg-[#39C5BB]/5 transition-all"
                                >
                                    <Upload size={15} /> 替换项目文件
                                </button>
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-2">
                            <button onClick={closeEdit} className="px-4 py-2 text-sm bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition-colors">
                                取消
                            </button>
                            <button
                                onClick={saveEdit}
                                disabled={!editForm.name.trim() || isUploadingThumb}
                                className="px-4 py-2 text-sm text-white rounded-lg font-medium transition-colors flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
                                style={{ backgroundColor: THEME_COLOR }}
                            >
                                <Save size={14} /> 保存
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
};

export default ProjectWorkspace;
