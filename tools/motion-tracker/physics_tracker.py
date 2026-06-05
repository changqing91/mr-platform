# ======================================================================
# VRED Physics Tracker
#
# tracker-1 → TransformTracker: vrConstraintService.createParentConstraint 驱动
# tracker-2 → ColaTracker: ParentConstraint + kinematic physics + 碰撞检测
#
# 用法（VRED Python 控制台）：
#   # ── 椅子（tracker 固定在椅子某处）──
#   setup_transform("tracker-1", "SeatNode")   # maintain_offset=True（默认，保持初始相对位置）
#   start_transform()
#   recalibrate_transform()                    # 如需重置基准（重建约束）
#
#   # ── 瓶子（tracker 固定在瓶子顶部）──
#   setup_cola("tracker-2", "Cola")
#   start_cola()
#   recalibrate_cola(dz=-15)                   # 将 Cola 定位到 tracker 本地 Z 轴下方 15 单位
#                                              # dz 为负 = Cola 在 tracker 下方（Z 朝上时）
#                                              # 调整 dz 数值直到 VR 中视觉位置正确
#   stop_cola()                                # 停止，删除约束
#   physics_status()                           # 打印状态
#   debug_tracker_rotation("tracker-2")        # 旋转数据调试
#
# 左手 Y 键：切换 tracker-1 追踪开/关
# 右手 B 键：切换 tracker-2 Cola 追踪开/关
# ======================================================================

import math

global _transform_tracker, _cola_tracker

# 每次重载先停止旧实例，确保代码更新生效
for _n in ('_cola_tracker', '_transform_tracker'):
    if _n in globals() and globals()[_n] is not None:
        try:
            globals()[_n].stop()
        except Exception:
            pass

global _physics_tracker_initialized
_physics_tracker_initialized = False

