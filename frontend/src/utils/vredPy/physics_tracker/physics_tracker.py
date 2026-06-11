# ======================================================================
# VRED Physics Tracker
#
# tracker-1 → TransformTracker: vrConstraintService.createPositionConstraint 仅跟随位置
# tracker-2 → ColaTracker: PositionConstraint + kinematic physics + 碰撞检测
#
# 自动校准：约束使用 maintain_offset=False（默认），启动时节点位置立即对齐 tracker
# 物体的自身旋转保持不变（正放），只跟随 tracker 移动。
#
# 用法（VRED Python 控制台）：
#   setup_transform("tracker-1", "SeatNode")   # 座椅跟随手柄位置，保持正放
#   start_transform()
#
#   setup_cola("tracker-2", "Cola")            # 瓶子跟随手柄位置，保持正放
#   start_cola()
#
# 左手 Y 键：切换座椅追踪开/关
# 右手 B 键：切换瓶子追踪开/关
# ======================================================================

import math

global _transform_tracker, _cola_tracker

# 每次重载先停止旧实例
for _n in ('_cola_tracker', '_transform_tracker'):
    if _n in globals() and globals()[_n] is not None:
        try:
            globals()[_n].stop()
        except Exception:
            pass

global _physics_tracker_initialized
_physics_tracker_initialized = False

if not _physics_tracker_initialized:

    # ======================================================================
    # TransformTracker (仅位置约束，保持物体自身旋转)
    # ======================================================================
    class TransformTracker:
        def __init__(self):
            self._tracker_name = None
            self._node_name = None
            self._active = False
            self._constraint = None
            self._tracker = None
            self._node = None
            self._maintain_offset = False

        def setup(self, tracker_name, node_name, maintain_offset=False):
            """配置 tracker → 节点绑定。maintain_offset=False：节点位置直接对齐 tracker。"""
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._node_name = node_name
            self._maintain_offset = maintain_offset
            print("[TransformTracker] Configured: {} -> '{}' (position only, maintain_offset={})".format(
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
                # 使用位置约束，不跟随旋转
                self._constraint = vrConstraintService.createPositionConstraint(
                    [self._tracker.getNode()], self._node, self._maintain_offset)
                self._active = True
                print("[TransformTracker] Started: {} -> '{}' (PositionConstraint, maintainOffset={})".format(
                    self._tracker_name, self._node_name, self._maintain_offset))
            except Exception as e:
                print("[TransformTracker] ERROR creating position constraint: " + str(e))

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

        def status(self):
            state = "ACTIVE" if self._active else "stopped"
            cfg = "{} -> '{}'".format(self._tracker_name, self._node_name) \
                if self._tracker_name else "(not configured)"
            print("[TransformTracker] {} [{}]".format(cfg, state))

    # ======================================================================
    # ColaTracker (仅位置约束 + kinematic physics + 碰撞检测)
    # ======================================================================
    class ColaTracker:
        def __init__(self):
            self._tracker_name = None
            self._cola_node_name = None
            self._active = False
            self._constraint = None
            self._physics_registered = False
            self._tracker = None
            self._cola_node = None
            self._cola_scale = None
            self._sig_start = None
            self._sig_stop = None
            self._sig_cont = None

        def setup(self, tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False):
            """配置 tracker → Cola 绑定。maintain_offset=False：瓶子位置直接对齐 tracker。"""
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._cola_node_name = cola_node_name
            self._maintain_offset = maintain_offset
            print("[ColaTracker] Configured: {} -> '{}' (position only, maintain_offset={})".format(
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

            # 记录原始缩放（解决瓶子变大问题）
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

            # 创建位置约束（不跟随旋转）
            try:
                self._constraint = vrConstraintService.createPositionConstraint(
                    [self._tracker.getNode()], self._cola_node, self._maintain_offset)
            except Exception as e:
                print("[ColaTracker] ERROR creating position constraint: " + str(e))
                return

            # 立即恢复原始缩放（覆盖约束可能带来的缩放影响）
            if self._cola_scale is not None:
                try:
                    setTransformNodeScale(self._cola_node,
                        self._cola_scale.x(), self._cola_scale.y(), self._cola_scale.z())
                    print("[ColaTracker] Scale restored to original")
                except Exception as e:
                    print("[ColaTracker] WARNING restoring scale: " + str(e))

            self._connect_collision_signals(self._cola_node)
            self._active = True
            print("[ColaTracker] Started: {} -> '{}' (PositionConstraint + kinematic physics)".format(
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

    # ======================================================================
    # 实例化
    # ======================================================================
    _transform_tracker = TransformTracker()
    _cola_tracker = ColaTracker()

    # ======================================================================
    # 控制器按键绑定
    # ======================================================================
    try:
        left_ctrl  = vrDeviceService.getDevice("LeftController")
        right_ctrl = vrDeviceService.getDevice("RightController")
        left_ctrl.getButton("ButtonY").signal().pressed.connect(lambda: _transform_tracker.toggle())
        right_ctrl.getButton("ButtonB").signal().pressed.connect(lambda: _cola_tracker.toggle())
        print("[PhysicsTracker] Buttons bound: left-Y=TransformTracker, right-B=ColaTracker")
    except Exception as e:
        print("[PhysicsTracker] WARNING binding buttons: " + str(e))

    _physics_tracker_initialized = True
    print("[PhysicsTracker] Initialized (position-only constraints, objects keep original rotation).")

# ======================================================================
# 模块级公开 API（无 recalibrate）
# ======================================================================

def setup_transform(tracker_name, node_name, maintain_offset=False):
    """配置 tracker → 节点绑定（仅位置，物体保持自身旋转）。"""
    global _transform_tracker
    _transform_tracker.setup(tracker_name, node_name, maintain_offset)

def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False):
    """配置 tracker → Cola 绑定（仅位置，瓶子保持正放）。"""
    global _cola_tracker
    _cola_tracker.setup(tracker_name, cola_node_name, maintain_offset)

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

setup_transform("tracker-1", "SeatNode")
start_transform()

setup_cola("tracker-2", "Cola")
start_cola()