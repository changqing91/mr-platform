# ======================================================================
# VRED MR Tools - Unified Script
# 一次注入所有工具，通过 switch_tool(name) 切换当前生效的工具
# 可用工具: adjust, draw_note, section, turntable, measure, voice_note, flashlight
# 全局默认: 左手柄 grip 按住移动 = 牵引漫游（拖拽世界，始终生效）
# ======================================================================

import os
import math
import random
import datetime
import tempfile
from PySide6 import QtCore, QtMultimedia, QtGui

# --- 防止重复初始化 ---
global _all_tools_initialized
if '_all_tools_initialized' in globals() and _all_tools_initialized:
    print("[AllTools] Already initialized, skipping re-init")
else:
    _all_tools_initialized = False

    # --- 运行时检测 ---
    _pad_input = 'touchpad'
    _grip_input = 'grip'
    try:
        _xr = getattr(vrImmersiveInteractionService, 'getOpenXRRuntime', None)
        if _xr and _xr():
            _pad_input = 'thumbstick'
            _grip_input = 'squeeze'
    except Exception:
        pass

    # --- 全局工具注册表 ---
    global vred_tool_registry
    if 'vred_tool_registry' not in globals():
        vred_tool_registry = {}

    # ======================================================================
    # 模块级资源加载
    # ======================================================================

    _MMR_OSB_PATH = r"\\192.168.7.80\upload\VRED\MMR_Stuff.osb"

    _mmrLoaded = False
    try:
        for node in getAllNodes():
            if node.getName() == "MRcontrollerRight":
                _mmrLoaded = True
                break
    except Exception:
        pass

    if not _mmrLoaded:
        loadGeometry(_MMR_OSB_PATH)
        findNode("MRcontrollerLeft").setActive(0)
        findNode("MRcontrollerRight").setActive(0)

    adjustControllerFound = True
    notesControllerFound = True
    clippingControllerFound = True
    rotationControllerFound = True

    # 左手控制器约束
    _mrLeft = findNode("MRcontrollerLeft")
    _leftCtrl = vrDeviceService.getVRDevice("left-controller")
    _mrLeft.setActive(1)
    vrConstraintService.createParentConstraint([_leftCtrl.getNode()], _mrLeft, False)

    # Notes 节点引用
    try:
        _tagIconSwitch = findNode("TagIconSwitch")
        refObject = _tagIconSwitch.getChild(0) if _tagIconSwitch else None
    except Exception:
        refObject = None

    try:
        Cloned_ref_obj = findNode("Cloned_ref_obj")
        moveNode(Cloned_ref_obj, Cloned_ref_obj.getParent(), getRootNode())
    except Exception:
        Cloned_ref_obj = createNode('Group', 'Cloned_ref_obj', getRootNode())

    # ======================================================================
    # 工具类定义
    # ======================================================================

    # ------------------------------------------------------------------
    # GripFlyMixin - Grip 飞行模式公共 Mixin
    # ------------------------------------------------------------------
    class GripFlyMixin:
        """
        右手 Grip 飞行模式公共 Mixin。
        子类 __init__ 中调用 self._fly_init()；
        enable() 中调用 self._fly_enable()；
        disable() 中调用 self._fly_disable()；
        每帧 timer 回调中调用 self._fly_tick()。
        """

        def _fly_init(self):
            """初始化飞行模式状态。在子类 __init__ 中调用。"""
            self._flyHeld = False
            self._flyBasePos = None
            self._flyVelX = 0.0
            self._flyVelY = 0.0
            self._flyVelZ = 0.0
            self.flySpeed = 0.35
            self._flyAccel = 0.015
            self._flyAlpha = 0.3
            self._flyDeadZone = 20.0
            self._flyMaxStep = 45.0
            self._gripHeld = False
            self._GRIP_THRESHOLD = 0.5
            self._gripTimer = vrTimer()
            self._gripTimerConnected = False

        def _fly_enable(self):
            """启动 grip 轮询 timer。在子类 enable() 中调用。"""
            if not self._gripTimerConnected:
                self._gripTimer.connect(self._poll_grip)
                self._gripTimerConnected = True
            self._gripTimer.setActive(1)

        def _fly_disable(self):
            """重置飞行状态并停止 grip timer。在子类 disable() 中调用。"""
            self._flyHeld = False
            self._flyBasePos = None
            self._gripHeld = False
            try:
                self._gripTimer.setActive(0)
            except Exception:
                pass

        def on_grip_pressed(self, action=None, device=None):
            self._flyHeld = True
            try:
                mat = self.rightController.getTrackingMatrix()
                col = mat.column(3)
                self._flyBasePos = (col.x(), col.y(), col.z())
            except Exception as e:
                print("[GripFly][PRESS] ERROR: " + str(e))
                self._flyBasePos = None

        def on_grip_released(self, action=None, device=None):
            self._flyHeld = False
            self._flyBasePos = None
            self._flyVelX = 0.0
            self._flyVelY = 0.0
            self._flyVelZ = 0.0

        def _poll_grip(self):
            try:
                state = self.rightController.getButtonState("grip")
                pressed = state.isPressed() or state.getPosition().x() >= self._GRIP_THRESHOLD
                if pressed and not self._gripHeld:
                    self._gripHeld = True
                    self.on_grip_pressed()
                elif not pressed and self._gripHeld:
                    self._gripHeld = False
                    self.on_grip_released()
            except Exception:
                pass

        def _fly_tick(self):
            """每帧飞行逻辑，在 timer 回调中调用。"""
            if not (self._flyHeld and self._flyBasePos is not None):
                return
            try:
                mat = self.rightController.getTrackingMatrix()
                col = mat.column(3)
                cx, cy, cz = col.x(), col.y(), col.z()
                dx = cx - self._flyBasePos[0]
                dy = cy - self._flyBasePos[1]
                dz = cz - self._flyBasePos[2]
                dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                if dist > self._flyDeadZone:
                    d = dist - self._flyDeadZone
                    speed = self.flySpeed + d * self._flyAccel + d * d * 0.0006
                    speed = min(speed, self._flyMaxStep)
                    nx, ny, nz = dx / dist, dy / dist, dz / dist
                    origin = vrDeviceService.getTrackingOrigin()
                    new_o = QVector3D(
                        origin.x() - nx * speed,
                        origin.y() - ny * speed,
                        origin.z() - nz * speed
                    )
                    vrDeviceService.setTrackingOrigin(new_o)
            except Exception as e:
                print("[GripFly] ERROR: " + str(e))

    # ------------------------------------------------------------------
    # AdjustTool - 地平面移动工具
    # ------------------------------------------------------------------
    class AdjustTool(GripFlyMixin):
        """
        地平面移动工具 (XY 为地平面, Z 为上下)
        - 右手trigger 按住 + 移动控制器: 物体跟随控制器在地平面上移动
        - 右手grip按住触发飞行模式，摄像机朝手柄移动方向移动，松开后停止飞行模式
        """
        def __init__(self):
            self.isEnabled = False
            self.node = None
            self.startMoveFlag = False
            self.nodeRefReady = False
            self.timer = vrTimer()
            self.timerConnected = False
            self.stickForward = False
            self.stickBackward = False
            self.stickLeft = False
            self.stickRight = False
            self.moveSpeed = 3.0
            self.rotateSpeed = 0.8
            self._fly_init()

            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
            vrImmersiveInteractionService.setDefaultInteractionsActive(1)

            padUp = vrdVirtualTouchpadButton('padup', 0.5, 1.0, 330.0, 30.0)
            padDown = vrdVirtualTouchpadButton('paddown', 0.5, 1.0, 150.0, 210.0)
            padLeft = vrdVirtualTouchpadButton('padleft', 0.5, 1.0, 210.0, 330.0)
            padRight = vrdVirtualTouchpadButton('padright', 0.5, 1.0, 30.0, 150.0)
            self.rightController.addVirtualButton(padUp, _pad_input)
            self.rightController.addVirtualButton(padDown, _pad_input)
            self.rightController.addVirtualButton(padLeft, _pad_input)
            self.rightController.addVirtualButton(padRight, _pad_input)

            multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadAdjust")
            multiButtonPad.setSupportedInteractionGroups(["AdjustGroup"])

            vrDeviceService.getInteraction("Teleport").addSupportedInteractionGroup("AdjustGroup")

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("AdjustGroup")

            self.padUpTouched = multiButtonPad.createControllerAction("right-padup-touched")
            self.padUpUntouched = multiButtonPad.createControllerAction("right-padup-untouched")
            self.padDownTouched = multiButtonPad.createControllerAction("right-paddown-touched")
            self.padDownUntouched = multiButtonPad.createControllerAction("right-paddown-untouched")
            self.padLeftTouched = multiButtonPad.createControllerAction("right-padleft-touched")
            self.padLeftUntouched = multiButtonPad.createControllerAction("right-padleft-untouched")
            self.padRightTouched = multiButtonPad.createControllerAction("right-padright-touched")
            self.padRightUntouched = multiButtonPad.createControllerAction("right-padright-untouched")

            self.registry_key = "tool_adjust"
            self.newRightCon = None
            self.AdjustControllerConstraint = None
            # 不在构造函数中调用 enable()

        def getMovable(self, node):
            while not node.isNull():
                if vrMetadataService.hasTag(node, 'Movable'):
                    return node
                if node.getName() == "Group" or node.getName() == "Transform":
                    break
                node = node.getParent()
            return node

        def _prepare_node_ref(self):
            self.nodeRefReady = False
            try:
                mypath = getUniquePath(self.node)
                nameString = "%s" % mypath
                vrSessionService.sendPython('"' + nameString + '"')
                vrSessionService.sendPython('nodeRef = findUniquePath("' + nameString + '")')
                self.nodeRefReady = True
            except Exception:
                self.nodeRefReady = False

        def _sync_transform(self):
            if not self.nodeRefReady or not self.node:
                return
            try:
                pos = getTransformNodeTranslation(self.node, 1)
                rot = getTransformNodeRotation(self.node)
                t = "%f,%f,%f" % (pos.x(), pos.y(), pos.z())
                r = "%f,%f,%f" % (rot.x(), rot.y(), rot.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
            except Exception:
                pass

        def _get_camera_forward_xy(self):
            try:
                cam = vrCameraService.getActiveCamera(True)
                if not cam:
                    return (0.0, 1.0)
                camNode = cam.getCameraNode()
                if not camNode or camNode.isNull():
                    return (0.0, 1.0)
                camRot = getTransformNodeRotation(camNode)
                angle_rad = math.radians(camRot.z())
                fx = -math.sin(angle_rad)
                fy = math.cos(angle_rad)
                length = math.sqrt(fx * fx + fy * fy)
                if length < 0.001:
                    return (0.0, 1.0)
                return (fx / length, fy / length)
            except Exception:
                return (0.0, 1.0)

        def _ensure_node(self):
            if self.node:
                try:
                    if not self.node.isNull():
                        return
                except Exception:
                    pass
            try:
                nodes = getSelectedNodes()
                if nodes and len(nodes) > 0 and not nodes[0].isNull():
                    self.node = self.getMovable(nodes[0])
                    self._prepare_node_ref()
                    return
            except Exception:
                pass
            try:
                tagged = vrMetadataService.getObjectsWithTag('Movable')
                if tagged and len(tagged) > 0:
                    for obj in tagged:
                        try:
                            if not obj.isNull():
                                name = obj.getName()
                                if "VRController" in name or "controller" in name.lower():
                                    continue
                                self.node = obj
                                self._prepare_node_ref()
                                return
                        except Exception:
                            continue
            except Exception:
                pass
            try:
                root = getRootNode()
                if root and not root.isNull():
                    children = root.getChildren()
                    if children and len(children) > 0:
                        for child in children:
                            try:
                                if not child.isNull():
                                    name = child.getName()
                                    if "VRController" in name or "controller" in name.lower():
                                        continue
                                    self.node = child
                                    self._prepare_node_ref()
                                    return
                            except Exception:
                                continue
            except Exception:
                pass

        def updateLoop(self):
            if self.startMoveFlag and self.node and not self.node.isNull():
                pos = getTransformNodeTranslation(self.node, 1)
                rot = getTransformNodeRotation(self.node)
                setTransformNodeTranslation(self.node, pos.x(), pos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), rot.z())
                self._sync_transform()
                return

            self._fly_tick()

            if not self.node:
                return
            try:
                if self.node.isNull():
                    return
            except Exception:
                return
            moved = False
            pos = getTransformNodeTranslation(self.node, 1)
            rot = getTransformNodeRotation(self.node)
            if self.stickForward or self.stickBackward:
                fx, fy = self._get_camera_forward_xy()
                direction = self.moveSpeed if self.stickForward else -self.moveSpeed
                setTransformNodeTranslation(self.node, pos.x() + fx * direction, pos.y() + fy * direction, pos.z(), 1)
                moved = True
            if self.stickLeft:
                setTransformNodeRotation(self.node, rot.x(), rot.y(), rot.z() + self.rotateSpeed)
                moved = True
            elif self.stickRight:
                setTransformNodeRotation(self.node, rot.x(), rot.y(), rot.z() - self.rotateSpeed)
                moved = True
            if moved:
                self._sync_transform()

        def startMove(self, action, device):
            self.node = self.getMovable(device.pick().getNode())
            if not self.node.isNull():
                self.originalNodeRot = getTransformNodeRotation(self.node)
                self.originalNodePos = getTransformNodeTranslation(self.node, 1)
                self.constraint = vrConstraintService.createParentConstraint([device.getNode()], self.node, True)
                self.startMoveFlag = True
                self._prepare_node_ref()

        def stopMove(self, action, device):
            if self.node is not None and not self.node.isNull():
                pos = getTransformNodeTranslation(self.node, 1)
                rot = getTransformNodeRotation(self.node)
                setTransformNodeTranslation(self.node, pos.x(), pos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), rot.z())
                vrConstraintService.deleteConstraint(self.constraint)
                self.startMoveFlag = False
                self._sync_transform()

        def on_up_touched(self, action=None, device=None):
            self._ensure_node()
            self.stickForward = True
        def on_up_untouched(self, action=None, device=None):
            self.stickForward = False
        def on_down_touched(self, action=None, device=None):
            self._ensure_node()
            self.stickBackward = True
        def on_down_untouched(self, action=None, device=None):
            self.stickBackward = False
        def on_left_touched(self, action=None, device=None):
            self._ensure_node()
            self.stickLeft = True
        def on_left_untouched(self, action=None, device=None):
            self.stickLeft = False
        def on_right_touched(self, action=None, device=None):
            self._ensure_node()
            self.stickRight = True
        def on_right_untouched(self, action=None, device=None):
            self.stickRight = False

        def enable(self):
            self.isEnabled = True
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
            # Hide stream panel when tool is activated
            global _stream_panel_visible
            _stream_panel_visible = False
            _sp_hide()
            vrDeviceService.setActiveInteractionGroup("AdjustGroup")

            start = self.pointer.getControllerAction("start")
            start.signal().triggered.connect(self.startMove)
            execute = self.pointer.getControllerAction("execute")
            execute.signal().triggered.connect(self.stopMove)

            self.padUpTouched.signal().triggered.connect(self.on_up_touched)
            self.padUpUntouched.signal().triggered.connect(self.on_up_untouched)
            self.padDownTouched.signal().triggered.connect(self.on_down_touched)
            self.padDownUntouched.signal().triggered.connect(self.on_down_untouched)
            self.padLeftTouched.signal().triggered.connect(self.on_left_touched)
            self.padLeftUntouched.signal().triggered.connect(self.on_left_untouched)
            self.padRightTouched.signal().triggered.connect(self.on_right_touched)
            self.padRightUntouched.signal().triggered.connect(self.on_right_untouched)

            self._fly_enable()
            print("[AdjustTool] grip polling timer active")

            if not self.timerConnected:
                self.timer.connect(self.updateLoop)
                self.timerConnected = True
            self.timer.setActive(1)
            print("[AdjustTool] timer active, timerConnected=%s" % self.timerConnected)

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 11)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.AdjustControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)
            print("[AllTools] AdjustTool enabled")

        def disable(self):
            try:
                self.isEnabled = False
                self.startMoveFlag = False
                self.stickForward = False
                self.stickBackward = False
                self.stickLeft = False
                self.stickRight = False
            except Exception:
                pass
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                act = self.pointer.getControllerAction("start")
                act.signal().triggered.disconnect(self.startMove)
            except Exception:
                pass
            try:
                act2 = self.pointer.getControllerAction("execute")
                act2.signal().triggered.disconnect(self.stopMove)
            except Exception:
                pass
            try:
                self.padUpTouched.signal().triggered.disconnect(self.on_up_touched)
            except Exception:
                pass
            try:
                self.padUpUntouched.signal().triggered.disconnect(self.on_up_untouched)
            except Exception:
                pass
            try:
                self.padDownTouched.signal().triggered.disconnect(self.on_down_touched)
            except Exception:
                pass
            try:
                self.padDownUntouched.signal().triggered.disconnect(self.on_down_untouched)
            except Exception:
                pass
            try:
                self.padLeftTouched.signal().triggered.disconnect(self.on_left_touched)
            except Exception:
                pass
            try:
                self.padLeftUntouched.signal().triggered.disconnect(self.on_left_untouched)
            except Exception:
                pass
            try:
                self.padRightTouched.signal().triggered.disconnect(self.on_right_touched)
            except Exception:
                pass
            try:
                self.padRightUntouched.signal().triggered.disconnect(self.on_right_untouched)
            except Exception:
                pass
            self._fly_disable()
            try:
                self.timer.setActive(0)
            except Exception:
                pass
            try:
                if hasattr(self, 'constraint') and self.constraint:
                    vrConstraintService.deleteConstraint(self.constraint)
                    self.constraint = None
            except Exception:
                pass
            try:
                self.rightController.setVisible(1)
            except Exception:
                pass
            try:
                if self.newRightCon:
                    self.newRightCon.setActive(0)
            except Exception:
                pass
            try:
                if self.AdjustControllerConstraint:
                    vrConstraintService.deleteConstraint(self.AdjustControllerConstraint)
                    self.AdjustControllerConstraint = None
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Notes - 图形标注工具 (draw_note)
    # ------------------------------------------------------------------
    class Notes:
        """
        图形标注工具:
          Trigger: 默认模式 -> TagAdd_R；再次点击 -> 放置当前标注
          B:       在 TagAdd_R 模式下循环切换标注样式
          A:       切换删除模式
          Grip:    靠近已放置标注后按住 → 拖动移位
        """
        _NOTE_TEMPLATE_NAMES = [
            "Move_S",
            "AlignCenter_S",
            "Smile_S",
            "Passed_S",
            "Notice_S",
            "AlignTo_S",
            "Good_S",
            "Flag_S",
            "Cancel_S",
            "MoreCurve_S",
        ]

        _TOUCH_DIST = 150.0  # mm — controller must be within this distance to grab a note

        def __init__(self):
            self.isEnabled = False
            self.deleteNoteIsActive = False
            self.isAddMode = False
            self.currentNoteIndex = 0

            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
            vrImmersiveInteractionService.setDefaultInteractionsActive(1)

            self.multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadNotes")
            self.multiButtonPad.setSupportedInteractionGroups(["NotesGroup"])

            vrDeviceService.getInteraction("Teleport").addSupportedInteractionGroup("NotesGroup")

            # "Tools Menu" 已在初始化时全局禁用（setSupportedInteractionGroups([])），
            # 这里不再重新添加任何 group，避免其内置 Y 键行为干扰工具状态。

            self.triggerRightPressed = self.multiButtonPad.createControllerAction("right-trigger-pressed")
            # Both A and B use getButtonState polling (OpenXR fires xa+yb simultaneously)
            self._aHeld = False
            self._bHeld = False
            self._abTimer = vrTimer()
            self._abTimerConnected = False

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("NotesGroup")

            self.registry_key = "tool_draw_note"
            self.newRightCon = None

            # ── grip drag ──
            self._GRIP_THRESHOLD = 0.5
            self._gripHeld = False
            self._grip_held = False
            self._dragging_node = None
            self._drag_constraint = None
            self._gripTimer = vrTimer()
            self._gripTimerConnected = False

        def _set_controller_choice(self, choice):
            try:
                findNode("CtrllrR_UI").fields().setInt32("choice", choice)
            except Exception:
                pass

        def _node_exists(self, node):
            if not node:
                return False
            try:
                is_null_fn = getattr(node, "isNull", None)
                if callable(is_null_fn):
                    return not is_null_fn()
            except Exception:
                return False
            return True

        def _get_tag_icon_switch(self):
            tag_switch = None
            try:
                tag_add_r = findNode("TagAdd_R")
                if self._node_exists(tag_add_r):
                    tag_add = tag_add_r.findChild("TagAdd")
                    if self._node_exists(tag_add):
                        tag_switch = tag_add.findChild("TagIconSwitch")
            except Exception:
                tag_switch = None

            if not self._node_exists(tag_switch):
                try:
                    tag_switch = findNode("TagIconSwitch")
                except Exception:
                    tag_switch = None
            return tag_switch

        def _get_note_templates(self):
            templates = []
            tag_switch = self._get_tag_icon_switch()
            if self._node_exists(tag_switch):
                for name in self._NOTE_TEMPLATE_NAMES:
                    child = None
                    try:
                        child = tag_switch.findChild(name)
                    except Exception:
                        child = None
                    if self._node_exists(child):
                        templates.append(child)

            # 兜底：按名称全局查找当前手柄图标节点
            if not templates:
                for name in self._NOTE_TEMPLATE_NAMES:
                    try:
                        node = findNode(name)
                        if self._node_exists(node):
                            templates.append(node)
                    except Exception:
                        pass
            return templates

        def _sync_tag_icon_switch(self, index):
            tag_switch = self._get_tag_icon_switch()

            try:
                if self._node_exists(tag_switch):
                    tag_switch.fields().setInt32("choice", index)
            except Exception:
                pass

        def _set_note_style(self, index):
            global refObject
            templates = self._get_note_templates()
            if not templates:
                refObject = None
                return False
            self.currentNoteIndex = index % len(templates)
            self._sync_tag_icon_switch(self.currentNoteIndex)
            refObject = self._get_note_templates()[self.currentNoteIndex]
            return True

        def _enter_default_mode(self):
            self.isAddMode = False
            self.deleteNoteIsActive = False
            self._set_controller_choice(1)

        def _enter_add_mode(self, reset_style=False):
            self.deleteNoteIsActive = False
            self.isAddMode = True
            if reset_style or not self._set_note_style(self.currentNoteIndex):
                self._set_note_style(0)
            self._set_controller_choice(2)

        def _enter_delete_mode(self):
            self.isAddMode = False
            self.deleteNoteIsActive = True
            self._set_controller_choice(3)

        def _get_cloned_note_root(self, node):
            while node:
                if not self._node_exists(node):
                    return None
                try:
                    if hasNodeTag(node, 'Cloned Note'):
                        return node
                except Exception:
                    pass
                try:
                    node = node.getParent()
                except Exception:
                    return None
            return None

        def _get_all_cloned_notes(self):
            """Return all scene nodes tagged 'Cloned Note' (placed graphic annotations)."""
            result = []
            try:
                for node in getAllNodes():
                    try:
                        if hasNodeTag(node, 'Cloned Note'):
                            result.append(node)
                    except Exception:
                        pass
            except Exception:
                pass
            return result

        def _poll_ab(self):
            try:
                a_pressed = self.rightController.getButtonState("xa").isPressed()
                if a_pressed and not self._aHeld:
                    self._aHeld = True
                    self.toggleDeleteMode()
                elif not a_pressed:
                    self._aHeld = False
            except Exception:
                pass
            try:
                b_pressed = self.rightController.getButtonState("yb").isPressed()
                if b_pressed and not self._bHeld:
                    self._bHeld = True
                    self.ChangeNote()
                elif not b_pressed:
                    self._bHeld = False
            except Exception:
                pass

        def _poll_b(self):
            # kept for compatibility; replaced by _poll_ab
            pass

        def _poll_grip(self):
            try:
                state = self.rightController.getButtonState("grip")
                pressed = state.isPressed() or state.getPosition().x() >= self._GRIP_THRESHOLD
                if pressed and not self._gripHeld:
                    self._gripHeld = True
                    self.on_grip_pressed()
                elif not pressed and self._gripHeld:
                    self._gripHeld = False
                    self.on_grip_released()
            except Exception:
                pass

        def on_grip_pressed(self, action=None, device=None):
            if self._grip_held:
                return
            if self._drag_constraint is not None:
                try:
                    vrConstraintService.deleteConstraint(self._drag_constraint)
                except Exception:
                    pass
                self._drag_constraint = None
            best_node = None
            best_dist = Notes._TOUCH_DIST
            try:
                ctrl_pos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                cx, cy, cz = ctrl_pos.x(), ctrl_pos.y(), ctrl_pos.z()
                for node in self._get_all_cloned_notes():
                    try:
                        p = getTransformNodeTranslation(node, 1)
                        dx = p.x() - cx
                        dy = p.y() - cy
                        dz = p.z() - cz
                        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                        if dist <= best_dist:
                            best_dist = dist
                            best_node = node
                    except Exception:
                        pass
            except Exception as e:
                print("[Notes] Grip proximity check failed: " + str(e))
            if best_node is None:
                print("[Notes] Grip: 范围内无可拖动标注 (TOUCH_DIST=%.1f mm)" % Notes._TOUCH_DIST)
                return
            try:
                self._drag_constraint = vrConstraintService.createParentConstraint(
                    [self.rightController.getNode()], best_node, False)
                self._grip_held = True
                self._dragging_node = best_node
                self._set_controller_choice(4)  # TagMove_R
                print("[Notes] Grip → 开始拖动: " + best_node.getName())
            except Exception as e:
                print("[Notes] Grip → createParentConstraint 失败: " + str(e))

        def on_grip_released(self, action=None, device=None):
            if self._drag_constraint is not None:
                try:
                    vrConstraintService.deleteConstraint(self._drag_constraint)
                except Exception:
                    pass
                self._drag_constraint = None
            self._grip_held = False
            self._dragging_node = None
            self._set_controller_choice(1)
            print("[Notes] Grip released → 停止拖动")

        def _on_pointer_start(self, action, device):
            """Pointer interaction callback – used for picking in delete mode."""
            if not self.deleteNoteIsActive:
                return
            try:
                picked = device.pick().getNode()
                if not picked or picked.isNull():
                    return
                target = self._get_cloned_note_root(picked)
                if not target:
                    return
                node_name = "%s" % target.getName()
                vrSessionService.sendPython('deleteNode(findNode("' + node_name + '"),True)')
            except Exception:
                pass

        def _spawn_current_note(self):
            global Cloned_ref_obj
            idx = self.currentNoteIndex

            # 直接从 TagIconSwitch 取对应的 xx_S 图标节点作为克隆源
            templates = self._get_note_templates()
            if not templates:
                print("[Notes] _spawn_current_note: no templates found")
                return

            icon_node = templates[idx % len(templates)]
            if not self._node_exists(icon_node):
                print("[Notes] _spawn_current_note: icon node not found")
                return

            template_name = self._NOTE_TEMPLATE_NAMES[idx % len(self._NOTE_TEMPLATE_NAMES)]

            try:
                icon_path = "%s" % getUniquePath(icon_node)
                node_num  = random.randint(0, 1000000)
                clone_name = "%s_%d" % (template_name, node_num)

                # 优先收归到 Cloned_ref_obj，保证 cleanup 时能统一删除
                container_path = ""
                if self._node_exists(Cloned_ref_obj):
                    try:
                        container_path = "%s" % getUniquePath(Cloned_ref_obj)
                    except Exception:
                        container_path = ""

                vrSessionService.sendPython(
                    '_icon = findUniquePath("' + icon_path + '"); '
                    '_mrRight = findNode("MRcontrollerRight"); '
                    '_wpos = _mrRight.getWorldTranslation(); '
                    '_wrot = _mrRight.getWorldRotation(); '
                    '_cpath = "' + container_path + '"; '
                    '_container = findUniquePath(_cpath) if _cpath else getRootNode(); '
                    'clonedRef = cloneNode(_icon, False); '
                    'clonedRef.setName("' + clone_name + '"); '
                    'moveNode(clonedRef, clonedRef.getParent(), _container); '
                    'clonedRef.setWorldTranslation(_wpos[0], _wpos[1], _wpos[2]); '
                    'clonedRef.setRotation(_wrot[0], _wrot[1], _wrot[2]); '
                    'addNodeTag(clonedRef, "Cloned Note"); '
                    'vrScenegraphService.clearSelection()'
                )
                print("[Notes] spawning %s at MRcontrollerRight transform" % clone_name)
            except Exception as e:
                print("[Notes] _spawn_current_note error: %s" % e)

        def enable(self):
            self.isEnabled = True

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
            # Hide stream panel when tool is activated
            global _stream_panel_visible
            _stream_panel_visible = False
            _sp_hide()
            self.multiButtonPad.setSupportedInteractionGroups(["NotesGroup"])
            vrDeviceService.setActiveInteractionGroup("NotesGroup")

            self.triggerRightPressed.signal().triggered.connect(self.trigger_right_pressed)
            if not self._abTimerConnected:
                self._abTimer.connect(self._poll_ab)
                self._abTimerConnected = True
            self._aHeld = False
            self._bHeld = False
            self._abTimer.setActive(1)
            self.pointer.getControllerAction("start").signal().triggered.connect(self._on_pointer_start)
            # grip 轮询 timer
            if not self._gripTimerConnected:
                self._gripTimer.connect(self._poll_grip)
                self._gripTimerConnected = True
            self._gripTimer.setActive(1)
            self.currentNoteIndex = 0
            self._set_note_style(0)

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 1)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.NoteControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)

            self._enter_default_mode()
            print("[AllTools] Notes enabled (Trigger=放置, A=删除, B=切换样式, Grip靠近=拖动)")

        def disable(self):
            self.isEnabled = False
            try:
                self.multiButtonPad.setSupportedInteractionGroups(["__disabled__"])
            except Exception:
                pass
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                self.triggerRightPressed.signal().triggered.disconnect(self.trigger_right_pressed)
            except Exception:
                pass
            try:
                self._abTimer.setActive(0)
            except Exception:
                pass
            self._aHeld = False
            self._bHeld = False
            try:
                self.pointer.getControllerAction("start").signal().triggered.disconnect(self._on_pointer_start)
            except Exception:
                pass
            try:
                self._gripTimer.setActive(0)
            except Exception:
                pass
            self._gripHeld = False
            if self._drag_constraint is not None:
                try:
                    vrConstraintService.deleteConstraint(self._drag_constraint)
                except Exception:
                    pass
                self._drag_constraint = None
            self._grip_held = False
            self._dragging_node = None
            try:
                if hasattr(self, 'NoteControllerConstraint') and self.NoteControllerConstraint:
                    vrConstraintService.deleteConstraint(self.NoteControllerConstraint)
                    self.NoteControllerConstraint = None
            except Exception:
                pass
            try:
                if hasattr(self, 'newRightCon') and self.newRightCon:
                    self.newRightCon.setActive(0)
            except Exception:
                pass
            try:
                self.rightController.setVisible(1)
            except Exception:
                pass
            self._enter_default_mode()

        def trigger_right_pressed(self):
            if self.deleteNoteIsActive:
                return  # deletion handled by Pointer interaction callback (_on_pointer_start)
            if not self.isAddMode:
                self._enter_add_mode(reset_style=True)
                return
            self._spawn_current_note()
            # 保持添加模式，支持连续Trigger放置
            self._enter_add_mode(reset_style=False)

        def toggleDeleteMode(self):
            print("toggling delete mode, currently deleteNoteIsActive=%s" % self.deleteNoteIsActive)
            if not self.deleteNoteIsActive:
                self._enter_delete_mode()
            else:
                self._enter_default_mode()

        def ChangeNote(self):
            print("changing note style, currently deleteNoteIsActive=%s" % self.deleteNoteIsActive)
            if self.deleteNoteIsActive:
                return
            templates = self._get_note_templates()
            if not templates:
                return
            self._set_note_style(self.currentNoteIndex + 1)
            if not self.isAddMode:
                self._enter_add_mode(reset_style=False)

    # ------------------------------------------------------------------
    # SectionTool - 剖面工具
    # ------------------------------------------------------------------
    class SectionTool(GripFlyMixin):
        """
        剖面工具:
          A:       循环启用 / 禁用截面
          Trigger: 按住时截面实时跟随手柄位置和朝向（垂直于手柄轴线），松开后停在当前位置
          B:       切换截面正/反面 (flipped)
        手柄样式: ClipPositive_R (choice=5)
        """
        def __init__(self):
            self.isEnabled = False
            self.clipping = False
            self.flipped = False
            self.triggerHeld = False
            self.timer = vrTimer()
            self.timerConnected = False

            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)

            multiButtonPadClip = vrDeviceService.createInteraction("MultiButtonPadClip")
            multiButtonPadClip.setSupportedInteractionGroups(["ClipGroup"])

            vrDeviceService.getInteraction("Teleport").addSupportedInteractionGroup("ClipGroup")

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("ClipGroup")

            self.triggerRightPressed = multiButtonPadClip.createControllerAction("right-trigger-pressed")
            self.triggerRightReleased = multiButtonPadClip.createControllerAction("right-trigger-released")
            # A and B use getButtonState polling (OpenXR fires xa+yb simultaneously)
            self._aHeld = False
            self._bHeld = False
            self._abTimer = vrTimer()
            self._abTimerConnected = False

            self.registry_key = "tool_section"
            self.newRightCon = None
            self.ClipControllerConstraint = None
            self._fly_init()

        def _apply_clipping_plane(self):
            try:
                node = self.newRightCon if self.newRightCon else self.rightController.getNode()
                icosa = findNode("Icosahedron")
                pos = getTransformNodeTranslation(icosa, 1)
                p = "%f,%f,%f" % (pos.x(), pos.y(), pos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
                try:
                    rot = getTransformNodeRotation(node)
                    r = "%f,%f,%f" % (rot.x() + 90 - 36.48, rot.y(), rot.z())
                    vrSessionService.sendPython("setClippingPlaneRotation(" + r + ")")
                except Exception:
                    pass
            except Exception as e:
                print("[SectionTool] _apply_clipping_plane ERROR: " + str(e))

        def _update_loop(self):
            if self.triggerHeld and self.clipping:
                self._apply_clipping_plane()

            self._fly_tick()

        def on_trigger_pressed(self, action=None, device=None):
            self.triggerHeld = True
            if self.clipping:
                self._apply_clipping_plane()

        def on_trigger_released(self, action=None, device=None):
            self.triggerHeld = False

        def toggle_clipping(self, action=None, device=None):
            """A 键：循环启用/禁用截面。"""
            self.clipping = not self.clipping
            state = 1 if self.clipping else 0
            enableClippingPlane(state)
            try:
                vrSessionService.sendPython("enableClippingPlane(%d)" % state)
            except Exception:
                pass
            if self.clipping:
                try:
                    setClippingContourVisualization(0, Vec3f(0, 0, 0))
                    setClippingPlaneVisualization(0, Vec3f(0, 0, 0))
                    setClippingGridVisualization(0, Vec3f(0, 0, 0))
                except Exception:
                    pass
            print("[SectionTool] clipping=%s" % self.clipping)

        def toggle_flipped(self, action=None, device=None):
            """B 键：切换截面正/反面。"""
            self.flipped = not self.flipped
            if self.clipping:
                try:
                    cur_pos = getClippingPlanePosition()
                    cur_normal = getClippingPlaneNormal()
                    setClippingPlane(cur_pos, cur_normal, self.flipped)
                except Exception:
                    pass
            print("[SectionTool] flipped=%s" % self.flipped)

        def _poll_ab(self):
            try:
                a_pressed = self.rightController.getButtonState("xa").isPressed()
                if a_pressed and not self._aHeld:
                    self._aHeld = True
                    self.toggle_clipping()
                elif not a_pressed:
                    self._aHeld = False
            except Exception:
                pass
            try:
                b_pressed = self.rightController.getButtonState("yb").isPressed()
                if b_pressed and not self._bHeld:
                    self._bHeld = True
                    self.toggle_flipped()
                elif not b_pressed:
                    self._bHeld = False
            except Exception:
                pass

        def enable(self):
            self.isEnabled = True
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
            # Hide stream panel when tool is activated
            global _stream_panel_visible
            _stream_panel_visible = False
            _sp_hide()
            setClippingShowManipulator(0)
            try:
                setClippingContourVisualization(0, Vec3f(0, 0, 0), 0)
            except Exception:
                pass
            vrDeviceService.setActiveInteractionGroup("ClipGroup")

            self.triggerRightPressed.signal().triggered.connect(self.on_trigger_pressed)
            self.triggerRightReleased.signal().triggered.connect(self.on_trigger_released)
            if not self._abTimerConnected:
                self._abTimer.connect(self._poll_ab)
                self._abTimerConnected = True
            self._aHeld = False
            self._bHeld = False
            self._abTimer.setActive(1)

            if not self.timerConnected:
                self.timer.connect(self._update_loop)
                self.timerConnected = True
            self.timer.setActive(1)

            self._fly_enable()
            print("[SectionTool] grip polling timer active")

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 5)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.ClipControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)
            print("[AllTools] SectionTool enabled")

        def disable(self):
            self.isEnabled = False
            self.triggerHeld = False
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                self.triggerRightPressed.signal().triggered.disconnect(self.on_trigger_pressed)
            except Exception:
                pass
            try:
                self.triggerRightReleased.signal().triggered.disconnect(self.on_trigger_released)
            except Exception:
                pass
            try:
                self._abTimer.setActive(0)
            except Exception:
                pass
            self._aHeld = False
            self._bHeld = False
            try:
                self.timer.setActive(0)
            except Exception:
                pass
            self._fly_disable()
            try:
                enableClippingPlane(0)
                self.clipping = False
            except Exception:
                pass
            try:
                self.rightController.setVisible(1)
            except Exception:
                pass
            try:
                if self.newRightCon:
                    self.newRightCon.setActive(0)
            except Exception:
                pass
            try:
                if self.ClipControllerConstraint:
                    vrConstraintService.deleteConstraint(self.ClipControllerConstraint)
                    self.ClipControllerConstraint = None
            except Exception:
                pass

    # ------------------------------------------------------------------
    # TurntableTool - 展示台旋转工具
    # ------------------------------------------------------------------
    class TurntableTool:
        def __init__(self):
            self.isEnabled = False
            self.node = None
            self.nodeRefReady = False
            self.aHeld = False
            self.currentAngle = 0.0
            self.originalAngle = 0.0
            self._sessionOriginalAngleSaved = False
            self.dragStartX = 0.0
            self.rotationStartAngle = 0.0
            self.rotationSensitivity = 0.2   # degrees per mm of controller X movement
            self.timer = vrTimer()
            self.timerConnected = False
            self.newRightCon = None
            self.RotationControllerConstraint = None

            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
            vrImmersiveInteractionService.setDefaultInteractionsActive(1)

            padLeft = vrdVirtualTouchpadButton('padleft', 0.3, 1.0, 180.0, 360.0)
            padRight = vrdVirtualTouchpadButton('padright', 0.3, 1.0, 0.0, 180.0)
            self.rightController.addVirtualButton(padLeft, _pad_input)
            self.rightController.addVirtualButton(padRight, _pad_input)

            self.multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadTurntable")
            self.multiButtonPad.setSupportedInteractionGroups(["TurntableGroup"])

            vrDeviceService.getInteraction("Teleport").addSupportedInteractionGroup("TurntableGroup")

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("TurntableGroup")

            self.aPressedAction = self.multiButtonPad.createControllerAction("right-xa-pressed")
            # A released and B pressed use getButtonState polling (OpenXR xa-released triggers yb-pressed bug)
            self._bHeld = False
            self._bTimer = vrTimer()
            self._bTimerConnected = False

            self.registry_key = "tool_turntable"

        def _resolve_target(self):
            try:
                nodes = getSelectedNodes()
                if nodes and len(nodes) > 0:
                    try:
                        if not nodes[0].isNull():
                            movable = self._get_movable(nodes[0])
                            return movable if movable else nodes[0]
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                tagged = vrMetadataService.getObjectsWithTag('Movable')
                if tagged and len(tagged) > 0:
                    for obj in tagged:
                        try:
                            if not obj.isNull():
                                name = obj.getName()
                                if "VRController" in name or "controller" in name.lower():
                                    continue
                                return obj
                        except Exception:
                            continue
            except Exception:
                pass
            try:
                root = getRootNode()
                if root and not root.isNull():
                    children = root.getChildren()
                    if children and len(children) > 0:
                        for child in children:
                            try:
                                if not child.isNull():
                                    name = child.getName()
                                    if "VRController" in name or "controller" in name.lower():
                                        continue
                                    return child
                            except Exception:
                                continue
            except Exception:
                pass
            return None

        def _get_movable(self, node):
            try:
                original_node = node
                while node and not node.isNull():
                    name = node.getName()
                    if vrMetadataService.hasTag(node, 'Movable'):
                        return node
                    if name in ("Group", "Transform"):
                        return node
                    node = node.getParent()
                return original_node
            except Exception:
                pass
            return None

        def _prepare_node_ref(self):
            self.nodeRefReady = False
            try:
                mypath = getUniquePath(self.node)
                nameString = "%s" % mypath
                vrSessionService.sendPython('"' + nameString + '"')
                vrSessionService.sendPython('nodeRef = findUniquePath("' + nameString + '")')
                self.nodeRefReady = True
            except Exception:
                self.nodeRefReady = False

        def _poll_b(self):
            try:
                state = self.rightController.getButtonState("yb")
                pressed = state.isPressed()
                if pressed and not self._bHeld:
                    self._bHeld = True
                    self.restore_rotation()
                elif not pressed:
                    self._bHeld = False
            except Exception:
                pass

        def _start_timer(self):
            self.timer.setActive(0)
            if not self.timerConnected:
                self.timer.connect(self.updateRotation)
                self.timerConnected = True
            self.timer.setActive(1)

        def _stop_timer(self):
            self.timer.setActive(0)

        def enable(self):
            self.isEnabled = True
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
            # Hide stream panel when tool is activated
            global _stream_panel_visible
            _stream_panel_visible = False
            _sp_hide()
            vrDeviceService.setActiveInteractionGroup("TurntableGroup")

            self.aPressedAction.signal().triggered.connect(self.start_rotation)
            if not self._bTimerConnected:
                self._bTimer.connect(self._poll_b)
                self._bTimerConnected = True
            self._bHeld = False
            self._bTimer.setActive(1)

            self._sessionOriginalAngleSaved = False

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 13)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.RotationControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)
            print("[AllTools] TurntableTool enabled")

        def disable(self):
            self.isEnabled = False
            self.stop_rotation()
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                self.aPressedAction.signal().triggered.disconnect(self.start_rotation)
            except Exception:
                pass
            try:
                self._bTimer.setActive(0)
            except Exception:
                pass
            self._bHeld = False
            try:
                self.rightController.setVisible(1)
            except Exception:
                pass
            try:
                if self.newRightCon and not self.newRightCon.isNull():
                    self.newRightCon.setActive(0)
            except Exception:
                pass
            try:
                if self.RotationControllerConstraint:
                    vrConstraintService.deleteConstraint(self.RotationControllerConstraint)
                    self.RotationControllerConstraint = None
            except Exception:
                pass

        def restore_rotation(self, action=None, device=None):
            if not self.node:
                return
            try:
                if self.node.isNull():
                    return
            except Exception:
                return
            try:
                rot = getTransformNodeRotation(self.node)
                setTransformNodeRotation(self.node, rot.x(), rot.y(), self.originalAngle)
                self.currentAngle = self.originalAngle
            except Exception:
                pass
            if self.nodeRefReady:
                try:
                    rot = getTransformNodeRotation(self.node)
                    r = "%f,%f,%f" % (rot.x(), rot.y(), self.originalAngle)
                    vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                except Exception:
                    pass

        def start_rotation(self, action=None, device=None):
            self.node = self._resolve_target()
            if not self.node:
                return
            try:
                if self.node.isNull():
                    return
            except Exception:
                pass
            self._prepare_node_ref()
            # Save original angle once per enable session (before any rotation)
            if not self._sessionOriginalAngleSaved:
                try:
                    self.originalAngle = getTransformNodeRotation(self.node).z()
                except Exception:
                    self.originalAngle = 0.0
                self._sessionOriginalAngleSaved = True
            # Capture drag baseline for this press
            try:
                ctrl_pos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                self.dragStartX = ctrl_pos.x()
            except Exception:
                self.dragStartX = 0.0
            try:
                self.rotationStartAngle = getTransformNodeRotation(self.node).z()
            except Exception:
                self.rotationStartAngle = self.currentAngle
            self.currentAngle = self.rotationStartAngle
            self.aHeld = True
            self._start_timer()

        def stop_rotation(self, action=None, device=None):
            self.aHeld = False
            self._stop_timer()

        def updateRotation(self):
            # Poll A released via getButtonState (xa-released event is buggy in OpenXR)
            if self.aHeld:
                try:
                    if not self.rightController.getButtonState("xa").isPressed():
                        self.stop_rotation()
                except Exception:
                    pass
            if not self.aHeld or not self.node:
                return
            try:
                if self.node.isNull():
                    self.stop_rotation()
                    return
            except Exception:
                pass
            try:
                ctrl_pos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                deltaX = ctrl_pos.x() - self.dragStartX
            except Exception:
                return
            self.currentAngle = self.rotationStartAngle + deltaX * self.rotationSensitivity
            try:
                rot = getTransformNodeRotation(self.node)
                setTransformNodeRotation(self.node, rot.x(), rot.y(), self.currentAngle)
            except Exception:
                pass
            if self.nodeRefReady:
                try:
                    rot = getTransformNodeRotation(self.node)
                    r = "%f,%f,%f" % (rot.x(), rot.y(), self.currentAngle)
                    vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # MeasureTool - 测量工具
    # ------------------------------------------------------------------
    class MeasureTool:
        def __init__(self):
            self.isEnabled = False
            self.on = False
            self.point1Selected = False
            self.node1 = None
            self.node2 = None
            self.point1 = None
            self.point2 = None
            self.pointer = None
            self.executeAction = None
            self.registry_key = "tool_measure"
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.newRightCon = None
            self.measureControllerConstraint = None
            self._measurement_shown = False

        def _find_or_load_measure_controller(self):
            return findNode("MRcontrollerRight")

        def _activate_measure_controller(self):
            self.newRightCon = self._find_or_load_measure_controller()
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            findNode("CtrllrR_UI").fields().setInt32("choice", 14)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.measureControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False
            )

        def _deactivate_measure_controller(self):
            try:
                if self.measureControllerConstraint:
                    vrConstraintService.deleteConstraint(self.measureControllerConstraint)
                    self.measureControllerConstraint = None
            except Exception:
                pass
            try:
                if self.newRightCon:
                    self.newRightCon.setActive(0)
            except Exception:
                pass
            try:
                self.rightController.setVisible(1)
            except Exception:
                pass

        def enable(self):
            self.isEnabled = True
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
            # Hide stream panel when tool is activated
            global _stream_panel_visible
            _stream_panel_visible = False
            _sp_hide()
            self.switchOn()
            self._activate_measure_controller()
            print("[AllTools] MeasureTool enabled")

        def switchOn(self):
            if not self.on:
                self.point1Selected = False
                self._measurement_shown = False
                try:
                    self.pointer = vrDeviceService.getInteraction("Pointer")
                    self.executeAction = self.pointer.getControllerAction("execute")
                    self.executeAction.signal().triggered.connect(self.selectPoint)
                    self.on = True
                except Exception:
                    self.on = False

        def switchOff(self):
            if self.on:
                try:
                    if self.executeAction:
                        self.executeAction.signal().triggered.disconnect(self.selectPoint)
                except Exception:
                    pass
                self.on = False

        def selectPoint(self, action, device):
            try:
                hit = device.pick()
            except Exception:
                hit = None
            if not hit or not hit.hasHit():
                return
            try:
                if hit.getNode().getName() == "VRMenuPanel":
                    return
            except Exception:
                pass
            if self._measurement_shown:
                self.removeMeasurement()
                self._measurement_shown = False
                self.point1Selected = False
                return
            if not self.point1Selected:
                self.point1Selected = True
                try:
                    self.node1 = hit.getNode()
                    self.point1 = hit.getPoint()
                except Exception:
                    self.node1 = None
                    self.point1 = None
            else:
                self.point1Selected = False
                try:
                    self.node2 = hit.getNode()
                    self.point2 = hit.getPoint()
                except Exception:
                    self.node2 = None
                    self.point2 = None
                self.createMeasurement()
                self._measurement_shown = True

        def createMeasurement(self):
            try:
                vrSessionService.sendPython("createPointPointMeasurement({},{},{},{})".format(
                    vrSessionService.toPythonString(self.node1),
                    vrSessionService.toPythonString(self.point1),
                    vrSessionService.toPythonString(self.node2),
                    vrSessionService.toPythonString(self.point2)))
            except Exception:
                try:
                    createPointPointMeasurement(self.node1, self.point1, self.node2, self.point2)
                except Exception:
                    pass

        def removeMeasurement(self):
            try:
                vrSessionService.sendPython("removeSelectedMeasurement()")
            except Exception:
                try:
                    removeSelectedMeasurement()
                except Exception:
                    pass

        def disable(self):
            self.isEnabled = False
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            self.switchOff()
            self._deactivate_measure_controller()

    # ------------------------------------------------------------------
    # FlashlightTool - 手电筒工具
    #   A: 开启手电筒   B: 关闭手电筒
    #   右手柄样式: Flashlight_R (choice=12)
    # ------------------------------------------------------------------
    class FlashlightTool(GripFlyMixin):
        def __init__(self):
            self.isEnabled = False
            self.registry_key = "tool_flashlight"
            self.lightNode = None
            self.lightSceneNode = None
            self.lightOn = False
            self.lightTimer = vrTimer()
            self.lightTimerConnected = False
            self.newRightCon = None
            self.flashlightControllerConstraint = None

            # grip 飞行模式（与 AdjustTool 一致）
            self._fly_init()

            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)

            self.multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadFlashlight")
            self.multiButtonPad.setSupportedInteractionGroups(["FlashlightGroup"])

            vrDeviceService.getInteraction("Teleport").addSupportedInteractionGroup("FlashlightGroup")

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("FlashlightGroup")

            self.aPressedAction = self.multiButtonPad.createControllerAction("right-a-pressed")
            self.bPressedAction = self.multiButtonPad.createControllerAction("right-b-pressed")

        def _create_spotlight(self):
            if self.lightNode is not None:
                return
            try:
                self.lightNode = vrLightService.createLight(
                    "VR_Flashlight_Spot", vrLightTypes.LightType.Spot)
                self.lightNode.setOn(False)
                self.lightNode.setIntensity(500.0)
                self.lightNode.setDiffuseColor(QVector3D(1.0, 0.98, 0.95))
                self.lightNode.setConeAngle(25.0)
                self.lightNode.setPenumbraAngle(5.0)
                self.lightNode.setVisualizationVisible(False)
            except Exception as e:
                print("[FlashlightTool] _create_spotlight 失败: " + str(e))
                self.lightNode = None
                return
            try:
                self.lightSceneNode = vrNodeService.findNode("VR_Flashlight_Spot")
            except Exception:
                self.lightSceneNode = None
            self._start_light_timer()

        def _remove_spotlight(self):
            self._stop_light_timer()
            try:
                if self.lightNode:
                    self.lightNode.setOn(False)
                    vrNodeService.removeNode(self.lightNode)
                    self.lightNode = None
            except Exception:
                pass
            self.lightSceneNode = None
            self.lightOn = False

        # 聚光灯相对手柄的局部变换（单位: mm / degree）
        _LIGHT_LOCAL_TRANSLATION = QVector3D(3.12888, -72.0161, -10.7245)
        _LIGHT_LOCAL_ROTATION_EULER = QVector3D(-34.617, -2.95854, 2.04049)

        def _update_light_transform(self):
            """Timer 回调：将聚光灯姿态同步到手柄，并叠加局部平移/旋转偏移。"""
            if not self.lightSceneNode:
                # 即使光节点不可用，也允许 grip 飞行逻辑继续运行
                self._fly_tick()
                return
            try:
                node = self.newRightCon if self.newRightCon else self.rightController.getNode()
                mat = node.getWorldTransform()

                # 先构建局部偏移矩阵，再乘到手柄世界矩阵上
                local = QMatrix4x4()
                t = self._LIGHT_LOCAL_TRANSLATION
                r = self._LIGHT_LOCAL_ROTATION_EULER
                local.translate(t.x(), t.y(), t.z())
                local.rotate(r.x(), 1.0, 0.0, 0.0)
                local.rotate(r.y(), 0.0, 1.0, 0.0)
                local.rotate(r.z(), 0.0, 0.0, 1.0)

                out = QMatrix4x4(mat)
                out *= local
                self.lightSceneNode.setWorldTransform(out)
            except Exception:
                # 降级：直接跟随手柄
                try:
                    node = self.newRightCon if self.newRightCon else self.rightController.getNode()
                    self.lightSceneNode.setWorldTransform(node.getWorldTransform())
                except Exception:
                    pass
            self._fly_tick()

        def _start_light_timer(self):
            self.lightTimer.setActive(0)
            if not self.lightTimerConnected:
                self.lightTimer.connect(self._update_light_transform)
                self.lightTimerConnected = True
            self.lightTimer.setActive(1)

        def _stop_light_timer(self):
            self.lightTimer.setActive(0)

        def toggle_light(self, action=None, device=None):
            """A 键切换手电筒开/关。"""
            if self.lightNode is None:
                self._create_spotlight()
            if not self.lightNode:
                return
            if self.lightOn:
                self.lightNode.setOn(False)
                self.lightOn = False
                print("[FlashlightTool] 手电筒关闭")
            else:
                self.lightNode.setOn(True)
                self.lightOn = True
                print("[FlashlightTool] 手电筒开启")

        def _activate_flashlight_controller(self):
            self.newRightCon = findNode("MRcontrollerRight")
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            findNode("CtrllrR_UI").fields().setInt32("choice", 12)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.flashlightControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)

        def _deactivate_flashlight_controller(self):
            try:
                if self.flashlightControllerConstraint:
                    vrConstraintService.deleteConstraint(self.flashlightControllerConstraint)
                    self.flashlightControllerConstraint = None
            except Exception:
                pass
            try:
                if self.newRightCon:
                    self.newRightCon.setActive(0)
            except Exception:
                pass
            try:
                self.rightController.setVisible(1)
            except Exception:
                pass

        def enable(self):
            self.isEnabled = True
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
            # Hide stream panel when tool is activated
            global _stream_panel_visible
            _stream_panel_visible = False
            _sp_hide()
            vrDeviceService.setActiveInteractionGroup("FlashlightGroup")
            # 只连接 aPressedAction；bPressedAction 在此 VRED 环境中与 A 键共用同一物理信号，
            # 不连接 bPressedAction 可确保每次 A 键只触发一次 toggle。
            try:
                self.aPressedAction.signal().triggered.disconnect(self.toggle_light)
            except Exception:
                pass
            self.aPressedAction.signal().triggered.connect(self.toggle_light)

            self._fly_enable()

            self._create_spotlight()
            self._activate_flashlight_controller()
            print("[AllTools] FlashlightTool enabled (A=开启, B=关闭)")

        def disable(self):
            self.isEnabled = False
            self._fly_disable()
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                self.aPressedAction.signal().triggered.disconnect(self.toggle_light)
            except Exception:
                pass
            self._remove_spotlight()
            self._deactivate_flashlight_controller()
            print("[AllTools] FlashlightTool disabled")

    # ------------------------------------------------------------------
    # VoiceNotes - 语音标注工具
    # ------------------------------------------------------------------
    class VoiceNotes:
        _TOUCH_DIST = 150.0      # mm — controller must be within this distance to trigger playback
        _FORWARD_OFFSET = 200.0  # mm — how far in front of the controller a new note is placed

        def __init__(self):
            # ── VRED devices ──
            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
            vrImmersiveInteractionService.setDefaultInteractionsActive(1)

            # ── interaction group ──
            self.multi = vrDeviceService.createInteraction("MultiButtonPadVoice")
            self.multi.setSupportedInteractionGroups(["VoiceNotesGroup"])
            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("VoiceNotesGroup")
            vrDeviceService.getInteraction("Teleport").addSupportedInteractionGroup("VoiceNotesGroup")

            # ── button actions ──
            self.aPressedAction = self.multi.createControllerAction("right-a-pressed")
            self.aReleasedAction = self.multi.createControllerAction("right-a-released")
            self.bPressedAction = self.multi.createControllerAction("right-b-pressed")
            self.bReleasedAction = self.multi.createControllerAction("right-b-released")
            self.triggerPressedAction = self.multi.createControllerAction("right-trigger-pressed")

            # grip 通过 getButtonState 轮询（与 AdjustTool / SectionTool 一致）
            self._GRIP_THRESHOLD = 0.5
            self._gripTimer = vrTimer()
            self._gripTimerConnected = False

            # ── audio ──
            self._recorder = None
            self._player = None
            self._audio_input = None
            self._audio_output = None
            self._capture_session = None

            # ── recording state ──
            self._is_recording = False
            self._current_rect = None
            self._current_annotation = None
            self._current_audio_path = None
            self._current_label = None
            self._last_audio_path = None
            self._last_rect = None

            # ── annotation data ──
            self._rect_audio_paths = {}   # key → wav path
            self._rect_base_scales = {}   # key → QVector3D base scale
            self._rect_annotations = {}   # key → vrAnnotation
            self._rect_labels = {}        # key → display label
            self._voice_note_nodes = {}   # key → scene node

            # ── hover ──
            self._hover_rect = None
            self._hover_scale = 1.2

            # ── template ──
            self._voice_player_template = None

            # ── drag / touch ──
            self._gripHeld = False    # polling state tracker
            self._grip_held = False   # drag-in-progress state
            self._dragging_node = None
            self._drag_constraint = None
            self._eraser_held = False
            self._b_down = False
            self._bTimer = QtCore.QTimer()
            self._bTimer.setSingleShot(True)
            self._bTimer.setInterval(500)
            self._bTimer.timeout.connect(self._activate_eraser)
            self._eraser_in_range = set()
            self._eraserTimer = vrTimer()
            self._eraserTimerConnected = False

            # ── pending node creation (deferred to release) ──
            self._pending_position = None
            self._pending_rotation = None

            # ── misc ──
            self.isEnabled = False
            self.registry_key = "tool_voice_note"
            self.newRightCon = None
            self.voiceControllerConstraint = None

        # ── audio / media ──────────────────────────────────────────────

        def _ensure_recorder(self):
            if self._recorder is not None:
                return self._recorder
            self._audio_input = QtMultimedia.QAudioInput()
            try:
                inputs = QtMultimedia.QMediaDevices.audioInputs()
                preferred = os.getenv("VOICE_NOTE_AUDIO_INPUT", "").strip().lower()
                chosen = None
                keywords = [
                    "alvr", "virtual audio", "virtual-audio", "virtualaudio",
                    "audio cable", "virtual audio cable", "cable", "vb-audio", "vac",
                    "microphone", "mic", "virtual desktop", "virtual desktop audio"
                ]
                for dev in inputs:
                    try:
                        name = ""
                        try:
                            name = dev.description()
                        except Exception:
                            pass
                        if not name:
                            try:
                                name = dev.deviceName()
                            except Exception:
                                name = ""
                        lowered = name.lower() if name else ""
                        if preferred and lowered and preferred in lowered:
                            chosen = dev
                            break
                        if lowered and any(k in lowered for k in keywords):
                            chosen = dev
                            break
                    except Exception:
                        pass
                if chosen is None:
                    for dev in inputs:
                        try:
                            if dev.isDefault():
                                chosen = dev
                                break
                        except Exception:
                            pass
                if chosen is None and len(inputs) == 1:
                    chosen = inputs[0]
                if chosen:
                    try:
                        self._audio_input.setDevice(chosen)
                    except Exception:
                        pass
            except Exception:
                pass
            self._recorder = QtMultimedia.QMediaRecorder()
            self._capture_session = QtMultimedia.QMediaCaptureSession()
            self._capture_session.setAudioInput(self._audio_input)
            self._capture_session.setRecorder(self._recorder)
            return self._recorder

        def _ensure_player(self):
            if self._player is not None:
                return self._player
            self._player = QtMultimedia.QMediaPlayer()
            self._audio_output = QtMultimedia.QAudioOutput()
            try:
                outputs = QtMultimedia.QMediaDevices.audioOutputs()
                preferred = os.getenv("VOICE_NOTE_AUDIO_DEVICE", "").strip().lower()
                chosen = None
                chosen_name = ""
                # 仅通过环境变量或系统默认选择设备，不做关键字匹配
                if preferred:
                    for dev in outputs:
                        try:
                            name = ""
                            try:
                                name = dev.description()
                            except Exception:
                                pass
                            if not name:
                                try:
                                    name = dev.deviceName()
                                except Exception:
                                    name = ""
                            if name and preferred in name.lower():
                                chosen = dev
                                chosen_name = name
                                break
                        except Exception:
                            pass
                if chosen is None:
                    for dev in outputs:
                        try:
                            if dev.isDefault():
                                chosen = dev
                                try:
                                    chosen_name = dev.description() or dev.deviceName()
                                except Exception:
                                    chosen_name = "default"
                                break
                        except Exception:
                            pass
                if chosen:
                    try:
                        self._audio_output.setDevice(chosen)
                    except Exception:
                        pass
                    print("[VoiceNotes] 选用音频输出: " + str(chosen_name))
                else:
                    print("[VoiceNotes] 未选到音频输出设备，使用系统默认")
                try:
                    self._audio_output.setVolume(1.0)
                except Exception:
                    pass
            except Exception as e:
                print("[VoiceNotes] _ensure_player 设备枚举失败: " + str(e))
            self._player.setAudioOutput(self._audio_output)
            return self._player

        def _play_audio(self, path):
            if not path or not os.path.exists(path):
                print("[VoiceNotes] _play_audio: 文件不存在: " + str(path))
                return False
            player = self._ensure_player()
            # 先停止当前播放，再切换音源
            try:
                player.stop()
            except Exception:
                pass
            url = QtCore.QUrl.fromLocalFile(path)
            if hasattr(QtMultimedia.QMediaPlayer, "setSource"):
                player.setSource(url)
            else:
                player.setMedia(QtMultimedia.QMediaContent(url))
            player.play()
            try:
                err = player.errorString()
                if err:
                    print("[VoiceNotes] 播放器错误: " + str(err))
                else:
                    print("[VoiceNotes] 播放已启动: " + str(path))
            except Exception:
                pass
            return True

        # ── node helpers ───────────────────────────────────────────────

        @staticmethod
        def _get_rect_key(node):
            if not node:
                return None
            try:
                oid = node.getObjectId()
                if oid is not None:
                    return "oid_" + str(int(oid))
            except Exception:
                pass
            try:
                key = node.getUniquePath()
                if key:
                    return key
            except Exception:
                pass
            try:
                name = node.getName()
                if name:
                    return name
            except Exception:
                pass
            return str(id(node))

        def _store_rect_scale(self, rect):
            pass  # hover/scale tracking removed with distanceFunc

        # ── eraser timer callback ──────────────────────────────────────

        def _eraser_tick(self):
            """Called by eraserTimer while eraser mode is active.
            Uses world-space distance between controller and VNR_ nodes.
            pick() raycast is not used here: it requires the controller to
            point at a node from a distance and fails for physical proximity."""
            try:
                ctrl_pos = getTransformNodeTranslation(
                    self.rightController.getNode(), 1)
                cx, cy, cz = ctrl_pos.x(), ctrl_pos.y(), ctrl_pos.z()
            except Exception:
                return
            in_range_now = set()
            for node in self._get_all_voice_note_nodes():
                key = self._get_rect_key(node)
                if not key:
                    continue
                try:
                    p = getTransformNodeTranslation(node, 1)
                    dx = p.x() - cx
                    dy = p.y() - cy
                    dz = p.z() - cz
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    if dist <= VoiceNotes._TOUCH_DIST:
                        if key not in self._eraser_in_range:
                            # 首次进入范围 → 删除 annotation 及节点
                            print("首次进入范围 → 删除 annotation 及节点")
                            print(self._rect_annotations)
                            print(key)
                            ann = self._rect_annotations.get(key)
                            print(ann)
                            print("[VoiceNotes] 橡皮擦范围内: " + str(key) + " (距离: {:.1f} mm)".format(dist))
                            if ann:
                                try:
                                    print("[VoiceNotes] 删除标注: " + str(self._rect_labels.get(key, "unknown")))
                                    vrAnnotationService.deleteAnnotation(ann)
                                except Exception:
                                    pass
                            for d in (self._rect_audio_paths, self._rect_base_scales,
                                        self._rect_annotations, self._rect_labels,
                                        self._voice_note_nodes):
                                d.pop(key, None)
                            deleteNode(node, True)
                            print("[VoiceNotes] 橡皮擦删除: " + str(key))
                        else:
                            # 仍在范围内，防止离开后重入时重复删除
                            in_range_now.add(key)
                except Exception:
                    pass
            self._eraser_in_range = in_range_now

        def _activate_eraser(self):
            """QTimer single-shot callback: long press threshold reached."""
            if not self._b_down or self._is_recording:
                # 录音中或 B 已松开，不切换模式
                self._b_down = False
                return
            self._eraser_held = True
            self._eraser_in_range.clear()
            try:
                findNode("CtrllrR_UI").fields().setInt32("choice", 9)
            except Exception:
                pass
            if not self._eraserTimerConnected:
                self._eraserTimer.connect(self._eraser_tick)
                self._eraserTimerConnected = True
            self._eraserTimer.setActive(1)
            print("[VoiceNotes] 长按B激活 → 橡皮擦模式")

        def _get_all_voice_note_nodes(self):
            if self._voice_note_nodes:
                return list(self._voice_note_nodes.values())
            result = []
            try:
                for node in getAllNodes():
                    try:
                        if node.getName().startswith("VNR_"):
                            result.append(node)
                    except Exception:
                        pass
            except Exception:
                pass
            return result

        # ── template / node creation ───────────────────────────────────

        def _ensure_voice_player_template(self):
            if self._voice_player_template is not None:
                try:
                    if not self._voice_player_template.isNull():
                        return self._voice_player_template
                except Exception:
                    pass
            tmpl = findNode("VoicePlayer")
            # tmpl.setActive(False)
            # setIsVRNode(tmpl, True)
            self._voice_player_template = tmpl
            return tmpl

        def _create_note_node(self, label, position=None, rotation=None):
            """Clone the VoicePlayer template, place it in the scene and register it."""
            if self._voice_player_template is None:
                print("[VoiceNotes] _create_note_node: VoicePlayer template not loaded")
                return None, None
            rect = cloneNode(self._voice_player_template, False)
            moveNode(rect, rect.getParent(), getRootNode())
            rect.setActive(True)
            # setIsVRNode(rect, True)
            rect.setName("VNR_" + (label if label else "VoiceNode"))
            try:
                vrScenegraphService.clearSelection()
            except Exception:
                pass
            self._store_rect_scale(rect)
            if position:
                setTransformNodeTranslation(rect, position.x(), position.y(), position.z(), 1)
            if rotation:
                try:
                    setTransformNodeRotation(rect, rotation.x(), rotation.y(), rotation.z())
                except Exception:
                    pass
            key = self._get_rect_key(rect)
            print("key0: " + key)
            if key:
                self._voice_note_nodes[key] = rect
                if label:
                    self._rect_labels[key] = label
            return rect, None

        # ── recording ─────────────────────────────────────────────────

        def _start_recording(self, position=None, rotation=None):
            base_dir = os.path.join(tempfile.gettempdir(), "vred_voice_notes")
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(base_dir, "voice_note_" + ts + ".wav")
            recorder = self._ensure_recorder()
            recorder.setOutputLocation(QtCore.QUrl.fromLocalFile(path))
            recorder.record()
            self._is_recording = True
            self._current_rect = None
            self._current_annotation = None
            self._current_audio_path = path
            self._current_label = ts
            self._pending_position = position
            self._pending_rotation = rotation

        def _stop_recording(self):
            self._ensure_recorder().stop()
            self._is_recording = False
            label = self._current_label
            path = self._current_audio_path
            position = self._pending_position
            rotation = self._pending_rotation
            self._pending_position = None
            self._pending_rotation = None
            rect = None
            if label and path:
                rect, annotation = self._create_note_node(label, position, rotation)
                if rect:
                    key = self._get_rect_key(rect)
                    print("key4: " + str(key))
                    if key:
                        self._rect_audio_paths[key] = path
                        self._rect_labels[key] = label
            self._last_rect = rect
            self._last_audio_path = path
            self._current_rect = None
            self._current_annotation = None
            self._current_audio_path = None
            self._current_label = None

        # ── controller position helpers ────────────────────────────────

        def _get_controller_position(self, controller):
            try:
                return getTransformNodeTranslation(controller.getNode(), 1)
            except Exception:
                pass
            try:
                matrix = controller.getTrackingMatrix()
                if matrix:
                    col = matrix.column(3)
                    return Vec3f(col.x(), col.y(), col.z())
            except Exception:
                pass
            return None

        def _get_controller_forward_position(self, controller):
            px, py, pz = None, None, None
            try:
                pos = getTransformNodeTranslation(controller.getNode(), 1)
                px, py, pz = pos.x(), pos.y(), pos.z()
            except Exception:
                pass
            if px is None:
                try:
                    matrix = controller.getTrackingMatrix()
                    if matrix:
                        col = matrix.column(3)
                        px, py, pz = col.x(), col.y(), col.z()
                except Exception:
                    pass
            if px is None:
                return None
            offset = VoiceNotes._FORWARD_OFFSET
            try:
                hit = controller.pick()
                if hit and hit.hasHit():
                    pt = hit.getPoint()
                    dx, dy, dz = pt.x() - px, pt.y() - py, pt.z() - pz
                    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                    if dist > 1.0:
                        s = offset / dist
                        return Vec3f(px + dx*s, py + dy*s, pz + dz*s)
            except Exception:
                pass
            try:
                matrix = controller.getTrackingMatrix()
                if matrix:
                    col2 = matrix.column(2)
                    fx, fy, fz = -col2.x(), -col2.y(), -col2.z()
                    length = math.sqrt(fx*fx + fy*fy + fz*fz)
                    if length > 0.0001:
                        s = offset / length
                        return Vec3f(px + fx*s, py + fy*s, pz + fz*s)
            except Exception:
                pass
            return Vec3f(px, py, pz)

        # ── custom controller ──────────────────────────────────────────

        def _find_or_load_voice_controller(self):
            return findNode("MRcontrollerRight")

        def _activate_voice_controller(self):
            self.newRightCon = self._find_or_load_voice_controller()
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            findNode("CtrllrR_UI").fields().setInt32("choice", 7)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.voiceControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)

        def _deactivate_voice_controller(self):
            try:
                if self.voiceControllerConstraint:
                    vrConstraintService.deleteConstraint(self.voiceControllerConstraint)
                    self.voiceControllerConstraint = None
            except Exception:
                pass
            try:
                if self.newRightCon:
                    self.newRightCon.setActive(0)
            except Exception:
                pass
            try:
                self.rightController.setVisible(1)
                self.rightController.setEnabled(1)
            except Exception:
                pass

        # ── event handlers ─────────────────────────────────────────────

        def on_a_pressed(self, action_obj=None, device_obj=None):
            if self._is_recording:
                return
            # 确保 B 长按计时器不干扰录音
            self._bTimer.stop()
            self._b_down = False
            findNode("CtrllrR_UI").fields().setInt32("choice", 8)
            self._start_recording(None, None)
            print("[VoiceNotes] A pressed → 开始录音")

        def on_a_released(self, action_obj=None, device_obj=None):
            if self._is_recording:
                pos = None
                rot = None
                try:
                    mrRight = findNode("MRcontrollerRight")
                    if mrRight:
                        wpos = mrRight.getWorldTranslation()
                        wrot = mrRight.getWorldRotation()
                        pos = Vec3f(wpos[0], wpos[1], wpos[2])
                        rot = Vec3f(wrot[0], wrot[1], wrot[2])
                except Exception:
                    pass
                if pos is None:
                    pos = self._get_controller_forward_position(self.rightController)
                self._pending_position = pos
                self._pending_rotation = rot
                self._stop_recording()
                findNode("CtrllrR_UI").fields().setInt32("choice", 7)
                print("[VoiceNotes] A released → 结束录音，位置: " + str(pos))

        def on_trigger_pressed(self, action_obj=None, device_obj=None):
            print("[VoiceNotes] Trigger pressed → 射线检测播放")
            if self._is_recording or self._eraser_held or self._grip_held:
                return
            # Raycast: find VNR_ node hit by right controller pointer
            hit_node = None
            try:
                hit = self.rightController.pick()
                if hit and hit.hasHit():
                    node = hit.getNode()
                    print("[VoiceNotes] Trigger hit node: " + str(node.getName() if node else "None"))
                    print(node)
                    while node and not node.isNull():
                        name = node.getName()
                        if name.startswith("VNR_"):
                            hit_node = node
                            break
                        node = node.getParent()
            except Exception as e:
                print("[VoiceNotes] trigger pick failed: " + str(e))
            if hit_node is None:
                print("[VoiceNotes] Trigger: 射线未命中可播放节点")
                return
            key = self._get_rect_key(hit_node)
            path = self._rect_audio_paths.get(key) if key else None
            # Fallback: derive audio path from node name (handles key mismatch and session restarts)
            if not path:
                try:
                    node_name = hit_node.getName()  # e.g. "VNR_20240319_123456"
                    if node_name.startswith("VNR_"):
                        ts = node_name[4:]  # strip "VNR_" prefix
                        base_dir = os.path.join(tempfile.gettempdir(), "vred_voice_notes")
                        candidate = os.path.join(base_dir, "voice_note_" + ts + ".wav")
                        if os.path.exists(candidate):
                            path = candidate
                            if key:  # restore mapping to avoid repeated fallback
                                self._rect_audio_paths[key] = path
                            print("[VoiceNotes] Fallback: 通过节点名恢复音频路径: " + candidate)
                        else:
                            print("[VoiceNotes] Fallback: 候选路径不存在: " + candidate)
                except Exception as e:
                    print("[VoiceNotes] Fallback lookup failed: " + str(e))
            if path:
                self._play_audio(path)
                print("[VoiceNotes] Trigger播放: " + str(path))
                ann = self._rect_annotations.get(key)
                if ann:
                    try:
                        ann.setText("Playing")
                    except Exception:
                        pass
            else:
                print("[VoiceNotes] Trigger命中节点但未找到音频 key=" + str(key))

        def on_b_pressed(self, action_obj=None, device_obj=None):
            # 录音中不启动橡皮擦
            if self._is_recording:
                return
            # 先确保 grip 拖动已停止，避免状态冲突
            if self._grip_held:
                self.on_grip_released()
            self._b_down = True
            self._eraser_in_range.clear()
            self._bTimer.start()  # 500 ms single-shot → _activate_eraser
            print("[VoiceNotes] B down → 等待长按激活橡皮擦 (0.5s)...")

        def on_b_released(self, action_obj=None, device_obj=None):
            self._b_down = False
            self._bTimer.stop()
            if self._eraser_held:
                self._eraser_held = False
                self._eraser_in_range.clear()
                self._eraserTimer.setActive(0)
                findNode("CtrllrR_UI").fields().setInt32("choice", 7)
                print("[VoiceNotes] B released → 橡皮擦停用")
            else:
                print("[VoiceNotes] B released → 未达长按阈值，忽略")

        def _poll_grip(self):
            try:
                state = self.rightController.getButtonState("grip")
                pressed = state.isPressed() or state.getPosition().x() >= self._GRIP_THRESHOLD
                if pressed and not self._gripHeld:
                    self._gripHeld = True
                    self.on_grip_pressed()
                elif not pressed and self._gripHeld:
                    self._gripHeld = False
                    self.on_grip_released()
            except Exception:
                pass

        def on_grip_pressed(self, action_obj=None, device_obj=None):
            if self._grip_held:
                return
            if self._drag_constraint is not None:
                try:
                    vrConstraintService.deleteConstraint(self._drag_constraint)
                except Exception:
                    pass
                self._drag_constraint = None
            # 使用近距离接触检测（与橡皮擦模式一致），不依赖射线命中
            best_node = None
            best_dist = VoiceNotes._TOUCH_DIST
            try:
                ctrl_pos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                cx, cy, cz = ctrl_pos.x(), ctrl_pos.y(), ctrl_pos.z()
                for node in self._get_all_voice_note_nodes():
                    try:
                        p = getTransformNodeTranslation(node, 1)
                        dx = p.x() - cx
                        dy = p.y() - cy
                        dz = p.z() - cz
                        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                        if dist <= best_dist:
                            best_dist = dist
                            best_node = node
                    except Exception:
                        pass
            except Exception as e:
                print("[VoiceNotes] Grip proximity check failed: " + str(e))
            if best_node is None:
                print("[VoiceNotes] Grip: 范围内无可拖动节点 (TOUCH_DIST=%.1f mm)" % VoiceNotes._TOUCH_DIST)
                return
            try:
                self._drag_constraint = vrConstraintService.createParentConstraint(
                    [self.rightController.getNode()], best_node, False)
                self._grip_held = True
                self._dragging_node = best_node
                findNode("CtrllrR_UI").fields().setInt32("choice", 10)
                print("[VoiceNotes] Grip → 开始拖动: " + best_node.getName())
            except Exception as e:
                print("[VoiceNotes] Grip → createParentConstraint 失败: " + str(e))

        def on_grip_released(self, action_obj=None, device_obj=None):
            if self._drag_constraint is not None:
                try:
                    vrConstraintService.deleteConstraint(self._drag_constraint)
                except Exception:
                    pass
                self._drag_constraint = None
            self._grip_held = False
            self._dragging_node = None
            findNode("CtrllrR_UI").fields().setInt32("choice", 7)
            print("[VoiceNotes] Grip released → 停止拖动")

        # ── lifecycle ──────────────────────────────────────────────────

        def enable(self):
            self.isEnabled = True
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
            # Hide stream panel when tool is activated
            global _stream_panel_visible
            _stream_panel_visible = False
            _sp_hide()
            self.multi.setSupportedInteractionGroups(["VoiceNotesGroup"])
            vrDeviceService.setActiveInteractionGroup("VoiceNotesGroup")
            self.aPressedAction.signal().triggered.connect(self.on_a_pressed)
            self.aReleasedAction.signal().triggered.connect(self.on_a_released)
            self.bPressedAction.signal().triggered.connect(self.on_b_pressed)
            self.bReleasedAction.signal().triggered.connect(self.on_b_released)
            self.triggerPressedAction.signal().triggered.connect(self.on_trigger_pressed)
            # grip 轮询 timer（与 AdjustTool / SectionTool 一致）
            if not self._gripTimerConnected:
                self._gripTimer.connect(self._poll_grip)
                self._gripTimerConnected = True
            self._gripTimer.setActive(1)
            print("[VoiceNotes] grip polling timer active")
            self._ensure_voice_player_template()
            self._activate_voice_controller()
            print("[AllTools] VoiceNotes enabled (A=录音, B长按=橡皮擦, Grip+射线=移动, Trigger+射线=播放)")

        def disable(self):
                self.isEnabled = False
                try:
                    self.multi.setSupportedInteractionGroups([])
                except Exception:
                    pass
                try:
                    if vred_tool_registry.get(self.registry_key) is self:
                        del vred_tool_registry[self.registry_key]
                except Exception:
                    pass
                try:
                    self.aPressedAction.signal().triggered.disconnect(self.on_a_pressed)
                except Exception:
                    pass
                try:
                    self.aReleasedAction.signal().triggered.disconnect(self.on_a_released)
                except Exception:
                    pass
                try:
                    self.bPressedAction.signal().triggered.disconnect(self.on_b_pressed)
                except Exception:
                    pass
                try:
                    self.bReleasedAction.signal().triggered.disconnect(self.on_b_released)
                except Exception:
                    pass
                try:
                    self.triggerPressedAction.signal().triggered.disconnect(self.on_trigger_pressed)
                except Exception:
                    pass
                try:
                    self._gripTimer.setActive(0)
                except Exception:
                    pass
                self._gripHeld = False
                if self._drag_constraint is not None:
                    try:
                        vrConstraintService.deleteConstraint(self._drag_constraint)
                    except Exception:
                        pass
                    self._drag_constraint = None
                self._grip_held = False
                self._dragging_node = None
                self._eraser_held = False
                self._b_down = False
                self._bTimer.stop()
                self._eraser_in_range.clear()
                self._eraserTimer.setActive(0)
                self._is_recording = False
                if self._is_recording:
                    try:
                        self._stop_recording()
                    except Exception:
                        pass
                self._deactivate_voice_controller()
                print("[AllTools] VoiceNotes disabled (A=录音, B长按=橡皮擦, Grip+射线=移动, Trigger+射线=播放)")

    # ======================================================================
    # LeftGripTraction - 左手柄 Grip 牵引（全局常驻，不随工具切换）
    # ======================================================================
    class LeftGripTraction:
        """
        左手柄 Grip 牵引 —— 全局常驻，不随工具切换而开关。
        按住左手 grip 移动控制器，场景随之平移（反向，放大 TRACTION_SCALE 倍）。
        参考 fly.py 的 grip0Pressed + isGripPressed 分支实现。
        """
        TRACTION_SCALE = 2.0
        _GRIP_THRESHOLD = 0.5

        def __init__(self):
            self._held = False
            self._basePos = None        # 按下时左手柄位置 (x, y, z)
            self._originBase = None     # 按下时 tracking origin (x, y, z)
            self._gripHeld = False      # polling 状态
            self._leftController = vrDeviceService.getVRDevice("left-controller")
            self._timer = vrTimer()
            self._timer.connect(self._tick)
            self._timer.setActive(1)
            print("[LeftGripTraction] started (left grip = traction)")

        def _is_locomotion(self):
            try:
                return _tool_manager.get_active() is None
            except Exception:
                return True

        def _tick(self):
            if not self._is_locomotion():
                # 非 Locomotion 状态：释放牵引，不做任何移动
                if self._gripHeld or self._held:
                    self._gripHeld = False
                    self._held = False
                    self._basePos = None
                    self._originBase = None
                return
            try:
                state = self._leftController.getButtonState("grip")
                pressed = state.isPressed() or state.getPosition().x() >= self._GRIP_THRESHOLD
                if pressed and not self._gripHeld:
                    self._gripHeld = True
                    self._on_pressed()
                elif not pressed and self._gripHeld:
                    self._gripHeld = False
                    self._on_released()
                if self._held and self._basePos is not None:
                    self._do_traction()
            except Exception as e:
                print("[LeftGripTraction] tick ERROR: " + str(e))

        def _on_pressed(self):
            try:
                mat = self._leftController.getTrackingMatrix()
                col = mat.column(3)
                self._basePos = (col.x(), col.y(), col.z())
                origin = vrDeviceService.getTrackingOrigin()
                self._originBase = (origin.x(), origin.y(), origin.z())
                self._held = True
                print("[LeftGripTraction] grip pressed")
            except Exception as e:
                print("[LeftGripTraction][PRESS] ERROR: " + str(e))
                self._basePos = None
                self._originBase = None

        def _on_released(self):
            self._held = False
            self._basePos = None
            self._originBase = None
            print("[LeftGripTraction] grip released")

        def _do_traction(self):
            try:
                mat = self._leftController.getTrackingMatrix()
                col = mat.column(3)
                dx = col.x() - self._basePos[0]
                dy = col.y() - self._basePos[1]
                dz = col.z() - self._basePos[2]
                vrDeviceService.setTrackingOrigin(QVector3D(
                    self._originBase[0] - self.TRACTION_SCALE * dx,
                    self._originBase[1] - self.TRACTION_SCALE * dy,
                    self._originBase[2] - self.TRACTION_SCALE * dz,
                ))
            except Exception as e:
                print("[LeftGripTraction] ERROR: " + str(e))

    # ======================================================================
    # LocomotionMode - Locomotion 状态下右手柄飞行 + 截图
    # ======================================================================
    class LocomotionMode:
        """
        Locomotion 状态下右手柄交互（全局常驻，只在无工具激活时生效）：
        - Grip: 飞行模式（与 GripFlyMixin 一致）
        - A 键: 截图，保存到 \\\\192.167.7.80\\upload\\screenshot
        """
        SCREENSHOT_DIR  = r"\\192.167.7.80\upload\screenshot"
        FLY_SPEED       = 0.35
        FLY_ACCEL       = 0.015
        FLY_DEAD_ZONE   = 20.0
        FLY_MAX_STEP    = 45.0
        _GRIP_THRESHOLD = 0.5

        def __init__(self):
            self._right      = vrDeviceService.getVRDevice("right-controller")
            self._flyHeld    = False
            self._flyBasePos = None
            self._gripHeld   = False

            # polling timer
            self._timer = vrTimer()
            self._timer.connect(self._tick)
            self._timer.setActive(1)

            # A 键绑定到 Locomotion 交互组
            try:
                _old_la = vrDeviceService.getInteraction("LocomotionActions")
                if _old_la.isValid():
                    vrDeviceService.removeInteraction(_old_la)
            except Exception:
                pass
            self._loco_interact  = vrDeviceService.createInteraction("LocomotionActions")
            self._loco_interact.setSupportedInteractionGroups(["Locomotion"])
            self._aPressedAction = self._loco_interact.createControllerAction("right-a-pressed")
            self._aPressedAction.signal().triggered.connect(self._take_screenshot)
            print("[LocomotionMode] started (right grip=fly, right A=screenshot)")

        def _is_locomotion(self):
            try:
                return _tool_manager.get_active() is None
            except Exception:
                return True

        def _tick(self):
            if not self._is_locomotion():
                if self._flyHeld or self._gripHeld:
                    self._flyHeld    = False
                    self._flyBasePos = None
                    self._gripHeld   = False
                return
            try:
                state   = self._right.getButtonState("grip")
                pressed = state.isPressed() or state.getPosition().x() >= self._GRIP_THRESHOLD
                if pressed and not self._gripHeld:
                    self._gripHeld = True
                    self._on_grip_pressed()
                elif not pressed and self._gripHeld:
                    self._gripHeld = False
                    self._on_grip_released()
            except Exception:
                pass
            self._fly_tick()

        def _on_grip_pressed(self):
            self._flyHeld = True
            try:
                mat = self._right.getTrackingMatrix()
                col = mat.column(3)
                self._flyBasePos = (col.x(), col.y(), col.z())
            except Exception as e:
                print("[LocomotionMode][GRIP] ERROR: " + str(e))
                self._flyBasePos = None

        def _on_grip_released(self):
            self._flyHeld    = False
            self._flyBasePos = None

        def _fly_tick(self):
            if not (self._flyHeld and self._flyBasePos is not None):
                return
            try:
                mat  = self._right.getTrackingMatrix()
                col  = mat.column(3)
                dx   = col.x() - self._flyBasePos[0]
                dy   = col.y() - self._flyBasePos[1]
                dz   = col.z() - self._flyBasePos[2]
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist > self.FLY_DEAD_ZONE:
                    d     = dist - self.FLY_DEAD_ZONE
                    speed = self.FLY_SPEED + d * self.FLY_ACCEL + d * d * 0.0006
                    speed = min(speed, self.FLY_MAX_STEP)
                    nx, ny, nz = dx/dist, dy/dist, dz/dist
                    origin = vrDeviceService.getTrackingOrigin()
                    vrDeviceService.setTrackingOrigin(QVector3D(
                        origin.x() - nx * speed,
                        origin.y() - ny * speed,
                        origin.z() - nz * speed,
                    ))
            except Exception as e:
                print("[LocomotionMode][FLY] ERROR: " + str(e))

        def _take_screenshot(self, action=None, device=None):
            if not self._is_locomotion():
                return
            try:
                if not os.path.exists(self.SCREENSHOT_DIR):
                    os.makedirs(self.SCREENSHOT_DIR)
                ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(self.SCREENSHOT_DIR, "screenshot_" + ts + ".png")
                vrRenderService.renderToFile(path)
                print("[LocomotionMode] Screenshot saved: " + path)
            except Exception as e:
                print("[LocomotionMode] Screenshot failed: " + str(e))

    # ======================================================================
    # 工具管理器 + 全局 API
    # ======================================================================
    class _ToolManager:
        def __init__(self):
            self.tools = {}
            self.active_tool = None

        def register(self, name, tool_instance):
            self.tools[name] = tool_instance

        def switch(self, name):
            if name not in self.tools:
                print("[AllTools] Unknown tool: " + str(name))
                return False
            # 当前工具先禁用 (enable 中也会禁用其他工具，但显式调用更安全)
            if self.active_tool and self.active_tool in self.tools:
                try:
                    self.tools[self.active_tool].disable()
                except Exception:
                    pass
            # 启用目标工具
            self.active_tool = name  # 先设置，确保 enable() 期间 get_active() 已返回正确值
            try:
                self.tools[name].enable()
                print("[AllTools] Switched to: " + str(name))
                return True
            except Exception as e:
                print("[AllTools] Failed to switch to " + str(name) + ": " + str(e))
                return False

        def disable_all(self):
            for name, tool in list(self.tools.items()):
                try:
                    tool.disable()
                except Exception:
                    pass
            self.active_tool = None
            print("[AllTools] All tools disabled")

        def get_active(self):
            return self.active_tool

    # --- 实例化所有工具 (但不激活) ---
    global _tool_manager
    _tool_manager = _ToolManager()

    try:
        _tool_manager.register("adjust", AdjustTool())
        print("[AllTools] AdjustTool registered")
    except Exception as e:
        print("[AllTools] Failed to register AdjustTool: " + str(e))

    try:
        _tool_manager.register("draw_note", Notes())
        print("[AllTools] Notes (draw_note) registered")
    except Exception as e:
        print("[AllTools] Failed to register Notes: " + str(e))

    try:
        _tool_manager.register("section", SectionTool())
        print("[AllTools] SectionTool registered")
    except Exception as e:
        print("[AllTools] Failed to register SectionTool: " + str(e))

    try:
        _tool_manager.register("turntable", TurntableTool())
        print("[AllTools] TurntableTool registered")
    except Exception as e:
        print("[AllTools] Failed to register TurntableTool: " + str(e))

    try:
        _tool_manager.register("measure", MeasureTool())
        print("[AllTools] MeasureTool registered")
    except Exception as e:
        print("[AllTools] Failed to register MeasureTool: " + str(e))

    try:
        _tool_manager.register("flashlight", FlashlightTool())
        print("[AllTools] FlashlightTool registered")
    except Exception as e:
        print("[AllTools] Failed to register FlashlightTool: " + str(e))

    try:
        _tool_manager.register("voice_note", VoiceNotes())
        print("[AllTools] VoiceNotes registered")
    except Exception as e:
        print("[AllTools] Failed to register VoiceNotes: " + str(e))

    # --- 左手柄 Grip 牵引（全局常驻，只在 Locomotion 状态生效）---
    global _left_grip_traction
    try:
        _left_grip_traction = LeftGripTraction()
    except Exception as e:
        print("[AllTools] Failed to start LeftGripTraction: " + str(e))

    # --- Locomotion 模式右手柄（飞行 + 截图，全局常驻）---
    global _locomotion_mode
    try:
        _locomotion_mode = LocomotionMode()
    except Exception as e:
        print("[AllTools] Failed to start LocomotionMode: " + str(e))

    # --- 全局 Teleport 绑定 ---
    # try:
    #     _jump_tele = vrDeviceService.getInteraction("Teleport")
    #     _jump_tele.setControllerActionMapping("prepare", "any-{}-touched".format(_pad_input))
    #     _jump_tele.setControllerActionMapping("abort",   "any-{}-untouched".format(_pad_input))
    #     _jump_tele.setControllerActionMapping("execute",  "any-{}-pressed".format(_pad_input))
    #     print("[AllTools] 全局 Teleport 已绑定 (any-{})".format(_pad_input))
    # except Exception as e:
    #     print("[AllTools] 全局 Teleport 绑定失败: " + str(e))

    _all_tools_initialized = True
    print("[AllTools] All tools initialized. Use switch_tool(name) to activate.")

