# ======================================================================
# VRED Physics Tracker
#
# tracker-1 → TransformTracker: timer 驱动任意 Transform3D 节点（保持相对偏移）
# tracker-2 → ColaTracker: 作为可乐瓶 (Cola) 的物理运动学对象
#             ├── kinematic: timer 同步位姿并锁定缩放（避免瓶子变大）
#             ├── 自动确保 Cola 注册为 kinematic physics 对象
#             └── 碰撞回调：打印碰撞开始/结束事件及接触点信息
#
# 用法（VRED Python 控制台）：
#   setup_transform("tracker-1", "SeatNode")  # 配置 tracker-1 → Transform3D 绑定
#   setup_cola("tracker-2", "Cola")           # 配置 tracker-2 → Cola kinematic 追踪
#   start_transform()                          # 启动 tracker-1 追踪
#   start_cola()                               # 启动 tracker-2 物理追踪
#   stop_cola()                                # 停止，解除约束
#   physics_status()                           # 打印当前状态
#
# 右手 Y 键（左手控制器）：切换 tracker-1 追踪开/关
# 右手 B 键（右手控制器）：切换 tracker-2 Cola 追踪开/关
# ======================================================================

import math

global _transform_tracker, _cola_tracker

# 每次重新加载时强制重新初始化，确保代码更新生效
if '_cola_tracker' in globals() and _cola_tracker is not None:
    try:
        _cola_tracker.stop()
    except Exception:
        pass
if '_transform_tracker' in globals() and _transform_tracker is not None:
    try:
        _transform_tracker.stop()
    except Exception:
        pass
global _physics_tracker_initialized
_physics_tracker_initialized = False

if '_physics_tracker_initialized' in globals() and _physics_tracker_initialized:
    print("[PhysicsTracker] Already initialized, skipping re-init")
