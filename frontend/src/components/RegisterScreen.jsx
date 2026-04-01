import React, { useState } from 'react';
import { Box, User, Lock, Mail, ArrowLeft, AlertTriangle, CheckSquare, Square, FileText } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const USER_AGREEMENT = `用户注册协议

欢迎使用 WhatTech MR 企业级混合现实运维管理平台（以下简称"本平台"）。在注册账户前，请仔细阅读以下协议条款。注册即表示您已阅读、理解并同意受本协议约束。

一、账户注册

1. 您注册的账户须提供真实、准确的信息。
2. 您有责任妥善保管账户及密码，因账户泄露造成的损失由您自行承担。
3. 每个用户只能注册一个账户，禁止以任何方式非法转让账户。

二、平台使用规范

1. 本平台仅供授权的企业用户在合法业务范围内使用。
2. 禁止使用本平台从事任何违法或侵权活动。
3. 禁止未经授权访问、修改或破坏平台系统及数据。
4. 用户上传的项目文件须拥有合法的使用权或授权。

三、数据与隐私

1. 本平台将依法保护您的个人信息，不向第三方泄露。
2. 您上传至平台的项目数据归您所有，本平台不对其进行商业性使用。
3. 平台运营方有权对匿名化的使用数据进行分析，以改善服务质量。

四、免责声明

1. 本平台按"现状"提供服务，不对服务的持续性、准确性作出明示或暗示的担保。
2. 因不可抗力、网络故障等原因导致的服务中断，平台不承担责任。
3. 用户因违反本协议造成的损失，由用户自行承担。

五、协议变更

本平台保留随时修改本协议的权利，修改后的协议将在平台上公告。继续使用本平台即表示您接受修改后的协议。

六、适用法律

本协议受中华人民共和国法律管辖，如有争议，双方应友好协商解决；协商不成的，提交有管辖权的法院诉讼解决。

© 2024 WhatTech Inc. 保留所有权利。`;