# --- 全局 API 函数 ---
def switch_tool(name):
    """切换到指定工具。name 可选: adjust, draw_note, section, turntable, measure, flashlight, voice_note"""
    global _tool_manager
    return _tool_manager.switch(name)

def disable_all_tools():
    """禁用所有工具"""
    global _tool_manager
    _tool_manager.disable_all()

def get_active_tool():
    """获取当前激活的工具名称"""
    global _tool_manager
    return _tool_manager.get_active()

def cleanup_all_tools():
    """完全清除: 禁用所有工具 + 删除脚本创建的所有场景节点 + 重置状态"""
    global _tool_manager, _all_tools_initialized
    global vred_tool_registry
    global refObject, Cloned_ref_obj

    # 1. 禁用所有工具
    try:
        _tool_manager.disable_all()
    except Exception:
        pass

    # 2. 删除脚本创建/加载的所有场景节点
    _nodes_to_remove = [
        "MRcontrollerLeft",
        "MRcontrollerRight",
        "MR_Stuff",
        "Cloned_ref_obj",
        "VR_Flashlight",
    ]

    for nodeName in _nodes_to_remove:
        try:
            nodes = findNodes(nodeName)
            for n in nodes:
                if n and not n.isNull():
                    try:
                        deleteNode(n, True)
                    except Exception:
                        pass
        except Exception:
            pass

    # 3. 清除剖面状态
    try:
        setClippingEnabled(False)
        setClippingShowManipulator(0)
        setClippingGridVisualization(0, Vec3f(1, 1, 1))
        setClippingPlaneVisualization(0, Vec3f(0.16, 0.16, 0.28))
        setClippingContourVisualization(0, Vec3f(0, 0, 0))
    except Exception:
        pass

    # 4. 清除所有测量
    try:
        removeAllMeasurements()
    except Exception:
        try:
            vrSessionService.sendPython("removeAllMeasurements()")
        except Exception:
            pass

    # 5. 清除所有注释 (VoiceNotes 创建的)
    try:
        annotations = vrAnnotationService.getAnnotations()
        for ann in annotations:
            try:
                vrAnnotationService.removeAnnotation(ann)
            except Exception:
                pass
    except Exception:
        pass

    # 6. 恢复默认交互
    try:
        vrImmersiveInteractionService.setDefaultInteractionsActive(1)
        vrDeviceService.setActiveInteractionGroup("Locomotion")
    except Exception:
        pass

    # 7. 重置全局变量
    try:
        refObject = None
        Cloned_ref_obj = None
    except Exception:
        pass

    # 8. 清空注册表并标记未初始化，允许重新注入
    vred_tool_registry = {}
    _tool_manager = _ToolManager()
    _all_tools_initialized = False
    # 清除 interaction 和 guard 标记，允许重新初始化
    _sp_geom_node = None
    if '_sp_interaction' in globals():
        del globals()['_sp_interaction']
    if '_left_x_return_guard' in globals():
        del globals()['_left_x_return_guard']

    print("[AllTools] Full cleanup complete. All tools disabled, all nodes removed, state reset.")

