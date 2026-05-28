# ======================================================================
# VRED Physics Tracker
#
# tracker-1 → TransformTracker: ParentConstraint 驱动任意 Transform3D 节点
# tracker-2 → ColaTracker: 作为可乐瓶 (Cola) 的物理运动学对象
#             ├── ParentConstraint 驱动 Cola 节点位置/旋转
#             ├── 确保 Cola 注册为 kinematic physics 对象（与中控台静态角色碰撞）
#             └── 碰撞回调：打印碰撞开始/结束事件及接触点信息
#
# 用法（VRED Python 控制台）：
#   setup_transform("tracker-1", "SeatNode")  # 配置 tracker-1 → Transform3D 绑定
#   setup_cola("tracker-2", "Cola")           # 配置 tracker-2 → Cola 物理绑定
#   start_transform()                          # 启动 tracker-1 追踪
#   start_cola()                               # 启动 tracker-2 物理追踪
#   stop_cola()                                # 停止，解除约束
#   physics_status()                           # 打印当前状态
#
# 右手 Y 键（左手控制器）：切换 tracker-1 追踪开/关
# 右手 B 键（右手控制器）：切换 tracker-2 Cola 追踪开/关
# ======================================================================

global _physics_tracker_initialized
if '_physics_tracker_initialized' in globals() and _physics_tracker_initialized:
    print("[PhysicsTracker] Already initialized, skipping re-init")