else:
    _physics_tracker_initialized = False

    def _mul3x3(a, b):
        return [[
            a[0][0] * b[0][0] + a[0][1] * b[1][0] + a[0][2] * b[2][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1] + a[0][2] * b[2][1],
            a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2] * b[2][2]],
            [
            a[1][0] * b[0][0] + a[1][1] * b[1][0] + a[1][2] * b[2][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1] + a[1][2] * b[2][1],
            a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2] * b[2][2]],
            [
            a[2][0] * b[0][0] + a[2][1] * b[1][0] + a[2][2] * b[2][0],
            a[2][0] * b[0][1] + a[2][1] * b[1][1] + a[2][2] * b[2][1],
            a[2][0] * b[0][2] + a[2][1] * b[1][2] + a[2][2] * b[2][2]]]

    def _extract_device_translation(device):
        """获取 VR 设备位置。从 tracker 场景节点世界坐标读取（与位置跟随一致）。"""
        try:
            node = device.getNode()
            return getTransformNodeTranslation(node, True)
        except Exception:
            return None

    def _euler_to_mat3(rx_deg, ry_deg, rz_deg):
        """Euler 角（度）→ 3x3 旋转矩阵，R = Rz*Ry*Rx 顺序（与 _mat3_to_euler 一致）。"""
        rx = math.radians(rx_deg)
        ry = math.radians(ry_deg)
        rz = math.radians(rz_deg)
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy_v = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        return [
            [cz*cy,              cz*sy_v*sx - sz*cx,  cz*sy_v*cx + sz*sx],
            [sz*cy,              sz*sy_v*sx + cz*cx,  sz*sy_v*cx - cz*sx],
            [-sy_v,              cy*sx,               cy*cx]
        ]

    def _mat3_t(m):
        """转置 3x3 矩阵（正交旋转矩阵的转置 = 逆）。"""
        return [[m[0][0], m[1][0], m[2][0]],
                [m[0][1], m[1][1], m[2][1]],
                [m[0][2], m[1][2], m[2][2]]]

    def _get_tracker_mat3(device):
        """从 tracker 提取世界空间 3x3 旋转矩阵。
        优先使用节点世界变换（不随摄像机方向变化），
        回退到 getTrackingMatrix()（可能受摄像机影响）。
        列主序 4x4 矩阵：列 0-2 的前三行即旋转矩阵。
        """
        # 方法1：v1 API node.getWorldTransform() → 16 浮点数列主序 4x4
        try:
            node = device.getNode()
            wm = node.getWorldTransform()
            if wm and len(wm) == 16:
                return [[wm[0], wm[4], wm[8]],
                        [wm[1], wm[5], wm[9]],
                        [wm[2], wm[6], wm[10]]]
        except Exception:
            pass
        # 方法2：v1 API device.getWorldMatrix() → 16 浮点数列主序 4x4
        try:
            wm = device.getWorldMatrix()
            if wm and len(wm) == 16:
                return [[wm[0], wm[4], wm[8]],
                        [wm[1], wm[5], wm[9]],
                        [wm[2], wm[6], wm[10]]]
        except Exception:
            pass
        # 方法3：回退 — getTrackingMatrix（可能随摄像机方向变化）
        try:
            m = device.getTrackingMatrix()
            if not m:
                return None
            c0, c1, c2 = m.column(0), m.column(1), m.column(2)
            return [[c0.x(), c1.x(), c2.x()],
                    [c0.y(), c1.y(), c2.y()],
                    [c0.z(), c1.z(), c2.z()]]
        except Exception:
            return None

    def _mat3_to_euler(rs):
        """3x3 旋转矩阵 → Euler 角（度），R = Rz*Ry*Rx 顺序。"""
        sy = -rs[2][0]
        if sy > 1.0: sy = 1.0
        elif sy < -1.0: sy = -1.0
        if abs(sy) < 0.999999:
            rx = math.atan2(rs[2][1], rs[2][2])
            ry = math.asin(sy)
            rz = math.atan2(rs[1][0], rs[0][0])
        else:
            rx = math.atan2(-rs[1][2], rs[1][1])
            ry = math.asin(sy)
            rz = 0.0
        return math.degrees(rx), math.degrees(ry), math.degrees(rz)

    def _debug_rot_methods(tracker_name):
        """对比所有旋转数据来源，用于排查坐标空间问题（内部实现）。"""
        try:
            device = vrDeviceService.getVRDevice(tracker_name)
        except Exception as e:
            print("找不到设备: " + str(e))
            return
        print("=== rotation debug: " + tracker_name + " ===")
        # getTransformNodeRotation (local Euler)
        try:
            node = device.getNode()
            r = getTransformNodeRotation(node)
            print("  getTransformNodeRotation: %.2f %.2f %.2f" % (r.x(), r.y(), r.z()))
        except Exception as e:
            print("  getTransformNodeRotation: ERROR " + str(e))
        # node.getWorldRotation() v1 API
        try:
            wr = node.getWorldRotation()
            print("  node.getWorldRotation(): " + str(wr))
        except Exception as e:
            print("  node.getWorldRotation(): ERROR " + str(e))
        # node.getWorldTransform() v1 API → 16 floats
        try:
            wm = node.getWorldTransform()
            if wm and len(wm) == 16:
                r3 = [[wm[0], wm[4], wm[8]], [wm[1], wm[5], wm[9]], [wm[2], wm[6], wm[10]]]
                rx, ry, rz = _mat3_to_euler(r3)
                print("  node.getWorldTransform() euler: %.2f %.2f %.2f" % (rx, ry, rz))
            else:
                print("  node.getWorldTransform(): None or wrong length")
        except Exception as e:
            print("  node.getWorldTransform(): ERROR " + str(e))
        # device.getWorldMatrix() v1 API → 16 floats
        try:
            wm = device.getWorldMatrix()
            if wm and len(wm) == 16:
                r3 = [[wm[0], wm[4], wm[8]], [wm[1], wm[5], wm[9]], [wm[2], wm[6], wm[10]]]
                rx, ry, rz = _mat3_to_euler(r3)
                print("  device.getWorldMatrix() euler: %.2f %.2f %.2f" % (rx, ry, rz))
            else:
                print("  device.getWorldMatrix(): None or wrong length")
        except Exception as e:
            print("  device.getWorldMatrix(): ERROR " + str(e))
        # getTrackingMatrix (current fallback)
        try:
            m = device.getTrackingMatrix()
            if m:
                c0, c1, c2 = m.column(0), m.column(1), m.column(2)
                r3 = [[c0.x(), c1.x(), c2.x()], [c0.y(), c1.y(), c2.y()], [c0.z(), c1.z(), c2.z()]]
                rx, ry, rz = _mat3_to_euler(r3)
                print("  getTrackingMatrix() euler: %.2f %.2f %.2f" % (rx, ry, rz))
        except Exception as e:
            print("  getTrackingMatrix(): ERROR " + str(e))
        print("=== end debug ===")


    # TransformTracker — tracker-1 → Transform3D 节点（ParentConstraint）
    # ======================================================================
    class TransformTracker:
        """
        通过 vrTimer 将指定 tracker 设备的位姿（位置+旋转）同步到任意 Transform3D 场景节点。
        每帧同步并锁定目标节点 scale，防止 tracker scale 链条污染。
        与 ColaTracker 保持一致的 kinematic timer 驱动方式。
        """

        def __init__(self):
            self._tracker_name = None
            self._node_name = None
            self._active = False
            self._maintain_offset = False
            self._tracker = None
            self._node = None
            self._node_scale = None
            self._node_offset = None
            self._rot_offset = None  # 旋转偏移矩阵 R_node_init * inv(R_tracker_init)
            self._timer = vrTimer()
            self._timer_connected = False

        def setup(self, tracker_name, node_name, maintain_offset=False):
            """配置 tracker → 节点绑定。如已激活先停止再更新。"""
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._node_name = node_name
            self._maintain_offset = maintain_offset
            print("[TransformTracker] Configured: {} -> '{}' (maintain_offset={})".format(
                tracker_name, node_name, maintain_offset))

        def start(self):
            """激活 timer 追踪，开始位置/旋转同步。"""
            if self._active:
                print("[TransformTracker] Already active.")
                return
            if not self._tracker_name or not self._node_name:
                print("[TransformTracker] Not configured. Call setup(tracker_name, node_name) first.")
                return

            try:
                self._tracker = vrDeviceService.getVRDevice(self._tracker_name)
                if not self._tracker:
                    print("[TransformTracker] WARNING: tracker not found: " + self._tracker_name)
                    return
            except Exception as e:
                print("[TransformTracker] ERROR getting tracker: " + str(e))
                return

            try:
                self._node = findNode(self._node_name)
                if not self._node:
                    print("[TransformTracker] WARNING: node not found: " + self._node_name)
                    return
            except Exception as e:
                print("[TransformTracker] ERROR finding node: " + str(e))
                return

            # 记录节点原始 scale，每帧恢复
            try:
                self._node_scale = getTransformNodeScale(self._node)
            except Exception:
                self._node_scale = None

            # maintain_offset：记录 tracker→节点 的初始位置偏移
            self._node_offset = None
            if self._maintain_offset:
                try:
                    t_tracker = getTransformNodeTranslation(self._tracker.getNode(), True)
                    t_node = getTransformNodeTranslation(self._node, True)
                    self._node_offset = Vec3f(
                        t_node.x() - t_tracker.x(),
                        t_node.y() - t_tracker.y(),
                        t_node.z() - t_tracker.z())
                    print("[TransformTracker] maintain_offset enabled")
                except Exception as e:
                    print("[TransformTracker] WARNING: failed to compute offset: " + str(e))

            # 旋转 maintain_offset：记录 R_node_init * inv(R_tracker_init)
            # 确保节点始终从其初始场景旋转出发跟随 tracker 旋转
            self._rot_offset = None
            try:
                node_euler = getTransformNodeRotation(self._node)
                R_node_init = _euler_to_mat3(node_euler.x(), node_euler.y(), node_euler.z())
                rt_init = _get_tracker_mat3(self._tracker)
                if rt_init is not None:
                    self._rot_offset = _mul3x3(R_node_init, _mat3_t(rt_init))
                    print("[TransformTracker] rotation offset computed")
            except Exception as e:
                print("[TransformTracker] WARNING rotation offset: " + str(e))

            if not self._timer_connected:
                self._timer.connect(self._update)
                self._timer_connected = True

            self._timer.setActive(1)
            self._active = True
            print("[TransformTracker] Started: {} -> '{}' (timer, scale locked)".format(
                self._tracker_name, self._node_name))

        def stop(self):
            """停止 timer，节点保持最后位置。"""
            if not self._active:
                return
            try:
                self._timer.setActive(0)
            except Exception:
                pass
            self._active = False
            self._tracker = None
            self._node = None
            self._node_scale = None
            self._node_offset = None
            self._rot_offset = None
            print("[TransformTracker] Stopped: {} -> '{}'".format(
                self._tracker_name, self._node_name))

        def toggle(self):
            if self._active:
                self.stop()
            else:
                self.start()

        def status(self):
            state = "ACTIVE" if self._active else "stopped"
            cfg = "{} -> '{}'".format(self._tracker_name, self._node_name) \
                if self._tracker_name else "(not configured)"
            print("[TransformTracker] {} [{}]".format(cfg, state))

        def _update(self):
            if not self._active:
                return
            if not self._tracker or not self._node:
                return
            try:
                t = _extract_device_translation(self._tracker)
                if t is None:
                    return

                tx = t.x()
                ty = t.y()
                tz = t.z()
                if self._node_offset is not None:
                    tx += self._node_offset.x()
                    ty += self._node_offset.y()
                    tz += self._node_offset.z()

                setTransformNodeTranslation(self._node, tx, ty, tz, True)

                # 应用旋转（带初始偏移，保持节点初始朝向作为基准）
                rt = _get_tracker_mat3(self._tracker)
                if rt is not None:
                    rs = _mul3x3(self._rot_offset, rt) if self._rot_offset is not None else rt
                    rx_d, ry_d, rz_d = _mat3_to_euler(rs)
                    setTransformNodeRotation(self._node, rx_d, ry_d, rz_d)

                # 每帧恢复原始 scale，防止 tracker scale 链条污染
                if self._node_scale is not None:
                    setTransformNodeScale(self._node,
                                         self._node_scale.x(),
                                         self._node_scale.y(),
                                         self._node_scale.z())
            except Exception as e:
                print("[TransformTracker] WARNING update failed: " + str(e))

    # ======================================================================
    # ColaTracker — tracker-2 → Cola 物理运动学对象 + 碰撞检测
    # ======================================================================
    class ColaTracker:
        """
        将 tracker-2 绑定到 Cola 节点（kinematic 模式）：
          1. 确保 Cola 在 vrPhysicsService 中注册为 kinematic 对象
          2. timer 同步位置+旋转并锁定 scale，避免瓶子变形
          3. 监听 collisionStarted / collisionStopped / collisionContinues 信号，
             打印碰撞事件及接触点坐标；通过 vrdPhysicsObjectNode.setHighlightEnabled() 启用 VRED 内置碰撞高亮
        """

        def __init__(self):
            self._tracker_name = None
            self._cola_node_name = None
            self._constraint = None
            self._active = False
            self._maintain_offset = False
            self._physics_registered = False
            self._tracker = None
            self._cola_node = None
            self._kinematic_timer = vrTimer()
            self._kinematic_timer_connected = False
            self._cola_scale = None
            self._kinematic_offset = None
            self._kinematic_rot_offset = None  # 旋转偏移矩阵
            # 碰撞信号连接句柄
            self._sig_start = None
            self._sig_stop = None
            self._sig_cont = None

        def setup(self, tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False):
            """配置 tracker → Cola kinematic 物理绑定。"""
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._cola_node_name = cola_node_name
            self._maintain_offset = maintain_offset
            print("[ColaTracker] Configured: {} -> '{}' (maintain_offset={})".format(
                tracker_name, cola_node_name, maintain_offset))

        def start(self):
            """
            激活物理追踪：
            1. 确保 Physics 服务激活
            2. 确保 Cola 注册为 kinematic
            3. 启动 timer pose-sync
            4. 连接碰撞信号
            """
            if self._active:
                print("[ColaTracker] Already active.")
                return
            if not self._tracker_name or not self._cola_node_name:
                print("[ColaTracker] Not configured. Call setup(tracker_name, cola_node_name) first.")
                return

            # 获取 tracker 设备
            tracker = None
            try:
                tracker = vrDeviceService.getVRDevice(self._tracker_name)
                if not tracker:
                    print("[ColaTracker] WARNING: tracker not found: " + self._tracker_name)
                    return
            except Exception as e:
                print("[ColaTracker] ERROR getting tracker: " + str(e))
                return

            # 获取 Cola 节点
            colaNode = None
            try:
                colaNode = findNode(self._cola_node_name)
                if not colaNode:
                    print("[ColaTracker] WARNING: Cola node not found: " + self._cola_node_name)
                    return
            except Exception as e:
                print("[ColaTracker] ERROR finding Cola node: " + str(e))
                return

            # 确保物理服务已激活
            try:
                if not vrPhysicsService.isActive():
                    vrPhysicsService.setActive(True)
                    print("[ColaTracker] Physics service activated")
            except Exception as e:
                print("[ColaTracker] WARNING: failed to activate physics service: " + str(e))

            # 确保 Cola 为 kinematic 物理对象
            self._ensure_physics_mode(colaNode)

            # 开启 VRED 原生碰撞高亮（vrdPhysicsObjectNode.setHighlightEnabled）
            try:
                cola_phys_node = vrPhysicsService.getPhysicsObject(colaNode, True)
                if cola_phys_node:
                    cola_phys_node.setHighlightEnabled(True)
                    print("[ColaTracker] Collision highlighting enabled on Cola physics object")
                else:
                    print("[ColaTracker] WARNING: could not get Cola physics object for highlight")
            except Exception as e:
                print("[ColaTracker] WARNING: setHighlightEnabled failed: " + str(e))

            self._tracker = tracker
            self._cola_node = colaNode

            if not self._start_kinematic_follow():
                return

            # 连接碰撞信号（先断开再连，防止重复注册）
            self._connect_collision_signals(colaNode)

            self._active = True
            print("[ColaTracker] Started. Cola kinematic follow by {}, collisions active.".format(
                self._tracker_name))

        def stop(self):
            """解除约束并断开碰撞信号，Cola 保持最后位置。"""
            if not self._active:
                return

            # 解除约束
            try:
                if self._constraint is not None:
                    vrConstraintService.deleteConstraint(self._constraint)
                    self._constraint = None
            except Exception as e:
                print("[ColaTracker] WARNING deleting constraint: " + str(e))

            self._stop_kinematic_follow()

            # 关闭高亮
            try:
                if self._cola_node:
                    cola_phys_node = vrPhysicsService.getPhysicsObject(self._cola_node, True)
                    if cola_phys_node:
                        cola_phys_node.setHighlightEnabled(False)
            except Exception:
                pass

            # 断开碰撞信号
            self._disconnect_collision_signals()

            self._active = False
            self._tracker = None
            self._cola_node = None
            self._cola_scale = None
            print("[ColaTracker] Stopped: {} -> '{}'".format(
                self._tracker_name, self._cola_node_name))

        def toggle(self):
            if self._active:
                self.stop()
            else:
                self.start()

        def status(self):
            state = "ACTIVE" if self._active else "stopped"
            cfg = "{} -> '{}'".format(self._tracker_name, self._cola_node_name) \
                if self._tracker_name else "(not configured)"
            phys = "kinematic registered" if self._physics_registered else "physics not registered"
            print("[ColaTracker] {} [{}] ({})".format(cfg, state, phys))

        # ------------------------------------------------------------------
        # 内部：物理注册
        # ------------------------------------------------------------------
        def _ensure_physics_mode(self, colaNode):
            try:
                if vrPhysicsService.hasPhysicsObject(colaNode):
                    kinematic_nodes = vrPhysicsService.getKinematicObjects()
                    is_kinematic = any(n.getName() == colaNode.getName() for n in kinematic_nodes)
                    if is_kinematic:
                        self._physics_registered = True
                        print("[ColaTracker] Cola already registered as kinematic (Physics Editor)")
                    else:
                        print("[ColaTracker] WARNING: Cola exists in physics but not as kinematic, re-registering...")
                        vrPhysicsService.removeObject(colaNode)
                        hullConf = vrdPhysicsHullConfig()
                        ok = vrPhysicsService.addKinematicObject(colaNode, hullConf)
                        self._physics_registered = ok
                        if ok:
                            print("[ColaTracker] Cola re-registered as kinematic")
                        else:
                            print("[ColaTracker] WARNING: failed to re-register Cola as kinematic")
                else:
                    hullConf = vrdPhysicsHullConfig()
                    ok = vrPhysicsService.addKinematicObject(colaNode, hullConf)
                    self._physics_registered = ok
                    if ok:
                        print("[ColaTracker] Cola registered as kinematic object")
                    else:
                        print("[ColaTracker] WARNING: failed to register Cola as kinematic")
            except Exception as e:
                print("[ColaTracker] WARNING during physics registration: " + str(e))

        # ------------------------------------------------------------------
        # 内部：kinematic 模式（无缩放传递）
        # ------------------------------------------------------------------
        def _start_kinematic_follow(self):
            try:
                self._cola_scale = getTransformNodeScale(self._cola_node)
            except Exception:
                self._cola_scale = None

            self._kinematic_offset = None
            if self._maintain_offset:
                try:
                    t_tracker = getTransformNodeTranslation(self._tracker.getNode(), True)
                    t_cola = getTransformNodeTranslation(self._cola_node, True)
                    self._kinematic_offset = Vec3f(
                        t_cola.x() - t_tracker.x(),
                        t_cola.y() - t_tracker.y(),
                        t_cola.z() - t_tracker.z())
                    print("[ColaTracker] Kinematic maintain_offset enabled (position offset)")
                except Exception as e:
                    print("[ColaTracker] WARNING: failed to compute maintain_offset: " + str(e))

            # 旋转 maintain_offset：记录 R_cola_init * inv(R_tracker_init)
            self._kinematic_rot_offset = None
            try:
                cola_euler = getTransformNodeRotation(self._cola_node)
                R_cola_init = _euler_to_mat3(cola_euler.x(), cola_euler.y(), cola_euler.z())
                rt_init = _get_tracker_mat3(self._tracker)
                if rt_init is not None:
                    self._kinematic_rot_offset = _mul3x3(R_cola_init, _mat3_t(rt_init))
                    print("[ColaTracker] rotation offset computed")
            except Exception as e:
                print("[ColaTracker] WARNING rotation offset: " + str(e))

            if not self._kinematic_timer_connected:
                self._kinematic_timer.connect(self._kinematic_update)
                self._kinematic_timer_connected = True

            self._kinematic_timer.setActive(1)
            print("[ColaTracker] Kinematic timer follow active (scale locked)")
            return True

        def _stop_kinematic_follow(self):
            try:
                self._kinematic_timer.setActive(0)
            except Exception:
                pass
            self._kinematic_offset = None
            self._kinematic_rot_offset = None

        def _kinematic_update(self):
            if not self._active:
                return
            if not self._tracker or not self._cola_node:
                return

            try:
                t = _extract_device_translation(self._tracker)
                if t is None:
                    return

                tx = t.x()
                ty = t.y()
                tz = t.z()
                if self._kinematic_offset is not None:
                    tx += self._kinematic_offset.x()
                    ty += self._kinematic_offset.y()
                    tz += self._kinematic_offset.z()

                setTransformNodeTranslation(self._cola_node, tx, ty, tz, True)

                # 应用旋转（带初始偏移）
                rt = _get_tracker_mat3(self._tracker)
                if rt is not None:
                    rs = _mul3x3(self._kinematic_rot_offset, rt) if self._kinematic_rot_offset is not None else rt
                    rx_d, ry_d, rz_d = _mat3_to_euler(rs)
                    setTransformNodeRotation(self._cola_node, rx_d, ry_d, rz_d)

                # 每帧恢复 Cola 原始缩放，防止 tracker 缩放链条污染
                if self._cola_scale is not None:
                    setTransformNodeScale(self._cola_node,
                                          self._cola_scale.x(),
                                          self._cola_scale.y(),
                                          self._cola_scale.z())
            except Exception as e:
                print("[ColaTracker] WARNING kinematic update failed: " + str(e))

        # ------------------------------------------------------------------
        # 内部：碰撞信号管理
        # ------------------------------------------------------------------
        def _connect_collision_signals(self, colaNode):
            cola_name = colaNode.getName()

            # 先断开旧连接
            self._disconnect_collision_signals()

            def on_collision_started(info):
                n1 = info.getCollidingRootNode1().getName()
                n2 = info.getCollidingRootNode2().getName()
                if cola_name not in (n1, n2):
                    return
                other = n2 if n1 == cola_name else n1
                pts = info.getContactPoints()
                pt_str = ""
                if pts:
                    p = pts[0]
                    pt_str = " | 接触点: ({:.2f}, {:.2f}, {:.2f})".format(p.x(), p.y(), p.z())
                print("[ColaTracker] 碰撞开始: Cola <-> '{}'{} ({} 接触点)".format(
                    other, pt_str, len(pts)))

            def on_collision_stopped(info):
                n1 = info.getCollidingRootNode1().getName()
                n2 = info.getCollidingRootNode2().getName()
                if cola_name not in (n1, n2):
                    return
                other = n2 if n1 == cola_name else n1
                print("[ColaTracker] 碰撞结束: Cola <-> '{}'".format(other))

            def on_collision_continues(info):
                n1 = info.getCollidingRootNode1().getName()
                n2 = info.getCollidingRootNode2().getName()
                if cola_name not in (n1, n2):
                    return
                other = n2 if n1 == cola_name else n1
                pts = info.getContactPoints()
                if pts:
                    p = pts[0]
                    print("[ColaTracker] 碰撞持续: Cola <-> '{}' | ({:.2f}, {:.2f}, {:.2f})".format(
                        other, p.x(), p.y(), p.z()))

            try:
                self._sig_start = vrPhysicsService.collisionStarted.connect(on_collision_started)
                self._sig_stop = vrPhysicsService.collisionStopped.connect(on_collision_stopped)
                self._sig_cont = vrPhysicsService.collisionContinues.connect(on_collision_continues)
                print("[ColaTracker] Collision callbacks connected")
            except Exception as e:
                print("[ColaTracker] WARNING connecting collision signals: " + str(e))

        def _disconnect_collision_signals(self):
            try:
                if self._sig_start is not None:
                    vrPhysicsService.collisionStarted.disconnect(self._sig_start)
                    self._sig_start = None
                if self._sig_stop is not None:
                    vrPhysicsService.collisionStopped.disconnect(self._sig_stop)
                    self._sig_stop = None
                if self._sig_cont is not None:
                    vrPhysicsService.collisionContinues.disconnect(self._sig_cont)
                    self._sig_cont = None
            except Exception:
                # 若未连接则忽略
                self._sig_start = None
                self._sig_stop = None
                self._sig_cont = None

    # ======================================================================
    # 实例化管理器
    # ======================================================================
    _transform_tracker = TransformTracker()
    _cola_tracker = ColaTracker()

    # ======================================================================
    # 控制器按键绑定（直连设备信号，不创建 Interaction，不影响内置 Teleport）
    # ======================================================================
    # 左手 Y 键 → toggle TransformTracker
    # 右手 B 键 → toggle ColaTracker
    try:
        # 先清除旧的残余 interaction（如果存在）
        try:
            _old_pt = vrDeviceService.getInteraction("PhysicsTrackerInteraction")
            if _old_pt and _old_pt.isValid():
                vrDeviceService.removeInteraction(_old_pt)
        except Exception:
            pass

        left_ctrl  = vrDeviceService.getDevice("LeftController")
        right_ctrl = vrDeviceService.getDevice("RightController")

        left_y  = left_ctrl.getButton("ButtonY")
        right_b = right_ctrl.getButton("ButtonB")

        left_y.signal().pressed.connect(lambda: _transform_tracker.toggle())
        right_b.signal().pressed.connect(lambda: _cola_tracker.toggle())

        print("[PhysicsTracker] Buttons bound: left-Y=TransformTracker, right-B=ColaTracker (direct signal)")
    except Exception as e:
        print("[PhysicsTracker] WARNING binding buttons: " + str(e))

    _physics_tracker_initialized = True
    print("[PhysicsTracker] Initialized.")
    print("[PhysicsTracker] Call setup_transform(tracker, node) and setup_cola(tracker, node) to configure.")

