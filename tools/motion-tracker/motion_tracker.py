# ======================================================================
# VRED Motion Tracker — 多 Tracker 动态绑定
#
# 用法（VRED Python 控制台）：
#   list_trackers()                         # 枚举已连接 tracker
#   bind("tracker-1", "Chair")              # 配置绑定
#   bind("tracker-2", "SteeringWheel")
#   start_tracking()                        # 激活所有绑定
#   stop_tracking("tracker-2")             # 单独停止某一个
#   status()                                # 打印当前状态
#
# 右手控制器 B 键：切换全部绑定开/关（仅在 Locomotion 交互组生效）
# ======================================================================

global _motion_tracker_initialized
if '_motion_tracker_initialized' in globals() and _motion_tracker_initialized:
    print("[MotionTracker] Already initialized, skipping re-init")
else:
    _motion_tracker_initialized = False

    # ======================================================================
    # MotionTrackerManager
    # ======================================================================
    class MotionTrackerManager:
        """
        管理多个 tracker → 场景节点 的 ParentConstraint 绑定。
        每条绑定独立控制，支持全局开/关切换。
        """

        # tracker-0 ~ tracker-9 枚举上限
        _TRACKER_MAX_INDEX = 9

        def __init__(self):
            # {tracker_name: {"node_name": str, "maintain_offset": bool,
            #                  "constraint": vrdConstraintNode|None, "active": bool}}
            self._bindings = {}

        # ------------------------------------------------------------------
        # 枚举
        # ------------------------------------------------------------------
        def list_trackers(self):
            """枚举并返回已连接的 tracker 设备名列表，同时打印到控制台。"""
            found = []
            for i in range(self._TRACKER_MAX_INDEX + 1):
                name = "tracker-{}".format(i)
                try:
                    dev = vrDeviceService.getVRDevice(name)
                    if dev:
                        found.append(name)
                except Exception:
                    pass
            if found:
                print("[MotionTracker] Connected trackers: " + ", ".join(found))
            else:
                print("[MotionTracker] No connected trackers found (tracker-0 ~ tracker-{})".format(
                    self._TRACKER_MAX_INDEX))
            return found

        # ------------------------------------------------------------------
        # 绑定配置
        # ------------------------------------------------------------------
        def bind(self, tracker_name, node_name, maintain_offset=False):
            """
            添加或更新一条 tracker → 场景节点 的绑定配置。
            如果该 tracker 已有激活的约束，先解除再重新创建。

            Args:
                tracker_name (str): VRED tracker 设备名，如 "tracker-0"
                node_name (str): VRED 场景节点名，如 "Chair"
                maintain_offset (bool): True=保留初始偏移，False=直接吸附到 tracker
            """
            # 若已存在且激活，先解除
            if tracker_name in self._bindings and self._bindings[tracker_name]["active"]:
                self._deactivate_binding(tracker_name)

            self._bindings[tracker_name] = {
                "node_name": node_name,
                "maintain_offset": maintain_offset,
                "constraint": None,
                "active": False,
            }
            print("[MotionTracker] Bound {} -> '{}' (maintain_offset={})".format(
                tracker_name, node_name, maintain_offset))

        def unbind(self, tracker_name):
            """删除一条绑定（如已激活则先解除约束）。"""
            if tracker_name not in self._bindings:
                print("[MotionTracker] No binding found for: " + tracker_name)
                return
            if self._bindings[tracker_name]["active"]:
                self._deactivate_binding(tracker_name)
            del self._bindings[tracker_name]
            print("[MotionTracker] Unbound: " + tracker_name)

        # ------------------------------------------------------------------
        # 启动 / 停止
        # ------------------------------------------------------------------
        def start(self, tracker_name=None):
            """
            激活约束。
            tracker_name=None 时激活所有已配置的绑定。
            """
            if tracker_name is not None:
                self._activate_binding(tracker_name)
            else:
                for name in list(self._bindings.keys()):
                    self._activate_binding(name)

        def stop(self, tracker_name=None):
            """
            解除约束（节点保持最后位置）。
            tracker_name=None 时停止所有绑定。
            """
            if tracker_name is not None:
                self._deactivate_binding(tracker_name)
            else:
                for name in list(self._bindings.keys()):
                    self._deactivate_binding(name)

        def toggle(self, tracker_name=None):
            """切换开/关。若存在任意激活绑定则全部停止，否则全部启动。"""
            names = [tracker_name] if tracker_name is not None else list(self._bindings.keys())
            any_active = any(self._bindings[n]["active"] for n in names if n in self._bindings)
            if any_active:
                for n in names:
                    self._deactivate_binding(n)
            else:
                for n in names:
                    self._activate_binding(n)

        # ------------------------------------------------------------------
        # 状态
        # ------------------------------------------------------------------
        def status(self):
            """打印所有绑定的当前状态。"""
            if not self._bindings:
                print("[MotionTracker] No bindings configured. Use bind(tracker_name, node_name).")
                return
            print("[MotionTracker] Current bindings:")
            for name, info in self._bindings.items():
                state = "ACTIVE" if info["active"] else "stopped"
                print("  {} -> '{}' [{}] (maintain_offset={})".format(
                    name, info["node_name"], state, info["maintain_offset"]))

        # ------------------------------------------------------------------
        # 内部：激活 / 解除单条绑定
        # ------------------------------------------------------------------
        def _activate_binding(self, tracker_name):
            if tracker_name not in self._bindings:
                print("[MotionTracker] No binding configured for: " + tracker_name)
                return
            info = self._bindings[tracker_name]
            if info["active"]:
                print("[MotionTracker] Already active: " + tracker_name)
                return

            # 获取 tracker 设备
            tracker = None
            try:
                tracker = vrDeviceService.getVRDevice(tracker_name)
                if not tracker:
                    print("[MotionTracker] WARNING: tracker device not found: " + tracker_name)
                    return
            except Exception as e:
                print("[MotionTracker] WARNING: failed to get tracker '{}': {}".format(tracker_name, e))
                return

            # 获取场景节点
            node = None
            try:
                node = findNode(info["node_name"])
                if not node:
                    print("[MotionTracker] WARNING: scene node not found: " + info["node_name"])
                    return
            except Exception as e:
                print("[MotionTracker] WARNING: failed to find node '{}': {}".format(info["node_name"], e))
                return

            # 创建 ParentConstraint: tracker 驱动 → scene node 跟随
            try:
                constraint = vrConstraintService.createParentConstraint(
                    [tracker.getNode()], node, info["maintain_offset"])
                info["constraint"] = constraint
                info["active"] = True
                print("[MotionTracker] Started: {} -> '{}'".format(tracker_name, info["node_name"]))
            except Exception as e:
                print("[MotionTracker] ERROR creating constraint for '{}': {}".format(tracker_name, e))

        def _deactivate_binding(self, tracker_name):
            if tracker_name not in self._bindings:
                return
            info = self._bindings[tracker_name]
            if not info["active"]:
                return
            try:
                if info["constraint"] is not None:
                    vrConstraintService.deleteConstraint(info["constraint"])
                    info["constraint"] = None
            except Exception as e:
                print("[MotionTracker] WARNING: failed to delete constraint for '{}': {}".format(
                    tracker_name, e))
            info["active"] = False
            print("[MotionTracker] Stopped: {} -> '{}'".format(tracker_name, info["node_name"]))

    # ======================================================================
    # B 键切换 Interaction（仅在 Locomotion 交互组生效）
    # ======================================================================
    global _mt_manager
    _mt_manager = MotionTrackerManager()

    try:
        # 清理旧的同名 interaction（防重入）
        _old = vrDeviceService.getInteraction("MotionTrackerInteraction")
        if _old and _old.isValid():
            vrDeviceService.removeInteraction(_old)
    except Exception:
        pass

    try:
        _mt_interaction = vrDeviceService.createInteraction("MotionTrackerInteraction")
        _mt_interaction.setSupportedInteractionGroups(["Locomotion"])
        _mt_b_action = _mt_interaction.createControllerAction("right-b-pressed")
        _mt_b_action.signal().triggered.connect(lambda: _mt_manager.toggle())
        print("[MotionTracker] Right-B toggle bound (Locomotion group)")
    except Exception as e:
        print("[MotionTracker] WARNING: failed to bind right-B toggle: " + str(e))

    _motion_tracker_initialized = True
    print("[MotionTracker] Initialized. Use list_trackers(), bind(), start_tracking(), status().")

