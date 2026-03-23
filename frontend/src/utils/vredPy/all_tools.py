# ======================================================================
# VRED MR Tools - Unified Script
# 一次注入所有工具，通过 switch_tool(name) 切换当前生效的工具
# 可用工具: adjust, draw_note, section, turntable, measure, voice_note, flashlight
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
        refObject = findNode("MR_Stuff").getChild(0)    # first tag style child (tag_Move)
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
    # AdjustTool - 地平面移动工具
    # ------------------------------------------------------------------
    class AdjustTool:
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
            self._flyHeld = False
            self._flyBasePos = None
            self._flyVelX = 0.0
            self._flyVelY = 0.0
            self._flyVelZ = 0.0
            self.flySpeed = 3.0    # 手柄位移放大倍率（可调）
            self._flyAlpha = 0.3   # EMA 平滑系数
            self._flyDeadZone = 20.0  # mm，低于此值视为抖动（2mm 太小易被手颤触发）
            self._flyMaxStep = 50.0  # 单帧最大位移 clamp（防飞出）

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

            teleport = vrDeviceService.getInteraction("Teleport")
            teleport.addSupportedInteractionGroup("AdjustGroup")
            teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
            teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
            teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

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

            # grip 通过 getButtonState 轮询（OpenXR squeeze 轴，运行时动态注册 action 无效）
            self._gripHeld = False
            self._GRIP_THRESHOLD = 0.5
            self._gripTimer = vrTimer()
            self._gripTimerConnected = False

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

            # --- Grip fly: 以握持起点为摇杆零点，手柄偏移方向即飞行方向 ---
            # getTrackingMatrix() 返回硬件原始追踪数据，不受 setTrackingOrigin 影响。
            # _flyBasePos 固定在按下 grip 时的手柄位置（摇杆中心），不随飞行更新。
            # 只要手柄保持偏离 base 超过死区，就持续飞行；松开 grip 才停止。
            if self._flyHeld and self._flyBasePos is not None:
                try:
                    mat = self.rightController.getTrackingMatrix()
                    col = mat.column(3)
                    cx, cy, cz = col.x(), col.y(), col.z()
                    dx = cx - self._flyBasePos[0]
                    dy = cy - self._flyBasePos[1]
                    dz = cz - self._flyBasePos[2]
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    self._flyDbgFrame = getattr(self, '_flyDbgFrame', 0) + 1
                    if self._flyDbgFrame % 30 == 1:
                        print("[Fly][DBG] cur_t=(%.1f,%.1f,%.1f)" % (cx, cy, cz))
                        print("[Fly][DBG] base_t=(%.1f,%.1f,%.1f)" % self._flyBasePos)
                        print("[Fly][DBG] delta=(%.1f,%.1f,%.1f)  dist=%.1f  deadzone=%.1f" % (dx, dy, dz, dist, self._flyDeadZone))
                    if dist > self._flyDeadZone:
                        speed = min((dist - self._flyDeadZone) * self.flySpeed, self._flyMaxStep)
                        nx, ny, nz = dx / dist, dy / dist, dz / dist
                        origin = vrDeviceService.getTrackingOrigin()
                        new_o = QVector3D(
                            origin.x() - nx * speed,
                            origin.y() - ny * speed,
                            origin.z() - nz * speed
                        )
                        if self._flyDbgFrame % 30 == 1:
                            print("[Fly][DBG] MOVE: speed=%.2f dir=(%.3f,%.3f,%.3f)" % (speed, nx, ny, nz))
                        vrDeviceService.setTrackingOrigin(new_o)
                        # base 不更新：手柄偏离 base 的量始终代表飞行意图，持续飞行
                except Exception as e:
                    print("[AdjustTool][Fly] ERROR: " + str(e))

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

            # (fly logic moved above node guard)

        def on_grip_pressed(self, action=None, device=None):
            self._flyHeld = True
            self._flyDbgFrame = 0
            try:
                mat = self.rightController.getTrackingMatrix()
                col = mat.column(3)
                # 以 tracking Y-Up 坐标作为 base，与 origin 同坐标系
                self._flyBasePos = (col.x(), col.y(), col.z())
                print("[Fly][PRESS] base_t=(%.1f,%.1f,%.1f)" % self._flyBasePos)
            except Exception as e:
                print("[Fly][PRESS] ERROR: " + str(e))
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

            # grip 轮询 timer
            if not self._gripTimerConnected:
                self._gripTimer.connect(self._poll_grip)
                self._gripTimerConnected = True
            self._gripTimer.setActive(1)
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
                self._flyHeld = False
                self._flyBasePos = None
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
            try:
                self._gripTimer.setActive(0)
                self._gripHeld = False
            except Exception:
                pass
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
        """
        _NOTE_TEMPLATE_NAMES = [
            "tag_Move",
            "tag_AlignCenter",
            "tag_Smile",
            "tag_Passed",
            "tag_Notice",
            "tag_AlignTo",
            "tag_Good",
            "tag_Flag",
            "tag_Cancel",
            "tag_MoreCurve",
        ]

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

            teleport = vrDeviceService.getInteraction("Teleport")
            teleport.addSupportedInteractionGroup("NotesGroup")
            teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
            teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
            teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

            self.triggerRightPressed = self.multiButtonPad.createControllerAction("right-trigger-pressed")
            self.aPressedAction = self.multiButtonPad.createControllerAction("right-a-pressed")
            self.bPressedAction = self.multiButtonPad.createControllerAction("right-b-pressed")

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("NotesGroup")

            self.registry_key = "tool_draw_note"

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

        def _get_note_templates(self):
            templates = []
            # 优先从 MR_Stuff 下取模板，避免拿到同名的非模板节点
            mr_stuff = None
            try:
                mr_stuff = findNode("MR_Stuff")
            except Exception:
                mr_stuff = None

            if self._node_exists(mr_stuff):
                for name in self._NOTE_TEMPLATE_NAMES:
                    child = None
                    try:
                        child = mr_stuff.findChild(name)
                    except Exception:
                        child = None
                    if self._node_exists(child):
                        templates.append(child)

            # 兜底：按名称全局查找
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
            # 精确同步 TagAdd_R/TagAdd/TagIconSwitch
            tag_switch = None
            try:
                tag_add_r = findNode("TagAdd_R")
                if self._node_exists(tag_add_r):
                    tag_add = tag_add_r.findChild("TagAdd")
                    if self._node_exists(tag_add):
                        tag_switch = tag_add.findChild("TagIconSwitch")
            except Exception:
                tag_switch = None

            # 兜底全局查找
            if not tag_switch:
                try:
                    tag_switch = findNode("TagIconSwitch")
                except Exception:
                    tag_switch = None

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
            refObject = templates[self.currentNoteIndex]
            self._sync_tag_icon_switch(self.currentNoteIndex)
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
            global refObject
            global Cloned_ref_obj
            templates = self._get_note_templates()
            if not templates:
                return
            try:
                # 使用当前样式对应模板作为克隆源
                refObject = templates[self.currentNoteIndex % len(templates)]
                tag_add_r = findNode("TagAdd_R")
                if not self._node_exists(tag_add_r):
                    return
                node_num = random.randint(0, 1000000)
                current_position = getTransformNodeTranslation(tag_add_r, True)
                current_rotation = getTransformNodeRotation(tag_add_r)
                current_scale = getTransformNodeScale(refObject)

                name_string = "%s" % refObject.getName()
                pos_string = "%f,%f,%f" % (current_position.x(), current_position.y(), current_position.z())
                rot_string = "%f,%f,%f" % (current_rotation.x(), current_rotation.y(), current_rotation.z())
                scale_string = "%f,%f,%f" % (current_scale.x(), current_scale.y(), current_scale.z())

                vrSessionService.sendPython('clonedRef = cloneNode(findNode("' + name_string + '"), False)')
                vrSessionService.sendPython('clonedRef.setName("' + name_string + '_' + str(node_num) + '")')
                vrSessionService.sendPython('moveNode(clonedRef, clonedRef.getParent(), getRootNode())')
                vrSessionService.sendPython('setTransformNodeRotation(clonedRef, ' + rot_string + ')')
                vrSessionService.sendPython('setTransformNodeTranslation(clonedRef, ' + pos_string + ', True)')
                vrSessionService.sendPython('setTransformNodeScale(clonedRef, ' + scale_string + ')')
                vrSessionService.sendPython('addNodeTag(clonedRef, "Cloned Note")')
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
            self.multiButtonPad.setSupportedInteractionGroups(["NotesGroup"])
            vrDeviceService.setActiveInteractionGroup("NotesGroup")

            self.triggerRightPressed.signal().triggered.connect(self.trigger_right_pressed)
            self.aPressedAction.signal().triggered.connect(self.toggleDeleteMode)
            self.bPressedAction.signal().triggered.connect(self.ChangeNote)
            self.pointer.getControllerAction("start").signal().triggered.connect(self._on_pointer_start)
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
            print("[AllTools] Notes enabled")

        def disable(self):
            self.isEnabled = False
            try:
                self.multiButtonPad.setSupportedInteractionGroups([])
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
                self.aPressedAction.signal().triggered.disconnect(self.toggleDeleteMode)
            except Exception:
                pass
            try:
                self.bPressedAction.signal().triggered.disconnect(self.ChangeNote)
            except Exception:
                pass
            try:
                self.pointer.getControllerAction("start").signal().triggered.disconnect(self._on_pointer_start)
            except Exception:
                pass
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
            if not self.deleteNoteIsActive:
                self._enter_delete_mode()
            else:
                self._enter_default_mode()

        def ChangeNote(self):
            if self.deleteNoteIsActive or not self.isAddMode:
                return
            templates = self._get_note_templates()
            if not templates:
                return
            self._set_note_style(self.currentNoteIndex + 1)

    # ------------------------------------------------------------------
    # SectionTool - 剖面工具
    # ------------------------------------------------------------------
    class SectionTool:
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

            teleport = vrDeviceService.getInteraction("Teleport")
            teleport.addSupportedInteractionGroup("ClipGroup")
            teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
            teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
            teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("ClipGroup")

            self.triggerRightPressed = multiButtonPadClip.createControllerAction("right-trigger-pressed")
            self.triggerRightReleased = multiButtonPadClip.createControllerAction("right-trigger-released")
            self.aPressedAction = multiButtonPadClip.createControllerAction("right-a-pressed")
            self.bPressedAction = multiButtonPadClip.createControllerAction("right-b-pressed")

            self.registry_key = "tool_section"
            self.newRightCon = None
            self.ClipControllerConstraint = None

            # grip 飞行模式（与 AdjustTool 一致）
            self._flyHeld = False
            self._flyBasePos = None
            self._flyVelX = 0.0
            self._flyVelY = 0.0
            self._flyVelZ = 0.0
            self.flySpeed = 3.0
            self._flyAlpha = 0.3
            self._flyDeadZone = 20.0
            self._flyMaxStep = 50.0
            self._gripHeld = False
            self._GRIP_THRESHOLD = 0.5
            self._gripTimer = vrTimer()
            self._gripTimerConnected = False

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

        def on_grip_pressed(self, action=None, device=None):
            self._flyHeld = True
            self._flyDbgFrame = 0
            try:
                mat = self.rightController.getTrackingMatrix()
                col = mat.column(3)
                self._flyBasePos = (col.x(), col.y(), col.z())
                print("[Fly][SectionTool][PRESS] base_t=(%.1f,%.1f,%.1f)" % self._flyBasePos)
            except Exception as e:
                print("[Fly][SectionTool][PRESS] ERROR: " + str(e))
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

        def _update_loop(self):
            if self.triggerHeld and self.clipping:
                self._apply_clipping_plane()

            # --- Grip fly（与 AdjustTool 逻辑一致）---
            if self._flyHeld and self._flyBasePos is not None:
                try:
                    mat = self.rightController.getTrackingMatrix()
                    col = mat.column(3)
                    cx, cy, cz = col.x(), col.y(), col.z()
                    dx = cx - self._flyBasePos[0]
                    dy = cy - self._flyBasePos[1]
                    dz = cz - self._flyBasePos[2]
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    self._flyDbgFrame = getattr(self, '_flyDbgFrame', 0) + 1
                    if self._flyDbgFrame % 30 == 1:
                        print("[Fly][SectionTool] cur=(%.1f,%.1f,%.1f) base=(%.1f,%.1f,%.1f) dist=%.1f" % (
                            cx, cy, cz,
                            self._flyBasePos[0], self._flyBasePos[1], self._flyBasePos[2],
                            dist))
                    if dist > self._flyDeadZone:
                        speed = min((dist - self._flyDeadZone) * self.flySpeed, self._flyMaxStep)
                        nx, ny, nz = dx / dist, dy / dist, dz / dist
                        origin = vrDeviceService.getTrackingOrigin()
                        new_o = QVector3D(
                            origin.x() - nx * speed,
                            origin.y() - ny * speed,
                            origin.z() - nz * speed
                        )
                        vrDeviceService.setTrackingOrigin(new_o)
                except Exception as e:
                    print("[SectionTool][Fly] ERROR: " + str(e))

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
            setClippingShowManipulator(0)
            try:
                setClippingContourVisualization(0, Vec3f(0, 0, 0), 0)
            except Exception:
                pass
            vrDeviceService.setActiveInteractionGroup("ClipGroup")

            self.triggerRightPressed.signal().triggered.connect(self.on_trigger_pressed)
            self.triggerRightReleased.signal().triggered.connect(self.on_trigger_released)
            self.aPressedAction.signal().triggered.connect(self.toggle_clipping)
            self.bPressedAction.signal().triggered.connect(self.toggle_flipped)

            if not self.timerConnected:
                self.timer.connect(self._update_loop)
                self.timerConnected = True
            self.timer.setActive(1)

            # grip 轮询 timer
            if not self._gripTimerConnected:
                self._gripTimer.connect(self._poll_grip)
                self._gripTimerConnected = True
            self._gripTimer.setActive(1)
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
            self._flyHeld = False
            self._flyBasePos = None
            self._gripHeld = False
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
                self.aPressedAction.signal().triggered.disconnect(self.toggle_clipping)
            except Exception:
                pass
            try:
                self.bPressedAction.signal().triggered.disconnect(self.toggle_flipped)
            except Exception:
                pass
            try:
                self.timer.setActive(0)
            except Exception:
                pass
            try:
                self._gripTimer.setActive(0)
            except Exception:
                pass
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

            teleport = vrDeviceService.getInteraction("Teleport")
            teleport.addSupportedInteractionGroup("TurntableGroup")
            teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
            teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
            teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("TurntableGroup")

            self.aPressedAction = self.multiButtonPad.createControllerAction("right-a-pressed")
            self.aReleasedAction = self.multiButtonPad.createControllerAction("right-a-released")
            self.bPressedAction = self.multiButtonPad.createControllerAction("right-b-pressed")

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
            vrDeviceService.setActiveInteractionGroup("TurntableGroup")

            self.aPressedAction.signal().triggered.connect(self.start_rotation)
            self.aReleasedAction.signal().triggered.connect(self.stop_rotation)
            self.bPressedAction.signal().triggered.connect(self.restore_rotation)

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
                self.aReleasedAction.signal().triggered.disconnect(self.stop_rotation)
            except Exception:
                pass
            try:
                self.bPressedAction.signal().triggered.disconnect(self.restore_rotation)
            except Exception:
                pass
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

        def _find_or_load_measure_controller(self):
            return findNode("MRcontrollerRight")

        def _activate_measure_controller(self):
            self.newRightCon = self._find_or_load_measure_controller()
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            findNode("CtrllrR_UI").fields().setInt32("choice", 14)
            self.rightController.setVisible(0)
            self.rightController.setEnabled(0)
            self.newRightCon.setActive(1)
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
            try:
                self.rightController.setEnabled(1)
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
            self.switchOn()
            self._activate_measure_controller()
            print("[AllTools] MeasureTool enabled")

        def switchOn(self):
            if not self.on:
                self.point1Selected = False
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
            if not self.point1Selected:
                self.point1Selected = True
                try:
                    self.node1 = hit.getNode()
                    self.point1 = hit.getPoint()
                except Exception:
                    self.node1 = None
                    self.point1 = None
                self.removeMeasurement()
            else:
                self.point1Selected = False
                try:
                    self.node2 = hit.getNode()
                    self.point2 = hit.getPoint()
                except Exception:
                    self.node2 = None
                    self.point2 = None
                self.createMeasurement()

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
    # FlashlightTool - 手电筒工具 (适配统一 enable/disable 模式)
    # ------------------------------------------------------------------
    class FlashlightTool:
        def __init__(self):
            self.isEnabled = False
            self.registry_key = "tool_flashlight"
            self.geo = None
            self.trans = None
            self.flashlight_handle = None
            self.on = False
            self.hand_node = None
            self.active_controller = None
            self.is_left_side = False
            self.visualization_mode = None
            self.constraint = None
            self.rightController = None
            self.newRightCon = None
            self.flashlightControllerConstraint = None
            self.lightNode = None
            self.lightSceneNode = None
            self.lightOn = False
            self.lightTimer = vrTimer()
            self.lightTimerConnected = False
            try:
                self.rightController = vrDeviceService.getVRDevice("right-controller")
                self.hand_node = self.rightController.getNode()
                self.active_controller = self.rightController
            except Exception:
                self.hand_node = None
                self.active_controller = None
                self.rightController = None

            # --- 创建交互组和 trigger 动作 ---
            self.multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadFlashlight")
            self.multiButtonPad.setSupportedInteractionGroups(["FlashlightGroup"])

            teleport = vrDeviceService.getInteraction("Teleport")
            teleport.addSupportedInteractionGroup("FlashlightGroup")
            teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
            teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
            teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("FlashlightGroup")

            self.triggerRightPressed = self.multiButtonPad.createControllerAction("right-trigger-pressed")

        def get_geo(self):
            if self.geo is not None:
                try:
                    if self.geo.isValid():
                        return self.geo
                except Exception:
                    pass
            self.create_geo()
            return self.geo

        def create_geo(self):
            try:
                for node in findNodes("VR_Flashlight"):
                    node.getParent().subChild(node)
            except Exception:
                pass
            root_node = getInternalRootNode()
            self.geo = createNode("Transform3D", "VR_Flashlight", root_node, False)
            self.trans = createNode("Transform3D", "FlashlightPos", self.geo, False)
            self.geo.setActive(False)
            try:
                setIsVRNode(self.trans, True)
                setIsVRNode(self.geo, True)
            except Exception:
                pass

        def update_flashlight(self, device):
            try:
                if device.getVisualizationMode() != self.visualization_mode:
                    self.adjust_flashlight(device)
                    self.visualization_mode = device.getVisualizationMode()
            except Exception:
                pass

        def adjust_flashlight(self, device):
            try:
                if device.getVisualizationMode() == 1:
                    self.set_hand_transform()
                    if self.flashlight_handle:
                        self.flashlight_handle.setVisibilityFlag(True)
                else:
                    self.set_controller_transform()
                    if self.flashlight_handle:
                        self.flashlight_handle.setVisibilityFlag(False)
            except Exception:
                pass

        def set_hand_transform(self):
            if self.is_left_side:
                setTransformNodeTranslation(self.trans, -17, -5, 60, False)
                setTransformNodeRotation(self.trans, 180, 10, 0)
            else:
                setTransformNodeTranslation(self.trans, 17, -5, 60, False)
                setTransformNodeRotation(self.trans, 180, -10, 0)

        def set_controller_transform(self):
            setTransformNodeTranslation(self.trans, 0, -50, 50, False)
            setTransformNodeRotation(self.trans, 110, 0, 0)

        def _create_spotlight(self):
            """创建聚光灯，通过 timer 跟踪手电筒朝向。"""
            if self.lightNode is not None:
                return
            try:
                self.lightNode = vrLightService.createLight(
                    "VR_Flashlight_Spot", vrLightTypes.LightType.Spot)
                self.lightNode.setOn(False)
                self.lightNode.setIntensity(30000.0)
                self.lightNode.setDiffuseColor(QVector3D(1.0, 0.98, 0.95))
                self.lightNode.setConeAngle(25.0)
                self.lightNode.setPenumbraAngle(5.0)
                self.lightNode.setVisualizationVisible(False)
            except Exception:
                self.lightNode = None
                return
            # 获取灯光在场景图中的节点，用于同步世界变换
            try:
                self.lightSceneNode = vrNodeService.findNode("VR_Flashlight_Spot")
            except Exception:
                self.lightSceneNode = None
            # 启动 timer 持续同步灯光位置和方向
            self._start_light_timer()

        def _remove_spotlight(self):
            """移除聚光灯及其 timer。"""
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

        def _update_light_transform(self):
            """Timer 回调：将聚光灯的世界变换同步到手电筒几何体。"""
            if not self.lightSceneNode or not self.geo:
                return
            try:
                worldMatrix = self.geo.getWorldTransform()
                self.lightSceneNode.setWorldTransform(worldMatrix)
            except Exception:
                pass

        def _start_light_timer(self):
            self.lightTimer.setActive(0)
            if not self.lightTimerConnected:
                self.lightTimer.connect(self._update_light_transform)
                self.lightTimerConnected = True
            self.lightTimer.setActive(1)

        def _stop_light_timer(self):
            self.lightTimer.setActive(0)

        def switch_on_light(self, action=None, device=None):
            if self.lightNode is None:
                self._create_spotlight()
            if self.lightNode:
                self.lightNode.setOn(True)
                self.lightOn = True

        def switch_off_light(self, action=None, device=None):
            if self.lightNode:
                self.lightNode.setOn(False)
                self.lightOn = False

        def switch_on(self):
            if self.on:
                return
            if not self.hand_node:
                return
            self.get_geo().setActive(True)
            self.on = True
            self.constraint = vrConstraintService.createParentConstraint([self.hand_node], self.geo, False)
            try:
                self.constraint.setVisualizationVisible(False)
            except Exception:
                pass
            if self.active_controller:
                self.active_controller.signal().moved.connect(self.update_flashlight)
                self.visualization_mode = self.active_controller.getVisualizationMode()
                self.adjust_flashlight(self.active_controller)
            # 创建聚光灯（默认关闭，等待 trigger 打开）
            self._create_spotlight()

        def switch_off(self):
            if not self.on:
                return
            # 先移除聚光灯
            self._remove_spotlight()
            try:
                self.get_geo().setActive(False)
            except Exception:
                pass
            self.on = False
            try:
                if self.constraint:
                    vrConstraintService.deleteConstraint(self.constraint)
                    self.constraint = None
            except Exception:
                pass
            if self.active_controller:
                try:
                    self.active_controller.signal().moved.disconnect(self.update_flashlight)
                except Exception:
                    pass

        def _find_or_load_flashlight_controller(self):
            return findNode("MRcontrollerRight")

        def _activate_flashlight_controller(self):
            self.newRightCon = self._find_or_load_flashlight_controller()
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            findNode("CtrllrR_UI").fields().setInt32("choice", 12)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.flashlightControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False
            )

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
            vrDeviceService.setActiveInteractionGroup("FlashlightGroup")
            self.aPressedAction.signal().triggered.connect(self.switch_on_light)
            self.bPressedAction.signal().triggered.connect(self.switch_off_light)
            self.switch_on()
            self._activate_flashlight_controller()
            print("[AllTools] FlashlightTool enabled")

        def disable(self):
            self.isEnabled = False
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                self.aPressedAction.signal().triggered.disconnect(self.switch_on_light)
            except Exception:
                pass
            try:
                self.bPressedAction.signal().triggered.disconnect(self.switch_off_light)
            except Exception:
                pass
            self.switch_off()
            self._deactivate_flashlight_controller()

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

                # ── misc ──
                self.isEnabled = False
                self.registry_key = "tool_voice_note"
                self.newRightCon = None
                self.voiceControllerConstraint = None
                self.teleport = None

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
                tmpl.setActive(False)
                # setIsVRNode(tmpl, True)
                self._voice_player_template = tmpl
                return tmpl

            def _create_note_node(self, label, position=None):
                """Clone the VoicePlayer template, place it in the scene and register it."""
                if self._voice_player_template is None:
                    print("[VoiceNotes] _create_note_node: VoicePlayer template not loaded")
                    return None, None
                rect = cloneNode(self._voice_player_template, False)
                moveNode(rect, rect.getParent(), getRootNode())
                rect.setActive(True)
                # setIsVRNode(rect, True)
                rect.setName("VNR_" + (label if label else "VoiceNode"))
                self._store_rect_scale(rect)
                if position:
                    setTransformNodeTranslation(rect, position.x(), position.y(), position.z(), 1)
                key = self._get_rect_key(rect)
                print("key0: " + key)
                if key:
                    self._voice_note_nodes[key] = rect
                    if label:
                        self._rect_labels[key] = label
                annotation = None
                if label:
                    try:
                        ann_pos = position if position else getTransformNodeTranslation(rect, 1)
                        annotation = vrAnnotationService.createAnnotation(label)
                        if key:
                            self._rect_annotations[key] = annotation
                        annotation.setText(label)
                        annotation.setSceneNode(rect)
                        annotation.setPosition(QtGui.QVector3D(
                            ann_pos.x(), ann_pos.y(), ann_pos.z()))
                        annotation.setAnchored(True)
                        print("[VoiceNotes] Annotation created: " + str(label))
                    except Exception as e:
                        print("[VoiceNotes] Annotation creation failed: " + str(e))
                return rect, annotation

            # ── recording ─────────────────────────────────────────────────

            def _start_recording(self, position=None):
                base_dir = os.path.join(tempfile.gettempdir(), "vred_voice_notes")
                if not os.path.exists(base_dir):
                    os.makedirs(base_dir)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(base_dir, "voice_note_" + ts + ".wav")
                recorder = self._ensure_recorder()
                recorder.setOutputLocation(QtCore.QUrl.fromLocalFile(path))
                rect, annotation = self._create_note_node(ts + " Recording", position)
                recorder.record()
                self._is_recording = True
                self._current_rect = rect
                self._current_annotation = annotation
                self._current_audio_path = path
                self._current_label = ts
                if rect:
                    key = self._get_rect_key(rect)
                    print("key2: " + key)
                    if key:
                        self._rect_audio_paths[key] = path

            def _stop_recording(self):
                self._ensure_recorder().stop()
                self._is_recording = False
                rect = self._current_rect
                if rect:
                    old_key = self._get_rect_key(rect)
                    print("key4: " + old_key)
                    label = self._current_label
                    try:
                        rect.setName("VNR_" + label)
                    except Exception:
                        pass
                    if self._current_annotation:
                        try:
                            self._current_annotation.setText(label)
                        except Exception:
                            pass
                    new_key = self._get_rect_key(rect)
                    if old_key and new_key and old_key != new_key:
                        for d in (self._rect_audio_paths, self._rect_base_scales,
                                  self._rect_annotations, self._rect_labels,
                                  self._voice_note_nodes):
                            if old_key in d:
                                d[new_key] = d.pop(old_key)
                    final_key = new_key or old_key
                    if final_key:
                        self._rect_labels[final_key] = label
                    self._last_rect = rect
                self._last_audio_path = self._current_audio_path
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
                pos = self._get_controller_forward_position(self.rightController)
                self._start_recording(pos)
                print("[VoiceNotes] A pressed → 开始录音，位置: " + str(pos))

            def on_a_released(self, action_obj=None, device_obj=None):
                if self._is_recording:
                    self._stop_recording()
                    findNode("CtrllrR_UI").fields().setInt32("choice", 7)
                    print("[VoiceNotes] A released → 结束录音")

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
                self.multi.setSupportedInteractionGroups(["VoiceNotesGroup"])
                vrDeviceService.setActiveInteractionGroup("VoiceNotesGroup")
                self.teleport = vrDeviceService.getInteraction("Teleport")
                self.teleport.addSupportedInteractionGroup("VoiceNotesGroup")
                self.teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
                self.teleport.setControllerActionMapping("abort",   "left-{}-untouched".format(_pad_input))
                self.teleport.setControllerActionMapping("execute",  "left-{}-pressed".format(_pad_input))
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
                    self.teleport.setControllerActionMapping("prepare", "any-{}-touched".format(_pad_input))
                    self.teleport.setControllerActionMapping("abort",   "any-{}-untouched".format(_pad_input))
                    self.teleport.setControllerActionMapping("execute",  "any-{}-pressed".format(_pad_input))
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
            try:
                self.tools[name].enable()
                self.active_tool = name
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

    # --- 全局摇杆 Teleport 绑定（左右手柄均适用）---
    try:
        _jump_tele = vrDeviceService.getInteraction("Teleport")
        _jump_tele.setControllerActionMapping("prepare", "any-{}-touched".format(_pad_input))
        _jump_tele.setControllerActionMapping("abort",   "any-{}-untouched".format(_pad_input))
        _jump_tele.setControllerActionMapping("execute",  "any-{}-pressed".format(_pad_input))
        print("[AllTools] 全局 Teleport 已绑定 (any-{})".format(_pad_input))
    except Exception as e:
        print("[AllTools] 全局 Teleport 绑定失败: " + str(e))

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

    print("[AllTools] Full cleanup complete. All tools disabled, all nodes removed, state reset.")

print("[AllTools] Script loaded. Available commands: switch_tool(name), disable_all_tools(), get_active_tool(), cleanup_all_tools()")