else:
    _physics_tracker_initialized = False

    # ======================================================================
    # TransformTracker — tracker-1 → Transform3D 节点（ParentConstraint）
    # ======================================================================
    class TransformTracker:
        """
        通过 ParentConstraint 将指定 tracker 设备绑定到任意 Transform3D 场景节点。
        与 motion_tracker.py 中的单条绑定逻辑等价，专用于此脚本。
        """

        def __init__(self):
            self._tracker_name = None
            self._node_name = None
            self._constraint = None
            self._active = False
            self._maintain_offset = False

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
            """激活约束，开始位置/旋转追踪。"""
            if self._active:
                print("[TransformTracker] Already active.")
                return
            if not self._tracker_name or not self._node_name:
                print("[TransformTracker] Not configured. Call setup(tracker_name, node_name) first.")
                return

            tracker = None
            try:
                tracker = vrDeviceService.getVRDevice(self._tracker_name)
                if not tracker:
                    print("[TransformTracker] WARNING: tracker not found: " + self._tracker_name)
                    return
            except Exception as e:
                print("[TransformTracker] ERROR getting tracker: " + str(e))
                return

            node = None
            try:
                node = findNode(self._node_name)
                if not node:
                    print("[TransformTracker] WARNING: node not found: " + self._node_name)
                    return
            except Exception as e:
                print("[TransformTracker] ERROR finding node: " + str(e))
                return

            try:
                self._constraint = vrConstraintService.createParentConstraint(
                    [tracker.getNode()], node, self._maintain_offset)
                self._active = True
                print("[TransformTracker] Started: {} -> '{}'".format(
                    self._tracker_name, self._node_name))
            except Exception as e:
                print("[TransformTracker] ERROR creating constraint: " + str(e))

        def stop(self):
            """解除约束，节点保持最后位置。"""
            if not self._active:
                return
            try:
                if self._constraint is not None:
                    vrConstraintService.deleteConstraint(self._constraint)
                    self._constraint = None
            except Exception as e:
                print("[TransformTracker] WARNING deleting constraint: " + str(e))
            self._active = False
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
    # ColaTracker — tracker-2 → Cola 物理运动学对象 + 碰撞检测
    # ======================================================================
    class ColaTracker:
        """
        将 tracker-2 绑定到 Cola 节点：
        1. 确保 Cola 节点已在 vrPhysicsService 中注册为 kinematic 对象
           （与中控台静态角色交互产生碰撞事件）
        2. 通过 ParentConstraint 用 tracker 驱动 Cola 位置/旋转
        3. 监听 collisionStarted / collisionStopped / collisionContinues 信号，
           打印碰撞事件及接触点坐标

        注意：如果 VRED 物理编辑器已经将 Cola 注册为 kinematic，脚本不会重复添加。
        若编辑器中注册的是 dynamic（力驱动），则 Cola 无法被 tracker 手动驱动，
        此时脚本会警告并尝试用 removeObject + addKinematicObject 重新注册。
        """

        def __init__(self):
            self._tracker_name = None
            self._cola_node_name = None
            self._constraint = None
            self._active = False
            self._maintain_offset = False
            self._physics_registered = False
            # 碰撞信号连接句柄
            self._sig_start = None
            self._sig_stop = None
            self._sig_cont = None

        def setup(self, tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False):
            """配置 tracker → Cola 物理绑定。"""
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
            2. 确保 Cola 为 kinematic 注册（如未注册则注册）
            3. 创建 tracker → Cola 的 ParentConstraint
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
            self._ensure_kinematic(colaNode)

            # 创建 ParentConstraint: tracker → Cola
            try:
                self._constraint = vrConstraintService.createParentConstraint(
                    [tracker.getNode()], colaNode, self._maintain_offset)
                print("[ColaTracker] Constraint created: {} -> '{}'".format(
                    self._tracker_name, self._cola_node_name))
            except Exception as e:
                print("[ColaTracker] ERROR creating constraint: " + str(e))
                return

            # 连接碰撞信号（先断开再连，防止重复注册）
            self._connect_collision_signals(colaNode)

            self._active = True
            print("[ColaTracker] Started. Cola tracked by {}, physics collisions active.".format(
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

            # 断开碰撞信号
            self._disconnect_collision_signals()

            self._active = False
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
        def _ensure_kinematic(self, colaNode):
            try:
                if vrPhysicsService.hasPhysicsObject(colaNode):
                    # 已注册：检查是否为 kinematic
                    kinematic_nodes = vrPhysicsService.getKinematicObjects()
                    is_kinematic = any(n.getName() == colaNode.getName() for n in kinematic_nodes)
                    if is_kinematic:
                        self._physics_registered = True
                        print("[ColaTracker] Cola already registered as kinematic (Physics Editor)")
                    else:
                        # dynamic 对象无法手动驱动，需要重新注册为 kinematic
                        print("[ColaTracker] WARNING: Cola is registered as dynamic/static, "
                              "attempting re-register as kinematic...")
                        vrPhysicsService.removeObject(colaNode)
                        hullConf = vrdPhysicsHullConfig()
                        ok = vrPhysicsService.addKinematicObject(colaNode, hullConf)
                        self._physics_registered = ok
                        if ok:
                            print("[ColaTracker] Cola re-registered as kinematic")
                        else:
                            print("[ColaTracker] WARNING: failed to re-register Cola as kinematic")
                else:
                    # 未注册，添加为 kinematic
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
    global _transform_tracker
    global _cola_tracker
    _transform_tracker = TransformTracker()
    _cola_tracker = ColaTracker()

    # ======================================================================
    # 控制器按键绑定
    # ======================================================================
    # 左手 Y 键 → toggle TransformTracker
    # 右手 B 键 → toggle ColaTracker
    # （仅在 Locomotion 交互组生效）
    try:
        _old_pt = vrDeviceService.getInteraction("PhysicsTrackerInteraction")
        if _old_pt and _old_pt.isValid():
            vrDeviceService.removeInteraction(_old_pt)
    except Exception:
        pass

    try:
        _pt_interaction = vrDeviceService.createInteraction("PhysicsTrackerInteraction")
        _pt_interaction.setSupportedInteractionGroups(["Locomotion"])

        _pt_y_action = _pt_interaction.createControllerAction("left-y-pressed")
        _pt_y_action.signal().triggered.connect(lambda: _transform_tracker.toggle())

        _pt_b_action = _pt_interaction.createControllerAction("right-b-pressed")
        _pt_b_action.signal().triggered.connect(lambda: _cola_tracker.toggle())

        print("[PhysicsTracker] Buttons bound: left-Y=TransformTracker, right-B=ColaTracker (Locomotion)")
    except Exception as e:
        print("[PhysicsTracker] WARNING binding buttons: " + str(e))

    _physics_tracker_initialized = True
    print("[PhysicsTracker] Initialized.")
    print("[PhysicsTracker] Call setup_transform(tracker, node) and setup_cola(tracker, node) to configure.")

# ======================================================================
# 模块级公开 API
# ======================================================================

def setup_transform(tracker_name, node_name, maintain_offset=False):
    """
    配置 tracker-1 → Transform3D 节点绑定。

    Args:
        tracker_name (str): tracker 设备名，如 "tracker-1"
        node_name (str): VRED 场景节点名，如 "Seat"
        maintain_offset (bool): True=保留初始偏移，False=直接吸附
    """
    global _transform_tracker
    _transform_tracker.setup(tracker_name, node_name, maintain_offset)

def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False):
    """
    配置 tracker-2 → Cola 物理绑定。

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