print("[AllTools] Script loaded. Available commands: switch_tool(name), disable_all_tools(), get_active_tool(), cleanup_all_tools()")

# ======================================================================
# 串流面板 + X 键守卫 — 仅首次注入时初始化
# OpenXR action set 在会话启动后锁定，重注入时不可再创建新 action。
# ======================================================================
global _stream_panel_url, _stream_panel_visible, _sp_geom_node
if '_stream_panel_url' not in globals():
    _stream_panel_url = globals().get('_STREAM_PANEL_URL', '')
if '_stream_panel_visible' not in globals():
    _stream_panel_visible = False
if '_sp_geom_node' not in globals():
    _sp_geom_node = None

_SP_NODE_NAME   = "MenuPanel_L"
_SP_ENGINE_NAME = "MRmenu"

def _sp_build():
    """找到 OSB 中已有的 MenuPanel_L 节点，设置 WebEngine URL，初始隐藏。"""
    global _sp_geom_node
    node = findNode(_SP_NODE_NAME)
    if not node:
        print("[StreamPanel] ERROR: node '" + _SP_NODE_NAME + "' not found in scene")
        return
    try:
        if node.isNull():
            print("[StreamPanel] ERROR: node '" + _SP_NODE_NAME + "' is null")
            return
    except AttributeError:
        pass  # vrNodePtr 无 isNull()，跳过检查
    _sp_geom_node = node

    # 设置 URL：直接按媒体编辑器中的 WebEngine 名称查找
    if _stream_panel_url:
        _url_set = False
        try:
            eng = vrWebEngineService.getWebEngine(_SP_ENGINE_NAME)
            if eng.isValid():
                eng.setUrl(_stream_panel_url)
                print("[StreamPanel] URL set on '" + _SP_ENGINE_NAME + "': " + _stream_panel_url)
                _url_set = True
        except Exception as _e:
            print("[StreamPanel] getWebEngine failed: " + str(_e))
        if not _url_set:
            # 兜底：遍历所有 WebEngine 找绑定到该节点材质的那个
            try:
                geo = vrdGeometryNode(node)
                mat = geo.getMaterial()
                if mat and mat.isValid():
                    for _eng in vrWebEngineService.getWebEngines():
                        try:
                            if _eng.getMaterial().getObjectId() == mat.getObjectId():
                                _eng.setUrl(_stream_panel_url)
                                print("[StreamPanel] URL set via material match: " + _stream_panel_url)
                                _url_set = True
                                break
                        except Exception:
                            pass
            except Exception as _e2:
                print("[StreamPanel] material fallback failed: " + str(_e2))
        if not _url_set:
            print("[StreamPanel] WARNING: could not set URL, no matching WebEngine found")

    # 初始隐藏
    node.setActive(False)
    print("[StreamPanel] ready. Node: " + _SP_NODE_NAME)

