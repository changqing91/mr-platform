import React from 'react';
import { FilePlus, Upload, FileText, Trash2, X, Image as ImageIcon, Tag, Save } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const ProjectModal = ({
    showProjectModal,
    setShowProjectModal,
    newProjectForm,
    setNewProjectForm,
    handleFileSelect,
    clearFile,
    fileInputRef,
    handleThumbnailSelect,
    handleAddProject,
    isUploading,
    uploadProgress
}) => {
    if (!showProjectModal) return null;

    return (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center animate-in fade-in">
            <div className="bg-white p-8 rounded-2xl shadow-2xl w-[500px] border border-gray-100 transform transition-all scale-100 relative">
                <h3 className="text-xl font-bold mb-4 flex items-center gap-2 text-gray-800">
                    <FilePlus size={24} style={{ color: THEME_COLOR }} />
                    上传项目资源
                </h3>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">项目文件 (支持 .vpb, .wire)</label>
                        {!newProjectForm.fileName ? (
                            <div className="flex items-center justify-center w-full">
                                <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors">
                                    <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                        <Upload className="w-8 h-8 mb-3 text-gray-400" />
                                        <p className="mb-2 text-sm text-gray-500"><span className="font-semibold">点击上传</span> 或拖拽文件</p>
                                        <p className="text-xs text-gray-400">自动识别 VRED (.vpb) 或 Alias (.wire)</p>
                                    </div>
                                    <input type="file" ref={fileInputRef} className="hidden" onChange={handleFileSelect} accept=".vpb,.wire,.sb" />
                                </label>
                            </div>
                        ) : (
                            <div className="w-full p-4 border border-[#39C5BB] bg-[#39C5BB]/5 rounded-lg flex items-center justify-between relative overflow-hidden">
                                {isUploading && (
                                    <div 
                                        className="absolute inset-y-0 left-0 bg-[#39C5BB]/20 transition-all duration-300 ease-out"
                                        style={{ width: `${uploadProgress}%` }}
                                    />
                                )}
                                <div className="flex items-center gap-3 relative z-10">
                                    <div className="p-2 bg-white rounded-md shadow-sm text-[#39C5BB]">
                                        <FileText size={20} />
                                    </div>
                                    <div>
                                        <div className="text-sm font-bold text-gray-800 truncate max-w-[200px]">{newProjectForm.fileName}</div>
                                        <div className="flex gap-2 text-xs text-gray-500">
                                            <span className="font-mono">{newProjectForm.size}</span>
                                            <span>•</span>
                                            <span className="font-bold text-[#39C5BB]">{newProjectForm.type || '未知格式'}</span>
                                        </div>
                                    </div>
                                </div>
                                {isUploading ? (
                                    <span className="text-sm font-bold text-[#39C5BB] relative z-10">{uploadProgress}%</span>
                                ) : (
                                    <button onClick={clearFile} className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors relative z-10" title="移除文件">
                                        <Trash2 size={18} />
                                    </button>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Thumbnail Section */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">项目封面 (JPG/PNG)</label>
                        <div className="relative">
                            <input type="file" accept="image/png, image/jpeg" onChange={handleThumbnailSelect} className="hidden" id="thumb-upload" />
                            <label htmlFor="thumb-upload" className={`w-full flex items-center justify-center gap-2 px-4 py-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50 transition-all ${newProjectForm.thumbnail ? 'border-[#39C5BB] bg-[#39C5BB]/5' : ''}`}>
                                {newProjectForm.thumbnail ? (
                                    <>
                                        <img src={newProjectForm.thumbnail} alt="Preview" className="w-8 h-8 rounded object-cover border border-gray-300"/>
                                        <span className="text-sm text-gray-600">已选择封面图 (点击更换)</span>
                                    </>
                                ) : (
                                    <>
                                        <ImageIcon size={20} className="text-gray-400" />
                                        <span className="text-sm text-gray-500">点击上传封面图片</span>
                                    </>
                                )}
                            </label>
                        </div>
                    </div>

                    {/* Project Tag Section */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">项目标签 (选填)</label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                <Tag size={16} />
                            </div>
                            <input 
                                type="text" 
                                value={newProjectForm.tags || ''} 
                                onChange={(e) => setNewProjectForm({...newProjectForm, tags: e.target.value})} 
                                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#39C5BB] transition-all text-sm" 
                                placeholder="输入标签，用逗号分隔 (例如: Concept, SUV)" 
                            />
                        </div>
                    </div>

                    <div className="flex gap-3 pt-4">
                        <button 
                            onClick={() => setShowProjectModal(false)} 
                            disabled={isUploading}
                            className={`flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                            取消
                        </button>
                        <button 
                            onClick={handleAddProject} 
                            disabled={!newProjectForm.fileName || isUploading} 
                            className={`flex-1 py-2 text-white rounded-lg font-medium transition-colors shadow-lg flex items-center justify-center gap-2 ${(!newProjectForm.fileName || isUploading) ? 'bg-gray-300 cursor-not-allowed' : 'hover:shadow-xl hover:-translate-y-0.5'}`} 
                            style={{ backgroundColor: (!newProjectForm.fileName || isUploading) ? undefined : THEME_COLOR }}
                        >
                            <Save size={18} />
                            {isUploading ? '正在保存...' : '保存项目'}
                        </button>
                    </div>
                </div>
                <button 
                    onClick={() => setShowProjectModal(false)} 
                    disabled={isUploading}
                    className={`absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                    <X size={20} />
                </button>
            </div>
        </div>
    );
};

export default ProjectModal;
