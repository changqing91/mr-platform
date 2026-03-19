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

    noteCount = 0
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
        - trigger 按住 + 移动控制器: 物体跟随控制器在地平面上移动
        - 摇杆左右拨动: 物体绕 Z 轴旋转
        - 摇杆前后拨动: 物体沿摄像机视线方向前进/后退
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

            if not self.timerConnected:
                self.timer.connect(self.updateLoop)
                self.timerConnected = True
            self.timer.setActive(1)

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 11)
            self.rightController.setVisible(0)
            self.rightController.setEnabled(0)
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
                self.rightController.setEnabled(1)
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
        标注工具:
          Right trigger: 放置标注 / 删除模式下删除标注
          Left trigger:  切换标注样式
          Left grip:     切换放置模式 (手持 <-> 射线)
          Right grip:    切换删除模式
          摇杆上拨:       放大标注
          摇杆下拨:       缩小标注
        """
        def __init__(self):
            self.isEnabled = False
            self.activeNode = None
            self.timer = vrTimer()
            self.orientationConstraint = None

            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
            vrImmersiveInteractionService.setDefaultInteractionsActive(1)

            padUp = vrdVirtualTouchpadButton('padup', 0.5, 1.0, 330.0, 30.0)
            padDown = vrdVirtualTouchpadButton('paddown', 0.5, 1.0, 150.0, 210.0)
            self.rightController.addVirtualButton(padUp, _pad_input)
            self.rightController.addVirtualButton(padDown, _pad_input)

            self.multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadNotes")
            self.multiButtonPad.setSupportedInteractionGroups(["NotesGroup"])

            teleport = vrDeviceService.getInteraction("Teleport")
            teleport.addSupportedInteractionGroup("NotesGroup")
            teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
            teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
            teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("NotesGroup")

            self.triggerRightPressed = self.multiButtonPad.createControllerAction("right-trigger-pressed")
            self.gripPressed = self.multiButtonPad.createControllerAction("right-{}-pressed".format(_grip_input))
            self.gripReleasedAction = self.multiButtonPad.createControllerAction("right-{}-released".format(_grip_input))
            self.aPressedAction = self.multiButtonPad.createControllerAction("right-a-pressed")
            self.bPressedAction = self.multiButtonPad.createControllerAction("right-b-pressed")

            self.deleteNoteIsActive = False
            self.grabConstraint = None

            self.registry_key = "tool_draw_note"

        def distanceFunc(self):
            global refObject
            handPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            refObject.setActive(0)
            intersectionRay = self.rightController.pick()
            hitpoint = intersectionRay.getPoint()
            hitNormal = intersectionRay.getNormal()
            hitNode = intersectionRay.getNode()
            hitNode = toNode(hitNode.getObjectId())
            interPosRay = Pnt3f(hitpoint.x(), hitpoint.y(), hitpoint.z())
            refObject.setActive(1)

            self.activeNode = hitNode
            if self.orientationConstraint:
                try:
                    vrConstraintService.deleteConstraint(self.orientationConstraint)
                except Exception:
                    pass
            self.orientationConstraint = vrConstraintService.createOrientationConstraint([self.rightController.getNode()], refObject)
            setTransformNodeTranslation(refObject, handPos.x(), handPos.y(), handPos.z(), 1)

        def enable(self):
            global refObject
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
            self.gripPressed.signal().triggered.connect(self.grabNote)
            self.gripReleasedAction.signal().triggered.connect(self.releaseNote)

            if refObject:
                refObject = findNode("MR_Stuff").getChild(0)

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 1)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.NoteControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)

            self.deleteNoteIsActive = False
            self.iconsNotesTrashOff()
            self.timer.setActive(1)
            self.timer.connect(self.distanceFunc)

            if refObject:
                refObject_node = vrNodeService.getNodeFromId(refObject.getID())
                refObject_node.getParent().setVisibilityFlag(True)
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
                self.gripPressed.signal().triggered.disconnect(self.grabNote)
            except Exception:
                pass
            try:
                self.gripReleasedAction.signal().triggered.disconnect(self.releaseNote)
            except Exception:
                pass
            try:
                self.timer.setActive(0)
            except Exception:
                pass
            try:
                if self.orientationConstraint:
                    vrConstraintService.deleteConstraint(self.orientationConstraint)
                    self.orientationConstraint = None
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

        def trigger_right_pressed(self):
            global refObject
            global Cloned_ref_obj
            nodeNum = random.randint(0, 1000000)
            if not self.activeNode.getName() == "VRMenuPanel":
                if self.deleteNoteIsActive:
                    node = self.activeNode.getParent().getParent()
                    nodeName = "%s" % node.getName()
                    if hasNodeTag(node.getParent(), 'Cloned Note'):
                        vrSessionService.sendPython('deleteNode(findNode("' + nodeName + '"),True)')
                else:
                    nameRefObject = refObject.getName()
                    current_position = getTransformNodeTranslation(refObject, True)
                    current_rotation = getTransformNodeRotation(refObject)
                    current_scale = getTransformNodeScale(refObject)

                    nameString = "%s" % nameRefObject
                    posString = "%f,%f,%f" % (current_position.x(), current_position.y(), current_position.z())
                    rotString = "%f,%f,%f" % (current_rotation.x(), current_rotation.y(), current_rotation.z())
                    scaleString = "%f,%f,%f" % (current_scale.x(), current_scale.y(), current_scale.z())

                    vrSessionService.sendPython('clonedRef = cloneNode(findNode("' + nameString + '"), False)')
                    clonedNewName = nameString + '_' + str(nodeNum)
                    vrSessionService.sendPython('clonedRef.setName("' + clonedNewName + '")')
                    vrSessionService.sendPython('moveNode(clonedRef, refObject, Cloned_ref_obj)')
                    vrSessionService.sendPython('setTransformNodeRotation(clonedRef, ' + rotString + ')')
                    vrSessionService.sendPython('setTransformNodeTranslation(clonedRef, ' + posString + ', True)')
                    vrSessionService.sendPython('setTransformNodeScale(clonedRef, ' + scaleString + ')')
                    vrSessionService.sendPython('addNodeTag(Cloned_ref_obj, "Cloned Note")')

        def toggleDeleteMode(self):
            global refObject
            refObject_node = vrNodeService.getNodeFromId(refObject.getID())
            if not self.deleteNoteIsActive:
                self.deleteNoteIsActive = True
                findNode("CtrllrR_UI").fields().setInt32("choice", 3)
                refObject_node.getParent().setVisibilityFlag(False)
            else:
                self.deleteNoteIsActive = False
                findNode("CtrllrR_UI").fields().setInt32("choice", 1)
                refObject_node.getParent().setVisibilityFlag(True)

        def sizeUp(self):
            global refObject
            currentsize = getTransformNodeScale(refObject)
            ref_Parent = vrNodeService.getNodeFromId(refObject.getParent().getID())
            switch_child = ref_Parent.getChildren()
            for current_note in switch_child:
                setTransformNodeScale(current_note, currentsize.x() * 1.2, currentsize.y() * 1.2, currentsize.z() * 1.2)

        def sizeDown(self):
            global refObject
            currentsize = getTransformNodeScale(refObject)
            ref_Parent = vrNodeService.getNodeFromId(refObject.getParent().getID())
            switch_child = ref_Parent.getChildren()
            for current_note in switch_child:
                setTransformNodeScale(current_note, currentsize.x() / 1.2, currentsize.y() / 1.2, currentsize.z() / 1.2)

        def ChangeNote(self):
            global refObject
        def ChangeNote(self):
            global refObject
            global noteCount
            _mr_stuff = findNode("MR_Stuff")
            _tag_nodes = [_mr_stuff.getChild(i) for i in range(_mr_stuff.getNChildren())
                          if _mr_stuff.getChild(i).getName().startswith("tag_")]
            if _tag_nodes:
                index = noteCount % len(_tag_nodes)
                noteCount += 1
                refObject = _tag_nodes[index]

        def iconsNotesTrashOn(self):
            findNode("CtrllrR_UI").fields().setInt32("choice", 3)

        def iconsNotesTrashOff(self):
            findNode("CtrllrR_UI").fields().setInt32("choice", 1)

        def iconsNotesConstraint(self):
            findNode("CtrllrR_UI").fields().setInt32("choice", 1)

        def iconsNotesRay(self):
            findNode("CtrllrR_UI").fields().setInt32("choice", 2)

        def grabNote(self, action=None, device=None):
            global Cloned_ref_obj
            right_node = self.rightController.getNode()
            best, best_dist = None, float('inf')
            try:
                for i in range(Cloned_ref_obj.getNChildren()):
                    child = Cloned_ref_obj.getChild(i)
                    pos = getTransformNodeTranslation(child, 1)
                    hand = getTransformNodeTranslation(right_node, 1)
                    dx = pos.x()-hand.x(); dy = pos.y()-hand.y(); dz = pos.z()-hand.z()
                    d = math.sqrt(dx*dx+dy*dy+dz*dz)
                    if d < best_dist:
                        best_dist, best = d, child
            except Exception:
                pass
            if best:
                self.grabConstraint = vrConstraintService.createParentConstraint([right_node], best, True)
                findNode("CtrllrR_UI").fields().setInt32("choice", 4)

        def releaseNote(self, action=None, device=None):
            if self.grabConstraint:
                vrConstraintService.deleteConstraint(self.grabConstraint)
                self.grabConstraint = None
            findNode("CtrllrR_UI").fields().setInt32("choice", 3 if self.deleteNoteIsActive else 1)

    # ------------------------------------------------------------------
    # SectionTool - 剖面工具
    # ------------------------------------------------------------------
    class SectionTool:
        def __init__(self):
            self.isEnabled = False
            self.clipping = False
            self.gridVis = False
            self.contourVis = False
            self.planeVis = False
            self.constXPressed = False
            self.constYPressed = False
            self.constZPressed = False
            self.timer = vrTimer()
            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)

            padCenter = vrdVirtualTouchpadButton('padcenter', 0.0, 0.5, 0.0, 360.0)
            padUpperLeft = vrdVirtualTouchpadButton('padupleft', 0.5, 1.0, 270.0, 330.0)
            padLowerLeft = vrdVirtualTouchpadButton('paddownleft', 0.5, 1.0, 210.0, 270.0)
            padUp = vrdVirtualTouchpadButton('padup', 0.5, 1.0, 330.0, 30.0)
            padUpperRight = vrdVirtualTouchpadButton('padupright', 0.5, 1.0, 30.0, 90.0)
            padLowerRight = vrdVirtualTouchpadButton('paddownright', 0.5, 1.0, 90.0, 150.0)
            padDown = vrdVirtualTouchpadButton('paddown', 0.5, 1.0, 150.0, 210.0)
            self.rightController.addVirtualButton(padCenter, _pad_input)
            self.rightController.addVirtualButton(padUpperLeft, _pad_input)
            self.rightController.addVirtualButton(padLowerLeft, _pad_input)
            self.rightController.addVirtualButton(padUp, _pad_input)
            self.rightController.addVirtualButton(padUpperRight, _pad_input)
            self.rightController.addVirtualButton(padLowerRight, _pad_input)
            self.rightController.addVirtualButton(padDown, _pad_input)

            multiButtonPadClip = vrDeviceService.createInteraction("MultiButtonPadClip")
            multiButtonPadClip.setSupportedInteractionGroups(["ClipGroup"])

            teleport = vrDeviceService.getInteraction("Teleport")
            teleport.addSupportedInteractionGroup("ClipGroup")
            teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
            teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
            teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("ClipGroup")

            self.leftUpperActionClip = multiButtonPadClip.createControllerAction("right-padupleft-pressed")
            self.leftDownActionClip = multiButtonPadClip.createControllerAction("right-paddownleft-pressed")
            self.upActionClip = multiButtonPadClip.createControllerAction("right-padup-pressed")
            self.downActionClip = multiButtonPadClip.createControllerAction("right-paddown-pressed")
            self.rightUpperActionClip = multiButtonPadClip.createControllerAction("right-padupright-pressed")
            self.rightDownActionClip = multiButtonPadClip.createControllerAction("right-paddownright-pressed")
            self.centerActionClip = multiButtonPadClip.createControllerAction("right-padcenter-pressed")
            self.triggerRightPressed = multiButtonPadClip.createControllerAction("right-trigger-pressed")
            self.triggerRightReleased = multiButtonPadClip.createControllerAction("right-trigger-released")
            self.aPressedAction = multiButtonPadClip.createControllerAction("right-a-pressed")
            self.bPressedAction = multiButtonPadClip.createControllerAction("right-b-pressed")

            self.registry_key = "tool_section"
            self.newRightCon = None
            self.ClipControllerConstraint = None

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
            vrDeviceService.setActiveInteractionGroup("ClipGroup")

            self.leftUpperActionClip.signal().triggered.connect(self.GridVis)
            self.leftDownActionClip.signal().triggered.connect(self.constX)
            self.upActionClip.signal().triggered.connect(self.PlaneVis)
            self.downActionClip.signal().triggered.connect(self.constY)
            self.rightUpperActionClip.signal().triggered.connect(self.ContourVis)
            self.rightDownActionClip.signal().triggered.connect(self.constZ)
            self.centerActionClip.signal().triggered.connect(self.ClippingState)
            self.aPressedAction.signal().triggered.connect(self.ClippingState)
            self.bPressedAction.signal().triggered.connect(self.toggleClipDir)
            self.triggerRightPressed.signal().triggered.connect(self.trigger_right_pressed)
            self.triggerRightReleased.signal().triggered.connect(self.trigger_right_released)

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 5)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.ClipControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)
            try:
                node = self.newRightCon if self.newRightCon else self.rightController.getNode()
                self.originalPos = getTransformNodeTranslation(node, 1)
            except Exception:
                pass
            print("[AllTools] SectionTool enabled")

        def disable(self):
            self.isEnabled = False
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                self.leftUpperActionClip.signal().triggered.disconnect(self.GridVis)
            except Exception:
                pass
            try:
                self.leftDownActionClip.signal().triggered.disconnect(self.constX)
            except Exception:
                pass
            try:
                self.upActionClip.signal().triggered.disconnect(self.PlaneVis)
            except Exception:
                pass
            try:
                self.downActionClip.signal().triggered.disconnect(self.constY)
            except Exception:
                pass
            try:
                self.rightUpperActionClip.signal().triggered.disconnect(self.ContourVis)
            except Exception:
                pass
            try:
                self.rightDownActionClip.signal().triggered.disconnect(self.constZ)
            except Exception:
                pass
            try:
                self.centerActionClip.signal().triggered.disconnect(self.ClippingState)
            except Exception:
                pass
            try:
                self.aPressedAction.signal().triggered.disconnect(self.ClippingState)
            except Exception:
                pass
            try:
                self.bPressedAction.signal().triggered.disconnect(self.toggleClipDir)
            except Exception:
                pass
            try:
                self.triggerRightPressed.signal().triggered.disconnect(self.trigger_right_pressed)
            except Exception:
                pass
            try:
                self.triggerRightReleased.signal().triggered.disconnect(self.trigger_right_released)
            except Exception:
                pass
            try:
                self.timer.setActive(0)
            except Exception:
                pass
            try:
                vrDeviceService.setActiveInteractionGroup("Locomotion")
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

        def GridVis(self):
            if not self.gridVis:
                try:
                    setClippingGridVisualization(1, Vec3f(1, 1, 1))
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingGridVisualization(1, Vec3f(1,1,1))")
                except Exception:
                    pass
                self.gridVis = True
            else:
                self.gridVis = False
                try:
                    setClippingGridVisualization(0, Vec3f(1, 1, 1))
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingGridVisualization(0, Vec3f(1,1,1))")
                except Exception:
                    pass
            if not self.planeVis:
                try:
                    setClippingPlaneVisualization(1, Vec3f(0.16, 0.16, 0.28))
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingPlaneVisualization(1, Vec3f(0.16,0.16,0.28))")
                except Exception:
                    pass
                self.planeVis = True
            else:
                self.planeVis = False
                try:
                    setClippingPlaneVisualization(0, Vec3f(0.16, 0.16, 0.28))
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingPlaneVisualization(0, Vec3f(0.16,0.16,0.28))")
                except Exception:
                    pass
            if not self.contourVis:
                try:
                    setClippingContourVisualization(1, Vec3f(0, 0, 0), 5)
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingContourVisualization(1, Vec3f(0,0,0),5)")
                except Exception:
                    pass
                self.contourVis = True
            else:
                self.contourVis = False
                try:
                    setClippingContourVisualization(0, Vec3f(0, 0, 0), 5)
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingContourVisualization(0, Vec3f(0,0,0),5)")
                except Exception:
                    pass
            if not self.constXPressed:
                self.constXPressed = True
                try:
                    self.clipXConstraintON()
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingPlaneRotation(0,0,90)")
                except Exception:
                    pass
            else:
                self.constXPressed = False
                try:
                    self.clipXConstraintOFF()
                except Exception:
                    pass

        def constY(self):
            if not self.constYPressed:
                self.constYPressed = True
                try:
                    self.clipYConstraintON()
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingPlaneRotation(0,90,0)")
                except Exception:
                    pass
            else:
                self.constYPressed = False
                try:
                    self.clipYConstraintOFF()
                except Exception:
                    pass

        def constZ(self):
            if not self.constZPressed:
                self.constZPressed = True
                try:
                    self.clipZConstraintON()
                except Exception:
                    pass
                try:
                    vrSessionService.sendPython("setClippingPlaneRotation(90,0,0)")
                except Exception:
                    pass
            else:
                self.constZPressed = False
                try:
                    self.clipZConstraintOFF()
                except Exception:
                    pass

        def ClippingState(self):
            if not self.clipping:
                enableClippingPlane(1)
                try:
                    vrSessionService.sendPython("enableClippingPlane(1)")
                except Exception:
                    pass
                self.clipping = True
            else:
                enableClippingPlane(0)
                try:
                    vrSessionService.sendPython("enableClippingPlane(0)")
                except Exception:
                    pass
                self.clipping = False

        def trigger_right_pressed(self):
            if self.clipping:
                self.timer.setActive(1)
                self.timer.connect(self.trigger_right_pressed)
                try:
                    node = self.newRightCon if self.newRightCon else self.rightController.getNode()
                except Exception:
                    node = None
                if not node:
                    return
                self.currentPos = getTransformNodeTranslation(node, 1)
                if self.constXPressed:
                    p = "%f,%f,%f" % (self.currentPos.x(), self.originalPos.y(), self.originalPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                elif self.constYPressed:
                    p = "%f,%f,%f" % (self.originalPos.x(), self.currentPos.y(), self.originalPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                elif self.constZPressed:
                    p = "%f,%f,%f" % (self.originalPos.x(), self.originalPos.y(), self.currentPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                else:
                    self.originalPos = getTransformNodeTranslation(node, 1)
                    p = "%f,%f,%f" % (self.originalPos.x(), self.originalPos.y(), self.originalPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                    try:
                        self.originalRot = getTransformNodeRotation(node)
                        r = "%f,%f,%f" % (self.originalRot.x() + 90, self.originalRot.y(), self.originalRot.z())
                        vrSessionService.sendPython("setClippingPlaneRotation(" + r + ")")
                    except Exception:
                        pass

        def trigger_right_released(self):
            if self.clipping:
                self.timer.setActive(0)
                if self.constXPressed and self.constYPressed:
                    p = "%f,%f,%f" % (self.currentPos.x(), self.currentPos.y(), self.originalPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                elif self.constYPressed and self.constZPressed:
                    p = "%f,%f,%f" % (self.originalPos.x(), self.currentPos.y(), self.currentPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                elif self.constXPressed and self.constZPressed:
                    p = "%f,%f,%f" % (self.currentPos.x(), self.originalPos.y(), self.currentPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                elif self.constXPressed:
                    p = "%f,%f,%f" % (self.currentPos.x(), self.originalPos.y(), self.originalPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                elif self.constYPressed:
                    p = "%f,%f,%f" % (self.originalPos.x(), self.currentPos.y(), self.originalPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                elif self.constZPressed:
                    p = "%f,%f,%f" % (self.originalPos.x(), self.originalPos.y(), self.currentPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")
                else:
                    try:
                        node = self.newRightCon if self.newRightCon else self.rightController.getNode()
                        self.originalPos = getTransformNodeTranslation(node, 1)
                    except Exception:
                        return
                    p = "%f,%f,%f" % (self.originalPos.x(), self.originalPos.y(), self.originalPos.z())
                    vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                    vrSessionService.sendPython("setClippingPlanePosition(point)")

        def clipXConstraintON(self):
            pass
        def clipXConstraintOFF(self):
            pass
        def clipYConstraintON(self):
            pass
        def clipYConstraintOFF(self):
            pass
        def clipZConstraintON(self):
            pass
        def clipZConstraintOFF(self):
            pass

        def toggleClipDir(self, action=None, device=None):
            try:
                cur = findNode("CtrllrR_UI").fields().getInt32("choice")
                findNode("CtrllrR_UI").fields().setInt32("choice", 6 if cur == 5 else 5)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # TurntableTool - 展示台旋转工具
    # ------------------------------------------------------------------
    class TurntableTool:
        def __init__(self):
            self.isEnabled = False
            self.direction = 1
            self.speed = 1.0
            self.node = None
            self.nodeRefReady = False
            self.rotating = False
            self.currentAngle = 0.0
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

            self.leftTouched = self.multiButtonPad.createControllerAction("right-padleft-touched")
            self.rightTouched = self.multiButtonPad.createControllerAction("right-padright-touched")
            self.aPressedAction = self.multiButtonPad.createControllerAction("right-a-pressed")
            self.aReleasedAction = self.multiButtonPad.createControllerAction("right-a-released")
            self.bPressedAction = self.multiButtonPad.createControllerAction("right-b-pressed")
            self.originalAngle = 0.0

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
            self.leftTouched.signal().triggered.connect(self.set_counterclockwise)
            self.rightTouched.signal().triggered.connect(self.set_clockwise)

            self.newRightCon = findNode("MRcontrollerRight")
            findNode("CtrllrR_UI").fields().setInt32("choice", 13)
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.RotationControllerConstraint = vrConstraintService.createParentConstraint(
                [self.rightController.getNode()], self.newRightCon, False)
            if self.node:
                try:
                    self.originalAngle = getTransformNodeRotation(self.node).z()
                except Exception:
                    self.originalAngle = 0.0
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
                self.leftTouched.signal().triggered.disconnect(self.set_counterclockwise)
            except Exception:
                pass
            try:
                self.rightTouched.signal().triggered.disconnect(self.set_clockwise)
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

        def set_clockwise(self, action=None, device=None):
            self.direction = 1

        def set_counterclockwise(self, action=None, device=None):
            self.direction = -1

        def restore_rotation(self, action=None, device=None):
            if self.node:
                try:
                    rot = getTransformNodeRotation(self.node)
                    setTransformNodeRotation(self.node, rot.x(), rot.y(), self.originalAngle)
                    self.currentAngle = self.originalAngle
                except Exception:
                    pass

        def start_rotation(self):
            self.node = self._resolve_target()
            if not self.node:
                return
            try:
                if self.node.isNull():
                    return
            except Exception:
                pass
            self._prepare_node_ref()
            try:
                rot = getTransformNodeRotation(self.node)
                self.currentAngle = rot.z()
            except Exception:
                self.currentAngle = 0.0
            self.rotating = True
            self._start_timer()

        def stop_rotation(self):
            self.rotating = False
            self._stop_timer()

        def updateRotation(self):
            if not self.rotating or not self.node:
                return
            try:
                if self.node.isNull():
                    self.stop_rotation()
                    return
            except Exception:
                pass
            self.currentAngle += self.speed * self.direction
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
                self.gripPressedAction = self.multi.createControllerAction(
                    "right-{}-pressed".format(_grip_input))
                self.gripReleasedAction = self.multi.createControllerAction(
                    "right-{}-released".format(_grip_input))
                _grip_alt = 'squeeze' if _grip_input == 'grip' else 'grip'
                self.gripPressedActionAlt = self.multi.createControllerAction(
                    "right-{}-pressed".format(_grip_alt))
                self.gripReleasedActionAlt = self.multi.createControllerAction(
                    "right-{}-released".format(_grip_alt))
                print("[VoiceNotes] grip actions: right-{0}-*/released + right-{1}-*/released".format(
                    _grip_input, _grip_alt))
                self.triggerPressedAction = self.multi.createControllerAction("right-trigger-pressed")

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
                self._grip_held = False
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

            def on_grip_pressed(self, action_obj=None, device_obj=None):
                if self._grip_held:
                    return
                if self._drag_constraint is not None:
                    try:
                        vrConstraintService.deleteConstraint(self._drag_constraint)
                    except Exception:
                        pass
                    self._drag_constraint = None
                # Use pick() raycast to find a VNR_ node under the controller pointer
                best_node = None
                try:
                    hit = self.rightController.pick()
                    if hit and hit.hasHit():
                        node = hit.getNode()
                        while node and not node.isNull():
                            if node.getName().startswith("VNR_"):
                                best_node = node
                                break
                            node = node.getParent()
                except Exception as e:
                    print("[VoiceNotes] Grip pick failed: " + str(e))
                if best_node is None:
                    print("[VoiceNotes] Grip: 射线未命中可拖动节点")
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
                for act_p, act_r, lbl in [
                    (self.gripPressedAction,    self.gripReleasedAction,    _grip_input),
                    (self.gripPressedActionAlt, self.gripReleasedActionAlt,
                     'squeeze' if _grip_input == 'grip' else 'grip'),
                ]:
                    try:
                        act_p.signal().triggered.connect(self.on_grip_pressed)
                        print("[VoiceNotes] grip-pressed ('{}') connected".format(lbl))
                    except Exception as e:
                        print("[VoiceNotes] grip-pressed ('{}') FAILED: {}".format(lbl, e))
                    try:
                        act_r.signal().triggered.connect(self.on_grip_released)
                        print("[VoiceNotes] grip-released ('{}') connected".format(lbl))
                    except Exception as e:
                        print("[VoiceNotes] grip-released ('{}') FAILED: {}".format(lbl, e))
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
                for act in (self.gripPressedAction, self.gripPressedActionAlt):
                    try:
                        if act:
                            act.signal().triggered.disconnect(self.on_grip_pressed)
                    except Exception:
                        pass
                for act in (self.gripReleasedAction, self.gripReleasedActionAlt):
                    try:
                        if act:
                            act.signal().triggered.disconnect(self.on_grip_released)
                    except Exception:
                        pass
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
    global refObject, Cloned_ref_obj, noteCount

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
        noteCount = 0
    except Exception:
        pass

    # 8. 清空注册表并标记未初始化，允许重新注入
    vred_tool_registry = {}
    _tool_manager = _ToolManager()
    _all_tools_initialized = False

    print("[AllTools] Full cleanup complete. All tools disabled, all nodes removed, state reset.")

print("[AllTools] Script loaded. Available commands: switch_tool(name), disable_all_tools(), get_active_tool(), cleanup_all_tools()")