const RegisterScreen = ({ handleRegister, onBackToLogin, registerError }) => {
    const [form, setForm] = useState({ username: '', email: '', password: '', confirmPassword: '' });
    const [agreed, setAgreed] = useState(false);
    const [showAgreement, setShowAgreement] = useState(false);
    const [formError, setFormError] = useState(null);

    const handleSubmit = (e) => {
        e.preventDefault();
        setFormError(null);

        if (!form.username.trim()) {
            setFormError('请输入用户名');
            return;
        }
        if (!form.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
            setFormError('请输入有效的邮箱地址');
            return;
        }
        if (form.password.length < 6) {
            setFormError('密码长度至少为6位');
            return;
        }
        if (form.password !== form.confirmPassword) {
            setFormError('两次输入的密码不一致');
            return;
        }
        if (!agreed) {
            setFormError('请阅读并同意用户协议');
            return;
        }

        handleRegister(form.username.trim(), form.email.trim(), form.password);
    };

    const displayError = formError || registerError;

    return (
        <div className="absolute inset-0 z-50 bg-white flex items-center justify-center animate-in fade-in duration-500">
            {showAgreement && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4" style={{ zIndex: 9999 }} onClick={() => setShowAgreement(false)}>
                    <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
                        <div className="flex items-center justify-between p-6 border-b border-gray-100">
                            <div className="flex items-center gap-2 font-bold text-gray-800">
                                <FileText size={20} style={{ color: THEME_COLOR }} />
                                用户注册协议
                            </div>
                            <button onClick={() => setShowAgreement(false)} className="text-gray-400 hover:text-gray-600 text-xl font-bold leading-none">×</button>
                        </div>
                        <div className="flex-1 overflow-y-auto p-6">
                            <pre className="text-xs text-gray-600 whitespace-pre-wrap leading-relaxed font-sans">{USER_AGREEMENT}</pre>
                        </div>
                        <div className="p-4 border-t border-gray-100 flex justify-end">
                            <button
                                onClick={() => { setAgreed(true); setShowAgreement(false); }}
                                className="px-6 py-2.5 text-white rounded-xl font-bold text-sm hover:opacity-90 transition-all"
                                style={{ backgroundColor: THEME_COLOR }}
                            >
                                我已阅读并同意
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden relative border border-gray-100">
                <div className="h-2 w-full absolute top-0" style={{ backgroundColor: THEME_COLOR }}></div>
                <div className="p-8 pt-12">
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-[#39C5BB]/10 text-[#39C5BB] mb-4 shadow-sm">
                            <Box size={32} strokeWidth={3} />
                        </div>
                        <h1 className="text-2xl font-bold text-gray-800 tracking-tight">WhatTech <span style={{ color: THEME_COLOR }}>MR</span></h1>
                        <p className="text-gray-500 text-sm mt-2">注册新账户</p>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        {displayError && (
                            <div className="bg-red-50 text-red-600 px-4 py-3 rounded-xl text-sm flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
                                <AlertTriangle size={16} />
                                {displayError}
                            </div>
                        )}

                        <div>
                            <label className="block text-sm font-bold text-gray-700 mb-2 ml-1">用户名</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-400">
                                    <User size={18} />
                                </div>
                                <input
                                    type="text"
                                    className="w-full pl-11 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all"
                                    placeholder="请输入用户名"
                                    value={form.username}
                                    onChange={e => setForm({ ...form, username: e.target.value })}
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-bold text-gray-700 mb-2 ml-1">邮箱</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-400">
                                    <Mail size={18} />
                                </div>
                                <input
                                    type="email"
                                    className="w-full pl-11 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all"
                                    placeholder="请输入邮箱地址"
                                    value={form.email}
                                    onChange={e => setForm({ ...form, email: e.target.value })}
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
                                    placeholder="至少6位密码"
                                    value={form.password}
                                    onChange={e => setForm({ ...form, password: e.target.value })}
                                />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-bold text-gray-700 mb-2 ml-1">确认密码</label>
                            <div className="relative">
                                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-400">
                                    <Lock size={18} />
                                </div>
                                <input
                                    type="password"
                                    className="w-full pl-11 pr-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#39C5BB] focus:border-transparent transition-all"
                                    placeholder="再次输入密码"
                                    value={form.confirmPassword}
                                    onChange={e => setForm({ ...form, confirmPassword: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="flex items-center gap-2 pt-1">
                            <button
                                type="button"
                                onClick={() => setAgreed(!agreed)}
                                className="flex-shrink-0 text-gray-400 hover:text-[#39C5BB] transition-colors"
                            >
                                {agreed
                                    ? <CheckSquare size={20} style={{ color: THEME_COLOR }} />
                                    : <Square size={20} />}
                            </button>
                            <span className="text-sm text-gray-600">
                                我已阅读并同意{' '}
                                <button
                                    type="button"
                                    onClick={() => setShowAgreement(true)}
                                    className="font-bold underline hover:opacity-80 transition-opacity"
                                    style={{ color: THEME_COLOR }}
                                >
                                    《用户注册协议》
                                </button>
                            </span>
                        </div>

                        <button
                            type="submit"
                            className="w-full py-3.5 hover:opacity-90 text-white rounded-xl font-bold shadow-lg shadow-[#39C5BB]/30 transition-all transform active:scale-[0.98] flex items-center justify-center gap-2 mt-2"
                            style={{ backgroundColor: THEME_COLOR }}
                        >
                            注册账户
                        </button>
                    </form>

                    <div className="mt-4 text-center">
                        <button
                            onClick={onBackToLogin}
                            className="text-sm text-gray-500 hover:text-gray-700 flex items-center justify-center gap-1 mx-auto transition-colors"
                        >
                            <ArrowLeft size={14} />
                            返回登录
                        </button>
                    </div>
                </div>
                <div className="bg-gray-50 p-4 text-center text-xs text-gray-400 border-t border-gray-100">
                    &copy; 2024 WhatTech Inc. All rights reserved.
                </div>
            </div>
        </div>
    );
};

export default RegisterScreen;
