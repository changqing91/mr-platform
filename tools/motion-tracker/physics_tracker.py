# ======================================================================
# VRED Physics Tracker
#
# tracker-1 → TransformTracker: ParentConstraint 驱动任意 Transform3D 节点
# tracker-2 → ColaTracker: 作为可乐瓶 (Cola) 的物理运动学对象
#             ├── kinematic: timer 同步位姿并锁定缩放（避免瓶子变大）
#             ├── dynamic: 施加力进行跟随（Moving Dynamic Actors）
#             ├── 自动确保 Cola 注册为对应 physics 对象类型
#             └── 碰撞回调：打印碰撞开始/结束事件及接触点信息
#
# 用法（VRED Python 控制台）：
#   setup_transform("tracker-1", "SeatNode")  # 配置 tracker-1 → Transform3D 绑定
#   setup_cola("tracker-2", "Cola", False, "kinematic")  # kinematic 模式
#   setup_cola("tracker-2", "Cola", False, "dynamic")    # dynamic 模式
#   set_cola_dynamic_tuning(18.0, 0.06)         # 可选：设置 dynamic 跟随参数
#   set_cola_dynamic_tuning(gain=200.0, max_step=0.5)  # 先用大参数测试
#   start_transform()                          # 启动 tracker-1 追踪
#   start_cola()                               # 启动 tracker-2 物理追踪
#   stop_cola()                                # 停止，解除约束
#   physics_status()                           # 打印当前状态
#
# 右手 Y 键（左手控制器）：切换 tracker-1 追踪开/关
# 右手 B 键（右手控制器）：切换 tracker-2 Cola 追踪开/关
# ======================================================================

try:
    from PySide6.QtGui import QVector3D
