# ======================================================================
# VRED 轮胎替换工具
# 手柄 trigger 抓取 WheelRack 上的轮胎（Wheel_1~Wheel_4），拖动至
# Hub 安装区（FL/FR/BL/BR），松手后：
#   1. 切换 VariantSet 6_Hub_Switch → 对应 Wheel1~Wheel4 状态
#   2. 隐藏拖动的轮胎节点
# 再次安装时，自动还原上一个已安装轮胎的可见性。
# 锚点跟随版，Z 轴固定，修正 timer 错误
# ======================================================================

import math

global _wheel_swap_tool
if '_wheel_swap_tool' not in globals():
    _wheel_swap_tool = None

if '_wheel_swap_tool' in globals() and _wheel_swap_tool is not None:
    try:
        _wheel_swap_tool.disable()
    except Exception:
        pass
_wheel_swap_tool = None

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
_WHEEL_NAMES    = ["Wheel_1", "Wheel_2", "Wheel_3", "Wheel_4"]
_HUB_NAMES      = ["FL", "FR", "BL", "BR"]
_VARIANT_SET    = "Switch1"

_SNAP_THRESHOLD    = 2600.0
_MIN_DRAG_DISTANCE = 250.0

_TRACKER_NAME          = "tracker-1"
_TRACKER_BIND_NODE     = "Jahuar_project_7"
_TRACKER_ANCHOR_NODE   = "Wheel1"
_TRACKER_FIXED_Z       = None   # None 自动取汽车初始 Z

# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def _scan_all_nodes_by_name(name):
    result = []
    try:
        for n in getAllNodes():
            try:
                if n.getName() == name:
                    result.append(n)
            except Exception:
                pass
    except Exception:
        pass
    return result

def _scan_node_by_name(name):
    nodes = _scan_all_nodes_by_name(name)
    return nodes[0] if nodes else None

def _distance_xyz(p0, p1):
    dx = p0.x() - p1.x()
    dy = p0.y() - p1.y()
    dz = p0.z() - p1.z()
    return math.sqrt(dx*dx + dy*dy + dz*dz)

def _find_nearest_hub(world_pos):
    best_node = None
    best_dist = None
    for hub_name in _HUB_NAMES:
        for node in _scan_all_nodes_by_name(hub_name):
            try:
                npos = getTransformNodeTranslation(node, 1)
                d = _distance_xyz(world_pos, npos)
                if best_dist is None or d < best_dist:
                    best_node = node
                    best_dist = d
            except Exception:
                pass
    return best_node, best_dist

def _wheel_to_variant_state(wheel_name):
    return wheel_name.replace("_", "")

def _node_key(node):
    try:
        return getUniquePath(node)
    except Exception:
        return node.getName()

def _capture_node_transform(node):
    state = {
        "translation": None, "rotation": None, "scale": None,
        "rotate_pivot": None, "scale_pivot": None,
        "rotate_pivot_translation": None, "scale_pivot_translation": None,
    }
    try:
        state["translation"] = getTransformNodeTranslation(node, 0)
    except Exception: pass
    try:
        state["rotation"] = getTransformNodeRotation(node)
    except Exception: pass
    try:
        state["scale"] = getTransformNodeScale(node)
    except Exception: pass
    try:
        state["rotate_pivot"] = getTransformNodeRotatePivot(node, 0)
    except Exception: pass
    try:
        state["scale_pivot"] = getTransformNodeScalePivot(node, 0)
    except Exception: pass
    try:
        state["rotate_pivot_translation"] = getTransformNodeRotatePivotTranslation(node)
    except Exception: pass
    try:
        state["scale_pivot_translation"] = getTransformNodeScalePivotTranslation(node)
    except Exception: pass
    return state

def _restore_node_transform(node, state):
    if not state: return
    t = state.get("translation")
    if t is not None:
        try: setTransformNodeTranslation(node, t.x(), t.y(), t.z(), 0)
        except: pass
    r = state.get("rotation")
    if r is not None:
        try: setTransformNodeRotation(node, r.x(), r.y(), r.z())
        except: pass
    s = state.get("scale")
    if s is not None:
        try: setTransformNodeScale(node, s.x(), s.y(), s.z())
        except: pass
    rp = state.get("rotate_pivot")
    if rp is not None:
        try: setTransformNodeRotatePivot(node, rp.x(), rp.y(), rp.z(), 0)
        except: pass
    sp = state.get("scale_pivot")
    if sp is not None:
        try: setTransformNodeScalePivot(node, sp.x(), sp.y(), sp.z(), 0)
        except: pass
    rpt = state.get("rotate_pivot_translation")
    if rpt is not None:
        try: setTransformNodeRotatePivotTranslation(node, rpt.x(), rpt.y(), rpt.z())
        except: pass
    spt = state.get("scale_pivot_translation")
    if spt is not None:
        try: setTransformNodeScalePivotTranslation(node, spt.x(), spt.y(), spt.z())
        except: pass

