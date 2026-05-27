import React, { useRef, useState, useEffect } from 'react';
import { ArrowLeft, Activity, Glasses, SplitSquareHorizontal, ImageIcon, Headset, FolderOpen, Monitor, RotateCcw, Power, Zap, Save, CheckCircle, XCircle, Mic, MicOff, Gamepad2 } from 'lucide-react';
import ProjectThumbnail from './ProjectThumbnail';
import { api } from '../services/api';
import { api as vredApi } from '../services/vredPython';
import { MR_TOOLS } from '../constants';
import { getAllToolsScript, getSwitchToolCommand, getCleanupAllCommand } from '../utils/vredPy';

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

// Build Python script for gamepad camera movement (pure function, no React deps)
// QMatrix4x4 is not iterable in PySide6 — extract with [row,col] tuple indexing (row-major),
// then reconstruct via QMatrix4x4(*m) for setWorldTransform.
// Yaw rotates around world Y axis (only x/z components change) to keep horizon level.
// Pitch rotates around local X (right) axis.
const buildGamepadPython = (lx, ly, rx, ry, roll, vz, ms, rs) => {
    const f = (n) => n.toFixed(4);
    return `import math
from PySide6.QtGui import QMatrix4x4
cam=vrCameraService.getActiveCamera()
_t=cam.getWorldTransform()
m=[_t[i//4,i%4] for i in range(16)]
ms=${ms};rs=${rs};lx=${f(lx)};ly=${f(ly)};rx_v=${f(rx)};ry_v=${f(-ry)};roll_v=${f(roll)};vz=${f(vz)}
right=[m[0],m[4],m[8]];fwd=[m[2],m[6],m[10]]
m[3]+=right[0]*lx*ms+fwd[0]*ly*ms;m[7]+=right[1]*lx*ms+fwd[1]*ly*ms;m[11]+=right[2]*lx*ms+fwd[2]*ly*ms+vz*ms
if abs(rx_v)>0.001:
 cy=math.cos(math.radians(rx_v*rs));sy=math.sin(math.radians(rx_v*rs))
 a,b=m[0],m[4];c,d=m[1],m[5];e,g=m[2],m[6]
 m[0]=cy*a+sy*b;m[4]=-sy*a+cy*b
 m[1]=cy*c+sy*d;m[5]=-sy*c+cy*d
 m[2]=cy*e+sy*g;m[6]=-sy*e+cy*g
if abs(ry_v)>0.001:
 up=[m[1],m[5],m[9]];fwd=[m[2],m[6],m[10]]
 cp=math.cos(math.radians(ry_v*rs));sp=math.sin(math.radians(ry_v*rs))
 nu0=cp*up[0]+sp*fwd[0];nu1=cp*up[1]+sp*fwd[1];nu2=cp*up[2]+sp*fwd[2]
 nf0=-sp*up[0]+cp*fwd[0];nf1=-sp*up[1]+cp*fwd[1];nf2=-sp*up[2]+cp*fwd[2]
 m[1],m[5],m[9]=nu0,nu1,nu2;m[2],m[6],m[10]=nf0,nf1,nf2
if abs(roll_v)>0.001:
 right=[m[0],m[4],m[8]];up=[m[1],m[5],m[9]]
 cr=math.cos(math.radians(roll_v*rs));sr=math.sin(math.radians(roll_v*rs))
 nr0=cr*right[0]-sr*up[0];nr1=cr*right[1]-sr*up[1];nr2=cr*right[2]-sr*up[2]
 nu0=sr*right[0]+cr*up[0];nu1=sr*right[1]+cr*up[1];nu2=sr*right[2]+cr*up[2]
 m[0],m[4],m[8]=nr0,nr1,nr2;m[1],m[5],m[9]=nu0,nu1,nu2
cam.setWorldTransform(QMatrix4x4(*m))`;
};