except ImportError:
    from PySide2.QtGui import QVector3D

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
        将 tracker-2 绑定到 Cola 节点：
          1. 根据模式确保 Cola 已在 vrPhysicsService 中注册为 dynamic/kinematic
          2. kinematic: timer 同步位置+旋转并锁定 scale
              dynamic: 每帧施加跟随力，保留物理惯性
        3. 监听 collisionStarted / collisionStopped / collisionContinues 信号，
           打印碰撞事件及接触点坐标

        注意：如果 VRED 物理编辑器已经将 Cola 注册为 kinematic，脚本不会重复添加。
        若编辑器中注册的是 dynamic（力驱动），则 Cola 无法被 tracker 手动驱动，
        此时脚本会警告并尝试用 removeObject + addKinematicObject 重新注册。
        """

        def __init__(self):
            self._tracker_name = None
            self._cola_node_name = None
            self._follow_mode = "kinematic"
            self._constraint = None
            self._active = False
            self._maintain_offset = False
            self._physics_registered = False
            self._tracker = None
            self._cola_node = None
            self._cola_physics_obj = None
            self._dynamic_timer = vrTimer()
            self._dynamic_timer_connected = False
            self._kinematic_timer = vrTimer()
            self._kinematic_timer_connected = False
            self._cola_scale = None
            self._kinematic_offset = None
            self._dynamic_gain = 18.0
            self._dynamic_max_step = 0.06
            # 碰撞信号连接句柄
            self._sig_start = None
            self._sig_stop = None
            self._sig_cont = None

        def setup(self, tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False,
                  follow_mode="kinematic"):
            """配置 tracker → Cola 物理绑定。"""
            if self._active:
                self.stop()

            mode = str(follow_mode).strip().lower()
            if mode not in ("kinematic", "dynamic"):
                print("[ColaTracker] WARNING: unsupported follow_mode='{}', fallback to 'kinematic'".format(
                    follow_mode))
                mode = "kinematic"

            self._tracker_name = tracker_name
            self._cola_node_name = cola_node_name
            self._maintain_offset = maintain_offset
            self._follow_mode = mode
            print("[ColaTracker] Configured: {} -> '{}' (maintain_offset={}, mode={})".format(
                tracker_name, cola_node_name, maintain_offset, mode))

        def start(self):
            """
            激活物理追踪：
            1. 确保 Physics 服务激活
            2. 确保 Cola 为当前模式注册（kinematic / dynamic）
            3. 按模式创建跟随（timer pose-sync / force-follow）
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

            # 注册物理对象前保存 Cola 的世界变换，
            # 防止 addKinematicObject/addDynamicObject 将节点重置到原点导致瓶子消失
            _saved_t = _saved_r = _saved_s = None
            try:
                _saved_t = getTransformNodeTranslation(colaNode, True)
                _saved_r = getTransformNodeRotation(colaNode)
                _saved_s = getTransformNodeScale(colaNode)
            except Exception:
                pass

            # 确保 Cola 为 kinematic 物理对象
            self._ensure_physics_mode(colaNode)

            # 恢复 Cola 原始世界变换
            try:
                if _saved_t is not None:
                    setTransformNodeTranslation(colaNode,
                        _saved_t.x(), _saved_t.y(), _saved_t.z(), True)
                if _saved_r is not None:
                    setTransformNodeRotation(colaNode,
                        _saved_r.x(), _saved_r.y(), _saved_r.z())
                if _saved_s is not None:
                    setTransformNodeScale(colaNode,
                        _saved_s.x(), _saved_s.y(), _saved_s.z())
            except Exception as e:
                print("[ColaTracker] WARNING: failed to restore Cola transform: " + str(e))

            self._tracker = tracker
            self._cola_node = colaNode

            if self._follow_mode == "kinematic":
                # kinematic 模式改为 timer 同步位姿，避免 ParentConstraint 继承 tracker 缩放
                if self._maintain_offset:
                    print("[ColaTracker] WARNING: maintain_offset is ignored in kinematic timer follow mode")
                if not self._start_kinematic_follow():
                    return
            else:
                # dynamic 模式通过每帧施加速度变化跟随 tracker
                if not self._start_dynamic_follow():
                    return

            # 连接碰撞信号（先断开再连，防止重复注册）
            self._connect_collision_signals(colaNode)

            self._active = True
            print("[ColaTracker] Started. Cola tracked by {}, mode={}, physics collisions active.".format(
                self._tracker_name, self._follow_mode))

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
            self._stop_dynamic_follow()

            # 断开碰撞信号
            self._disconnect_collision_signals()

            self._active = False
            self._tracker = None
            self._cola_node = None
            self._cola_physics_obj = None
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
            print("[ColaTracker] {} [{}] ({}, mode={})".format(cfg, state, phys, self._follow_mode))

        # ------------------------------------------------------------------
        # 内部：物理注册
        # ------------------------------------------------------------------
        def _ensure_physics_mode(self, colaNode):
            try:
                want_dynamic = self._follow_mode == "dynamic"
                dynamic_nodes = vrPhysicsService.getDynamicObjects()
                kinematic_nodes = vrPhysicsService.getKinematicObjects()
                is_dynamic = any(n.getName() == colaNode.getName() for n in dynamic_nodes)
                is_kinematic = any(n.getName() == colaNode.getName() for n in kinematic_nodes)

                if vrPhysicsService.hasPhysicsObject(colaNode):
                    if want_dynamic and is_dynamic:
                        self._physics_registered = True
                        print("[ColaTracker] Cola already registered as dynamic (Physics Editor)")
                    elif (not want_dynamic) and is_kinematic:
                        self._physics_registered = True
                        print("[ColaTracker] Cola already registered as kinematic (Physics Editor)")
                    else:
                        # 角色类型不符合当前模式，重新注册
                        print("[ColaTracker] WARNING: Cola collider type does not match mode={}, "
                              "attempting re-register...".format(self._follow_mode))
                        vrPhysicsService.removeObject(colaNode)
                        hullConf = vrdPhysicsHullConfig()
                        ok = vrPhysicsService.addDynamicObject(colaNode, hullConf) if want_dynamic \
                            else vrPhysicsService.addKinematicObject(colaNode, hullConf)
                        self._physics_registered = ok
                        if ok:
                            print("[ColaTracker] Cola re-registered as {}".format(
                                "dynamic" if want_dynamic else "kinematic"))
                        else:
                            print("[ColaTracker] WARNING: failed to re-register Cola")
                else:
                    # 未注册，按当前模式注册
                    hullConf = vrdPhysicsHullConfig()
                    ok = vrPhysicsService.addDynamicObject(colaNode, hullConf) if want_dynamic \
                        else vrPhysicsService.addKinematicObject(colaNode, hullConf)
                    self._physics_registered = ok
                    if ok:
                        print("[ColaTracker] Cola registered as {} object".format(
                            "dynamic" if want_dynamic else "kinematic"))
                    else:
                        print("[ColaTracker] WARNING: failed to register Cola")
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
            if not self._active or self._follow_mode != "kinematic":
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

                # 每帧恢复 Cola 原始缩放，防止 tracker 缩放链条污染
                if self._cola_scale is not None:
                    setTransformNodeScale(self._cola_node,
                                          self._cola_scale.x(),
                                          self._cola_scale.y(),
                                          self._cola_scale.z())
            except Exception as e:
                print("[ColaTracker] WARNING kinematic update failed: " + str(e))

        # ------------------------------------------------------------------
        # 内部：dynamic 模式（Moving Dynamic Actors）
        # ------------------------------------------------------------------
        def _start_dynamic_follow(self):
            try:
                self._cola_physics_obj = vrPhysicsService.getPhysicsObject(self._cola_node, True)
                if not self._cola_physics_obj:
                    print("[ColaTracker] ERROR: failed to get Cola physics object in dynamic mode")
                    return False
            except Exception as e:
                print("[ColaTracker] ERROR: getPhysicsObject failed: " + str(e))
                return False

            try:
                # 如果可用，优先速度变化模式提升跟随性。
                try:
                    self._cola_physics_obj.setForceMode(vrPhysicsTypes.ForceMode.VelocityChange)
                except Exception:
                    pass
                self._cola_physics_obj.setForceWorldFrame(True)
                self._cola_physics_obj.setForceEnabled(True)
            except Exception as e:
                print("[ColaTracker] WARNING: dynamic force setup failed: " + str(e))

            if not self._dynamic_timer_connected:
                self._dynamic_timer.connect(self._dynamic_update)
                self._dynamic_timer_connected = True
            self._dynamic_timer.setActive(1)
            print("[ColaTracker] Dynamic follow loop active")
            return True

        def _stop_dynamic_follow(self):
            try:
                self._dynamic_timer.setActive(0)
            except Exception:
                pass

            try:
                if self._cola_physics_obj:
                    self._cola_physics_obj.setForceEnabled(False)
                    self._cola_physics_obj.setForce(QVector3D(0.0, 0.0, 0.0))
            except Exception:
                pass

        def _dynamic_update(self):
            if not self._active or self._follow_mode != "dynamic":
                return
            if not self._tracker or not self._cola_node or not self._cola_physics_obj:
                return

            try:
                col = self._tracker.getTrackingMatrix().column(3)
                # tracking(Y-up) -> scene(Z-up)
                tx = col.x()
                ty = col.y()
                tz = col.z()
                target_x = -tx
                target_y = -tz
                target_z = ty

                cur = getTransformNodeTranslation(self._cola_node, True)
                dx = target_x - cur.x()
                dy = target_y - cur.y()
                dz = target_z - cur.z()

                # 限幅，防止一次校正过猛导致抖动
                dx = max(min(dx, self._dynamic_max_step), -self._dynamic_max_step)
                dy = max(min(dy, self._dynamic_max_step), -self._dynamic_max_step)
                dz = max(min(dz, self._dynamic_max_step), -self._dynamic_max_step)

                self._cola_physics_obj.setForce(QVector3D(
                    dx * self._dynamic_gain,
                    dy * self._dynamic_gain,
                    dz * self._dynamic_gain))
            except Exception as e:
                print("[ColaTracker] WARNING dynamic update failed: " + str(e))

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
               follow_mode="kinematic"):
    """
    配置 tracker-2 → Cola 物理绑定。

    Args:
        tracker_name (str): tracker 设备名，默认 "tracker-2"
        cola_node_name (str): Cola 节点名，默认 "Cola"
        maintain_offset (bool): True=保留初始偏移，False=直接吸附
        follow_mode (str): "kinematic"(默认) 或 "dynamic"
    """
    global _cola_tracker
    _cola_tracker.setup(tracker_name, cola_node_name, maintain_offset, follow_mode)

def set_cola_follow_mode(follow_mode):
    """设置 Cola 跟随模式。可选: "kinematic" / "dynamic"。"""
    global _cola_tracker
    _cola_tracker.setup(_cola_tracker._tracker_name or "tracker-2",
                        _cola_tracker._cola_node_name or "Cola",
                        _cola_tracker._maintain_offset,
                        follow_mode)

def set_cola_dynamic_tuning(gain=None, max_step=None):
    """
    设置 dynamic 模式跟随参数。

    Args:
        gain (float): 误差增益，越大跟随越快（也更易抖动）
        max_step (float): 每帧误差限幅，越大响应越快
    """
    global _cola_tracker
    if gain is not None:
        try:
            _cola_tracker._dynamic_gain = float(gain)
        except Exception:
            print("[ColaTracker] WARNING: invalid gain={}".format(gain))
    if max_step is not None:
        try:
            _cola_tracker._dynamic_max_step = float(max_step)
        except Exception:
            print("[ColaTracker] WARNING: invalid max_step={}".format(max_step))
    print("[ColaTracker] Dynamic tuning: gain={}, max_step={}".format(
        _cola_tracker._dynamic_gain, _cola_tracker._dynamic_max_step))

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