def _switch_variant(state_name):
    try:
        selectNodeVariant(_VARIANT_SET, state_name)
        print("[WheelSwap] selectNodeVariant OK")
        return
    except Exception as e:
        print("[WheelSwap] selectNodeVariant ERROR: %s" % str(e))
    try:
        vs = vrVariantSets.getVariantSet(_VARIANT_SET)
        vs.loadVariant(state_name)
        print("[WheelSwap] vrVariantSets.loadVariant OK")
    except Exception as e2:
        print("[WheelSwap] vrVariantSets fallback ERROR: %s" % str(e2))

def _set_node_visible(node, visible):
    flag = 1 if visible else 0
    try:
        setNodeActive(node, flag)
        return
    except Exception:
        pass
    try:
        node.fields().setBool("active", visible)
        return
    except Exception:
        pass
    try:
        if visible: showNode(node)
        else: hideNode(node)
    except Exception as e:
        print("[WheelSwap] _set_node_visible ERROR: %s" % str(e))

def _get_vr_device(name):
    try:
        dev = vrDeviceService.getVRDevice(name)
        if dev: return dev
    except Exception: pass
    return None

# ------------------------------------------------------------------
# tracker 绑定（手动更新，Z 轴固定）
# ------------------------------------------------------------------
class TrackerBinding:
    def __init__(self):
        self.active = False
        self.tracker = None
        self.car_node = None
        self.anchor_node = None
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.fixed_z = 0.0
        self.timer = None
        self.timer_connected = False

    def setup(self, tracker_name, car_node_name, anchor_node_name, fixed_z=None):
        self.tracker = _get_vr_device(tracker_name)
        if not self.tracker:
            print("[TrackerBinding] Tracker not found:", tracker_name)
            return False
        self.car_node = _scan_node_by_name(car_node_name)
        if not self.car_node:
            print("[TrackerBinding] Car node not found:", car_node_name)
            return False
        self.anchor_node = _scan_node_by_name(anchor_node_name)
        if not self.anchor_node:
            print("[TrackerBinding] Anchor node not found:", anchor_node_name)
            return False

        try:
            setTransformNodeRotation(self.car_node, 0, 0, 0)
        except Exception as e:
            print("[TrackerBinding] WARNING reset rotation:", e)

        car_pos = getTransformNodeTranslation(self.car_node, 1)
        anchor_pos = getTransformNodeTranslation(self.anchor_node, 1)
        self.offset_x = anchor_pos.x() - car_pos.x()
        self.offset_y = anchor_pos.y() - car_pos.y()

        if fixed_z is None:
            self.fixed_z = car_pos.z()
        else:
            self.fixed_z = fixed_z

        tracker_pos = getTransformNodeTranslation(self.tracker.getNode(), 1)
        new_x = tracker_pos.x() - self.offset_x
        new_y = tracker_pos.y() - self.offset_y
        setTransformNodeTranslation(self.car_node, new_x, new_y, self.fixed_z, 1)
        print("[TrackerBinding] Initialized: offset=(%.2f, %.2f), fixed_z=%.2f" % (
            self.offset_x, self.offset_y, self.fixed_z))
        return True

    def start(self):
        if self.active:
            return
        if not self.tracker or not self.car_node:
            print("[TrackerBinding] Not set up")
            return
        if not self.timer_connected:
            self.timer = vrTimer()
            self.timer.connect(self._update)
            self.timer_connected = True
        # 修正：使用 setActive(1) 启动定时器
        self.timer.setActive(1)
        self.active = True
        print("[TrackerBinding] Started (X/Y follow, Z fixed)")

    def stop(self):
        if not self.active:
            return
        if self.timer:
            self.timer.setActive(0)
        self.active = False
        print("[TrackerBinding] Stopped")

    def _update(self):
        if not self.active:
            return
        try:
            tracker_pos = getTransformNodeTranslation(self.tracker.getNode(), 1)
            new_x = tracker_pos.x() - self.offset_x
            new_y = tracker_pos.y() - self.offset_y
            cur_pos = getTransformNodeTranslation(self.car_node, 1)
            if abs(cur_pos.x() - new_x) > 0.01 or abs(cur_pos.y() - new_y) > 0.01:
                setTransformNodeTranslation(self.car_node, new_x, new_y, self.fixed_z, 1)
        except Exception as e:
            print("[TrackerBinding] Update error:", e)

