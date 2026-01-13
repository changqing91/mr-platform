import React from 'react';
import { FilePlus, Upload, FileText, Trash2, X } from 'lucide-react';
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
    clearThumbnail,
    thumbnailInputRef,
    handleAddProject
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
                            <div className="w-full p-4 border border-primary bg-primary/5 rounded-lg flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="p-2 bg-white rounded-md shadow-sm text-primary">
                                        <FileText size={20} />
                                    </div>
                                    <div>
                                        <div className="text-sm font-bold text-gray-800 truncate max-w-[200px]">{newProjectForm.fileName}</div>
                                        <div className="flex gap-2 text-xs text-gray-500">
                                            <span className="font-mono">{newProjectForm.size}</span>
                                            <span>•</span>
                                            <span className="font-bold text-primary">{newProjectForm.type || '未知格式'}</span>
                                        </div>
                                    </div>
                                </div>
                                <button onClick={clearFile} className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-full transition-colors" title="移除文件">
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        )}
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">缩略图 (可选)</label>
                        <div className="flex items-center gap-4">
                            {newProjectForm.thumbnail ? (
                                <div className="relative w-32 h-24 rounded-lg overflow-hidden border border-gray-200 group">
                                    <img src={newProjectForm.thumbnail} alt="Thumbnail" className="w-full h-full object-cover" />
                                    <button onClick={clearThumbnail} className="absolute inset-0 bg-black/50 text-white opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                        <X size={20} />
                                    </button>
                                </div>
                            ) : (
                                <button onClick={() => thumbnailInputRef.current.click()} className="w-32 h-24 border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center text-gray-400 hover:bg-gray-50 hover:border-gray-400 transition-colors">
                                    <span className="text-xs">上传图片</span>
                                </button>
                            )}
                            <input type="file" ref={thumbnailInputRef} className="hidden" onChange={handleThumbnailSelect} accept="image/*" />
                            <div className="text-xs text-gray-400 flex-1">推荐尺寸: 800x600<br />支持 JPG, PNG</div>
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">项目名称</label>
                        <input 
                            type="text" 
                            value={newProjectForm.name} 
                            onChange={e => setNewProjectForm({...newProjectForm, name: e.target.value})} 
                            className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary transition-all" 
                            placeholder="输入项目名称..." 
                        />
                    </div>
                    <div className="flex gap-3 pt-4">
                        <button onClick={() => setShowProjectModal(false)} className="flex-1 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium transition-colors">取消</button>
                        <button 
                            onClick={handleAddProject} 
                            disabled={!newProjectForm.name || !newProjectForm.fileName} 
                            className={`flex-1 py-2 text-white rounded-lg font-medium transition-colors shadow-lg ${(!newProjectForm.name || !newProjectForm.fileName) ? 'bg-gray-300 cursor-not-allowed' : 'hover:shadow-xl hover:-translate-y-0.5'}`} 
                            style={{ backgroundColor: (!newProjectForm.name || !newProjectForm.fileName) ? undefined : THEME_COLOR }}
                        >
                            添加项目
                        </button>
                    </div>
                </div>
                <button onClick={() => setShowProjectModal(false)} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors">
                    <X size={20} />
                </button>
            </div>
        </div>
    );
};

export default ProjectModal;
