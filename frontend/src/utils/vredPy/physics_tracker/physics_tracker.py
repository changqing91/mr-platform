# ======================================================================
# VRED Physics Tracker (带旋转补偿，解决倒置)
#
# tracker-1 → TransformTracker: 位置+方向约束，物体完全跟随 tracker
# tracker-2 → ColaTracker: 位置+方向约束 + kinematic physics + 碰撞检测
#
# 新增 rotation_offset 参数，可纠正物体朝向（默认 [180,0,0] 可解决常见倒置）
# ======================================================================

import math

global _transform_tracker, _cola_tracker

# 停止可能存在的旧实例
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
    # 辅助函数：将欧拉角（度）转换为四元数
    # ------------------------------------------------------------------
    def _euler_to_quat(euler_deg):
        rx = math.radians(euler_deg[0])
        ry = math.radians(euler_deg[1])
        rz = math.radians(euler_deg[2])
        cx, cy, cz = math.cos(rx/2), math.cos(ry/2), math.cos(rz/2)
        sx, sy, sz = math.sin(rx/2), math.sin(ry/2), math.sin(rz/2)
        qx = sx*cy*cz + cx*sy*sz
        qy = cx*sy*cz - sx*cy*sz
        qz = cx*cy*sz + sx*sy*cz
        qw = cx*cy*cz - sx*sy*sz
        return (qx, qy, qz, qw)

    # ======================================================================
    # TransformTracker (位置约束 + 方向约束 + 旋转补偿)
    # ======================================================================
    class TransformTracker:
        def __init__(self):
            self._tracker_name = None
            self._node_name = None
            self._active = False
            self._parent_constraint = None
            self._tracker = None
            self._node = None
            self._maintain_offset = False
            self._rotation_offset = [0.0, 0.0, 0.0]

        def setup(self, tracker_name, node_name, maintain_offset=True, rotation_offset=None):
            """配置 tracker → 节点绑定。
            maintain_offset: 保持初始相对变换（推荐True）
            rotation_offset: 额外的旋转补偿 [rx, ry, rz] 度，用于修正物体朝向。
            """
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._node_name = node_name
            self._maintain_offset = maintain_offset
            if rotation_offset is None:
                # 默认补偿：绕 X 轴旋转 180 度（解决常见倒置）
                self._rotation_offset = [180.0, 0.0, 0.0]
            else:
                self._rotation_offset = rotation_offset
            print("[TransformTracker] Configured: {} -> '{}' (maintain_offset={}, rot_offset={})".format(
                tracker_name, node_name, maintain_offset, self._rotation_offset))

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

            # 校准：将物体放置到 tracker 位置，并施加旋转补偿
            try:
                tracker_node = self._tracker.getNode()
                # 获取 tracker 的世界位置和旋转
                tracker_pos = getTransformNodeTranslation(tracker_node, 1)
                tracker_rot = getTransformNodeRotation(tracker_node)  # 欧拉角
                # 目标旋转 = tracker 旋转 + 补偿偏移（欧拉角直接相加，简化处理）
                target_rot = [tracker_rot.x() + self._rotation_offset[0],
                              tracker_rot.y() + self._rotation_offset[1],
                              tracker_rot.z() + self._rotation_offset[2]]
                # 设置物体位置和旋转
                setTransformNodeTranslation(self._node, tracker_pos.x(), tracker_pos.y(), tracker_pos.z(), 1)
                setTransformNodeRotation(self._node, target_rot[0], target_rot[1], target_rot[2])
                print("[TransformTracker] Calibrated: {} -> {} with offset {}".format(
                    self._node_name, self._tracker_name, self._rotation_offset))
            except Exception as e:
                print("[TransformTracker] Calibration error: " + str(e))
                return

            # 创建父约束（同时约束位置和旋转，保持校准后的相对关系）
            try:
                self._parent_constraint = vrConstraintService.createParentConstraint(
                    [self._tracker.getNode()], self._node, self._maintain_offset)
                if self._parent_constraint is None:
                    print("[TransformTracker] ERROR: parent constraint is None")
                    return
                self._active = True
                print("[TransformTracker] Started: {} -> '{}' (parent_constraint)".format(
                    self._tracker_name, self._node_name))
            except Exception as e:
                print("[TransformTracker] ERROR creating constraint: " + str(e))

        def stop(self):
            if not self._active:
                return
            try:
                if self._parent_constraint:
                    vrConstraintService.deleteConstraint(self._parent_constraint)
                    self._parent_constraint = None
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

        def status(self):
            state = "ACTIVE" if self._active else "stopped"
            cfg = "{} -> '{}'".format(self._tracker_name, self._node_name) \
                if self._tracker_name else "(not configured)"
            print("[TransformTracker] {} [{}]".format(cfg, state))

    # ======================================================================
    # ColaTracker (位置+方向约束 + 旋转补偿 + kinematic physics)
    # ======================================================================
    class ColaTracker:
        def __init__(self):
            self._tracker_name = None
            self._cola_node_name = None
            self._active = False
            self._parent_constraint = None
            self._physics_registered = False
            self._tracker = None
            self._cola_node = None
            self._cola_scale = None
            self._sig_start = None
            self._sig_stop = None
            self._sig_cont = None
            self._maintain_offset = False
            self._rotation_offset = [0.0, 0.0, 0.0]

        def setup(self, tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=True, rotation_offset=None):
            """配置 tracker → Cola 绑定。
            maintain_offset: 保持初始相对变换（推荐True）
            rotation_offset: 额外的旋转补偿 [rx, ry, rz] 度，用于修正物体朝向。
            """
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._cola_node_name = cola_node_name
            self._maintain_offset = maintain_offset
            if rotation_offset is None:
                self._rotation_offset = [180.0, 0.0, 0.0]  # 默认补偿
            else:
                self._rotation_offset = rotation_offset
            print("[ColaTracker] Configured: {} -> '{}' (maintain_offset={}, rot_offset={})".format(
                tracker_name, cola_node_name, maintain_offset, self._rotation_offset))

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

            # 记录原始缩放
            try:
                self._cola_scale = getTransformNodeScale(self._cola_node)
            except Exception:
                self._cola_scale = None

            # 激活物理服务
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

            # 校准：将物体放置到 tracker 位置，并施加旋转补偿
            try:
                tracker_node = self._tracker.getNode()
                tracker_pos = getTransformNodeTranslation(tracker_node, 1)
                tracker_rot = getTransformNodeRotation(tracker_node)
                target_rot = [tracker_rot.x() + self._rotation_offset[0],
                              tracker_rot.y() + self._rotation_offset[1],
                              tracker_rot.z() + self._rotation_offset[2]]
                setTransformNodeTranslation(self._cola_node, tracker_pos.x(), tracker_pos.y(), tracker_pos.z(), 1)
                setTransformNodeRotation(self._cola_node, target_rot[0], target_rot[1], target_rot[2])
                print("[ColaTracker] Calibrated: {} -> {} with offset {}".format(
                    self._cola_node_name, self._tracker_name, self._rotation_offset))
            except Exception as e:
                print("[ColaTracker] Calibration error: " + str(e))
                return

            # 创建父约束（同时约束位置和旋转）
            try:
                self._parent_constraint = vrConstraintService.createParentConstraint(
                    [self._tracker.getNode()], self._cola_node, self._maintain_offset)
                if self._parent_constraint is None:
                    print("[ColaTracker] ERROR: parent constraint is None")
                    return
            except Exception as e:
                print("[ColaTracker] ERROR creating constraint: " + str(e))
                return

            # 恢复原始缩放
            if self._cola_scale is not None:
                try:
                    setTransformNodeScale(self._cola_node,
                        self._cola_scale.x(), self._cola_scale.y(), self._cola_scale.z())
                    print("[ColaTracker] Scale restored to original")
                except Exception as e:
                    print("[ColaTracker] WARNING restoring scale: " + str(e))

            self._connect_collision_signals(self._cola_node)
            self._active = True
            print("[ColaTracker] Started: {} -> '{}' (parent_constraint + kinematic physics)".format(
                self._tracker_name, self._cola_node_name))

        def stop(self):
            if not self._active:
                return
            try:
                if self._parent_constraint:
                    vrConstraintService.deleteConstraint(self._parent_constraint)
                    self._parent_constraint = None
            except Exception as e:
                print("[ColaTracker] WARNING deleting constraint: " + str(e))
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

        def status(self):
            state = "ACTIVE" if self._active else "stopped"
            cfg = "{} -> '{}'".format(self._tracker_name, self._cola_node_name) \
                if self._tracker_name else "(not configured)"
            phys = "kinematic" if self._physics_registered else "no physics"
            print("[ColaTracker] {} [{}] ({})".format(cfg, state, phys))

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

    # 实例化
    _transform_tracker = TransformTracker()
    _cola_tracker = ColaTracker()

    _physics_tracker_initialized = True
    print("[PhysicsTracker] Initialized (with rotation offset compensation).")

