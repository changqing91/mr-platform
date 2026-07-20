import React from 'react';
import { Box, LogOut, Users, Video } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const Header = ({ currentUser, handleLogout, onAccountManagement, onMeetingPanel }) => {
    const isManager = !!currentUser?.isManager;
    const displayName = currentUser?.displayName || currentUser?.username || '';
    const username = currentUser?.username || '';
    const role = currentUser?.appUser?.appRole?.name || (isManager ? '管理员' : '');

    return (
        <header className="h-16 border-b border-gray-100 flex items-center justify-between px-8 bg-white z-20 shrink-0">
            <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white shadow-lg shadow-[#39C5BB]/30" style={{ backgroundColor: THEME_COLOR }}>
                    <Box size={20} strokeWidth={3} />
                </div>
                <h1 className="text-xl font-bold text-gray-800 tracking-tight">WhatTech <span style={{ color: THEME_COLOR }}>MR</span></h1>
            </div>
            <div className="flex items-center gap-3">
                <div className="text-right mr-2 hidden sm:block">
                    <div className="text-sm font-bold text-gray-700 flex items-center gap-1.5">
                        {displayName}
                        {isManager && (
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md text-white" style={{ backgroundColor: THEME_COLOR }}>
                                管理员
                            </span>
                        )}
                    </div>
                    <div className="text-[10px] text-gray-400">
                        @{username}{role ? ` · ${role}` : ''}
                    </div>
                </div>
                <div className="w-9 h-9 rounded-full bg-gray-200 border border-gray-200 flex items-center justify-center text-gray-500 font-bold">
                    {(displayName || username).charAt(0).toUpperCase()}
                </div>
                {isManager && onAccountManagement && (
                    <button
                        onClick={onAccountManagement}
                        className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors"
                        title="管理面板（成员/项目组/角色）"
                    >
                        <Users size={18} />
                    </button>
                )}
                {onMeetingPanel && (
                    <button
                        onClick={onMeetingPanel}
                        className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors"
                        title="会议"
                    >
                        <Video size={18} />
                    </button>
                )}
                <button onClick={handleLogout} className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors ml-1" title="退出登录">
                    <LogOut size={18} />
                </button>
            </div>
        </header>
    );
};

export default Header;
