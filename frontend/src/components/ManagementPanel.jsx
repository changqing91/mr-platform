import React, { useState } from 'react';
import { X, Users, FolderKanban, Shield } from 'lucide-react';
import { THEME_COLOR } from '../constants';
import MemberView from './management/MemberView';
import ProjectGroupView from './management/ProjectGroupView';
import RoleView from './management/RoleView';

const TAB_BTN = (active) =>
    `px-4 py-1.5 rounded-md text-sm font-medium transition-colors inline-flex items-center gap-1.5 ${
        active ? 'text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
    }`;

const ManagementPanel = ({ onClose, addNotification, currentUser }) => {
    const [activeTab, setActiveTab] = useState('users');

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
            <div
                className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between p-5 border-b border-gray-100 shrink-0 gap-4">
                    <div className="flex items-center gap-3 shrink-0">
                        <div
                            className="w-9 h-9 rounded-xl flex items-center justify-center text-white"
                            style={{ backgroundColor: THEME_COLOR }}
                        >
                            <Users size={18} />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-gray-800">管理面板</h2>
                            <p className="text-xs text-gray-400">成员 / 项目组 / 角色</p>
                        </div>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setActiveTab('users')}
                            className={TAB_BTN(activeTab === 'users')}
                            style={activeTab === 'users' ? { backgroundColor: THEME_COLOR } : undefined}
                        >
                            <Users size={14} /> 成员管理
                        </button>
                        <button
                            onClick={() => setActiveTab('groups')}
                            className={TAB_BTN(activeTab === 'groups')}
                            style={activeTab === 'groups' ? { backgroundColor: THEME_COLOR } : undefined}
                        >
                            <FolderKanban size={14} /> 项目组
                        </button>
                        <button
                            onClick={() => setActiveTab('roles')}
                            className={TAB_BTN(activeTab === 'roles')}
                            style={activeTab === 'roles' ? { backgroundColor: THEME_COLOR } : undefined}
                        >
                            <Shield size={14} /> 角色
                        </button>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 text-gray-400 hover:bg-gray-100 rounded-xl transition-colors shrink-0"
                    >
                        <X size={18} />
                    </button>
                </div>

                <div className="flex-1 overflow-hidden">
                    {activeTab === 'users' && (
                        <MemberView addNotification={addNotification} currentUser={currentUser} />
                    )}
                    {activeTab === 'groups' && <ProjectGroupView addNotification={addNotification} />}
                    {activeTab === 'roles' && <RoleView addNotification={addNotification} />}
                </div>
            </div>
        </div>
    );
};

export default ManagementPanel;