# ======================================================================
# 公开 API
# ======================================================================
def setup_transform(tracker_name, node_name, maintain_offset=True, rotation_offset=None):
    global _transform_tracker
    _transform_tracker.setup(tracker_name, node_name, maintain_offset, rotation_offset)

def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=True, rotation_offset=None):
    global _cola_tracker
    _cola_tracker.setup(tracker_name, cola_node_name, maintain_offset, rotation_offset)

def start_transform():
    global _transform_tracker
    _transform_tracker.start()

def stop_transform():
    global _transform_tracker
    _transform_tracker.stop()

def toggle_transform():
    global _transform_tracker
    _transform_tracker.toggle()

def start_cola():
    global _cola_tracker
    _cola_tracker.start()

def stop_cola():
    global _cola_tracker
    _cola_tracker.stop()

def toggle_cola():
    global _cola_tracker
    _cola_tracker.toggle()

def physics_status():
    global _transform_tracker, _cola_tracker
    _transform_tracker.status()
    _cola_tracker.status()

# ======================================================================
# 自动启动（使用默认旋转补偿 [180,0,0] 修正倒置）
# ======================================================================
setup_transform("tracker-1", "SeatNode", maintain_offset=True, rotation_offset=[180,0,0])
start_transform()

setup_cola("tracker-2", "Cola", maintain_offset=True, rotation_offset=[180,0,0])
start_cola()

print("[PhysicsTracker] Auto-started with rotation offset [180,0,0]. If still inverted, adjust rotation_offset.")