# ------------------------------------------------------------------
# 工具类 WheelSwapTool
# ------------------------------------------------------------------
class WheelSwapTool:
    def __init__(self):
        self._dragging = None
        self._ctrl_node = None
        self._drag_constraint = None
        self._tracker_binding = TrackerBinding()
        self._drag_orig_pos_local = None
        self._drag_orig_rot = None
        self._drag_orig_state = None
        self._drag_orig_parent = None
        self._drag_distance_accum = 0.0
        self._last_world_pos = None
        self._installed_wheel = None
        self._wheel_initial_states = {}

        # 直接使用默认 Pointer 交互，不创建自定义 Interaction
        self._pointer = vrDeviceService.getInteraction("Pointer")
        self._act_start = self._pointer.getControllerAction("start")
        self._act_execute = self._pointer.getControllerAction("execute")

        self._timer = vrTimer()
        self._timer_connected = False
        self._debug_tick = 0
        self.registry_key = "tool_wheel_swap"

    def _find_wheel_ancestor(self, node):
        cur = node
        while not cur.isNull():
            if cur.getName() in _WHEEL_NAMES:
                return cur
            cur = cur.getParent()
        return None

    def _remember_initial_state(self, wheel):
        key = _node_key(wheel)
        if key not in self._wheel_initial_states:
            self._wheel_initial_states[key] = _capture_node_transform(wheel)

    def _restore_initial_state(self, wheel):
        key = _node_key(wheel)
        state = self._wheel_initial_states.get(key)
        if state is not None:
            _restore_node_transform(wheel, state)

    def _enable_tracker_binding(self):
        if self._tracker_binding.active:
            return
        ok = self._tracker_binding.setup(_TRACKER_NAME, _TRACKER_BIND_NODE, _TRACKER_ANCHOR_NODE, _TRACKER_FIXED_Z)
        if ok:
            self._tracker_binding.start()

    def _disable_tracker_binding(self):
        self._tracker_binding.stop()

    def _on_trigger_press(self, action, device):
        if self._dragging is not None:
            return
        picked = device.pick().getNode()
        if picked.isNull():
            print("[WheelSwap] trigger pressed — no node picked")
            return
        wheel = self._find_wheel_ancestor(picked)
        if wheel is None or wheel.isNull():
            print("[WheelSwap] trigger pressed — not a wheel node: " + picked.getName())
            return
        print("[WheelSwap] Grabbed: " + wheel.getName())
        self._remember_initial_state(wheel)
        self._dragging = wheel
        self._ctrl_node = device.getNode()
        self._drag_orig_pos_local = getTransformNodeTranslation(wheel, 0)
        self._drag_orig_rot = getTransformNodeRotation(wheel)
        self._drag_orig_state = _capture_node_transform(wheel)
        self._drag_orig_parent = wheel.getParent()
        self._drag_distance_accum = 0.0
        self._last_world_pos = getTransformNodeTranslation(wheel, 1)
        try:
            self._drag_constraint = vrConstraintService.createParentConstraint(
                [self._ctrl_node], wheel, True)
        except Exception as e:
            print("[WheelSwap] createParentConstraint ERROR: " + str(e))
            self._drag_constraint = None
            self._dragging = None
            self._ctrl_node = None
            self._last_world_pos = None
            return
        if not self._timer_connected:
            self._timer.connect(self._update_loop)
            self._timer_connected = True
        self._timer.setActive(1)

    def _on_trigger_release(self, action, device):
        if self._dragging is None:
            return
        self._timer.setActive(0)
        wheel = self._dragging
        orig_pos_local = self._drag_orig_pos_local
        orig_rot = self._drag_orig_rot
        drag_dist = self._drag_distance_accum
        try:
            if self._drag_constraint:
                vrConstraintService.deleteConstraint(self._drag_constraint)
                self._drag_constraint = None
        except Exception:
            self._drag_constraint = None
        self._dragging = None
        self._ctrl_node = None
        self._drag_distance_accum = 0.0
        self._last_world_pos = None
        if wheel is None or wheel.isNull():
            return
        snapped = False
        try:
            wpos = getTransformNodeTranslation(wheel, 1)
            hub_node, hub_dist = _find_nearest_hub(wpos)
            if hub_node is not None:
                print("[WheelSwap] Nearest hub: %s  dist=%.1f mm  drag=%.1f mm" % (
                    hub_node.getName(), hub_dist, drag_dist))
            if (hub_node is not None and hub_dist < _SNAP_THRESHOLD and drag_dist >= _MIN_DRAG_DISTANCE):
                self._do_snap(wheel)
                snapped = True
        except Exception as e:
            print("[WheelSwap] Release snap check ERROR: " + str(e))
        if not snapped:
            try:
                _restore_node_transform(wheel, self._drag_orig_state)
                if self._drag_orig_state is None:
                    setTransformNodeTranslation(wheel, orig_pos_local.x(), orig_pos_local.y(), orig_pos_local.z(), 0)
                    setTransformNodeRotation(wheel, orig_rot.x(), orig_rot.y(), orig_rot.z())
                print("[WheelSwap] Restored: " + wheel.getName())
            except Exception as e:
                print("[WheelSwap] Restore ERROR: " + str(e))
        self._drag_orig_state = None

    def _update_loop(self):
        try:
            if self._dragging is None or self._ctrl_node is None:
                self._timer.setActive(0)
                return
            try:
                if self._dragging.isNull():
                    self._timer.setActive(0)
                    return
            except Exception:
                pass
            cur_pos = getTransformNodeTranslation(self._dragging, 1)
            if self._last_world_pos is not None:
                dx = cur_pos.x() - self._last_world_pos.x()
                dy = cur_pos.y() - self._last_world_pos.y()
                dz = cur_pos.z() - self._last_world_pos.z()
                self._drag_distance_accum += math.sqrt(dx*dx + dy*dy + dz*dz)
            self._last_world_pos = cur_pos
            self._debug_tick += 1
            if self._debug_tick % 30 == 0:
                hub_node, hub_dist = _find_nearest_hub(cur_pos)
                if hub_node is not None:
                    print("[WheelSwap] [drag] nearest %s dist=%.1f mm (drag=%.1f mm)" % (
                        hub_node.getName(), hub_dist, self._drag_distance_accum))
        except Exception as e:
            print("[WheelSwap] _update_loop ERROR: " + str(e))

    def _do_snap(self, wheel):
        print("[WheelSwap] Installing: " + wheel.getName())
        if self._installed_wheel is not None:
            try:
                prev = self._installed_wheel
                if not prev.isNull():
                    self._restore_initial_state(prev)
                    _set_node_visible(prev, True)
                    print("[WheelSwap] Restored prev: " + prev.getName())
            except Exception as e:
                print("[WheelSwap] Restore prev ERROR: " + str(e))
        state = _wheel_to_variant_state(wheel.getName())
        _switch_variant(state)
        try:
            self._restore_initial_state(wheel)
            print("[WheelSwap] Reset full transform: " + wheel.getName())
        except Exception as e:
            print("[WheelSwap] Reset position ERROR: " + str(e))
        try:
            _set_node_visible(wheel, False)
            print("[WheelSwap] Hidden: " + wheel.getName())
        except Exception as e:
            print("[WheelSwap] Hide ERROR: " + str(e))
        self._installed_wheel = wheel

    def enable(self):
        global vred_tool_registry
        try:
            for k, obj in list(vred_tool_registry.items()):
                if obj is not self and hasattr(obj, 'disable'):
                    try:
                        obj.disable()
                    except Exception:
                        pass
        except Exception:
            pass
        vred_tool_registry[self.registry_key] = self

        self._enable_tracker_binding()
        self._act_start.signal().triggered.connect(self._on_trigger_press)
        self._act_execute.signal().triggered.connect(self._on_trigger_release)

        wheel_found = [n for name in _WHEEL_NAMES for n in _scan_all_nodes_by_name(name)]
        hub_found = [n for name in _HUB_NAMES for n in _scan_all_nodes_by_name(name)]
        self._wheel_initial_states = {}
        for wheel in wheel_found:
            self._remember_initial_state(wheel)
        print("[WheelSwap] Enabled — wheels found: %d, hub zones found: %d" % (len(wheel_found), len(hub_found)))

    def disable(self):
        try:
            self._act_start.signal().triggered.disconnect(self._on_trigger_press)
        except Exception:
            pass
        try:
            self._act_execute.signal().triggered.disconnect(self._on_trigger_release)
        except Exception:
            pass
        try:
            self._timer.setActive(0)
        except Exception:
            pass
        try:
            if self._drag_constraint:
                vrConstraintService.deleteConstraint(self._drag_constraint)
                self._drag_constraint = None
        except Exception:
            pass
        self._disable_tracker_binding()
        try:
            if vred_tool_registry.get(self.registry_key) is self:
                del vred_tool_registry[self.registry_key]
        except Exception:
            pass
        print("[WheelSwap] Disabled")

# ------------------------------------------------------------------
# 全局注册表
# ------------------------------------------------------------------
global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

_wheel_swap_tool = WheelSwapTool()
_wheel_swap_tool.enable()
print("[WheelSwap] Initialized successfully")