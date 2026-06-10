# ======================================================================
# VRED Wheel Swap Tool (POC)
# 手柄射线选中轮胎，trigger 按住拖动，靠近 Wheel1_Position 自动吸附。
# 再次吸附新轮胎时，将前一个轮胎还原到原父节点和原变换。
# ======================================================================

import math

global _wheel_swap_tool
if '_wheel_swap_tool' not in globals():
    _wheel_swap_tool = None

# 每次注入先停止旧实例，确保代码更新生效
if '_wheel_swap_tool' in globals() and _wheel_swap_tool is not None:
    try:
        _wheel_swap_tool.disable()
    except Exception:
        pass
_wheel_swap_tool = None

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
_WHEEL_NAMES = ["Wheel1", "Wheel2", "Wheel3", "Wheel4"]
_SNAP_NODE_NAME = "Wheel1_Position"
_SNAP_THRESHOLD = 2000.0   # mm
_MIN_DRAG_DISTANCE = 250.0 # mm
_CAR_NODE_NAME = "Jahuar_project_7"
_CAR_RELEASE_THRESHOLD = 3500.0  # mm, 用整车中心做释放范围判定

# ------------------------------------------------------------------
# 工具函数：用 getAllNodes() 扫描，不调用 findNode
# ------------------------------------------------------------------
def _scan_node_by_name(name):
    try:
        for n in getAllNodes():
            try:
                if n.getName() == name:
                    return n
            except Exception:
                pass
    except Exception:
        pass
    return None

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

def _distance_xyz(p0, p1):
    dx = p0.x() - p1.x()
    dy = p0.y() - p1.y()
    dz = p0.z() - p1.z()
    return math.sqrt(dx * dx + dy * dy + dz * dz)

def _node_path_contains(node, token):
    try:
        p = getUniquePath(node)
        return token in p
    except Exception:
        return False

def _choose_nearest_snap_node(pos, prefer_path_token=None):
    candidates = _scan_all_nodes_by_name(_SNAP_NODE_NAME)
    if len(candidates) == 0:
        return None, None

    if prefer_path_token:
        preferred = []
        for cand in candidates:
            if _node_path_contains(cand, prefer_path_token):
                preferred.append(cand)
        if len(preferred) > 0:
            candidates = preferred

    best = None
    best_dist = None
    for cand in candidates:
        try:
            cand_pos = getTransformNodeTranslation(cand, 1)
            d = _distance_xyz(pos, cand_pos)
            if best is None or d < best_dist:
                best = cand
                best_dist = d
        except Exception:
            continue
    return best, best_dist

def _log_node_transform_and_pivot(node, tag):
    if node is None:
        print("[WheelSwap][%s] node is None" % tag)
        return
    try:
        if node.isNull():
            print("[WheelSwap][%s] node is null" % tag)
            return
    except Exception:
        pass

    try:
        name = node.getName()
    except Exception:
        name = "<unknown>"

    try:
        parent_name = node.getParent().getName()
    except Exception:
        parent_name = "<unknown>"

    try:
        path = getUniquePath(node)
    except Exception:
        path = "<unknown>"

    try:
        lp = getTransformNodeTranslation(node, 0)
        wp = getTransformNodeTranslation(node, 1)
        lr = getTransformNodeRotation(node)
        ls = getTransformNodeScale(node)
        print("[WheelSwap][%s] %s parent=%s path=%s" % (tag, name, parent_name, path))
        print("[WheelSwap][%s] local T=(%.3f, %.3f, %.3f) R=(%.3f, %.3f, %.3f) S=(%.3f, %.3f, %.3f)" % (
            tag, lp.x(), lp.y(), lp.z(), lr.x(), lr.y(), lr.z(), ls.x(), ls.y(), ls.z()))
        print("[WheelSwap][%s] world T=(%.3f, %.3f, %.3f)" % (tag, wp.x(), wp.y(), wp.z()))
    except Exception as e:
        print("[WheelSwap][%s] transform read ERROR: %s" % (tag, str(e)))

    # Pivot 在不同 VRED 版本 API 不一致，这里做多路尝试。
    pivot_printed = False
    try:
        pv = getTransformNodePivot(node)
        print("[WheelSwap][%s] pivot=(%.3f, %.3f, %.3f) [getTransformNodePivot]" % (tag, pv.x(), pv.y(), pv.z()))
        pivot_printed = True
    except Exception:
        pass

    if not pivot_printed:
        try:
            pv = getTransformNodePivot(node, 0)
            print("[WheelSwap][%s] pivot=(%.3f, %.3f, %.3f) [getTransformNodePivot local]" % (tag, pv.x(), pv.y(), pv.z()))
            pivot_printed = True
        except Exception:
            pass

    if not pivot_printed:
        try:
            f = node.fields()
            for key in ["pivot", "rotatePivot", "rotationPivot", "scalePivot"]:
                try:
                    v = f.getVec3f(key)
                    print("[WheelSwap][%s] %s=(%.3f, %.3f, %.3f) [fields]" % (tag, key, v.x(), v.y(), v.z()))
                    pivot_printed = True
                except Exception:
                    continue
        except Exception:
            pass

    if not pivot_printed:
        print("[WheelSwap][%s] pivot=<unavailable in this VRED API>" % tag)

