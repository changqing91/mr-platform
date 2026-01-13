import React from 'react';
import { Filter, List, Grid, FilePlus, Tag, ArrowUp, ArrowDown } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const ResourceDetail = ({
    sortBy,
    setSortBy,
    sortOrder,
    setSortOrder,
    showTagFilter,
    setShowTagFilter,
    selectedFilterTags,
    setSelectedFilterTags,
    projectViewMode,
    setProjectViewMode,
    setShowProjectModal,
    allAvailableTags,
    projectCount
}) => {
    const toggleFilterTag = (tag) => {
        const newTags = new Set(selectedFilterTags);
        if (newTags.has(tag)) {
            newTags.delete(tag);
        } else {
            newTags.add(tag);
        }
        setSelectedFilterTags(newTags);
    };

    return (
        <div className="flex flex-col w-full">
            <div className="flex items-center justify-between">
                <p className="text-gray-500 text-sm flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-300"></span>
                    共 {projectCount} 个项目资产，选中即可分配
                </p>

                <div className="flex items-center gap-4">
                    {/* Sort / Filter / View Group */}
                <div className="flex items-center bg-white border border-gray-200 rounded-xl p-1 shadow-sm">
                    
                    {/* Sort */}
                    <div className="flex items-center px-2 border-r border-gray-200 mr-1 gap-1">
                        <span className="text-[10px] font-bold text-gray-400 uppercase mr-1">排序:</span>
                        <button 
                            onClick={() => { if(sortBy==='date'){setSortOrder(sortOrder==='asc'?'desc':'asc')}else{setSortBy('date');setSortOrder('desc')} }} 
                            className={`px-2 py-1 rounded text-xs font-bold transition-colors flex items-center gap-1 ${sortBy === 'date' ? 'bg-gray-100 text-gray-800' : 'text-gray-400 hover:text-gray-600'}`}
                        >
                            日期 {sortBy === 'date' && (sortOrder === 'asc' ? <ArrowUp size={10}/> : <ArrowDown size={10}/>)}
                        </button>
                        <button 
                            onClick={() => { if(sortBy==='name'){setSortOrder(sortOrder==='asc'?'desc':'asc')}else{setSortBy('name');setSortOrder('asc')} }} 
                            className={`px-2 py-1 rounded text-xs font-bold transition-colors flex items-center gap-1 ${sortBy === 'name' ? 'bg-gray-100 text-gray-800' : 'text-gray-400 hover:text-gray-600'}`}
                        >
                            名称 {sortBy === 'name' && (sortOrder === 'asc' ? <ArrowUp size={10}/> : <ArrowDown size={10}/>)}
                        </button>
                        <button 
                            onClick={() => { if(sortBy==='type'){setSortOrder(sortOrder==='asc'?'desc':'asc')}else{setSortBy('type');setSortOrder('asc')} }} 
                            className={`px-2 py-1 rounded text-xs font-bold transition-colors flex items-center gap-1 ${sortBy === 'type' ? 'bg-gray-100 text-gray-800' : 'text-gray-400 hover:text-gray-600'}`}
                        >
                            类型 {sortBy === 'type' && (sortOrder === 'asc' ? <ArrowUp size={10}/> : <ArrowDown size={10}/>)}
                        </button>
                    </div>

                    {/* Filter */}
                    <button 
                        onClick={() => setShowTagFilter(!showTagFilter)}
                        className={`p-1.5 px-2.5 rounded-lg transition-all flex items-center gap-1.5 text-xs font-bold mx-0.5 ${showTagFilter || selectedFilterTags.size > 0 ? 'text-white shadow-sm' : 'text-gray-500 hover:bg-gray-100'}`}
                        style={showTagFilter || selectedFilterTags.size > 0 ? { backgroundColor: THEME_COLOR } : {}}
                        title="标签筛选"
                    >
                        <Filter size={14} /> 筛选
                    </button>

                    {/* View Mode */}
                    <button 
                        onClick={() => setProjectViewMode(projectViewMode === 'grid' ? 'list' : 'grid')}
                        className="p-1.5 rounded-lg text-gray-500 hover:bg-white hover:shadow-sm transition-all ml-1"
                        title={projectViewMode === 'grid' ? '切换到列表视图' : '切换到网格视图'}
                    >
                        {projectViewMode === 'grid' ? <List size={16}/> : <Grid size={16}/>}
                    </button>
                </div>

                {/* Upload Button */}
                <button 
                    onClick={() => setShowProjectModal(true)} 
                    className="flex items-center gap-2 px-5 py-2.5 text-white rounded-xl text-sm font-bold shadow-lg shadow-[#39C5BB]/20 hover:shadow-[#39C5BB]/40 hover:-translate-y-0.5 transition-all active:scale-[0.98]"
                    style={{ backgroundColor: THEME_COLOR }}
                >
                    <FilePlus size={18} />
                    上传新项目
                </button>
                </div>
            </div>

            {/* Tag Filter Bar */}
            {(showTagFilter || selectedFilterTags.size > 0) && (
                <div className="mt-4 pt-3 border-t border-gray-100 flex gap-2 overflow-x-auto pb-1 custom-scrollbar animate-in slide-in-from-top-1 fade-in">
                    <span className="text-xs text-gray-400 flex items-center mr-2"><Tag size={12} className="mr-1"/> 标签:</span>
                    {allAvailableTags.map(tag => (
                        <button
                            key={tag}
                            onClick={() => toggleFilterTag(tag)}
                            className={`px-3 py-1 rounded-md text-xs font-medium transition-all whitespace-nowrap border ${selectedFilterTags.has(tag) ? 'bg-[#39C5BB]/10 text-[#39C5BB] border-[#39C5BB]' : 'bg-white text-gray-600 border-gray-200 hover:border-[#39C5BB]/50'}`}
                        >
                            {tag}
                        </button>
                    ))}
                    {selectedFilterTags.size > 0 && (
                        <button 
                            onClick={() => setSelectedFilterTags(new Set())}
                            className="px-3 py-1 rounded-md text-xs text-red-500 hover:bg-red-50 transition-colors whitespace-nowrap ml-auto"
                        >
                            清除筛选
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default ResourceDetail;