if not _physics_tracker_initialized:

    # ------------------------------------------------------------------
    # 工具函数（仅供 recalibrate 定位使用）
    # ------------------------------------------------------------------
    def _get_tracker_mat3(device):
        """获取 tracker 节点世界旋转矩阵（3x3），不随摄像机方向变化。"""
        try:
            m = device.getNode().getWorldTransform()
            if m:
                c0, c1, c2 = m.column(0), m.column(1), m.column(2)
                return [[c0.x(), c1.x(), c2.x()],
                        [c0.y(), c1.y(), c2.y()],
                        [c0.z(), c1.z(), c2.z()]]
        except Exception:
            pass
        return None

    def _debug_rot_methods(tracker_name):
        """对比所有旋转数据来源，用于排查坐标空间问题。"""
        try:
            device = vrDeviceService.getVRDevice(tracker_name)
        except Exception as e:
            print("找不到设备: " + str(e))
            return
        print("=== rotation debug: " + tracker_name + " ===")
        try:
            node = device.getNode()
            r = getTransformNodeRotation(node)
            print("  getTransformNodeRotation: %.2f %.2f %.2f" % (r.x(), r.y(), r.z()))
        except Exception as e:
            print("  getTransformNodeRotation: ERROR " + str(e))
        try:
            m = node.getWorldTransform()
            if m:
                c0, c1, c2 = m.column(0), m.column(1), m.column(2)
                r3 = [[c0.x(), c1.x(), c2.x()],
                      [c0.y(), c1.y(), c2.y()],
                      [c0.z(), c1.z(), c2.z()]]
                sy = max(-1.0, min(1.0, -r3[2][0]))
                ry = math.degrees(math.asin(sy))
                if abs(sy) < 0.999999:
                    rx = math.degrees(math.atan2(r3[2][1], r3[2][2]))
                    rz = math.degrees(math.atan2(r3[1][0], r3[0][0]))
                else:
                    rx = math.degrees(math.atan2(-r3[1][2], r3[1][1]))
                    rz = 0.0
                print("  node.getWorldTransform() euler: %.2f %.2f %.2f" % (rx, ry, rz))
        except Exception as e:
            print("  node.getWorldTransform(): ERROR " + str(e))
        print("=== end debug ===")

    # ======================================================================
    # TransformTracker
    # ======================================================================
    class TransformTracker:
        def __init__(self):
            self._tracker_name = None
            self._node_name = None
            self._active = False
            self._maintain_offset = True
            self._constraint = None
            self._tracker = None
            self._node = None

        def setup(self, tracker_name, node_name, maintain_offset=True):
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._node_name = node_name
            self._maintain_offset = maintain_offset
            print("[TransformTracker] Configured: {} -> '{}' (maintain_offset={})".format(
                tracker_name, node_name, maintain_offset))

        def start(self):
            if self._active:
                print("[TransformTracker] Already active.")
                return
            if not self._tracker_name or not self._node_name:
                print("[TransformTracker] Not configured. Call setup() first.")
                return
            try:
                self._tracker = vrDeviceService.getVRDevice(self._tracker_name)
                if not self._tracker:
                    print("[TransformTracker] Tracker not found: " + self._tracker_name)
                    return
            except Exception as e:
                print("[TransformTracker] ERROR getting tracker: " + str(e))
                return
            try:
                self._node = findNode(self._node_name)
                if not self._node:
                    print("[TransformTracker] Node not found: " + self._node_name)
                    return
            except Exception as e:
                print("[TransformTracker] ERROR finding node: " + str(e))
                return
            try:
                self._constraint = vrConstraintService.createParentConstraint(
                    [self._tracker.getNode()], self._node, self._maintain_offset)
                self._active = True
                print("[TransformTracker] Started: {} -> '{}' (ParentConstraint, maintainOffset={})".format(
                    self._tracker_name, self._node_name, self._maintain_offset))
            except Exception as e:
                print("[TransformTracker] ERROR creating constraint: " + str(e))

        def stop(self):
            if not self._active:
                return
            try:
                if self._constraint:
                    vrConstraintService.deleteConstraint(self._constraint)
                    self._constraint = None
            except Exception as e:
                print("[TransformTracker] WARNING deleting constraint: " + str(e))
            self._active = False
            self._tracker = None
            self._node = None
            print("[TransformTracker] Stopped: {} -> '{}'".format(
                self._tracker_name, self._node_name))

        def toggle(self):
            if self._active:
                self.stop()
            else:
                self.start()

        def recalibrate(self, dz=0.0):
            """重建约束，重置节点与 tracker 的相对位置/旋转基准。
            dz：沿 tracker 本地 Z 轴的位置偏移（场景单位，负值=节点在tracker下方）。
            """
            if not self._active or not self._tracker or not self._node:
                print("[TransformTracker] Not active, cannot recalibrate.")
                return
            try:
                if self._constraint:
                    vrConstraintService.deleteConstraint(self._constraint)
                    self._constraint = None
            except Exception:
                pass
            if dz != 0.0:
                try:
                    rt = _get_tracker_mat3(self._tracker)
                    tp = getTransformNodeTranslation(self._tracker.getNode(), True)
                    if rt:
                        nx = tp.x() + rt[0][2] * dz
                        ny = tp.y() + rt[1][2] * dz
                        nz = tp.z() + rt[2][2] * dz
                    else:
                        nx, ny, nz = tp.x(), tp.y(), tp.z() + dz
                    setTransformNodeTranslation(self._node, nx, ny, nz, True)
                    setTransformNodeRotation(self._node, 0, 0, 0)
                except Exception as e:
                    print("[TransformTracker] WARNING positioning: " + str(e))
            try:
                self._constraint = vrConstraintService.createParentConstraint(
                    [self._tracker.getNode()], self._node, True)
                print("[TransformTracker] Recalibrated. dz={:.2f}".format(dz))
            except Exception as e:
                print("[TransformTracker] ERROR recreating constraint: " + str(e))

        def status(self):
            state = "ACTIVE" if self._active else "stopped"
            cfg = "{} -> '{}'".format(self._tracker_name, self._node_name) \
                if self._tracker_name else "(not configured)"
            print("[TransformTracker] {} [{}]".format(cfg, state))

    # ======================================================================
    # ColaTracker
    # ======================================================================
    class ColaTracker:
        def __init__(self):
            self._tracker_name = None
            self._cola_node_name = None
            self._active = False
            self._maintain_offset = True
            self._constraint = None
            self._physics_registered = False
            self._tracker = None
            self._cola_node = None
            self._cola_scale = None
            self._scale_timer = vrTimer()
            self._scale_timer_connected = False
            self._sig_start = None
            self._sig_stop = None
            self._sig_cont = None

        def setup(self, tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=True):
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._cola_node_name = cola_node_name
            self._maintain_offset = maintain_offset
            print("[ColaTracker] Configured: {} -> '{}' (maintain_offset={})".format(
                tracker_name, cola_node_name, maintain_offset))

        def start(self):
            if self._active:
                print("[ColaTracker] Already active.")
                return
            if not self._tracker_name or not self._cola_node_name:
                print("[ColaTracker] Not configured. Call setup() first.")
                return
            try:
                self._tracker = vrDeviceService.getVRDevice(self._tracker_name)
                if not self._tracker:
                    print("[ColaTracker] Tracker not found: " + self._tracker_name)
                    return
            except Exception as e:
                print("[ColaTracker] ERROR getting tracker: " + str(e))
                return
            try:
                self._cola_node = findNode(self._cola_node_name)
                if not self._cola_node:
                    print("[ColaTracker] Cola node not found: " + self._cola_node_name)
                    return
            except Exception as e:
                print("[ColaTracker] ERROR finding Cola node: " + str(e))
                return

            try:
                if not vrPhysicsService.isActive():
                    vrPhysicsService.setActive(True)
                    print("[ColaTracker] Physics service activated")
            except Exception as e:
                print("[ColaTracker] WARNING activating physics: " + str(e))

            self._ensure_physics_mode(self._cola_node)

            try:
                phys_node = vrPhysicsService.getPhysicsObject(self._cola_node, True)
                if phys_node:
                    phys_node.setHighlightEnabled(True)
            except Exception as e:
                print("[ColaTracker] WARNING setHighlightEnabled: " + str(e))

            try:
                self._cola_scale = getTransformNodeScale(self._cola_node)
            except Exception:
                self._cola_scale = None

            # 核心：一行 ParentConstraint 替代所有 timer + 矩阵运算
            try:
                self._constraint = vrConstraintService.createParentConstraint(
                    [self._tracker.getNode()], self._cola_node, self._maintain_offset)
            except Exception as e:
                print("[ColaTracker] ERROR creating constraint: " + str(e))
                return

            if self._cola_scale is not None:
                if not self._scale_timer_connected:
                    self._scale_timer.connect(self._restore_scale)
                    self._scale_timer_connected = True
                self._scale_timer.setActive(1)

            self._connect_collision_signals(self._cola_node)
            self._active = True
            print("[ColaTracker] Started: {} -> '{}' (ParentConstraint + kinematic physics)".format(
                self._tracker_name, self._cola_node_name))

        def stop(self):
            if not self._active:
                return
            try:
                if self._constraint:
                    vrConstraintService.deleteConstraint(self._constraint)
                    self._constraint = None
            except Exception as e:
                print("[ColaTracker] WARNING deleting constraint: " + str(e))
            try:
                self._scale_timer.setActive(0)
            except Exception:
                pass
            try:
                if self._cola_node:
                    phys_node = vrPhysicsService.getPhysicsObject(self._cola_node, True)
                    if phys_node:
                        phys_node.setHighlightEnabled(False)
            except Exception:
                pass
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

        def recalibrate(self, dz=0.0):
            """重建约束，重置 Cola 与 tracker 的相对位置/旋转基准。
            dz：沿 tracker 本地 Z 轴的位置偏移（负值=Cola在tracker下方）。
            示例：recalibrate_cola(dz=-15)  # Cola 在 tracker 下方 15 单位
            """
            if not self._active or not self._tracker or not self._cola_node:
                print("[ColaTracker] Not active, cannot recalibrate.")
                return
            try:
                if self._constraint:
                    vrConstraintService.deleteConstraint(self._constraint)
                    self._constraint = None
            except Exception:
                pass
            if dz != 0.0:
                try:
                    rt = _get_tracker_mat3(self._tracker)
                    tp = getTransformNodeTranslation(self._tracker.getNode(), True)
                    if rt:
                        nx = tp.x() + rt[0][2] * dz
                        ny = tp.y() + rt[1][2] * dz
                        nz = tp.z() + rt[2][2] * dz
                    else:
                        nx, ny, nz = tp.x(), tp.y(), tp.z() + dz
                    setTransformNodeTranslation(self._cola_node, nx, ny, nz, True)
                    setTransformNodeRotation(self._cola_node, 0, 0, 0)
                except Exception as e:
                    print("[ColaTracker] WARNING positioning: " + str(e))
            try:
                self._constraint = vrConstraintService.createParentConstraint(
                    [self._tracker.getNode()], self._cola_node, True)
                print("[ColaTracker] Recalibrated. dz={:.2f}".format(dz))
            except Exception as e:
                print("[ColaTracker] ERROR recreating constraint: " + str(e))

        def status(self):
            state = "ACTIVE" if self._active else "stopped"
            cfg = "{} -> '{}'".format(self._tracker_name, self._cola_node_name) \
                if self._tracker_name else "(not configured)"
            phys = "kinematic" if self._physics_registered else "no physics"
            print("[ColaTracker] {} [{}] ({})".format(cfg, state, phys))

        def _restore_scale(self):
            if not self._active or not self._cola_node or not self._cola_scale:
                return
            try:
                setTransformNodeScale(self._cola_node,
                    self._cola_scale.x(), self._cola_scale.y(), self._cola_scale.z())
            except Exception:
                pass

        def _ensure_physics_mode(self, colaNode):
            try:
                if vrPhysicsService.hasPhysicsObject(colaNode):
                    kinematic_nodes = vrPhysicsService.getKinematicObjects()
                    is_kinematic = any(n.getName() == colaNode.getName() for n in kinematic_nodes)
                    if is_kinematic:
                        self._physics_registered = True
                        print("[ColaTracker] Cola already registered as kinematic")
                    else:
                        print("[ColaTracker] Re-registering Cola as kinematic...")
                        vrPhysicsService.removeObject(colaNode)
                        ok = vrPhysicsService.addKinematicObject(colaNode, vrdPhysicsHullConfig())
                        self._physics_registered = ok
                        print("[ColaTracker] Cola re-registered: " + str(ok))
                else:
                    ok = vrPhysicsService.addKinematicObject(colaNode, vrdPhysicsHullConfig())
                    self._physics_registered = ok
                    print("[ColaTracker] Cola registered as kinematic: " + str(ok))
            except Exception as e:
                print("[ColaTracker] WARNING physics registration: " + str(e))

        def _connect_collision_signals(self, colaNode):
            cola_name = colaNode.getName()
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
                self._sig_start = self._sig_stop = self._sig_cont = None

    # ======================================================================
    # 实例化
    # ======================================================================
    _transform_tracker = TransformTracker()
    _cola_tracker = ColaTracker()

    # ======================================================================
    # 控制器按键绑定（直连设备信号，不影响内置 Teleport）
    # ======================================================================
    try:
        try:
            _old_pt = vrDeviceService.getInteraction("PhysicsTrackerInteraction")
            if _old_pt and _old_pt.isValid():
                vrDeviceService.removeInteraction(_old_pt)
        except Exception:
            pass
        left_ctrl  = vrDeviceService.getDevice("LeftController")
        right_ctrl = vrDeviceService.getDevice("RightController")
        left_ctrl.getButton("ButtonY").signal().pressed.connect(lambda: _transform_tracker.toggle())
        right_ctrl.getButton("ButtonB").signal().pressed.connect(lambda: _cola_tracker.toggle())
        print("[PhysicsTracker] Buttons bound: left-Y=TransformTracker, right-B=ColaTracker")
    except Exception as e:
        print("[PhysicsTracker] WARNING binding buttons: " + str(e))

    _physics_tracker_initialized = True
    print("[PhysicsTracker] Initialized (ParentConstraint-based).")

