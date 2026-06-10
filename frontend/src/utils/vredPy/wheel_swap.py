# ======================================================================
# VRED 轮胎替换工具
# 手柄 trigger 抓取 WheelRack 上的轮胎（Wheel_1~Wheel_4），拖动至
# Hub 安装区（FL/FR/BL/BR），松手后：
#   1. 切换 VariantSet 6_Hub_Switch → 对应 Wheel1~Wheel4 状态
#   2. 隐藏拖动的轮胎节点
# 再次安装时，自动还原上一个已安装轮胎的可见性。
# ======================================================================

import math

# ------------------------------------------------------------------
# 防重复注入
# ------------------------------------------------------------------
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
_VARIANT_SET    = "Switch1"   # node variant 名称（位于 6_Hub_Switch group 下）

_SNAP_THRESHOLD    = 2600.0   # mm — 松手时距最近 Hub 节点的最大距离
_MIN_DRAG_DISTANCE = 250.0    # mm — 防误触：累计移动距离需超过此值才触发安装

# tracker 自动绑定配置
_TRACKER_NAME          = "tracker-1"
_TRACKER_BIND_NODE     = "Jahuar_project_7"
_TRACKER_MAINTAIN_OFFSET = False

# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _scan_all_nodes_by_name(name):
    """遍历全部场景节点，返回名称匹配 name 的列表。"""
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
    """返回第一个名称匹配 name 的节点，未找到返回 None。"""
    nodes = _scan_all_nodes_by_name(name)
    return nodes[0] if nodes else None

def _distance_xyz(p0, p1):
    dx = p0.x() - p1.x()
    dy = p0.y() - p1.y()
    dz = p0.z() - p1.z()
    return math.sqrt(dx * dx + dy * dy + dz * dz)

def _find_nearest_hub(world_pos):
    """
    扫描 _HUB_NAMES 中所有节点，返回距 world_pos 最近的 (node, dist)。
    未找到任何候选时返回 (None, None)。
    """
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
    """
    将 WheelRack 节点名映射到 VariantSet 状态名。
    Wheel_1 → Wheel1, Wheel_2 → Wheel2, ...
    """
    return wheel_name.replace("_", "")

def _node_key(node):
    """为节点生成稳定 key，优先使用唯一路径。"""
    try:
        return getUniquePath(node)
    except Exception:
        return node.getName()

def _capture_node_transform(node):
    """抓取节点完整变换状态（含 pivot 信息）。"""
    state = {
        "translation": None,
        "rotation": None,
        "scale": None,
        "rotate_pivot": None,
        "scale_pivot": None,
        "rotate_pivot_translation": None,
        "scale_pivot_translation": None,
    }
    try:
        state["translation"] = getTransformNodeTranslation(node, 0)
    except Exception:
        pass
    try:
        state["rotation"] = getTransformNodeRotation(node)
    except Exception:
        pass
    try:
        state["scale"] = getTransformNodeScale(node)
    except Exception:
        pass
    try:
        state["rotate_pivot"] = getTransformNodeRotatePivot(node, 0)
    except Exception:
        pass
    try:
        state["scale_pivot"] = getTransformNodeScalePivot(node, 0)
    except Exception:
        pass
    try:
        state["rotate_pivot_translation"] = getTransformNodeRotatePivotTranslation(node)
    except Exception:
        pass
    try:
        state["scale_pivot_translation"] = getTransformNodeScalePivotTranslation(node)
    except Exception:
        pass
    return state

def _restore_node_transform(node, state):
    """恢复节点完整变换状态（含 pivot 信息）。"""
    if not state:
        return

    t = state.get("translation")
    if t is not None:
        try:
            setTransformNodeTranslation(node, t.x(), t.y(), t.z(), 0)
        except Exception:
            pass

    r = state.get("rotation")
    if r is not None:
        try:
            setTransformNodeRotation(node, r.x(), r.y(), r.z())
        except Exception:
            pass

    s = state.get("scale")
    if s is not None:
        try:
            setTransformNodeScale(node, s.x(), s.y(), s.z())
        except Exception:
            pass

    rp = state.get("rotate_pivot")
    if rp is not None:
        try:
            setTransformNodeRotatePivot(node, rp.x(), rp.y(), rp.z(), 0)
        except Exception:
            pass

    sp = state.get("scale_pivot")
    if sp is not None:
        try:
            setTransformNodeScalePivot(node, sp.x(), sp.y(), sp.z(), 0)
        except Exception:
            pass

    rpt = state.get("rotate_pivot_translation")
    if rpt is not None:
        try:
            setTransformNodeRotatePivotTranslation(node, rpt.x(), rpt.y(), rpt.z())
        except Exception:
            pass

    spt = state.get("scale_pivot_translation")
    if spt is not None:
        try:
            setTransformNodeScalePivotTranslation(node, spt.x(), spt.y(), spt.z())
        except Exception:
            pass

