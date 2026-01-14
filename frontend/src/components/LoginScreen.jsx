import React from 'react';
import { Box, User, Lock, ArrowLeft } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const LoginScreen = ({ handleLogin, loginForm, setLoginForm }) => (
    <div className="absolute inset-0 z-50 bg-white flex items-center justify-center animate-in fade-in duration-500">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden relative border border-gray-100">
            <div className="h-2 w-full absolute top-0" style={{ backgroundColor: THEME_COLOR }}></div>
            <div className="p-8 pt-12">
                <div className="text-center mb-10">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-[#39C5BB]/10 text-[#39C5BB] mb-4 shadow-sm">
                        <Box size={32} strokeWidth={3} />
                    </div>
                    <h1 className="text-2xl font-bold text-gray-800 tracking-tight">WhatTech <span style={{ color: THEME_COLOR }}>MR</span></h1>
                    <p className="text-gray-500 text-sm mt-2">企业级混合现实运维管理平台</p>
                </div>
                
                <form onSubmit={handleLogin} className="space-y-6">
                    <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2 ml-1">账号</label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-400">
                                <User size={18} />
                            </div>
                            <input 
                                type="text" 
                                className="w-full pl-11 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all" 
                                placeholder="请输入用户名" 
                                value={loginForm.username}
                                onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                            />
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2 ml-1">密码</label>
                        <div className="relative">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-400">
                                <Lock size={18} />
                            </div>
                            <input 
                                type="password" 
                                className="w-full pl-11 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all" 
                                placeholder="请输入密码" 
                                value={loginForm.password}
                                onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                            />
                        </div>
                    </div>
                    <button type="submit" className="w-full py-3.5 hover:opacity-90 text-white rounded-xl font-bold shadow-lg shadow-[#39C5BB]/30 transition-all transform active:scale-[0.98] flex items-center justify-center gap-2 mt-4" style={{ backgroundColor: THEME_COLOR }}>
                        登录平台 <ArrowLeft size={18} className="rotate-180" />
                    </button>
                </form>
            </div>
            <div className="bg-gray-50 p-4 text-center text-xs text-gray-400 border-t border-gray-100">
                &copy; 2024 WhatTech Inc. All rights reserved.
            </div>
        </div>
    </div>
);

export default LoginScreen;