# ======================================================================
# 模块级公开 API
# ======================================================================

def setup_transform(tracker_name, node_name, maintain_offset=True):
    """配置 tracker-1 → Transform3D 节点绑定。maintain_offset=True 保持初始相对位置。"""
    global _transform_tracker
    _transform_tracker.setup(tracker_name, node_name, maintain_offset)

def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=True):
    """配置 tracker-2 → Cola kinematic 物理绑定。maintain_offset=True 保持初始相对位置。"""
    global _cola_tracker
    _cola_tracker.setup(tracker_name, cola_node_name, maintain_offset)

def start_transform():
    """启动 tracker-1 追踪（创建 ParentConstraint）。"""
    global _transform_tracker
    _transform_tracker.start()

def stop_transform():
    """停止 tracker-1 追踪（删除约束）。"""
    global _transform_tracker
    _transform_tracker.stop()

def toggle_transform():
    """切换 tracker-1 追踪开/关（同左手 Y 键）。"""
    global _transform_tracker
    _transform_tracker.toggle()

def start_cola():
    """启动 tracker-2 → Cola 物理追踪（创建 ParentConstraint + kinematic 物理）。"""
    global _cola_tracker
    _cola_tracker.start()

def stop_cola():
    """停止 Cola 追踪（删除约束，断开碰撞信号）。"""
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
    """对比旋转数据来源，排查坐标空间问题。"""
    _debug_rot_methods(tracker_name)