const StreamingView = ({
    streamingMachineId,
    setStreamingMachineId,
    machines,
    projects,
    runningMachines,
    onProjectCreated
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

    const ensureStreamPanelInjected = async () => {
        if (!machine) return;
        try {
            // 每次进入 XR/MR 都重新注入以更新面板 URL（guard 外的 StreamPanel 段会重新执行）
            await api.processes.executePython(
                machine.ip,
                machine.port || 8888,
                getAllToolsScript(getStreamPanelUrl())
            );
            setIsToolsInjected(true);
        } catch (e) {
            console.error('Failed to inject stream panel:', e);
        }
    };

    const setShadowPlaneVisibility = (visible) => {
        sendPython(`node = vrNodeService.findNode("ShadowPlane")
if node.isValid():
    node.setVisibilityFlag(${visible ? 'True' : 'False'})`);
    };

    const handleEnterXR = async () => {
        updateStreamParam('displayMode', 'xr');
        sendPython('setDisplayMode(VR_DISPLAY_OPEN_XR)');
        setShadowPlaneVisibility(true);
        await removeSceneplateFloor();
        // await ensureStreamPanelInjected();
    };

    const handleEnterMR = async () => {
        updateStreamParam('displayMode', 'mr');
        sendPython('setDisplayMode(VR_DISPLAY_OPEN_XR)');
        setShadowPlaneVisibility(false);
        await createSceneplateFloor();
        // await ensureStreamPanelInjected();
    };

    const createSceneplateFloor = async () => {
        if (!machine) return;
        try {
            // 网络路径需要使用正斜杠或双反斜杠
            const floorImagePath = `//${import.meta.env.VITE_UPLOAD_HOST}/upload/blue.jpg`;
            
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

    // --- Gamepad control ---
    const [gamepadConnected, setGamepadConnected] = useState(false);
    const [gamepadEnabled, setGamepadEnabled] = useState(false);
    const [gamepadMoveSpeed, setGamepadMoveSpeed] = useState('100');
    const [gamepadRotSpeed, setGamepadRotSpeed] = useState('1.0');
    const [cameraHeight, setCameraHeight] = useState('175'); // cm
    const gamepadRafRef = useRef(null);
    const gamepadSendingRef = useRef(false);   // request in-flight
    const gamepadPendingRef = useRef(null);    // latest input buffered while in-flight
    const gamepadEnabledRef = useRef(false);
    const machineRef = useRef(null);
    const gamepadMoveSpeedRef = useRef(300);
    const gamepadRotSpeedRef = useRef(2.0);

    // Keep refs in sync with state/props for use inside rAF callback
    useEffect(() => { machineRef.current = machine; });
    useEffect(() => { gamepadEnabledRef.current = gamepadEnabled; }, [gamepadEnabled]);
    useEffect(() => { gamepadMoveSpeedRef.current = parseFloat(gamepadMoveSpeed) || 300; }, [gamepadMoveSpeed]);
    useEffect(() => { gamepadRotSpeedRef.current = parseFloat(gamepadRotSpeed) || 2.0; }, [gamepadRotSpeed]);

    const handleSetCameraHeight = () => {
        if (!machine) return;
        const heightMm = (parseFloat(cameraHeight) || 170) * 10; // cm → mm
        const code = `from PySide6.QtGui import QMatrix4x4
cam=vrCameraService.getActiveCamera()
_t=cam.getWorldTransform()
m=[_t[i//4,i%4] for i in range(16)]
m[11]=${heightMm}
cam.setWorldTransform(QMatrix4x4(*m))`;
        api.processes.executePython(machine.ip, machine.port || 8888, code).catch(() => {});
    };

    // Listen for gamepad connect/disconnect events
    useEffect(() => {
        const onConnect = () => setGamepadConnected(true);
        const onDisconnect = () => {
            setGamepadConnected(false);
            setGamepadEnabled(false);
        };
        window.addEventListener('gamepadconnected', onConnect);
        window.addEventListener('gamepaddisconnected', onDisconnect);
        // Check if a gamepad is already connected on mount
        const pads = navigator.getGamepads ? navigator.getGamepads() : [];
        for (const pad of pads) { if (pad) { setGamepadConnected(true); break; } }
        return () => {
            window.removeEventListener('gamepadconnected', onConnect);
            window.removeEventListener('gamepaddisconnected', onDisconnect);
        };
    }, []);

    // Gamepad rAF loop — reassigned each render so it always reads latest refs
    const gamepadTick = useRef(null);
    gamepadTick.current = () => {
        const pads = navigator.getGamepads ? navigator.getGamepads() : [];
        const pad = Array.from(pads).find(p => p !== null) ?? null;
        if (pad && gamepadEnabledRef.current && machineRef.current) {
            const DEAD = 0.12;
            const lx = Math.abs(pad.axes[0] || 0) > DEAD ? (pad.axes[0] || 0) : 0;
            const ly = Math.abs(pad.axes[1] || 0) > DEAD ? (pad.axes[1] || 0) : 0;
            const rx = Math.abs(pad.axes[2] || 0) > DEAD ? (pad.axes[2] || 0) : 0;
            const ry = Math.abs(pad.axes[3] || 0) > DEAD ? (pad.axes[3] || 0) : 0;
            const b4 = pad.buttons[4]?.pressed ? -1 : 0; // LB = roll left
            const b5 = pad.buttons[5]?.pressed ?  1 : 0; // RB = roll right
            const roll = b4 + b5;
            const b0 = pad.buttons[12]?.pressed ?  1 : 0; // DPad Up = move up
            const b3 = pad.buttons[13]?.pressed ? -1 : 0; // DPad Down = move down
            const vz = b0 + b3;
            // Blur any focused input to prevent iPad system keyboard from popping up
            // when gamepad buttons (mapped to Tab by Safari) shift focus to inputs
            if ((roll || vz || lx || ly || rx || ry) && document.activeElement && document.activeElement !== document.body) {
                document.activeElement.blur();
            }
            const hasInput = lx || ly || rx || ry || roll || vz;
            if (hasInput) {
                // Always store latest values; will be consumed by sendPending
                gamepadPendingRef.current = { lx, ly, rx, ry, roll, vz };
                if (!gamepadSendingRef.current) {
                    const sendPending = () => {
                        const input = gamepadPendingRef.current;
                        if (!input || !machineRef.current) return;
                        gamepadPendingRef.current = null;
                        gamepadSendingRef.current = true;
                        const code = buildGamepadPython(input.lx, input.ly, input.rx, input.ry, input.roll, input.vz, gamepadMoveSpeedRef.current, gamepadRotSpeedRef.current);
                        api.processes.executePython(machineRef.current.ip, machineRef.current.port || 8888, code)
                            .catch(() => {})
                            .finally(() => {
                                gamepadSendingRef.current = false;
                                // If new input arrived while request was in-flight, send it immediately
                                if (gamepadPendingRef.current) sendPending();
                            });
                    };
                    sendPending();
                }
                // else: in-flight — pending updated above, will be flushed on complete
            }
        }
        gamepadRafRef.current = requestAnimationFrame(gamepadTick.current);
    };

    useEffect(() => {
        if (gamepadEnabled) {
            gamepadRafRef.current = requestAnimationFrame(gamepadTick.current);
        } else {
            if (gamepadRafRef.current) { cancelAnimationFrame(gamepadRafRef.current); gamepadRafRef.current = null; }
        }
        return () => { if (gamepadRafRef.current) { cancelAnimationFrame(gamepadRafRef.current); gamepadRafRef.current = null; } };
    }, [gamepadEnabled]);

    // --- Tab & MR Tools state ---
    const [activeTab, setActiveTab] = useState(0); // 0: 控制面板, 1: MR 工具
    const [gamepadPanelOpen, setGamepadPanelOpen] = useState(false);
    const [activeTool, setActiveTool] = useState(null);
    const [isToolsInjected, setIsToolsInjected] = useState(false);

    const getStreamPanelUrl = () => {
        const token = localStorage.getItem('jwt') || '';
        return `${window.location.origin}/#/stream?machineId=${streamingMachineId}&token=${encodeURIComponent(token)}`;
    };

    const handleSwitchTool = async (tool) => {
        if (!machine) return;
        try {
            let code = '';
            if (!isToolsInjected) {
                code = getAllToolsScript(getStreamPanelUrl()) + '\n';
            }
            code += getSwitchToolCommand(tool.id);
            await api.processes.executePython(machine.ip, machine.port || 8888, code);
            setIsToolsInjected(true);
            setActiveTool(tool.id);
        } catch (e) {
            console.error('Failed to switch MR tool:', e);
        }
    };

    const handleResetTools = async () => {
        if (!machine || !isToolsInjected) return;
        try {
            await api.processes.executePython(machine.ip, machine.port || 8888, getCleanupAllCommand());
            setActiveTool(null);
            setIsToolsInjected(false);
        } catch (e) {
            console.error('Failed to reset MR tools:', e);
        }
    };

    const [iframeLoading, setIframeLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [saveResult, setSaveResult] = useState(null); // { ok: bool, msg: string } | null

    // --- Voice control state ---
    // Use same-origin proxy (/voice-api) so getUserMedia works over HTTPS
    const VOICE_SERVICE_URL = '/voice-api';
    const [isRecording, setIsRecording] = useState(false);
    const [voiceStatus, setVoiceStatus] = useState(null); // { ok, msg } | null
    const [voiceTranscript, setVoiceTranscript] = useState('');
    const [variantSets, setVariantSets] = useState([]);
    const [chatInput, setChatInput] = useState('');
    const [chatLoading, setChatLoading] = useState(false);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);

    const fetchVariantSets = async () => {
        if (!machine) return;
        try {
            const params = new URLSearchParams({
                vred_ip: machine.ip,
                vred_port: machine.port || 8888,
            });
            const resp = await fetch(`${VOICE_SERVICE_URL}/variant-sets?${params}`);
            if (resp.ok) {
                const data = await resp.json();
                setVariantSets(data.variant_sets || []);
            }
        } catch (e) {
            console.error('Failed to fetch variant sets:', e);
        }
    };

    const sendTextCommand = async (text) => {
        if (!text.trim() || chatLoading) return;
        setChatLoading(true);
        setVoiceStatus({ ok: null, msg: '处理中…' });
        setVoiceTranscript('');
        try {
            const form = new FormData();
            form.append('text', text.trim());
            if (machine) {
                form.append('vred_ip', machine.ip);
                form.append('vred_port', String(machine.port || 8888));
            }
            const resp = await fetch(`${VOICE_SERVICE_URL}/text-command`, { method: 'POST', body: form });
            if (!resp.ok) throw new Error(await resp.text());
            const data = await resp.json();
            setVoiceTranscript(data.transcript || text.trim());
            if (data.intent?.action === 'activate_variant') {
                const ok = data.vred_result?.ok ?? false;
                setVoiceStatus({ ok, msg: ok ? `已切换: ${data.intent.name}` : `切换失败: ${data.intent.name}` });
            } else {
                setVoiceStatus({ ok: false, msg: data.intent?.reason || '未识别到指令' });
            }
        } catch (e) {
            setVoiceStatus({ ok: false, msg: '请求失败: ' + e.message });
        } finally {
            setChatLoading(false);
            setTimeout(() => setVoiceStatus(null), 6000);
        }
    };

    const startRecording = async () => {
        if (isRecording) return;
        if (!navigator.mediaDevices?.getUserMedia) {
            setVoiceStatus({ ok: false, msg: '浏览器不支持麦克风访问（需要 HTTPS 或 localhost）' });
            return;
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream);
            audioChunksRef.current = [];
            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunksRef.current.push(e.data);
            };
            mediaRecorderRef.current = recorder;
            recorder.start(100); // collect data every 100 ms
            setIsRecording(true);
            setVoiceStatus(null);
            setVoiceTranscript('');
        } catch (e) {
            setVoiceStatus({ ok: false, msg: '麦克风权限被拒绝: ' + e.message });
        }
    };

    const stopRecordingAndSend = async () => {
        if (!isRecording || !mediaRecorderRef.current) return;
        setIsRecording(false);
        const recorder = mediaRecorderRef.current;
        await new Promise((resolve) => {
            recorder.onstop = resolve;
            recorder.stop();
        });
        // Stop all mic tracks
        recorder.stream?.getTracks().forEach(t => t.stop());

        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        audioChunksRef.current = [];

        if (blob.size < 512) {
            setVoiceStatus({ ok: false, msg: '录音太短，请按住按钮说话后再松开' });
            setTimeout(() => setVoiceStatus(null), 4000);
            return;
        }

        setVoiceStatus({ ok: null, msg: '识别中…' });
        try {
            const form = new FormData();
            form.append('audio', blob, 'audio.webm');
            if (machine) {
                form.append('vred_ip', machine.ip);
                form.append('vred_port', String(machine.port || 8888));
            }
            const resp = await fetch(`${VOICE_SERVICE_URL}/voice-command`, {
                method: 'POST',
                body: form,
            });
            if (!resp.ok) {
                const err = await resp.text();
                throw new Error(err);
            }
            const data = await resp.json();
            setVoiceTranscript(data.transcript || '');
            if (data.intent?.action === 'activate_variant') {
                const ok = data.vred_result?.ok ?? false;
                setVoiceStatus({ ok, msg: ok ? `已切换: ${data.intent.name}` : `切换失败: ${data.intent.name}` });
            } else {
                setVoiceStatus({ ok: false, msg: data.intent?.reason || '未识别到指令' });
            }
        } catch (e) {
            setVoiceStatus({ ok: false, msg: '请求失败: ' + e.message });
        } finally {
            setTimeout(() => setVoiceStatus(null), 6000);
        }
    };

    const onIframeLoad = () => {
        setIframeLoading(false);
    };

    const goBack = () => setStreamingMachineId(null);

    const handleSaveAs = async () => {
        if (!machine || isSaving) return;
        setIsSaving(true);
        setSaveResult(null);
        try {
            const tusdPrefix = import.meta.env.VITE_TUSD_PATH_PREFIX || '';
            const backupDir = (tusdPrefix + 'backup\\').replace(/\\/g, '\\\\');

            // 从 project 记录直接取文件名，避免依赖 VRED Python API
            let rawFileName = project?.fileName || project?.name || 'backup';
            // 确保扩展名为 .vpb
            const fileName = rawFileName.toLowerCase().endsWith('.vpb')
                ? rawFileName
                : rawFileName.replace(/\.[^.]+$/, '') + '.vpb';

            const pythonScript = `
import os

try:
    fileName = '${fileName}'
    backupDir = '${backupDir}'
    if not os.path.exists(backupDir):
        os.makedirs(backupDir)
    savePath = os.path.join(backupDir, fileName)
    vrFileIOService.saveFile(savePath)
    print('SAVE_OK:' + savePath)
except Exception as e:
    print('SAVE_ERR:' + str(e))
`;
            let output = '';
            try {
                const result = await api.processes.executePython(machine.ip, machine.port || 8888, pythonScript);
                output = typeof result === 'string' ? result : JSON.stringify(result);
            } catch (fetchErr) {
                const msg = fetchErr?.message || '';
                // 超时说明 VRED 正在保存（耗时较长），实际已触发保存，视为成功
                if (/timeout/i.test(msg)) {
                    setSaveResult({ ok: true, msg: `${fileName} (保存中，请稍候)` });
                    // 仍然注册到项目库
                    try {
                        const tusdPrefix = import.meta.env.VITE_TUSD_PATH_PREFIX || '';
                        const backupFilePath = tusdPrefix + 'backup\\' + fileName;
                        const newProjectData = {
                            name: (project?.name || fileName) + ' (备份)',
                            type: 'VRED',
                            fileName: fileName,
                            filePath: backupFilePath,
                            size: '',
                            date: new Date().toISOString().split('T')[0],
                            tags: Array.isArray(project?.tags) ? project.tags : [],
                            thumbnail: project?.thumbnail || null,
                        };
                        const created = await api.projects.create(newProjectData);
                        if (onProjectCreated) onProjectCreated(created);
                    } catch (regErr) {
                        console.error('Failed to register backup project:', regErr);
                    }
                    return;
                }
                throw fetchErr;
            }
            if (output && output.includes('SAVE_ERR:')) {
                const errMsg = output.split('SAVE_ERR:')[1]?.split('\n')[0] || '保存失败';
                setSaveResult({ ok: false, msg: errMsg });
            } else {
                const pathMatch = output && output.match(/SAVE_OK:(.+)/);
                const savedPath = pathMatch ? pathMatch[1].trim() : '已保存';
                setSaveResult({ ok: true, msg: savedPath });

                // 将备份文件注册到项目资源库
                try {
                    const tusdPrefix = import.meta.env.VITE_TUSD_PATH_PREFIX || '';
                    const backupFilePath = tusdPrefix + 'backup\\' + fileName;
                    const newProjectData = {
                        name: (project?.name || fileName) + ' (备份)',
                        type: 'VRED',
                        fileName: fileName,
                        filePath: backupFilePath,
                        size: '',
                        date: new Date().toISOString().split('T')[0],
                        tags: Array.isArray(project?.tags) ? project.tags : [],
                        thumbnail: project?.thumbnail || null,
                    };
                    const created = await api.projects.create(newProjectData);
                    if (onProjectCreated) onProjectCreated(created);
                } catch (regErr) {
                    console.error('Failed to register backup project:', regErr);
                }
            }
        } catch (e) {
            setSaveResult({ ok: false, msg: e.message || '执行失败' });
        } finally {
            setIsSaving(false);
            setTimeout(() => setSaveResult(null), 5000);
        }
    };

    const vredUrl = machine ? `http://${machine.ip}:${machine.port || 8888}/apps/VREDStreamApp/index.html` : '';

    return (
        <div className="absolute inset-0 z-30 bg-gray-900 flex flex-col animate-in fade-in duration-300">
            {/* Streaming Header */}
            <div className="h-16 flex items-center justify-between px-6 bg-gray-900 border-b border-gray-800 text-white shrink-0">
                <div className="flex items-center gap-4">
                    <button onClick={goBack} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors text-sm">
                        <ArrowLeft size={16} />退出预览
                    </button>
                    <button
                        onClick={handleSaveAs}
                        disabled={isSaving}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                        title={`另存为 VPB 到 backup 文件夹`}
                    >
                        {isSaving
                            ? <div className="w-4 h-4 border-2 border-t-transparent border-[#39C5BB] rounded-full animate-spin" />
                            : <Save size={16} className="text-[#39C5BB]" />
                        }
                        另存为
                    </button>
                    {saveResult && (
                        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono max-w-xs truncate animate-in fade-in duration-300 ${saveResult.ok ? 'bg-green-900/40 border border-green-700 text-green-400' : 'bg-red-900/40 border border-red-700 text-red-400'}`}>
                            {saveResult.ok ? <CheckCircle size={12} /> : <XCircle size={12} />}
                            <span className="truncate">{saveResult.ok ? `已保存: ${saveResult.msg}` : `失败: ${saveResult.msg}`}</span>
                        </div>
                    )}
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
                <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col overflow-hidden">
                    {/* Tab Bar */}
                    <div className="flex shrink-0 border-b border-gray-800">
                        <button
                            onClick={() => setActiveTab(0)}
                            className={`flex-1 py-3 text-xs font-bold tracking-wide transition-colors border-b-2 ${activeTab === 0 ? 'text-[#39C5BB] border-[#39C5BB]' : 'text-gray-500 border-transparent hover:text-gray-300'}`}
                        >
                            控制面板
                        </button>
                        <button
                            onClick={() => setActiveTab(1)}
                            className={`flex-1 py-3 text-xs font-bold tracking-wide transition-colors border-b-2 ${activeTab === 1 ? 'text-[#39C5BB] border-[#39C5BB]' : 'text-gray-500 border-transparent hover:text-gray-300'}`}
                        >
                            MR 工具
                        </button>
                    </div>

                    {/* Tab 1: 控制面板 */}
                    {activeTab === 0 && (
                        <div className="flex-1 flex flex-col p-4 overflow-y-auto custom-scrollbar">
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
                                        <button onClick={() => handleAutoTracking(true)} className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.isTracking ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}>开启追踪</button>
                                        <div className="w-[1px] bg-gray-700"></div>
                                        <button onClick={() => handleAutoTracking(false)} className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.isTracking ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}>停止追踪</button>
                                    </div>
                                </div>
                            </div>

                            {/* 2. Scheme Compare */}
                            <div className="mb-6 p-4 bg-gray-800/50 rounded-xl border border-gray-700">
                                <h3 className="text-sm font-bold text-gray-300 mb-3 flex items-center gap-2"><SplitSquareHorizontal size={16} className="text-[#39C5BB]" />方案对比</h3>
                                <div className="space-y-3">
                                    <div className="grid grid-cols-3 gap-2">
                                        <div className="col-span-2"><label className="block text-[10px] text-gray-500 mb-1">Node IP</label><input type="text" placeholder="192.168.x.x" value={streamParams.schemeIp} onChange={(e) => updateStreamParam('schemeIp', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" /></div>
                                        <div><label className="block text-[10px] text-gray-500 mb-1">Port</label><input type="text" placeholder="8888" value={streamParams.schemePort} onChange={(e) => updateStreamParam('schemePort', e.target.value)} className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" /></div>
                                    </div>
                                    <div className="flex rounded-lg overflow-hidden border border-gray-700 w-full">
                                        <button onClick={handleStartCompare} className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.schemeCompareActive ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}>开启对比</button>
                                        <div className="w-[1px] bg-gray-700"></div>
                                        <button onClick={handleStopCompare} className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.schemeCompareActive ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}>关闭对比</button>
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
                                        <button onClick={() => handleRealtimeReference(true)} className={`flex-1 py-2 text-xs font-bold transition-colors ${streamParams.realtimeRefActive ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}>开启参照</button>
                                        <div className="w-[1px] bg-gray-700"></div>
                                        <button onClick={() => handleRealtimeReference(false)} className={`flex-1 py-2 text-xs font-bold transition-colors ${!streamParams.realtimeRefActive ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}>关闭参照</button>
                                    </div>
                                </div>
                            </div>

                            <div className="mt-auto pt-4 border-t border-gray-800 space-y-3">
                                <h3 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">显示模式</h3>
                                <div className="grid grid-cols-3 gap-2">
                                    <button onClick={handleStandardDisplay} className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'standard' ? 'text-white shadow-lg' : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'}`} style={{ backgroundColor: streamParams.displayMode === 'standard' ? THEME_COLOR : '' }}>
                                        <Monitor size={18} /> 标准
                                    </button>
                                    <button onClick={handleEnterXR} className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'xr' ? 'text-white shadow-lg' : 'bg-gray-800 border border-gray-700 text-gray-400 hover:bg-gray-700 hover:text-white'}`} style={{ backgroundColor: streamParams.displayMode === 'xr' ? THEME_COLOR : '' }}>
                                        <Glasses size={18} /> XR
                                    </button>
                                    <button onClick={handleEnterMR} className={`py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 transition-all ${streamParams.displayMode === 'mr' ? 'text-white shadow-lg' : 'bg-gray-800 border border-gray-700 text-gray-400 hover:bg-gray-700 hover:text-white'}`} style={{ backgroundColor: streamParams.displayMode === 'mr' ? THEME_COLOR : '' }}>
                                        <Headset size={18} /> MR
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Tab 2: MR 工具 */}
                    {activeTab === 1 && (
                        <div className="flex-1 flex flex-col p-4 overflow-y-auto custom-scrollbar">
                            {/* Header */}
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">MR工具菜单</span>
                                    {isToolsInjected && (
                                        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#39C5BB]/10 border border-[#39C5BB]/30">
                                            <Zap size={10} className="text-[#39C5BB]" />
                                            <span className="text-[10px] font-bold text-[#39C5BB]">已注入</span>
                                        </div>
                                    )}
                                </div>
                                <button
                                    onClick={handleResetTools}
                                    disabled={!isToolsInjected}
                                    className="text-[10px] px-2 py-1 rounded border border-red-800 text-red-400 bg-red-900/20 hover:bg-red-900/40 transition-all font-bold flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
                                >
                                    <RotateCcw size={10} /> 清除
                                </button>
                            </div>

                            {/* Tools Grid */}
                            <div className="grid grid-cols-2 gap-3">
                                {MR_TOOLS.map(tool => {
                                    const isActive = activeTool === tool.id;
                                    return (
                                        <button
                                            key={tool.id}
                                            onClick={() => handleSwitchTool(tool)}
                                            className={`relative flex flex-col items-center p-4 rounded-xl border transition-all ${
                                                isActive
                                                    ? 'border-[#39C5BB] bg-[#39C5BB]/10 shadow-lg shadow-[#39C5BB]/10'
                                                    : 'border-gray-700 bg-gray-800/50 hover:border-gray-600 hover:bg-gray-800'
                                            }`}
                                        >
                                            {isActive && (
                                                <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-[#39C5BB] flex items-center justify-center animate-pulse">
                                                    <Power size={8} className="text-white" />
                                                </div>
                                            )}
                                            <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-2 ${isActive ? 'bg-[#39C5BB]/20' : 'bg-gray-700/50'}`}>
                                                <tool.icon size={20} style={{ color: isActive ? '#39C5BB' : '#9ca3af' }} />
                                            </div>
                                            <span className="text-xs font-bold" style={{ color: isActive ? '#39C5BB' : '#d1d5db' }}>
                                                {tool.name}
                                            </span>
                                            <span className="text-[10px] text-center mt-0.5" style={{ color: isActive ? '#6ee7e3' : '#6b7280' }}>
                                                {isActive ? '当前生效' : tool.description}
                                            </span>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                    {/* Tab 3: 手柄控制 */}
                    {activeTab === 2 && (
                        <div className="flex-1 flex flex-col p-4 overflow-y-auto custom-scrollbar">
                        </div>
                    )}
                </div>
            </div>

            {/* Gamepad floating button — only when connected */}
            {gamepadConnected && (
                <button
                    onClick={() => setGamepadPanelOpen(v => !v)}
                    className={`absolute bottom-6 right-[340px] z-40 flex items-center gap-2 px-3 py-2 rounded-xl shadow-lg border transition-all ${
                        gamepadEnabled
                            ? 'bg-[#39C5BB] border-[#39C5BB] text-white shadow-[#39C5BB]/30'
                            : 'bg-gray-800/90 border-gray-700 text-gray-300 hover:border-[#39C5BB]/50 hover:text-[#39C5BB]'
                    }`}
                    title="手柄控制"
                >
                    <Gamepad2 size={16} />
                    {gamepadEnabled && <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />}
                </button>
            )}

            {/* Gamepad floating panel */}
            {gamepadPanelOpen && gamepadConnected && (
                <div className="absolute bottom-16 right-[340px] z-40 w-72 bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-200">
                    {/* Panel header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                        <div className="flex items-center gap-2">
                            <Gamepad2 size={14} className="text-[#39C5BB]" />
                            <span className="text-xs font-bold text-gray-200">手柄控制</span>
                            <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-[#39C5BB]/10 border border-[#39C5BB]/30">
                                <div className="w-1 h-1 rounded-full bg-[#39C5BB] animate-pulse" />
                                <span className="text-[9px] font-bold text-[#39C5BB]">已连接</span>
                            </div>
                        </div>
                        <button onClick={() => setGamepadPanelOpen(false)} className="text-gray-500 hover:text-gray-200 transition-colors text-xs">✕</button>
                    </div>

                    <div className="p-4 space-y-4 overflow-y-auto max-h-[70vh] custom-scrollbar">
                        {/* Speed Settings */}
                        <div className="space-y-2">
                            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">速度设置</p>
                            <div className="grid grid-cols-2 gap-2">
                                <div>
                                    <label className="block text-[10px] text-gray-500 mb-1">移动 (mm/步)</label>
                                    <input type="number" min="1" max="500" value={gamepadMoveSpeed} onChange={(e) => setGamepadMoveSpeed(e.target.value)}
                                        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                </div>
                                <div>
                                    <label className="block text-[10px] text-gray-500 mb-1">旋转 (°/步)</label>
                                    <input type="number" min="0.1" max="10" step="0.1" value={gamepadRotSpeed} onChange={(e) => setGamepadRotSpeed(e.target.value)}
                                        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                </div>
                            </div>
                        </div>

                        {/* Camera Height */}
                        <div className="space-y-2">
                            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">摄像机高度</p>
                            <div className="flex gap-2">
                                <div className="flex-1">
                                    <label className="block text-[10px] text-gray-500 mb-1">身高 (cm)</label>
                                    <input type="number" min="50" max="250" step="1" value={cameraHeight} onChange={(e) => setCameraHeight(e.target.value)}
                                        className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white focus:border-[#39C5BB] outline-none" />
                                </div>
                                <div className="flex items-end">
                                    <button onClick={handleSetCameraHeight} disabled={!machine}
                                        className="px-3 py-1.5 rounded text-xs font-bold bg-[#39C5BB]/20 border border-[#39C5BB]/40 text-[#39C5BB] hover:bg-[#39C5BB]/30 transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                                        应用
                                    </button>
                                </div>
                            </div>
                            <p className="text-[9px] text-gray-600">{cameraHeight} cm = {((parseFloat(cameraHeight)||0)*10).toFixed(0)} mm</p>
                        </div>

                        {/* Stick legend */}
                        <div className="space-y-2">
                            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">按键映射</p>
                            <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                                <div className="bg-gray-800 rounded-lg p-2"><span className="text-[#39C5BB] font-bold">L STICK</span><br/><span className="text-gray-400">↑↓ 前后 · ←→ 左右</span></div>
                                <div className="bg-gray-800 rounded-lg p-2"><span className="text-[#39C5BB] font-bold">R STICK</span><br/><span className="text-gray-400">←→ 偏航 · ↑↓ 俯仰</span></div>
                                <div className="bg-gray-800 rounded-lg p-2"><span className="text-[#39C5BB] font-bold">LB / RB</span><br/><span className="text-gray-400">向左 / 向右横滚</span></div>
                                <div className="bg-gray-800 rounded-lg p-2"><span className="text-[#39C5BB] font-bold">十字键 ↑↓</span><br/><span className="text-gray-400">上升 / 下降</span></div>
                            </div>
                        </div>

                        {/* Enable / Disable — bottom */}
                        <div className="pt-1 border-t border-gray-800">
                            <div className="flex rounded-lg overflow-hidden border border-gray-700 w-full">
                                <button
                                    onClick={() => { setGamepadEnabled(true); setTimeout(() => setGamepadPanelOpen(false), 5000); }}
                                    className={`flex-1 py-2.5 text-xs font-bold transition-colors ${gamepadEnabled ? 'bg-[#39C5BB] text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    启用飞行控制
                                </button>
                                <div className="w-[1px] bg-gray-700"></div>
                                <button
                                    onClick={() => { setGamepadEnabled(false); setTimeout(() => setGamepadPanelOpen(false), 5000); }}
                                    className={`flex-1 py-2.5 text-xs font-bold transition-colors ${!gamepadEnabled ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-500 hover:bg-gray-700'}`}
                                >
                                    停用
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default StreamingView;