def _sp_show():
    """激活 MRmenu 节点（位置由 OSB 约束控制）。"""
    global _sp_geom_node
    if _sp_geom_node is None:
        _sp_build()
    if _sp_geom_node is None:
        print("[StreamPanel] show failed: node not available")
        return
    _sp_geom_node.setActive(True)
    print("[StreamPanel] shown")

def _sp_hide():
    """隐藏 MRmenu 节点。"""
    global _sp_geom_node
    try:
        if _sp_geom_node is not None:
            _sp_geom_node.setActive(False)
    except Exception:
        pass
    print("[StreamPanel] hidden")

def _sp_toggle():
    global _stream_panel_visible
    _stream_panel_visible = not _stream_panel_visible
    if _stream_panel_visible:
        _sp_show()
    else:
        _sp_hide()

# 注入时初始化（找节点、设 URL、隐藏）——仅首次执行
if _sp_geom_node is None:
    _sp_build()

# 以下 interaction 注册仅首次注入时执行（OpenXR action set 会话中锁定，不可重建）
# 每次注入都执行——确保 Tools Menu 始终被真正禁用
# 注意: setSupportedInteractionGroups([]) 在 VRED 中等同于"所有组"，必须用不存在的组名才能禁用
try:
    _toolsMenu = vrDeviceService.getInteraction("Tools Menu")
    _toolsMenu.setSupportedInteractionGroups(["__disabled__"])
    print("[StreamPanel] Tools Menu disabled (Y key freed)")