def recalibrate_transform(dz=0.0):
    """重建 TransformTracker 约束，重置相对位置/旋转基准。
    dz：沿 tracker 本地 Z 轴的位置偏移（场景单位，负值=节点在tracker下方）。
    """
    global _transform_tracker
    _transform_tracker.recalibrate(dz)

def recalibrate_cola(dz=0.0):
    """重建 ColaTracker 约束，重置 Cola 与 tracker 的相对位置/旋转基准。
    dz：tracker 在瓶顶时，dz=-瓶高 将 Cola 定位到 tracker 正下方。
    翻转 tracker 后 Cola 跟着翻转，始终保持本地坐标系相对位置不变。

    示例：recalibrate_cola(dz=-15)   # Cola 在 tracker 下方 15 单位
    """
    global _cola_tracker
    _cola_tracker.recalibrate(dz)

# 向后兼容别名
def recalibrate_cola_rotation(target_rx=0.0, target_ry=0.0, target_rz=0.0):
    recalibrate_cola()

def recalibrate_transform_rotation(target_rx=0.0, target_ry=0.0, target_rz=0.0):
    recalibrate_transform()

def recalibrate_cola_position(world_dx=None, world_dy=None, world_dz=None):
    recalibrate_cola(dz=world_dz or 0.0)

def recalibrate_transform_position(world_dx=None, world_dy=None, world_dz=None):
    recalibrate_transform(dz=world_dz or 0.0)
