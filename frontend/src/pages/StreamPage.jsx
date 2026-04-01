import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import StreamingView from '../components/StreamingView';

const StreamPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    // URL 参数总是字符串；Strapi 返回的 id 是数字，用 Number() 统一类型
    const machineId = Number(searchParams.get('machineId')) || null;

    // 若 URL 中携带 token（来自 VRED 面板注入），写入 localStorage 供 api.js 使用
    const urlToken = searchParams.get('token');
    if (urlToken) {
        localStorage.setItem('jwt', urlToken);
    }

    const [machines, setMachines] = useState([]);
    const [projects, setProjects] = useState([]);
    const [runningMachines, setRunningMachines] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (!machineId) return;
        const load = async () => {
            try {
                const [p, m, procs] = await Promise.all([
                    api.projects.list(),
                    api.machines.list(),
                    api.processes.list(),
                ]);
                setProjects(p || []);
                setMachines(
                    (m || []).map(mach => ({
                        ...mach,
                        currentProject: mach.current_project?.id || null,
                    }))
                );
                const running = {};
                (procs || []).forEach(proc => {
                    if (proc.machine?.id && proc.project?.id) {
                        running[proc.machine.id] = proc.project.id;
                    }
                });
                setRunningMachines(running);
            } catch (e) {
                setError(e.message || '数据加载失败');
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [machineId]);

    if (!machineId) {
        return (
            <div className="flex items-center justify-center h-screen w-screen bg-gray-900 text-gray-400 text-sm font-sans">
                缺少参数：URL 中需要提供 <code className="mx-1 px-1 bg-gray-800 rounded">machineId</code>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-screen w-screen bg-gray-900 text-gray-500 text-sm">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-6 h-6 border-2 border-t-transparent border-[#39C5BB] rounded-full animate-spin" />
                    <span>加载串流数据…</span>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-screen w-screen bg-gray-900 text-red-400 text-sm">
                {error}
            </div>
        );
    }

    if (!runningMachines[machineId]) {
        return (
            <div className="flex items-center justify-center h-screen w-screen bg-gray-900 text-gray-400 text-sm">
                该节点当前没有运行中的项目
            </div>
        );
    }

    return (
        <div className="w-screen h-screen bg-gray-900 overflow-hidden relative">
            <StreamingView
                streamingMachineId={machineId}
                setStreamingMachineId={(id) => {
                    if (!id) navigate('/');
                }}
                machines={machines}
                projects={projects}
                runningMachines={runningMachines}
            />
        </div>
    );
};

export default StreamPage;