# ======================================================================
# 模块级公开 API
# ======================================================================

def list_trackers():
    """枚举并返回当前已连接的 tracker 设备名列表。"""
    global _mt_manager
    return _mt_manager.list_trackers()

def bind(tracker_name, node_name, maintain_offset=False):
    """
    配置一条 tracker → 场景节点绑定（不立即激活）。

    Args:
        tracker_name (str): 如 "tracker-0"
        node_name (str): VRED 场景节点名，如 "Chair"
        maintain_offset (bool): True=保留初始位置偏移，False=直接吸附
    """
    global _mt_manager
    _mt_manager.bind(tracker_name, node_name, maintain_offset)

def unbind(tracker_name):
    """删除指定 tracker 的绑定（如已激活则先停止）。"""
    global _mt_manager
    _mt_manager.unbind(tracker_name)

def start_tracking(tracker_name=None):
    """
    激活约束，开始追踪。
    tracker_name=None 时激活所有已配置绑定。
    """
    global _mt_manager
    _mt_manager.start(tracker_name)

def stop_tracking(tracker_name=None):
    """
    解除约束，停止追踪（节点保持最后位置）。
    tracker_name=None 时停止所有绑定。
    """
    global _mt_manager
    _mt_manager.stop(tracker_name)

def toggle_tracking(tracker_name=None):
    """切换开/关。存在任意激活绑定时全部停止，否则全部启动。"""
    global _mt_manager
    _mt_manager.toggle(tracker_name)

def status():
    """打印所有绑定的当前状态。"""
    global _mt_manager
    _mt_manager.status()
