# ======================================================================
# VRED Physics Tracker
#
# tracker-1 → TransformTracker: ParentConstraint 驱动任意 Transform3D 节点
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
        将 tracker-2 绑定到 Cola 节点（kinematic 模式）：
          1. 确保 Cola 在 vrPhysicsService 中注册为 kinematic 对象
          2. timer 同步位置+旋转并锁定 scale，避免瓶子变形
          3. 监听 collisionStarted / collisionStopped / collisionContinues 信号，
             打印碰撞事件及接触点坐标，碰撞时 Cola 放大高亮
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
            # 碰撞高亮（距离检测）
            self._highlight_active = False
            self._highlight_scale_factor = 1.15
            self._highlight_distance = 150.0   # 场景单位（mm），可通过 set_cola_highlight_distance 调整
            self._console_node = None
            self._console_node_name = ""
            # 碰撞信号连接句柄（辅助用）
            self._sig_start = None
            self._sig_stop = None
            self._sig_cont = None

        def setup(self, tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False,
                  console_node_name=""):
            """配置 tracker → Cola kinematic 物理绑定。

            console_node_name: 用于高亮检测的目标节点名（如 "Console1"）。留空则不检测。
            """
            if self._active:
                self.stop()
            self._tracker_name = tracker_name
            self._cola_node_name = cola_node_name
            self._maintain_offset = maintain_offset
            self._console_node_name = console_node_name
            print("[ColaTracker] Configured: {} -> '{}' (maintain_offset={}, console_highlight='{}')".format(
                tracker_name, cola_node_name, maintain_offset, console_node_name))

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

            # 断开碰撞信号
            self._disconnect_collision_signals()

            self._active = False
            self._highlight_active = False
            self._tracker = None
            self._cola_node = None
            self._console_node = None
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

            # 解析高亮目标节点
            self._console_node = None
            if self._console_node_name:
                try:
                    self._console_node = findNode(self._console_node_name)
                    if self._console_node:
                        print("[ColaTracker] Highlight target: '{}' (distance threshold={})".format(
                            self._console_node_name, self._highlight_distance))
                    else:
                        print("[ColaTracker] WARNING: highlight target node not found: '{}'".format(
                            self._console_node_name))
                except Exception as e:
                    print("[ColaTracker] WARNING: error finding highlight target: " + str(e))

            self._kinematic_offset = None
            if self._maintain_offset:
                try:
                    tracker_node = self._tracker.getNode()
                    t_tracker = getTransformNodeTranslation(tracker_node, True)
                    t_cola = getTransformNodeTranslation(self._cola_node, True)
                    self._kinematic_offset = Vec3f(
                        t_cola.x() - t_tracker.x(),
                        t_cola.y() - t_tracker.y(),
                        t_cola.z() - t_tracker.z())
                    print("[ColaTracker] Kinematic maintain_offset enabled (position offset)")
                except Exception as e:
                    print("[ColaTracker] WARNING: failed to compute maintain_offset: " + str(e))

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

        def _kinematic_update(self):
            if not self._active:
                return
            if not self._tracker or not self._cola_node:
                return

            try:
                tracker_node = self._tracker.getNode()
                t = getTransformNodeTranslation(tracker_node, True)
                r = getTransformNodeRotation(tracker_node)

                tx = t.x()
                ty = t.y()
                tz = t.z()
                if self._kinematic_offset is not None:
                    tx += self._kinematic_offset.x()
                    ty += self._kinematic_offset.y()
                    tz += self._kinematic_offset.z()

                setTransformNodeTranslation(self._cola_node, tx, ty, tz, True)
                setTransformNodeRotation(self._cola_node, r.x(), r.y(), r.z())

                # 距离检测高亮（不依赖碰撞信号，kinematic/static 对均有效）
                if self._console_node is not None:
                    try:
                        c = getTransformNodeTranslation(self._console_node, True)
                        dist = max(abs(tx - c.x()), abs(ty - c.y()), abs(tz - c.z()))
                        prev = self._highlight_active
                        self._highlight_active = dist < self._highlight_distance
                        if self._highlight_active != prev:
                            print("[ColaTracker] Highlight {} (dist={:.1f})".format(
                                "ON" if self._highlight_active else "OFF", dist))
                    except Exception:
                        pass

                # 每帧应用 scale（正常锁定 or 高亮放大）
                sx = self._cola_scale.x() if self._cola_scale is not None else 1.0
                sy = self._cola_scale.y() if self._cola_scale is not None else 1.0
                sz = self._cola_scale.z() if self._cola_scale is not None else 1.0
                f = self._highlight_scale_factor if self._highlight_active else 1.0
                setTransformNodeScale(self._cola_node, sx * f, sy * f, sz * f)
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
                self._highlight_active = True
                pts = info.getContactPoints()
                pt_str = ""
                if pts:
                    p = pts[0]
                    pt_str = " | 接触点: ({:.2f}, {:.2f}, {:.2f})".format(p.x(), p.y(), p.z())
                print("[ColaTracker] 碰撞开始: Cola <-> '{}'{} ({} 接触点) [HIGHLIGHT ON]".format(
                    other, pt_str, len(pts)))

            def on_collision_stopped(info):
                n1 = info.getCollidingRootNode1().getName()
                n2 = info.getCollidingRootNode2().getName()
                if cola_name not in (n1, n2):
                    return
                other = n2 if n1 == cola_name else n1
                self._highlight_active = False
                print("[ColaTracker] 碰撞结束: Cola <-> '{}' [HIGHLIGHT OFF]".format(other))

            def on_collision_continues(info):
                n1 = info.getCollidingRootNode1().getName()
                n2 = info.getCollidingRootNode2().getName()
                if cola_name not in (n1, n2):
                    return
                self._highlight_active = True
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

def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False,
               console_node_name=""):
    """
    配置 tracker-2 → Cola kinematic 物理绑定。

    Args:
        tracker_name (str): tracker 设备名，默认 "tracker-2"
        cola_node_name (str): Cola 节点名，默认 "Cola"
        maintain_offset (bool): True=保留初始偏移，False=直接吸附
        console_node_name (str): 高亮检测目标节点名（如 "Console1"），留空则不检测
    """
    global _cola_tracker
    _cola_tracker.setup(tracker_name, cola_node_name, maintain_offset, console_node_name)

def set_cola_highlight_distance(distance):
    """设置高亮距离阈值（场景单位，默认 150）。Cola 与目标节点中心距离小于此值时触发高亮。"""
    global _cola_tracker
    try:
        _cola_tracker._highlight_distance = float(distance)
        print("[ColaTracker] Highlight distance threshold set to {}".format(distance))
    except Exception:
        print("[ColaTracker] WARNING: invalid distance={}".format(distance))

def set_cola_highlight_scale(factor):
    """
    设置碰撞高亮时 Cola 的缩放倍数，默认 1.15（放大 15%）。
    factor=1.0 等效于关闭高亮缩放。
    """
    global _cola_tracker
    try:
        _cola_tracker._highlight_scale_factor = float(factor)
        print("[ColaTracker] Highlight scale factor set to {}".format(factor))
    except Exception:
        print("[ColaTracker] WARNING: invalid factor={}".format(factor))

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

# ======================================================================
# 脚本加载时自动执行步骤 2、3、4
# ======================================================================
try:
    setup_cola("tracker-2", "Cola", maintain_offset=False, console_node_name="Console1")
    set_cola_highlight_distance(150)
    start_cola()
    print("[physics_tracker] Auto setup+start complete.")
except Exception as _e:
    print("[physics_tracker] Auto start failed: " + str(_e))