def _switch_variant(state_name):
    """
    切换 6_Hub_Switch VariantSet 到指定状态。
    先尝试 v1 API selectNodeVariant；若不可用则尝试 vrVariantSets 对象 API。
    """
    try:
        selectNodeVariant(_VARIANT_SET, state_name)
        print("[WheelSwap] selectNodeVariant('%s', '%s') OK" % (_VARIANT_SET, state_name))
        return
    except Exception as e:
        print("[WheelSwap] selectNodeVariant ERROR: %s — trying fallback" % str(e))
    try:
        vs = vrVariantSets.getVariantSet(_VARIANT_SET)
        vs.loadVariant(state_name)
        print("[WheelSwap] vrVariantSets.loadVariant('%s') OK" % state_name)
    except Exception as e2:
        print("[WheelSwap] vrVariantSets fallback ERROR: %s" % str(e2))

def _set_node_visible(node, visible):
    """
    显示或隐藏节点。vrdTransformNode 没有 setActive()，
    使用 VRED v1 全局函数 setNodeActive()。
    """
    flag = 1 if visible else 0
    # 方法1：v1 全局函数
    try:
        setNodeActive(node, flag)
        return
    except Exception:
        pass
    # 方法2：字段直接写
    try:
        node.fields().setBool("active", visible)
        return
    except Exception:
        pass
    # 方法3：hideNode / showNode
    try:
        if visible:
            showNode(node)
        else:
            hideNode(node)
        return
    except Exception as e:
        print("[WheelSwap] _set_node_visible ERROR: %s" % str(e))


def _get_vr_device(name):
    try:
        dev = vrDeviceService.getVRDevice(name)
        if dev:
            return dev
    except Exception:
        pass
    return None


def _bind_tracker_to_node(tracker_name, node_name, maintain_offset=True):
    tracker = _get_vr_device(tracker_name)
    if tracker is None:
        print("[WheelSwap] tracker device not found: %s" % tracker_name)
        return None

    node = _scan_node_by_name(node_name)
    if node is None:
        print("[WheelSwap] bind node not found: %s" % node_name)
        return None

    try:
        constraint = vrConstraintService.createParentConstraint(
            [tracker.getNode()], node, maintain_offset)
        print("[WheelSwap] tracker bound: %s -> %s (maintain_offset=%s)" % (
            tracker_name, node_name, maintain_offset))
        return constraint
    except Exception as e:
        print("[WheelSwap] createParentConstraint for tracker ERROR: %s" % str(e))
        return None

