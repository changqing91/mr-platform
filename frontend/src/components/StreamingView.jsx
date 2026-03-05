import React, { useRef, useState, useEffect } from 'react';
import { ArrowLeft, Activity, Glasses, SplitSquareHorizontal, ImageIcon, Headset, FolderOpen, Monitor } from 'lucide-react';
import ProjectThumbnail from './ProjectThumbnail';
import { api } from '../services/api';
import { api as vredApi } from '../services/vredPython';

// --- Camera helpers ---
const parseVec3 = (v) => {
    if (Array.isArray(v)) return v.map(Number);
    if (typeof v === 'string') return v.split(/\s+/).map(Number);
    return [0, 0, 0];
};

// 解析 QMatrix4x4（4x4 变换矩阵），提取平移和欧拉角
// QMatrix4x4 返回值为 16 个数字的数组（行优先），即：
//   [ m11, m12, m13, m14,
//     m21, m22, m23, m24,
//     m31, m32, m33, m34,
//     m41, m42, m43, m44 ]
const parseWorldTransform = (matrix) => {
    const m = Array.isArray(matrix) ? matrix.map(Number) : (typeof matrix === 'string' ? matrix.split(/\s+/).map(Number) : []);
    if (m.length < 16) return { translation: [0, 0, 0], rotation: [0, 0, 0] };

    // 平移：第 4 列 (m14, m24, m34)，索引 3, 7, 11
    const translation = [m[3], m[7], m[11]];

    // 从旋转矩阵（左上 3x3）提取欧拉角 (XYZ 顺序)
    // m11=m[0], m12=m[1], m13=m[2]
    // m21=m[4], m22=m[5], m23=m[6]
    // m31=m[8], m32=m[9], m33=m[10]
    const toDeg = 180 / Math.PI;
    let rx, ry, rz;
    if (Math.abs(m[8]) < 0.99999) {
        ry = Math.asin(-m[8]);
        rx = Math.atan2(m[9], m[10]);
        rz = Math.atan2(m[4], m[0]);
    } else {
        // 万向锁情况
        ry = m[8] < 0 ? Math.PI / 2 : -Math.PI / 2;
        rx = Math.atan2(m[1], m[5]);
        rz = 0;
    }
    const rotation = [rx * toDeg, ry * toDeg, rz * toDeg];

    return { translation, rotation };
};

// 计算两个向量的欧几里得距离
const vec3Distance = (a, b) => {
    const dx = a[0] - b[0];
    const dy = a[1] - b[1];
    const dz = a[2] - b[2];
    return Math.sqrt(dx * dx + dy * dy + dz * dz);
};

// 计算两个欧拉角的差异（考虑角度环绕）
const eulerDistance = (a, b) => {
    let sum = 0;
    for (let i = 0; i < 3; i++) {
        let diff = Math.abs(a[i] - b[i]);
        // 处理角度环绕（例如 359° 和 1° 的差异应该是 2°，而不是 358°）
        if (diff > 180) diff = 360 - diff;
        sum += diff * diff;
    }
    return Math.sqrt(sum);
};