# ======================================================================
# 模块级公开 API
# ======================================================================

def setup_transform(tracker_name, node_name, maintain_offset=True):
    """
    配置 tracker-1 → Transform3D 节点绑定。

    Args:
        tracker_name (str): tracker 设备名，如 "tracker-1"
        node_name (str): VRED 场景节点名，如 "Seat"
        maintain_offset (bool): True=保留初始相对偏移（默认，节点在 tracker 上方时保持相交关系），
                                False=直接吸附到 tracker 位置
    """
    global _transform_tracker
    _transform_tracker.setup(tracker_name, node_name, maintain_offset)

def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False):
    """
    配置 tracker-2 → Cola kinematic 物理绑定。

    Args:
        tracker_name (str): tracker 设备名，默认 "tracker-2"
        cola_node_name (str): Cola 节点名，默认 "Cola"
        maintain_offset (bool): True=保留初始偏移，False=直接吸附
    """
    global _cola_tracker
    _cola_tracker.setup(tracker_name, cola_node_name, maintain_offset)

def start_transform():
    """激活 tracker-1 → Transform3D 追踪。"""
    global _transform_tracker
    _transform_tracker.start()

def stop_transform():
    """停止 tracker-1 追踪，节点保持最后位置。"""
    global _transform_tracker
    _transform_tracker.stop()

def toggle_transform():
    """切换 tracker-1 追踪开/关（同左手 Y 键）。"""
    global _transform_tracker
    _transform_tracker.toggle()

def start_cola():
    """激活 tracker-2 → Cola 物理追踪及碰撞检测。"""
    global _cola_tracker
    _cola_tracker.start()

def stop_cola():
    """停止 Cola 追踪，解除约束与碰撞回调。"""
    global _cola_tracker
    _cola_tracker.stop()

def toggle_cola():
    """切换 Cola 追踪开/关（同右手 B 键）。"""
    global _cola_tracker
    _cola_tracker.toggle()

def physics_status():
    """打印两个 tracker 的当前状态。"""
    global _transform_tracker, _cola_tracker
    _transform_tracker.status()
    _cola_tracker.status()

def debug_tracker_rotation(tracker_name="tracker-1"):
    """对比所有旋转数据来源，排查坐标空间问题。
    用法：debug_tracker_rotation("tracker-2")
    """
    _debug_rot_methods(tracker_name)
