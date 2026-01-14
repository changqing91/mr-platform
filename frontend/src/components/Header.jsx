import React from 'react';
import { Box, LogOut } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const Header = ({ currentUser, handleLogout }) => {
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
                    <div className="text-sm font-bold text-gray-700">{currentUser?.username}</div>
                    <div className="text-[10px] text-gray-400 font-mono">ID: {currentUser?.id}</div>
                </div>
                <div className="w-9 h-9 rounded-full bg-gray-200 border border-gray-200 flex items-center justify-center text-gray-500 font-bold">
                    {currentUser?.username?.charAt(0).toUpperCase()}
                </div>
                <button onClick={handleLogout} className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors ml-2" title="退出登录">
                    <LogOut size={18} />
                </button>
            </div>
        </header>
    );
};

export default Header;