const StreamingView = ({
    streamingMachineId,
    setStreamingMachineId,
    machines,
    projects,
    runningMachines
}) => {
    const machine = machines.find(m => m.id === streamingMachineId);
    const project = projects.find(p => p.id === runningMachines[streamingMachineId]);
    const THEME_COLOR = '#39C5BB';

    const [streamParams, setStreamParams] = useState({
        hmdIp: '',
        hmdPort: '8888',
        trackingInterval: '2.0',
        fovMultiplier: '3.0',
        isTracking: false,
        schemeIp: '',
        schemePort: '8888',
        schemeCompareActive: false,
        liveRefFolder: '',
        realtimeRefActive: false,
        displayMode: 'standard', // 'standard', 'xr', 'mr'
        showCalibration: false
    });

    const updateStreamParam = (key, value) => setStreamParams(prev => {
        return { ...prev, [key]: value };
    });

    const validateStreamParam = (key) => setStreamParams(prev => {
        if (key === 'trackingInterval') {
            const numericValue = Number.parseFloat(prev[key]);
            const safeValue = Number.isFinite(numericValue) && numericValue >= 2 ? numericValue : 2;
            return { ...prev, [key]: safeValue.toFixed(1) };
        }
        if (key === 'fovMultiplier') {
            const numericValue = Number.parseFloat(prev[key]);
            const safeValue = Number.isFinite(numericValue) && numericValue >= 0.5 && numericValue <= 10 ? numericValue : 3;
            return { ...prev, [key]: safeValue.toFixed(1) };
        }
        return prev;
    });

    const trackingTimerRef = useRef(null);
    const lastCameraRef = useRef(null);
    const syncLockRef = useRef(false);

    // 组件卸载时清理定时器
    useEffect(() => {
        return () => {
            if (trackingTimerRef.current) {
                clearInterval(trackingTimerRef.current);
            }
        };
    }, []);

    // 同步 HMD 摄像机到旁观者屏幕，使用 viewpoint 动画实现平滑过渡
    const syncCameraOnce = async () => {
        if (!machine || !streamParams.hmdIp || syncLockRef.current) return;
        syncLockRef.current = true;
        try {
            // 1. 从头显机器读取实时摄像机
            vredApi.setBaseUrl(`http://${machine.ip}:${machine.port || 8888}`);
            const sourceCamera = await vredApi.vrCameraService.getActiveCamera(true);
            if (!sourceCamera) return;

            const worldTransform = await sourceCamera.getWorldTransform();
            const { translation, rotation } = parseWorldTransform(worldTransform);
            const fov = Number(await sourceCamera.getFov());

            // 2. 阈值检测：只有当变化足够大时才更新旁观者摄像机
            const positionThreshold = 1;    // 位置变化阈值（单位：mm）
            const rotationThreshold = 0.5;   // 旋转变化阈值（单位：度）
            const fovThreshold = 0.1;        // FOV 变化阈值

            const prev = lastCameraRef.current;
            if (prev) {
                const positionDiff = vec3Distance(translation, prev.t);
                const rotationDiff = eulerDistance(rotation, prev.r);
                const fovDiff = Math.abs(fov - prev.fov);

                // 如果变化太小，跳过更新，避免静止时抖动
                if (positionDiff < positionThreshold &&
                    rotationDiff < rotationThreshold &&
                    fovDiff < fovThreshold) {
                    return;
                }
            }

            // 保存当前值作为下次比较的基准
            lastCameraRef.current = { t: translation, r: rotation, fov };

            // 3. 在旁观者机器上使用 viewpoint 动画设置摄像机
            vredApi.setBaseUrl(`http://${streamParams.hmdIp}:${streamParams.hmdPort || 8888}`);
            const targetCamera = await vredApi.vrCameraService.getActiveCamera(true);
            if (!targetCamera) return;

            // 获取或创建摄像机轨道
            const cameraTrack = await vredApi.vrCameraService.getOrCreateRenderQueueCameraTrack(targetCamera);

            // 每次创建新的 viewpoint
            const viewpointName = `HMDTrackingViewpoint_${Date.now()}`;
            const viewpoint = await vredApi.vrCameraService.createViewpoint(viewpointName, cameraTrack);

            // 设置过渡时间（单位：秒）
            const transitionDuration = Math.max(0.5, Number.parseFloat(streamParams.trackingInterval) * 0.8);
            await viewpoint.setViewpointTransition(true);
            await viewpoint.setViewpointTransitionDuration(transitionDuration);

            // 设置 viewpoint 的位置和旋转（直接使用原始值，让 viewpoint 处理插值）
            await viewpoint.setTranslation(translation);
            await viewpoint.setRotationAsEuler(rotation);

            // 激活 viewpoint，触发平滑过渡动画
            await viewpoint.activate(false, true);

            // 设置 FOV（应用倍数以扩大大屏视野）
            const fovMultiplier = Number.parseFloat(streamParams.fovMultiplier) || 3;
            await targetCamera.setFov(fov * fovMultiplier);

            // 激活后删除 viewpoint，避免累积
            await vredApi.vrCameraService.deleteViewpoint(viewpoint);
        } catch (e) {
            console.error('Failed to sync HMD camera:', e);
        } finally {
            syncLockRef.current = false;
        }
    };

    const handleAutoTracking = (enabled) => {
        updateStreamParam('isTracking', enabled);

        // 清理现有的定时器
        if (trackingTimerRef.current) {
            clearInterval(trackingTimerRef.current);
            trackingTimerRef.current = null;
        }

        if (!enabled) {
            // 停止追踪时清理状态
            lastCameraRef.current = null;
            return;
        }

        // 启动追踪：定期读取 HMD 数据并更新摄像机
        const intervalMs = Math.max(2, Number.parseFloat(streamParams.trackingInterval)) * 1000;

        // 立即执行一次同步
        syncCameraOnce();

        // 定期同步（VRED 会根据摄像机的 viewpoint transition 设置自动处理平滑过渡）
        trackingTimerRef.current = setInterval(syncCameraOnce, intervalMs);
    };

    const sendPython = async (code) => {
        if (!machine) return;
        try {
            await api.processes.executePython(machine.ip, machine.port || 8888, code);
        } catch (e) {
            console.error('Python Exec Error:', e);
        }
    };

    const handleStandardDisplay = async () => {
        updateStreamParam('displayMode', 'standard');
        sendPython('setDisplayMode(VR_DISPLAY_STANDARD)');
        // 关闭底板
        await removeSceneplateFloor();
    };

    const handleEnterXR = async () => {
        updateStreamParam('displayMode', 'xr');
        sendPython('setDisplayMode(VR_DISPLAY_OPEN_XR)');
        // 关闭底板
        await removeSceneplateFloor();
    };

    const handleEnterMR = async () => {
        updateStreamParam('displayMode', 'mr');
        sendPython('setDisplayMode(VR_DISPLAY_OPEN_XR)');
        // 创建底板
        await createSceneplateFloor();
    };

    const createSceneplateFloor = async () => {
        if (!machine) return;
        try {
            // 网络路径需要使用正斜杠或双反斜杠
            const floorImagePath = '//192.168.7.80/upload/blue.jpg';
            
            // 使用 Python 脚本创建场景板底板
            const pythonScript = `
# 创建 MR 底板
NodeType = vrSceneplateTypes.NodeType
ContentType = vrSceneplateTypes.ContentType

# 开启场景板显示
vrOSGWidget.enableSceneplates(True)

# 获取场景板根节点
theRoot = vrSceneplateService.getRootNode()

# 查找并删除已存在的 MR_Floor
existingNode = vrSceneplateService.findNode('MR_Floor')
if existingNode.isValid():
    vrSceneplateService.removeNodes([existingNode])

# 创建 Backplate 类型的场景板节点（背景板，适合作为底板）
theNode = vrSceneplateService.createNode(theRoot, NodeType.Backplate, 'MR_Floor')
thePlate = vrdSceneplateNode(theNode)

# 设置内容类型为图片
thePlate.setContentType(ContentType.Image)

# 加载并设置图片
imagePath = '${floorImagePath}'
print('Loading image from:', imagePath)

try:
    theImage = vrImageService.loadImage(imagePath)
    if theImage.isValid():
        thePlate.setImage(theImage)
        print('Image loaded and set successfully')
    else:
        print('ERROR: Image is not valid')
except Exception as e:
    print('ERROR loading image:', str(e))

# 设置为可见
thePlate.setVisibilityFlag(True)

print('MR floor created')
`;
            
            await api.processes.executePython(machine.ip, machine.port || 8888, pythonScript);
        } catch (e) {
            console.error('Failed to create sceneplate floor:', e);
        }
    };

    const removeSceneplateFloor = async () => {
        if (!machine) return;
        try {
            // 使用 Python 脚本删除场景板底板
            const pythonScript = `
# 删除 MR 底板
existingNode = vrSceneplateService.findNode('MR_Floor')
if existingNode.isValid():
    vrSceneplateService.removeNodes([existingNode])
    print('MR floor removed successfully')
else:
    print('MR floor not found')

# 关闭场景板显示
vrOSGWidget.enableSceneplates(False)
`;
            
            await api.processes.executePython(machine.ip, machine.port || 8888, pythonScript);
        } catch (e) {
            console.error('Failed to remove sceneplate floor:', e);
        }
    };

    const handleStartCompare = async () => {
        if (!streamParams.schemeIp) return;

        updateStreamParam('schemeCompareActive', true);

        try {
            // 开启对比后发送python命令，使两个进程的摄像机视角同步
            // 让从机 (Secondary Node) 加入主机 (Primary Node) 的会话
            // 参考 API 文档: vrSessionService.join(sessionLink, userName, color, roomName, passwd, forceVersion)
            // sessionLink 通常格式为 "schemeIp" (VRED 默认端口可能不需要显式指定，或者格式为 "ip:port")
            // 这里我们使用简化的调用方式，或者根据 API 文档构建完整的 sessionLink
            // 假设直接传入 IP 即可连接到默认会话
            // 2025-02-04: 添加 vrSessionService.spectate(True) 以启用观看模式，同步摄像机视角

            // 1. 让主机 (Primary Node) 加入协作会话 (连接到本地或指定服务器)
            vredApi.setBaseUrl(`http://${machine.ip}:${machine.port || 8888}`);
            await vredApi.vrSessionService.join('localhost', 'Primary', '0 1 0 1', 'MR-Room', '');
            const primaryUser = await vredApi.vrSessionService.getUser();
            const userIdValue = primaryUser ? await primaryUser.getUserId() : null;
            const userId = userIdValue != null ? String(userIdValue) : '0';
            console.log('Primary User ID:', userId);

            // 2. 让从机 (Secondary Node) 加入主机 (Primary Node) 的会话
            // 并同步主机的视角 (传入主机的 userId)
            vredApi.setBaseUrl(`http://${streamParams.schemeIp}:${streamParams.schemePort || 8888}`);
            await vredApi.vrSessionService.join(machine.ip, 'Secondary', '1 0 0 1', 'MR-Room', '');
            await vredApi.vrSessionService.spectate(true, userId);
        } catch (e) {
            console.error('Failed to start comparison sync:', e);
        }
    };

    const handleStopCompare = async () => {
        updateStreamParam('schemeCompareActive', false);
        try {
            if (streamParams.schemeIp) {
                vredApi.setBaseUrl(`http://${streamParams.schemeIp}:${streamParams.schemePort || 8888}`);
                await vredApi.vrSessionService.leave();
            }
            if (machine) {
                vredApi.setBaseUrl(`http://${machine.ip}:${machine.port || 8888}`);
                await vredApi.vrSessionService.leave();
            }
        } catch (e) {
            console.error('Failed to stop comparison sync:', e);
        }
    };

    const handleRealtimeReference = async (enabled) => {
        updateStreamParam('realtimeRefActive', enabled);
        if (!enabled || !machine) return;
        try {
            vredApi.setBaseUrl(`http://${machine.ip}:${machine.port || 8888}`);
            await vredApi.vrLiveReferenceService.setStorePath(streamParams.liveRefFolder);
            const references = await vredApi.vrLiveReferenceService.getReferences();
            if (Array.isArray(references)) {
                await Promise.all(references.map((reference) => reference?.setAutoUpdate?.(true)));
            } else if (references?.setAutoUpdate) {
                await references.setAutoUpdate(true);
            }
        } catch (e) {
            console.error('Failed to enable realtime reference:', e);
        }
    };

    const [iframeLoading, setIframeLoading] = useState(true);

    const onIframeLoad = () => {
        setIframeLoading(false);
    };

    const goBack = () => setStreamingMachineId(null);

    const vredUrl = machine ? `http://${machine.ip}:${machine.port || 8888}/apps/VREDStreamApp/index.html` : '';

    return (
        <div className="absolute inset-0 z-30 bg-gray-900 flex flex-col animate-in fade-in duration-300">
            {/* Streaming Header */}
            <div className="h-16 flex items-center justify-between px-6 bg-gray-900 border-b border-gray-800 text-white shrink-0">
                <div className="flex items-center gap-4">
                    <button onClick={goBack} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors text-sm">
                        <ArrowLeft size={16} />退出预览
                    </button>
                    <div className="h-6 w-[1px] bg-gray-700"></div>
                    <div>
                        <h2 className="text-lg font-bold flex items-center gap-2">
                            <Activity size={18} className="text-[#39C5BB] animate-pulse" />
                            实时串流: {machine?.name}
                        </h2>
                        <p className="text-xs text-gray-400">Project: {project?.name}</p>
                    </div>
                </div>
                <div className="flex gap-4 text-xs font-mono text-gray-500">
                    {streamParams.isTracking && <span className="text-[#39C5BB] flex items-center gap-1"><Glasses size={12} /> HMD TRACKING</span>}
                    {streamParams.schemeCompareActive && <span className="text-[#39C5BB] flex items-center gap-1"><SplitSquareHorizontal size={12} /> COMPARING</span>}
                    {streamParams.realtimeRefActive && <span className="text-[#39C5BB] flex items-center gap-1"><ImageIcon size={12} /> REF ACTIVE</span>}
                    {streamParams.displayMode === 'xr' && (
                        <span className="text-[#39C5BB] flex items-center gap-1 bg-[#39C5BB]/10 px-2 py-0.5 rounded border border-[#39C5BB]/20"><Glasses size={12} /> XR ACTIVE</span>
                    )}
                    {streamParams.displayMode === 'mr' && (
                        <span className="text-[#39C5BB] flex items-center gap-1 bg-[#39C5BB]/10 px-2 py-0.5 rounded border border-[#39C5BB]/20"><Headset size={12} /> MR ACTIVE</span>
                    )}
                </div>
            </div>

            {/* Streaming Content */}
            <div className="flex-1 flex overflow-hidden">
                <div className="flex-1 bg-black relative flex items-center justify-center overflow-hidden">
                    {iframeLoading && (
                        <div className="absolute inset-0 flex items-center justify-center z-10">
                            <ProjectThumbnail project={project} className="w-full h-full opacity-80" />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[#39C5BB]"></div>
                            </div>
                        </div>
                    )}

                    {/* Primary Stream (Left) */}
                    <div className={`relative h-full transition-all duration-300 ${streamParams.schemeCompareActive ? 'w-1/2 border-r border-gray-800' : 'w-full'}`}>
                        <iframe
                            src={vredUrl}
                            frameBorder="0"
                            width="100%"
                            height="100%"
                            onLoad={onIframeLoad}
                            style={{ opacity: iframeLoading ? 0 : 1 }}
                            allow="autoplay; fullscreen"
                        ></iframe>
                        {streamParams.schemeCompareActive && (
                            <div className="absolute bottom-4 left-4 text-white font-bold text-shadow bg-black/30 px-2 rounded z-20 pointer-events-none">方案 A (Main)</div>
                        )}
                    </div>

                    {/* Secondary Stream (Right) */}
                    {streamParams.schemeCompareActive && (
                        <div className="w-1/2 h-full relative animate-in fade-in slide-in-from-right-10 duration-500">
                            <iframe
                                src={`http://${streamParams.schemeIp}:${streamParams.schemePort || 8888}/apps/VREDStreamApp/index.html`}
                                frameBorder="0"
                                width="100%"
                                height="100%"
                                allow="autoplay; fullscreen"
                            ></iframe>
                            <div className="absolute bottom-4 right-4 text-white font-bold text-shadow bg-black/30 px-2 rounded z-20 pointer-events-none">方案 B ({streamParams.schemeIp})</div>
                        </div>
                    )}

                    {streamParams.showCalibration && <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: 'linear-gradient(rgba(57, 197, 187, 0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(57, 197, 187, 0.3) 1px, transparent 1px)', backgroundSize: '50px 50px' }}></div>}
                </div>
                <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col p-6 overflow-y-auto custom-scrollbar">
                    {/* 1. HMD View Tracking */}
                    <div className="mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                        <h3 className="text-sm font-bold text-gray-300 mb-3 flex items-center gap-2"><Glasses size={16} className="text-[#39C5BB]" />HMD 视角追踪</h3>
                        <div className="space-y-3">
                            <div className="grid grid-cols-3 gap-2">
                                <div className="col-span-2">
                                    <label className="block text-[10px] text-gray-500 mb-1">SCREEN IP</label>
                                    <input type="text" placeholder="192.168.x.x" value={streamParams.hmdIp} onChange={(e) => updateStreamParam('hmdIp', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                </div>
                                <div>
                                    <label className="block text-[10px] text-gray-500 mb-1">Port</label>
                                    <input type="text" placeholder="8888" value={streamParams.hmdPort} onChange={(e) => updateStreamParam('hmdPort', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                </div>
                            </div>
                            <div>
                                <label className="block text-[10px] text-gray-500 mb-1">追踪间隔 (s)</label>
                                <input type="text" placeholder="2.0" value={streamParams.trackingInterval} onChange={(e) => updateStreamParam('trackingInterval', e.target.value)} onBlur={() => validateStreamParam('trackingInterval')} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                            </div>
                            <div>
                                <label className="block text-[10px] text-gray-500 mb-1">FOV 倍数 (0.5-10.0)</label>
                                <input type="text" placeholder="3.0" value={streamParams.fovMultiplier} onChange={(e) => updateStreamParam('fovMultiplier', e.target.value)} onBlur={() => validateStreamParam('fovMultiplier')} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                            </div>

                            <div className="flex rounded-lg overflow-hidden border border-gray-700 w-full">
                                <button
                                    onClick={() => handleAutoTracking(true)}
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.isTracking ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    开启追踪
                                </button>
                                <div className="w-[1px] bg-gray-700"></div>
                                <button
                                    onClick={() => handleAutoTracking(false)}
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.isTracking ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    停止追踪
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* 2. Scheme Compare */}
                    <div className="mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                        <h3 className="text-sm font-bold text-gray-300 mb-3 flex items-center gap-2"><SplitSquareHorizontal size={16} className="text-[#39C5BB]" />方案对比</h3>
                        <div className="space-y-3">
                            <div className="grid grid-cols-3 gap-2"><div className="col-span-2"><label className="block text-[10px] text-gray-500 mb-1">Node IP</label><input type="text" placeholder="192.168.x.x" value={streamParams.schemeIp} onChange={(e) => updateStreamParam('schemeIp', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" /></div><div><label className="block text-[10px] text-gray-500 mb-1">Port</label><input type="text" placeholder="8888" value={streamParams.schemePort} onChange={(e) => updateStreamParam('schemePort', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" /></div></div>

                            <div className="flex rounded-lg overflow-hidden border border-gray-700 w-full">
                                <button
                                    onClick={handleStartCompare}
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.schemeCompareActive ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    开启对比
                                </button>
                                <div className="w-[1px] bg-gray-700"></div>
                                <button
                                    onClick={handleStopCompare}
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.schemeCompareActive ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    关闭对比
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* 3. Realtime Reference */}
                    <div className="mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                        <h3 className="text-sm font-bold text-gray-300 mb-3 flex items-center gap-2"><ImageIcon size={16} className="text-[#39C5BB]" />实时参照</h3>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-[10px] text-gray-500 mb-1">参照图片目录</label>
                                <div className="flex gap-2">
                                    <input type="text" placeholder="C:/Reference/..." value={streamParams.liveRefFolder} onChange={(e) => updateStreamParam('liveRefFolder', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                    <button className="px-2 bg-gray-700 hover:bg-gray-600 rounded text-white border border-gray-600"><FolderOpen size={14} /></button>
                                </div>
                            </div>

                            <div className="flex rounded-lg overflow-hidden border border-gray-700 w-full">
                                <button
                                    onClick={() => handleRealtimeReference(true)}
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.realtimeRefActive ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    开启参照
                                </button>
                                <div className="w-[1px] bg-gray-700"></div>
                                <button
                                    onClick={() => handleRealtimeReference(false)}
                                    className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.realtimeRefActive ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    关闭参照
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="mt-auto pt-4 border-t border-gray-800 space-y-3">
                        <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">显示模式</h3>
                        <div className="grid grid-cols-3 gap-2">
                            <button
                                onClick={handleStandardDisplay}
                                className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'standard' ? `text-white shadow-lg` : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'}`}
                                style={{ backgroundColor: streamParams.displayMode === 'standard' ? THEME_COLOR : '' }}
                            >
                                <Monitor size={18} /> 标准
                            </button>

                            <button
                                onClick={handleEnterXR}
                                className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'xr' ? `text-white shadow-lg` : 'bg-gray-800 border border-gray-700 text-gray-400 hover:bg-gray-700 hover:text-white'}`}
                                style={{ backgroundColor: streamParams.displayMode === 'xr' ? THEME_COLOR : '' }}
                            >
                                <Glasses size={18} /> XR
                            </button>

                            <button
                                onClick={handleEnterMR}
                                className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'mr' ? `text-white shadow-lg` : 'bg-gray-800 border border-gray-700 text-gray-400 hover:bg-gray-700 hover:text-white'}`}
                                style={{ backgroundColor: streamParams.displayMode === 'mr' ? THEME_COLOR : '' }}
                            >
                                <Headset size={18} /> MR
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StreamingView;