# ------------------------------------------------------------------
# 工具类
# ------------------------------------------------------------------
class WheelSwapTool:
    def __init__(self):
        self._dragging      = None
        self._ctrl_node     = None
        self._drag_offset   = None   # (ox, oy, oz) wheel_world - ctrl_world
        self._drag_constraint = None

        # 保存两份原始变换：world用于drag偏移计算，local用于还原位置
        self._drag_orig_pos       = None   # world QVector3D
        self._drag_orig_pos_local = None   # local QVector3D  <-- 还原用
        self._drag_orig_rot       = None   # local rotation
        self._drag_orig_parent    = None
        self._drag_distance_accum = 0.0
        self._last_world_pos      = None

        # 上一个已吸附轮胎的信息（全部用local坐标还原）
        self._snapped_node           = None
        self._snapped_orig_pos_local = None
        self._snapped_orig_rot       = None
        self._snapped_orig_parent    = None

        self._snap_node = None   # 缓存 snap 目标节点
        self._car_node = None

        # 交互组 —— 若已存在则复用
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

        self._timer = vrTimer()
        self._timer_connected = False
        self._debug_tick = 0

        self.registry_key = "tool_wheel_swap"

    # ------------------------------------------------------------------
    def _find_wheel_ancestor(self, node):
        cur = node
        while not cur.isNull():
            if cur.getName() in _WHEEL_NAMES:
                return cur
            cur = cur.getParent()
        return None

    # ------------------------------------------------------------------
    def _on_trigger_press(self, action, device):
        if self._dragging is not None:
            print("[WheelSwap] Already dragging, ignore duplicate press")
            return

        picked = device.pick().getNode()
        if picked.isNull():
            print("[WheelSwap] trigger pressed but no node picked")
            return
        print("[WheelSwap] Picked node: " + picked.getName())
        wheel = self._find_wheel_ancestor(picked)
        if wheel is None or wheel.isNull():
            print("[WheelSwap] Not a wheel node, ignoring")
            return

        if wheel.getName() == "Wheel1":
            _log_node_transform_and_pivot(wheel, "before_drag")

        self._dragging  = wheel
        self._ctrl_node = device.getNode()

        wpos = getTransformNodeTranslation(wheel, 1)

        self._drag_orig_pos       = wpos
        self._drag_orig_pos_local = getTransformNodeTranslation(wheel, 0)  # 局部坐标，还原用
        self._drag_orig_rot       = getTransformNodeRotation(wheel)
        self._drag_orig_parent    = wheel.getParent()
        self._drag_distance_accum = 0.0
        self._last_world_pos      = wpos

        # 用约束驱动拖动，避免 timer 手动更新导致“按住不动”问题
        try:
            self._drag_constraint = vrConstraintService.createParentConstraint([
                self._ctrl_node
            ], wheel, True)
        except Exception as e:
            self._drag_constraint = None
            print("[WheelSwap] createParentConstraint ERROR: " + str(e))

        if self._drag_constraint is None:
            self._dragging = None
            self._ctrl_node = None
            self._drag_distance_accum = 0.0
            self._last_world_pos = None
            return

        # 不在按下时固定目标；吸附目标在松手时按当前位置选择最近候选。
        self._snap_node = None
        cands = _scan_all_nodes_by_name(_SNAP_NODE_NAME)
        print("[WheelSwap] Snap candidates found: %d" % len(cands))

        if not self._timer_connected:
            self._timer.connect(self._update_loop)
            self._timer_connected = True
        self._timer.setActive(1)
        print("[WheelSwap] Dragging: " + wheel.getName())

    # ------------------------------------------------------------------
    def _on_trigger_release(self, action, device):
        if self._dragging is None:
            return

        self._timer.setActive(0)

        node           = self._dragging
        orig_pos_local = self._drag_orig_pos_local
        orig_rot       = self._drag_orig_rot
        orig_parent    = self._drag_orig_parent
        drag_dist      = self._drag_distance_accum

        # 先释放拖动约束，再做吸附/还原判断
        try:
            if self._drag_constraint:
                vrConstraintService.deleteConstraint(self._drag_constraint)
                self._drag_constraint = None
        except Exception:
            self._drag_constraint = None

        self._dragging    = None
        self._ctrl_node   = None
        self._drag_offset = None
        self._drag_distance_accum = 0.0
        self._last_world_pos = None

        # 松手时按当前位置选择最近 snap 候选并检查距离
        snap_node = None
        snap_dist = None
        try:
            if node and not node.isNull() and node.getName() == "Wheel1":
                _log_node_transform_and_pivot(node, "after_drag_before_finalize")
        except Exception:
            pass

        if node and not node.isNull():
            try:
                wpos     = getTransformNodeTranslation(node, 1)

                # 先用整车节点判断“释放位置是否在整车附近”
                car_node = self._car_node
                if car_node is None:
                    car_node = _scan_node_by_name(_CAR_NODE_NAME)
                    self._car_node = car_node
                if car_node is not None:
                    car_pos = getTransformNodeTranslation(car_node, 1)
                    car_dist = _distance_xyz(wpos, car_pos)
                    print("[WheelSwap] Release dist to %s: %.1f mm" % (_CAR_NODE_NAME, car_dist))
                    if car_dist > _CAR_RELEASE_THRESHOLD:
                        print("[WheelSwap] Release outside car range, no snap")
                        raise Exception("outside car range")

                snap_node, snap_dist = _choose_nearest_snap_node(wpos, _CAR_NODE_NAME)
                if snap_node is None:
                    print("[WheelSwap] Release: no snap candidates")
                else:
                    print("[WheelSwap] Release nearest %s dist: %.1f mm (drag=%.1f)" % (
                        _SNAP_NODE_NAME, snap_dist, drag_dist))
                if snap_node is not None and snap_dist < _SNAP_THRESHOLD and drag_dist >= _MIN_DRAG_DISTANCE:
                    self._do_snap(node, snap_node, orig_pos_local, orig_rot, orig_parent)
                    try:
                        if node.getName() == "Wheel1":
                            _log_node_transform_and_pivot(node, "after_snap")
                    except Exception:
                        pass
                    return
            except Exception as e:
                print("[WheelSwap] Release snap check ERROR: " + str(e))

        # 未吸附：用局部坐标还原到原位
        if node and not node.isNull():
            setTransformNodeTranslation(node, orig_pos_local.x(), orig_pos_local.y(), orig_pos_local.z(), 0)
            setTransformNodeRotation(node, orig_rot.x(), orig_rot.y(), orig_rot.z())
            try:
                if node.getName() == "Wheel1":
                    _log_node_transform_and_pivot(node, "after_restore")
            except Exception:
                pass
        print("[WheelSwap] Released without snap, restored position")

    # ------------------------------------------------------------------
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

            # 约束驱动位置；这里仅统计累计拖动距离用于防误吸附门槛
            cur_pos = getTransformNodeTranslation(self._dragging, 1)
            if self._last_world_pos is not None:
                frame_dx = cur_pos.x() - self._last_world_pos.x()
                frame_dy = cur_pos.y() - self._last_world_pos.y()
                frame_dz = cur_pos.z() - self._last_world_pos.z()
                self._drag_distance_accum += math.sqrt(frame_dx * frame_dx + frame_dy * frame_dy + frame_dz * frame_dz)
            self._last_world_pos = cur_pos

            # 调试：显示当前位置到最近 snap 候选的距离
            snap_node, dist = _choose_nearest_snap_node(cur_pos, _CAR_NODE_NAME)
            if snap_node is None:
                return

            self._debug_tick += 1
            if self._debug_tick % 30 == 0:
                print("[WheelSwap] nearest %s dist: %.1f mm (threshold=%.1f, drag=%.1f, min_drag=%.1f)" % (
                    _SNAP_NODE_NAME, dist, _SNAP_THRESHOLD, self._drag_distance_accum, _MIN_DRAG_DISTANCE))

            # 不在拖动过程中吸附，吸附统一在 trigger 松开时判断执行。

        except Exception as e:
            print("[WheelSwap] _update_loop ERROR: " + str(e))

    # ------------------------------------------------------------------
    def _do_snap(self, wheel, snap_node, orig_pos_local, orig_rot, orig_parent):
        print("[WheelSwap] _do_snap: %s -> %s" % (wheel.getName(), snap_node.getName()))

        # 1. 还原上一个吸附的轮胎（用局部坐标，精确还原到原父节点下的原位置）
        if self._snapped_node is not None:
            try:
                prev           = self._snapped_node
                prev_pos_local = self._snapped_orig_pos_local
                prev_rot       = self._snapped_orig_rot
                prev_parent    = self._snapped_orig_parent
                moveNode(prev, prev.getParent(), prev_parent)
                setTransformNodeTranslation(prev,
                    prev_pos_local.x(), prev_pos_local.y(), prev_pos_local.z(), 0)
                setTransformNodeRotation(prev, prev_rot.x(), prev_rot.y(), prev_rot.z())
                print("[WheelSwap] Restored prev: " + prev.getName())
            except Exception as e:
                print("[WheelSwap] ERROR restoring prev: " + str(e))

        # 2. 记录新吸附信息（保存局部坐标）
        self._snapped_node           = wheel
        self._snapped_orig_pos_local = orig_pos_local
        self._snapped_orig_rot       = orig_rot
        self._snapped_orig_parent    = orig_parent

        # 3. 将轮胎挂到 snap_node 下
        try:
            cur_parent = wheel.getParent()
            moveNode(wheel, cur_parent, snap_node)
            print("[WheelSwap] moveNode OK")
        except Exception as e:
            print("[WheelSwap] moveNode ERROR: " + str(e))
            try:
                vrNodeService.moveNode(wheel, snap_node)
                print("[WheelSwap] vrNodeService.moveNode OK")
            except Exception as e2:
                print("[WheelSwap] vrNodeService.moveNode ERROR: " + str(e2))

        # 4. 清零本地变换（归位到 Wheel1_Position 原点）
        try:
            setTransformNodeTranslation(wheel, 0, 0, 0, 0)
            setTransformNodeRotation(wheel, 0, 0, 0)
            print("[WheelSwap] Snapped OK: %s -> %s" % (wheel.getName(), _SNAP_NODE_NAME))
        except Exception as e:
            print("[WheelSwap] ERROR zeroing transform: " + str(e))

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

        candidates = _scan_all_nodes_by_name(_SNAP_NODE_NAME)
        self._snap_node = None
        self._car_node = _scan_node_by_name(_CAR_NODE_NAME)
        if len(candidates) > 0:
            print("[WheelSwap] Snap node candidates found: %d" % len(candidates))
        else:
            print("[WheelSwap] WARNING: snap node '%s' not found at enable time!" % _SNAP_NODE_NAME)
        if self._car_node is not None:
            print("[WheelSwap] Car node found: " + self._car_node.getName())
        else:
            print("[WheelSwap] WARNING: car node '%s' not found" % _CAR_NODE_NAME)

        vrDeviceService.setActiveInteractionGroup("WheelSwapGroup")
        self._act_start.signal().triggered.connect(self._on_trigger_press)
        self._act_execute.signal().triggered.connect(self._on_trigger_release)
        print("[WheelSwap] Enabled")

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
            self._drag_constraint = None
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