# ------------------------------------------------------------------
# 工具类
# ------------------------------------------------------------------
class WheelSwapTool:
    def __init__(self):
        # 拖动状态
        self._dragging            = None   # 当前拖动的轮胎节点
        self._ctrl_node           = None
        self._drag_constraint     = None
        self._tracker_constraint  = None
        self._drag_orig_pos_local = None   # local 坐标，用于还原
        self._drag_orig_rot       = None
        self._drag_orig_state     = None   # 完整变换快照（含 pivot）
        self._drag_orig_parent    = None
        self._drag_distance_accum = 0.0
        self._last_world_pos      = None

        # 已安装轮胎（用于下次安装时还原可见性）
        self._installed_wheel     = None

        # 轮胎初始状态：用于每次安装后精确还原到 WheelRack 初始姿态
        self._wheel_initial_states = {}

        # 交互组 — 若已存在则复用
        _ig = "WheelSwapGroup"
        try:
            self._interaction = vrDeviceService.getInteraction("WheelSwapInteraction")
            if self._interaction is None or not hasattr(self._interaction, 'setSupportedInteractionGroups'):
                raise Exception("not found")
        except Exception:
            self._interaction = vrDeviceService.createInteraction("WheelSwapInteraction")
        self._interaction.setSupportedInteractionGroups([_ig])

        try:
            vrDeviceService.getInteraction("Teleport").addSupportedInteractionGroup(_ig)
        except Exception:
            pass

        self._pointer = vrDeviceService.getInteraction("Pointer")
        try:
            self._pointer.addSupportedInteractionGroup(_ig)
        except Exception:
            pass

        self._act_start   = self._pointer.getControllerAction("start")
        self._act_execute = self._pointer.getControllerAction("execute")

        self._timer           = vrTimer()
        self._timer_connected = False
        self._debug_tick      = 0

        self.registry_key = "tool_wheel_swap"

    # ------------------------------------------------------------------
    def _find_wheel_ancestor(self, node):
        """向上遍历，找到名称在 _WHEEL_NAMES 中的祖先节点。"""
        cur = node
        while not cur.isNull():
            if cur.getName() in _WHEEL_NAMES:
                return cur
            cur = cur.getParent()
        return None

    def _remember_initial_state(self, wheel):
        """首次遇到某个轮胎时记录其初始完整变换。"""
        key = _node_key(wheel)
        if key not in self._wheel_initial_states:
            self._wheel_initial_states[key] = _capture_node_transform(wheel)

    def _restore_initial_state(self, wheel):
        """将轮胎恢复为启动时记录的初始完整变换。"""
        key = _node_key(wheel)
        state = self._wheel_initial_states.get(key)
        if state is not None:
            _restore_node_transform(wheel, state)

    def _enable_tracker_binding(self):
        if self._tracker_constraint is not None:
            return
        self._tracker_constraint = _bind_tracker_to_node(
            _TRACKER_NAME, _TRACKER_BIND_NODE, _TRACKER_MAINTAIN_OFFSET)

    def _disable_tracker_binding(self):
        if self._tracker_constraint is None:
            return
        try:
            vrConstraintService.deleteConstraint(self._tracker_constraint)
        except Exception:
            pass
        self._tracker_constraint = None

    # ------------------------------------------------------------------
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

        self._dragging            = wheel
        self._ctrl_node           = device.getNode()
        self._drag_orig_pos_local = getTransformNodeTranslation(wheel, 0)
        self._drag_orig_rot       = getTransformNodeRotation(wheel)
        self._drag_orig_state     = _capture_node_transform(wheel)
        self._drag_orig_parent    = wheel.getParent()
        self._drag_distance_accum = 0.0
        self._last_world_pos      = getTransformNodeTranslation(wheel, 1)

        try:
            self._drag_constraint = vrConstraintService.createParentConstraint(
                [self._ctrl_node], wheel, True)
        except Exception as e:
            print("[WheelSwap] createParentConstraint ERROR: " + str(e))
            self._drag_constraint = None
            self._dragging    = None
            self._ctrl_node   = None
            self._last_world_pos = None
            return

        if not self._timer_connected:
            self._timer.connect(self._update_loop)
            self._timer_connected = True
        self._timer.setActive(1)

    # ------------------------------------------------------------------
    def _on_trigger_release(self, action, device):
        if self._dragging is None:
            return

        self._timer.setActive(0)

        wheel          = self._dragging
        orig_pos_local = self._drag_orig_pos_local
        orig_rot       = self._drag_orig_rot
        drag_dist      = self._drag_distance_accum

        # 释放拖动约束
        try:
            if self._drag_constraint:
                vrConstraintService.deleteConstraint(self._drag_constraint)
                self._drag_constraint = None
        except Exception:
            self._drag_constraint = None

        self._dragging            = None
        self._ctrl_node           = None
        self._drag_distance_accum = 0.0
        self._last_world_pos      = None

        if wheel is None or wheel.isNull():
            return

        # 检查是否靠近安装区
        snapped = False
        try:
            wpos      = getTransformNodeTranslation(wheel, 1)
            hub_node, hub_dist = _find_nearest_hub(wpos)

            if hub_node is not None:
                print("[WheelSwap] Nearest hub: %s  dist=%.1f mm  drag=%.1f mm" % (
                    hub_node.getName(), hub_dist, drag_dist))

            if (hub_node is not None
                    and hub_dist < _SNAP_THRESHOLD
                    and drag_dist >= _MIN_DRAG_DISTANCE):
                self._do_snap(wheel)
                snapped = True
        except Exception as e:
            print("[WheelSwap] Release snap check ERROR: " + str(e))

        # 未安装 → 还原到原始局部坐标
        if not snapped:
            try:
                _restore_node_transform(wheel, self._drag_orig_state)
                if self._drag_orig_state is None:
                    setTransformNodeTranslation(
                        wheel,
                        orig_pos_local.x(), orig_pos_local.y(), orig_pos_local.z(), 0)
                    setTransformNodeRotation(
                        wheel, orig_rot.x(), orig_rot.y(), orig_rot.z())
                print("[WheelSwap] Restored: " + wheel.getName())
            except Exception as e:
                print("[WheelSwap] Restore ERROR: " + str(e))

        self._drag_orig_state = None

    # ------------------------------------------------------------------
    def _update_loop(self):
        """Timer 回调：统计累计拖动距离，用于防误触阈值判断。"""
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

            # 调试：每 30 帧打印一次最近 Hub 距离
            self._debug_tick += 1
            if self._debug_tick % 30 == 0:
                hub_node, hub_dist = _find_nearest_hub(cur_pos)
                if hub_node is not None:
                    print("[WheelSwap] [drag] nearest %s dist=%.1f mm (drag=%.1f mm)" % (
                        hub_node.getName(), hub_dist, self._drag_distance_accum))

        except Exception as e:
            print("[WheelSwap] _update_loop ERROR: " + str(e))

    # ------------------------------------------------------------------
    def _do_snap(self, wheel):
        print("[WheelSwap] Installing: " + wheel.getName())

        # 1. 还原上一个已安装轮胎的可见性
        if self._installed_wheel is not None:
            try:
                prev = self._installed_wheel
                if not prev.isNull():
                    self._restore_initial_state(prev)
                    _set_node_visible(prev, True)
                    print("[WheelSwap] Restored prev: " + prev.getName())
            except Exception as e:
                print("[WheelSwap] Restore prev ERROR: " + str(e))

        # 2. 切换 VariantSet
        state = _wheel_to_variant_state(wheel.getName())
        _switch_variant(state)

        # 3. 重要！将当前轮胎完整变换（含 pivot）重置回 WheelRack 初始状态
        try:
            self._restore_initial_state(wheel)
            print("[WheelSwap] Reset full transform: " + wheel.getName())
        except Exception as e:
            print("[WheelSwap] Reset position ERROR: " + str(e))

        # 4. 隐藏当前轮胎
        try:
            _set_node_visible(wheel, False)
            print("[WheelSwap] Hidden: " + wheel.getName())
        except Exception as e:
            print("[WheelSwap] Hide ERROR: " + str(e))

        self._installed_wheel = wheel
    # ------------------------------------------------------------------
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

        vrDeviceService.setActiveInteractionGroup("WheelSwapGroup")
        self._enable_tracker_binding()
        self._act_start.signal().triggered.connect(self._on_trigger_press)
        self._act_execute.signal().triggered.connect(self._on_trigger_release)

        # 启动时扫描节点，打印诊断信息
        wheel_found = [n for name in _WHEEL_NAMES for n in _scan_all_nodes_by_name(name)]
        hub_found   = [n for name in _HUB_NAMES   for n in _scan_all_nodes_by_name(name)]

        # 记录每个轮胎的初始完整变换，用于后续精确还原
        self._wheel_initial_states = {}
        for wheel in wheel_found:
            self._remember_initial_state(wheel)

        print("[WheelSwap] Enabled — wheels found: %d, hub zones found: %d" % (
            len(wheel_found), len(hub_found)))

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
# 全局注册表（与 all_tools.py 兼容）
# ------------------------------------------------------------------
global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

_wheel_swap_tool = WheelSwapTool()
_wheel_swap_tool.enable()
print("[WheelSwap] Initialized successfully")