except Exception as _tme:
    print("[StreamPanel] Tools Menu disable failed: " + str(_tme))

# X / Y 按键通过 _LeftXReturnGuard 轮询处理（OpenXR left-x-pressed 会同时触发 left-y-pressed）
# StreamPanelToggle createInteraction 不再需要

def _to_locomotion():
    """禁用所有工具，切换回 Locomotion 状态。"""
    global _stream_panel_visible
    try:
        _tool_manager.disable_all()
    except Exception:
        pass
    try:
        vrDeviceService.setActiveInteractionGroup("Locomotion")
    except Exception:
        pass
    if _stream_panel_visible:
        _sp_hide()
        _stream_panel_visible = False
    print("[AllTools] Returned to Locomotion (X key)")


class _LeftXReturnGuard:
    """
    左手柄 X / Y 键轮询 (OpenXR createControllerAction 存在 X→Y 串扰 bug)。
    X: 任意工具状态下返回 Locomotion
    Y: Locomotion 状态下切换串流面板
    """

    def __init__(self):
        self._xHeld = False
        self._yHeld = False
        self._leftController = vrDeviceService.getVRDevice("left-controller")
        self._pollTimer = vrTimer()
        self._pollTimer.connect(self._poll_xy)
        self._pollTimer.setActive(1)
        print("[AllTools] LeftXReturnGuard ready (polling, X=locomotion, Y=stream panel)")

    def _now_ms(self):
        try:
            return int(QtCore.QDateTime.currentMSecsSinceEpoch())
        except Exception:
            return 0

    def _poll_xy(self):
        try:
            x_pressed = self._leftController.getButtonState("xa").isPressed()
            if x_pressed and not self._xHeld:
                self._xHeld = True
                self._on_x()
            elif not x_pressed:
                self._xHeld = False
        except Exception:
            pass
        try:
            y_pressed = self._leftController.getButtonState("yb").isPressed()
            if y_pressed and not self._yHeld:
                self._yHeld = True
                self._on_y()
            elif not y_pressed:
                self._yHeld = False
        except Exception:
            pass

    def _on_x(self):
        try:
            active = _tool_manager.get_active()
        except Exception:
            active = None
        if active is None:
            return  # Locomotion 下不处理
        print("[AllTools] LocomotionReturn triggered (X)")
        _to_locomotion()

    def _on_y(self):
        _sp_toggle()


global _left_x_return_guard
if '_left_x_return_guard' not in globals():
    try:
        _left_x_return_guard = _LeftXReturnGuard()
    except Exception as _ex:
        print("[AllTools] LeftXReturnGuard init error: " + str(_ex))
