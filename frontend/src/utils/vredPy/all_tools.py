# ======================================================================
# VRED MR Tools - Unified Script
# 一次注入所有工具，通过 switch_tool(name) 切换当前生效的工具
# 可用工具: adjust, draw_note, section, turntable, measure, voice_note, flashlight
# ======================================================================

import os
import math
import random

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

    def _get_vred_documents_dir():
        base_dir = None
        try:
            base_dir = os.path.join(os.environ['USERPROFILE'], 'Documents')
        except Exception:
            try:
                base_dir = os.path.join(os.environ['HOME'], 'Documents')
            except Exception:
                pass
        if base_dir:
            return os.path.join(base_dir, 'Autodesk', 'Automotive', 'VRED')
        return None

    # --- Adjust 控制器 ---
    adjustControllerFound = False
    try:
        for node in getAllNodes():
            if node.getName() == "WT-MR_Remote_controllers":
                adjustControllerFound = True
                break
    except Exception:
        pass

    if not adjustControllerFound:
        try:
            vred_dir = _get_vred_documents_dir()
            if vred_dir:
                filepath = os.path.join(vred_dir, 'ControllerBase.osb')
                if os.path.exists(filepath):
                    node = loadGeometry(filepath)
                    try:
                        node.setName("WT-MR_Remote_controllers")
                    except Exception:
                        pass
                    adjustControllerFound = True
        except Exception:
            pass

    # --- Notes (draw_note) 资源 ---
    notesControllerFound = False
    mainCustomFuncGroup = False
    customFunctionsGroup = None

    notesController = 0
    goodBadNotes = 0
    try:
        allNotesNodes = getAllNodes()
        for node in allNotesNodes:
            allNotesNodeName = node.getName()
            if allNotesNodeName == "VRController_Notes":
                notesController += 1
            elif allNotesNodeName == "Notes":
                goodBadNotes += 1
            elif allNotesNodeName == "VRED-VR-Custom-Fucntion":
                mainCustomFuncGroup = True
                customFunctionsGroup = node
    except Exception:
        pass

    notesControllerFound = notesController > 0

    if goodBadNotes == 0:
        try:
            vred_dir = _get_vred_documents_dir()
            if vred_dir:
                filepath = os.path.join(vred_dir, 'VRControllerNotes_Notes.osb')
                if os.path.exists(filepath):
                    node = loadGeometry(filepath)
                    node.setName("VRControllerNotes_Notes")
                    createNode("Group", "Cloned_ref_obj")
        except Exception:
            pass

    if not mainCustomFuncGroup:
        try:
            customFunctionsGroup = createNode('Group', 'VRED-VR-Custom-Fucntion')
        except Exception:
            pass

    allFuncNames = [
        "VRControllerMove", "VRControllerSelect", "VRControllerNotes",
        "VRControllerDraw", "VRControllerNotes_Notes", "Cloned_ref_obj",
        "D_Tool", "D_Lines", "D_tempLine", "Group_html"
    ]

    try:
        if customFunctionsGroup:
            allNodeFuncname = getAllNodes()
            for node in allNodeFuncname:
                if node.getName() in allFuncNames:
                    addChilds(customFunctionsGroup, [node])
    except Exception:
        pass

    try:
        refObject = findNode("Notes").getChild(0)
        switchNode = findNode("Notes")
    except Exception:
        refObject = None
        switchNode = None

    noteCount = 0
    try:
        Cloned_ref_obj = findNode("Cloned_ref_obj")
    except Exception:
        Cloned_ref_obj = None

    # --- Section (剖面) 控制器 ---
    clippingControllerFound = False
    try:
        for node in getAllNodes():
            nodeName = node.getName()
            if nodeName == "VRController_Clip" or nodeName == "VRControllerClip":
                clippingControllerFound = True
                break
    except Exception:
        pass

    if not clippingControllerFound:
        try:
            vred_dir = _get_vred_documents_dir()
            if vred_dir:
                filename = os.path.join(vred_dir, 'VRControllerClip.osb')
                if os.path.exists(filename):
                    node = loadGeometry(filename)
                    try:
                        node.setName("VRControllerClip")
                    except Exception:
                        pass
                    clippingControllerFound = True
        except Exception:
            pass

    # --- Turntable 旋转控制器 (目前禁用加载) ---
    rotationControllerFound = False

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

            if adjustControllerFound:
                try:
                    self.newRightCon = findNode("WT-MR_Remote_controllers")
                except Exception:
                    self.newRightCon = None
                if self.newRightCon:
                    try:
                        self.rightController.setVisible(0)
                    except Exception:
                        pass
                    try:
                        self.rightController.setEnabled(0)
                    except Exception:
                        pass
                    try:
                        self.newRightCon.setActive(1)
                    except Exception:
                        pass
                    try:
                        controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                        setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
                    except Exception:
                        pass
                    try:
                        self.AdjustControllerConstraint = vrConstraintService.createParentConstraint([self.rightController.getNode()], self.newRightCon, False)
                    except Exception:
                        self.AdjustControllerConstraint = None
            else:
                try:
                    self.rightController.setVisible(1)
                except Exception:
                    pass
                try:
                    self.rightController.setEnabled(1)
                except Exception:
                    pass
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
            self.upbuttonIsActive = False
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
            self.leftTriggerPressed = self.multiButtonPad.createControllerAction("left-trigger-pressed")
            self.leftGripPressed = self.multiButtonPad.createControllerAction("left-{}-pressed".format(_grip_input))
            self.gripPressed = self.multiButtonPad.createControllerAction("right-{}-pressed".format(_grip_input))
            self.padUpTouched = self.multiButtonPad.createControllerAction("right-padup-touched")
            self.padDownTouched = self.multiButtonPad.createControllerAction("right-paddown-touched")

            self.deleteNoteIsActive = False
            self.changeView = False

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
            if not self.changeView:
                if self.orientationConstraint:
                    try:
                        vrConstraintService.deleteConstraint(self.orientationConstraint)
                    except Exception:
                        pass
                self.orientationConstraint = vrConstraintService.createOrientationConstraint([self.rightController.getNode()], refObject)
                setTransformNodeTranslation(refObject, handPos.x(), handPos.y(), handPos.z(), 1)
            else:
                if self.orientationConstraint:
                    try:
                        vrConstraintService.deleteConstraint(self.orientationConstraint)
                        self.orientationConstraint = None
                    except Exception:
                        pass

                nx, ny, nz = hitNormal.x(), hitNormal.y(), hitNormal.z()
                normalLen = math.sqrt(nx * nx + ny * ny + nz * nz)
                if normalLen > 1e-6:
                    nx /= normalLen
                    ny /= normalLen
                    nz /= normalLen

                noteScale = getTransformNodeScale(refObject)
                offset = max(noteScale.x(), noteScale.y(), noteScale.z()) * 0.5
                posX = interPosRay.x() + nx * offset
                posY = interPosRay.y() + ny * offset
                posZ = interPosRay.z() + nz * offset
                setTransformNodeTranslation(refObject, posX, posY, posZ, 1)

                ry = math.degrees(math.atan2(nx, nz))
                rx = math.degrees(math.atan2(-ny, math.sqrt(nx * nx + nz * nz)))
                setTransformNodeRotation(refObject, rx, ry, 0)

        def enable(self):
            global refObject
            global switchNode
            global notesControllerFound
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
            self.leftTriggerPressed.signal().triggered.connect(self.ChangeNote)
            self.leftGripPressed.signal().triggered.connect(self.changeNoteView)
            self.gripPressed.signal().triggered.connect(self.deleteNote)
            self.padUpTouched.signal().triggered.connect(self.sizeUp)
            self.padDownTouched.signal().triggered.connect(self.sizeDown)

            if refObject:
                refObject_node = vrNodeService.getNodeFromId(refObject.getID())
                refObject_node.getChild(0).setVisibilityFlag(True)

                refObject = switchNode.getChild(0)
                switchNode.fields().setInt32("choice", 0)

            if notesControllerFound:
                self.newRightCon = findNode("VRController_Notes")
                self.rightController.setVisible(0)
                self.newRightCon.setActive(1)
                controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
                self.NoteControllerConstraint = vrConstraintService.createParentConstraint([self.rightController.getNode()], self.newRightCon, False)
            else:
                self.rightController.setVisible(1)

            self.deleteNoteIsActive = False
            self.changeView = False
            self.iconsNotesTrashOff()
            self.timer.setActive(1)
            self.timer.connect(self.distanceFunc)

            if not self.changeView:
                self.iconsNotesConstraint()
                if refObject:
                    refObject_node = vrNodeService.getNodeFromId(refObject.getID())
                    refObject_node.getParent().setVisibilityFlag(True)
                self.onControllerNotesMapping()
            else:
                self.iconsNotesRay()
                self.onRayNotesMapping()
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
                self.leftTriggerPressed.signal().triggered.disconnect(self.ChangeNote)
            except Exception:
                pass
            try:
                self.leftGripPressed.signal().triggered.disconnect(self.changeNoteView)
            except Exception:
                pass
            try:
                self.gripPressed.signal().triggered.disconnect(self.deleteNote)
            except Exception:
                pass
            try:
                self.padUpTouched.signal().triggered.disconnect(self.sizeUp)
            except Exception:
                pass
            try:
                self.padDownTouched.signal().triggered.disconnect(self.sizeDown)
            except Exception:
                pass
            try:
                self.timer.setActive(0)
            except Exception:
                pass
            try:
                self.neutralNotes()
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

        def deleteNote(self):
            global refObject
            refObject_node = vrNodeService.getNodeFromId(refObject.getID())
            if not self.deleteNoteIsActive:
                self.iconsNotesTrashOn()
                refObject_node.getParent().setVisibilityFlag(False)
                self.deleteNoteIsActive = True
                self.onRayNotesMapping()
            else:
                self.deleteNoteIsActive = False
                self.iconsNotesTrashOff()
                refObject_node.getParent().setVisibilityFlag(True)
                self.defaultNotesMappings()

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

        def changeNoteView(self):
            global refObject
            if not self.deleteNoteIsActive:
                if not self.changeView:
                    self.iconsNotesRay()
                    self.changeView = True
                    self.onRayNotesMapping()
                else:
                    self.changeView = False
                    self.iconsNotesConstraint()
                    self.onControllerNotesMapping()

        def ChangeNote(self):
            global refObject
            global noteCount
            global switchNode

            refObject.getParent()
            hello = vrNodeService.getNodeFromId(refObject.getParent().getID())
            all_child = hello.getChildren()

            if not self.upbuttonIsActive:
                index = noteCount % len(all_child)
                noteCount += 1
                refObject = switchNode.getChild(index)
                switchNode.fields().setInt32("choice", index)
            else:
                self.upbuttonIsActive = False

        def iconsNotesTrashOn(self):
            global notesControllerFound
            if notesControllerFound:
                setSwitchMaterialChoice("C_N_Icon_Minus", 0)
                setSwitchMaterialChoice("C_N_Icon_Next", 0)
                setSwitchMaterialChoice("C_N_Icon_Plus", 0)
                setSwitchMaterialChoice("C_N_Icon_Trash", 2)

        def iconsNotesTrashOff(self):
            global notesControllerFound
            if notesControllerFound:
                setSwitchMaterialChoice("C_N_Icon_Minus", 1)
                setSwitchMaterialChoice("C_N_Icon_Next", 1)
                setSwitchMaterialChoice("C_N_Icon_Plus", 1)
                setSwitchMaterialChoice("C_N_Icon_Trash", 1)

        def iconsNotesConstraint(self):
            global notesControllerFound
            if notesControllerFound:
                setSwitchMaterialChoice("C_N_Icon_Notes", 2)

        def iconsNotesRay(self):
            global notesControllerFound
            if notesControllerFound:
                setSwitchMaterialChoice("C_N_Icon_Notes", 1)

        def neutralNotes(self):
            self.pointer.setControllerActionMapping("prepare", "any-customtrigger-touched")
            self.pointer.setControllerActionMapping("abort", "any-customtrigger-untouched")
            self.pointer.setControllerActionMapping("start", "any-customtrigger-pressed")
            self.pointer.setControllerActionMapping("execute", "any-customtrigger-released")

        def onControllerNotesMapping(self):
            self.pointer.setControllerActionMapping("prepare", "disable")
            self.pointer.setControllerActionMapping("abort", "any-customtrigger-untouched")
            self.pointer.setControllerActionMapping("start", "any-customtrigger-pressed")
            self.pointer.setControllerActionMapping("execute", "any-customtrigger-released")

        def onRayNotesMapping(self):
            self.pointer.setControllerActionMapping("prepare", "right-customtrigger-touched")
            self.pointer.setControllerActionMapping("abort", "disable")
            self.pointer.setControllerActionMapping("start", "right-customtrigger-pressed")
            self.pointer.setControllerActionMapping("execute", "right-customtrigger-released")

        def defaultNotesMappings(self):
            if not self.changeView:
                self.onControllerNotesMapping()
            else:
                self.onRayNotesMapping()

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
            self.triggerRightPressed.signal().triggered.connect(self.trigger_right_pressed)
            self.triggerRightReleased.signal().triggered.connect(self.trigger_right_released)

            if clippingControllerFound:
                try:
                    try:
                        self.newRightCon = findNode("VRController_Clip")
                    except Exception:
                        self.newRightCon = None
                    if not self.newRightCon:
                        try:
                            self.newRightCon = findNode("VRControllerClip")
                        except Exception:
                            self.newRightCon = None
                except Exception:
                    self.newRightCon = None
                if self.newRightCon:
                    try:
                        self.rightController.setVisible(0)
                    except Exception:
                        pass
                    try:
                        self.newRightCon.setActive(1)
                    except Exception:
                        pass
                    try:
                        controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                        setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
                    except Exception:
                        pass
                    try:
                        self.ClipControllerConstraint = vrConstraintService.createParentConstraint([self.rightController.getNode()], self.newRightCon, False)
                    except Exception:
                        self.ClipControllerConstraint = None
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
                if clippingControllerFound:
                    setSwitchMaterialChoice("C_C_Icon_X", 0)
                    setSwitchMaterialChoice("C_C_Icon_Y", 0)
                    setSwitchMaterialChoice("C_C_Icon_Z", 0)
                    setSwitchMaterialChoice("C_C_Clip", 0)
                    setSwitchMaterialChoice("C_C_Grid", 0)
                    setSwitchMaterialChoice("C_C_Contour", 0)
                    setSwitchMaterialChoice("C_C_Plane", 0)
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
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Grid", 1)
                except Exception:
                    pass
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
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Grid", 0)
                except Exception:
                    pass

        def PlaneVis(self):
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
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Plane", 1)
                except Exception:
                    pass
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
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Plane", 0)
                except Exception:
                    pass

        def ContourVis(self):
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
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Contour", 1)
                except Exception:
                    pass
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
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Contour", 0)
                except Exception:
                    pass

        def constX(self):
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
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Clip", 1)
                except Exception:
                    pass
            else:
                enableClippingPlane(0)
                try:
                    vrSessionService.sendPython("enableClippingPlane(0)")
                except Exception:
                    pass
                self.clipping = False
                try:
                    if clippingControllerFound:
                        setSwitchMaterialChoice("C_C_Clip", 0)
                except Exception:
                    pass

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
            if clippingControllerFound:
                setSwitchMaterialChoice("C_C_Icon_X", 1)
                setSwitchMaterialChoice("C_C_Icon_Y", 0)
                setSwitchMaterialChoice("C_C_Icon_Z", 0)
        def clipXConstraintOFF(self):
            if clippingControllerFound:
                setSwitchMaterialChoice("C_C_Icon_X", 0)
        def clipYConstraintON(self):
            if clippingControllerFound:
                setSwitchMaterialChoice("C_C_Icon_X", 0)
                setSwitchMaterialChoice("C_C_Icon_Y", 1)
                setSwitchMaterialChoice("C_C_Icon_Z", 0)
        def clipYConstraintOFF(self):
            if clippingControllerFound:
                setSwitchMaterialChoice("C_C_Icon_Y", 0)
        def clipZConstraintON(self):
            if clippingControllerFound:
                setSwitchMaterialChoice("C_C_Icon_X", 0)
                setSwitchMaterialChoice("C_C_Icon_Y", 0)
                setSwitchMaterialChoice("C_C_Icon_Z", 1)
        def clipZConstraintOFF(self):
            if clippingControllerFound:
                setSwitchMaterialChoice("C_C_Icon_Z", 0)

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

            self.registry_key = "tool_turntable"

        def _find_node_by_names(self, names):
            try:
                all_nodes = getAllNodes()
                if not all_nodes:
                    return None
                for node in all_nodes:
                    try:
                        if node and not node.isNull() and node.getName() in names:
                            return node
                    except Exception:
                        continue
            except Exception:
                pass
            return None

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

            triggerStart = self.pointer.getControllerAction("start")
            triggerStart.signal().triggered.connect(self.on_trigger_toggle)
            self.leftTouched.signal().triggered.connect(self.set_counterclockwise)
            self.rightTouched.signal().triggered.connect(self.set_clockwise)

            if rotationControllerFound:
                try:
                    self.newRightCon = self._find_node_by_names(("VRController_Rotation", "VRControllerRotation"))
                except Exception:
                    self.newRightCon = None
                if self.newRightCon:
                    try:
                        if not self.newRightCon.isNull():
                            self.rightController.setVisible(0)
                            self.newRightCon.setActive(1)
                            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
                            self.RotationControllerConstraint = vrConstraintService.createParentConstraint([self.rightController.getNode()], self.newRightCon, False)
                    except Exception:
                        pass
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
                triggerStart = self.pointer.getControllerAction("start")
                triggerStart.signal().triggered.disconnect(self.on_trigger_toggle)
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

        def on_trigger_toggle(self, action=None, device=None):
            if self.rotating:
                self.stop_rotation()
            else:
                self.start_rotation()

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
            try:
                node = findNode("ControllerDraw")
                if node and not node.isNull():
                    return node
            except Exception:
                pass
            try:
                vred_dir = _get_vred_documents_dir()
                if not vred_dir:
                    return None
                filepath = os.path.join(vred_dir, 'ControllerDraw.osb')
                if not os.path.exists(filepath):
                    return None
                node = loadGeometry(filepath)
                try:
                    node.setName("ControllerDraw")
                except Exception:
                    pass
                return node
            except Exception:
                return None

        def _activate_measure_controller(self):
            self.newRightCon = self._find_or_load_measure_controller()
            if self.newRightCon:
                try:
                    self.rightController.setVisible(0)
                except Exception:
                    pass
                try:
                    self.rightController.setEnabled(0)
                except Exception:
                    pass
                try:
                    self.newRightCon.setActive(1)
                except Exception:
                    pass
                try:
                    self.measureControllerConstraint = vrConstraintService.createParentConstraint(
                        [self.rightController.getNode()], self.newRightCon, False
                    )
                except Exception:
                    self.measureControllerConstraint = None
            else:
                try:
                    self.rightController.setVisible(1)
                except Exception:
                    pass
                try:
                    self.rightController.setEnabled(1)
                except Exception:
                    pass

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
            self.load_model()
            try:
                self.flashlight_handle = vrNodeService.findNode("Housing_02", False, False, self.trans)
            except Exception:
                self.flashlight_handle = None
            self.geo.setActive(False)
            try:
                setIsVRNode(self.trans, True)
                setIsVRNode(self.geo, True)
            except Exception:
                pass

        def load_model(self):
            model_path = self.get_controller_osb_path()
            nodes = []
            if model_path:
                try:
                    nodes = loadOSB([model_path])
                except Exception:
                    nodes = []
            for node in nodes:
                self.trans.addChild(node)

        def get_controller_osb_path(self):
            vred_dir = _get_vred_documents_dir()
            if not vred_dir:
                return None
            filename = os.path.join(vred_dir, "ControllerFlashlight.osb")
            if os.path.exists(filename):
                return filename
            return None

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

        def toggle_light(self, action=None, device=None):
            """Trigger 按下时切换聚光灯开/关。"""
            if self.lightNode is None:
                self._create_spotlight()
            if self.lightNode is None:
                return
            if self.lightOn:
                try:
                    self.lightNode.setOn(False)
                except Exception:
                    pass
                self.lightOn = False
            else:
                try:
                    self.lightNode.setOn(True)
                except Exception:
                    pass
                self.lightOn = True

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
            try:
                node = findNode("ControllerFlashlight")
                if node and not node.isNull():
                    return node
            except Exception:
                pass
            try:
                vred_dir = _get_vred_documents_dir()
                if not vred_dir:
                    return None
                filepath = os.path.join(vred_dir, 'ControllerFlashlight.osb')
                if not os.path.exists(filepath):
                    return None
                node = loadGeometry(filepath)
                try:
                    node.setName("ControllerFlashlight")
                except Exception:
                    pass
                return node
            except Exception:
                return None

        def _activate_flashlight_controller(self):
            self.newRightCon = self._find_or_load_flashlight_controller()
            if self.newRightCon:
                try:
                    self.rightController.setVisible(0)
                except Exception:
                    pass
                try:
                    self.newRightCon.setActive(1)
                except Exception:
                    pass
                try:
                    self.flashlightControllerConstraint = vrConstraintService.createParentConstraint(
                        [self.rightController.getNode()], self.newRightCon, False
                    )
                except Exception:
                    self.flashlightControllerConstraint = None
            else:
                try:
                    self.rightController.setVisible(1)
                except Exception:
                    pass

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
            self.triggerRightPressed.signal().triggered.connect(self.toggle_light)
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
                self.triggerRightPressed.signal().triggered.disconnect(self.toggle_light)
            except Exception:
                pass
            self.switch_off()
            self._deactivate_flashlight_controller()

    # ------------------------------------------------------------------
    # VoiceNotes - 语音标注工具 (需要 PySide6)
    # ------------------------------------------------------------------
    _voice_notes_available = False
    try:
        from PySide6 import QtCore, QtMultimedia, QtGui
        _voice_notes_available = True
    except Exception:
        _voice_notes_available = False

    if _voice_notes_available:
        import datetime
        import tempfile

        if 'voice_note_state' not in globals() or voice_note_state.get('qt_binding') != 'pyside6':
            voice_note_state = {
                'qt_binding': 'pyside6',
                'recorder': None,
                'player': None,
                'audio_input': None,
                'audio_output': None,
                'capture_session': None,
                'is_recording': False,
                'last_audio_path': None,
                'current_rect': None,
                'last_rect': None,
                'current_annotation': None,
                'current_label': None,
                'current_audio_path': None,
                'rect_audio_paths': {},
                'rect_base_scales': {},
                'hover_rect': None,
                'hover_scale': 1.2
            }
        state = voice_note_state

        def _ensure_recorder():
            if state['recorder'] is not None:
                return state['recorder']
            state['audio_input'] = QtMultimedia.QAudioInput()
            try:
                inputs = QtMultimedia.QMediaDevices.audioInputs()
                preferred_input = os.getenv("VOICE_NOTE_AUDIO_INPUT", "").strip().lower()
                chosen_input = None
                input_keywords = [
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
                        if preferred_input and lowered and preferred_input in lowered:
                            chosen_input = dev
                            break
                        if lowered and any(k in lowered for k in input_keywords):
                            chosen_input = dev
                            break
                    except Exception:
                        pass
                if chosen_input is None:
                    for dev in inputs:
                        try:
                            if dev.isDefault():
                                chosen_input = dev
                                break
                        except Exception:
                            pass
                if chosen_input is None:
                    try:
                        if len(inputs) == 1:
                            chosen_input = inputs[0]
                    except Exception:
                        pass
                if chosen_input:
                    try:
                        state['audio_input'].setDevice(chosen_input)
                    except Exception:
                        pass
            except Exception:
                pass
            state['recorder'] = QtMultimedia.QMediaRecorder()
            state['capture_session'] = QtMultimedia.QMediaCaptureSession()
            state['capture_session'].setAudioInput(state['audio_input'])
            state['capture_session'].setRecorder(state['recorder'])
            return state['recorder']

        def _ensure_player():
            state['player'] = QtMultimedia.QMediaPlayer()
            try:
                state['player'].setVolume(100)
            except Exception:
                pass
            state['audio_output'] = QtMultimedia.QAudioOutput()
            try:
                outputs = QtMultimedia.QMediaDevices.audioOutputs()
                preferred = os.getenv("VOICE_NOTE_AUDIO_DEVICE", "").strip().lower()
                chosen = None
                keywords = [
                    "alvr", "virtual audio", "virtual-audio", "virtualaudio",
                    "audio cable", "virtual audio cable", "cable", "vb-audio", "vac",
                    "vr", "vive", "valve", "index", "oculus", "rift", "openxr",
                    "reverb", "wmr", "headset", "headphones"
                ]
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
                    for dev in outputs:
                        try:
                            if dev.isDefault():
                                chosen = dev
                                break
                        except Exception:
                            pass
                if chosen is None:
                    try:
                        if len(outputs) == 1:
                            chosen = outputs[0]
                    except Exception:
                        pass
                if chosen:
                    try:
                        state['audio_output'].setDevice(chosen)
                    except Exception:
                        pass
                try:
                    state['audio_output'].setVolume(1.0)
                except Exception:
                    pass
            except Exception:
                pass
            state['player'].setAudioOutput(state['audio_output'])
            return state['player']

        def _get_device_pick_position(device):
            if not device:
                return None
            try:
                hit = device.pick()
                if hit and hit.hasHit():
                    point = hit.getPoint()
                    if point:
                        try:
                            normal = hit.getNormal()
                            if normal and normal.length() > 0.0001:
                                return point + normal.normalized() * 42.0
                        except Exception:
                            pass
                        return point
            except Exception:
                pass
            return None

        def _get_device_target_position(device):
            pos = _get_device_pick_position(device)
            if pos:
                return pos
            try:
                matrix = device.getTrackingMatrix()
                if matrix:
                    col = matrix.column(3)
                    origin = QtGui.QVector3D(col.x(), col.y(), col.z())
                    axis = matrix.column(2)
                    forward = QtGui.QVector3D(axis.x(), axis.y(), axis.z())
                    if forward.length() > 0.0001:
                        return origin + forward.normalized() * 2.0
            except Exception:
                pass
            return None

        def _get_rect_key(node):
            if not node:
                return None
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

        def _store_rect_scale(rect):
            if not rect:
                return
            key = _get_rect_key(rect)
            if not key:
                return
            if key in state['rect_base_scales']:
                return
            try:
                base = rect.getScale()
            except Exception:
                base = QtGui.QVector3D(1.0, 1.0, 1.0)
            state['rect_base_scales'][key] = base

        def _apply_rect_scale(rect, scale):
            if not rect or not scale:
                return
            try:
                rect.setScale(scale)
                return
            except Exception:
                pass
            try:
                rect.setWorldScale(scale)
            except Exception:
                pass

        def _set_hover_rect(node):
            if node == state.get('hover_rect'):
                return
            prev = state.get('hover_rect')
            if prev:
                prev_key = _get_rect_key(prev)
                base = state['rect_base_scales'].get(prev_key)
                if base:
                    _apply_rect_scale(prev, base)
            state['hover_rect'] = node
            if node:
                key = _get_rect_key(node)
                base = state['rect_base_scales'].get(key)
                if not base:
                    try:
                        base = node.getScale()
                    except Exception:
                        base = QtGui.QVector3D(1.0, 1.0, 1.0)
                    state['rect_base_scales'][key] = base
                factor = state.get('hover_scale', 1.2)
                scale = QtGui.QVector3D(base.x() * factor, base.y() * factor, base.z() * factor)
                _apply_rect_scale(node, scale)

        def _play_audio(path):
            if not path or not os.path.exists(path):
                return False
            player = _ensure_player()
            url = QtCore.QUrl.fromLocalFile(path)
            if hasattr(QtMultimedia.QMediaPlayer, "setSource"):
                player.setSource(url)
            else:
                player.setMedia(QtMultimedia.QMediaContent(url))
            player.play()
            return True

        def _create_rectangle(text, position=None):
            root = vrScenegraphService.getRootNode()
            color = QtGui.QColor(0, 60, 180)
            rect = None
            annotation = None
            try:
                rect = vrGeometryService.createSphere(root, 40.0, 32, 32, color)
            except Exception:
                rect = None
            if rect:
                try:
                    rect.setName(text if text else "VoiceNode")
                except Exception:
                    pass
                try:
                    cam = vrCameraService.getActiveCamera(True)
                    aim = vrConstraintService.createAimConstraint([cam], [], rect)
                    if aim:
                        aim.setVisualizationVisible(False)
                except Exception:
                    pass
                _store_rect_scale(rect)
            if position and rect:
                try:
                    rect.setWorldTranslation(position)
                except Exception:
                    try:
                        rect.setTranslation(position)
                    except Exception:
                        pass
            if rect:
                try:
                    vrMetadataService.addTags([rect], ["voice_note_rect"])
                except Exception:
                    pass
                if text:
                    try:
                        annotation = vrAnnotationService.createAnnotation(text)
                        annotation.setText(text)
                        annotation.setSceneNode(rect)
                        annotation.setAnchored(True)
                        if position:
                            annotation.setPosition(position)
                    except Exception:
                        annotation = None
            return rect, annotation

        def _start_recording(position=None):
            base_dir = os.path.join(tempfile.gettempdir(), "vred_voice_notes")
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = "voice_note_" + ts + ".wav"
            path = os.path.join(base_dir, filename)
            recorder = _ensure_recorder()
            recorder.setOutputLocation(QtCore.QUrl.fromLocalFile(path))
            label = ts
            rect, annotation = _create_rectangle(label + " Recording", position)
            recorder.record()
            state['is_recording'] = True
            state['current_rect'] = rect
            state['current_annotation'] = annotation
            state['current_audio_path'] = path
            state['current_label'] = label
            if rect:
                key = _get_rect_key(rect)
                if key:
                    state['rect_audio_paths'][key] = path

        def _stop_recording():
            recorder = _ensure_recorder()
            recorder.stop()
            state['is_recording'] = False
            if state['current_rect']:
                old_key = _get_rect_key(state['current_rect'])
                try:
                    state['current_rect'].setName(state['current_label'])
                except Exception:
                    pass
                if state['current_annotation']:
                    try:
                        state['current_annotation'].setText(state['current_label'])
                    except Exception:
                        pass
                new_key = _get_rect_key(state['current_rect'])
                if old_key and new_key and old_key != new_key:
                    if old_key in state['rect_audio_paths']:
                        state['rect_audio_paths'][new_key] = state['rect_audio_paths'].pop(old_key)
                    if old_key in state['rect_base_scales']:
                        state['rect_base_scales'][new_key] = state['rect_base_scales'].pop(old_key)
                state['last_rect'] = state['current_rect']
            state['last_audio_path'] = state.get('current_audio_path')
            state['current_rect'] = None
            state['current_annotation'] = None
            state['current_audio_path'] = None
            state['current_label'] = None

        class VoiceNotes:
            def __init__(self):
                self.leftController = vrDeviceService.getVRDevice("left-controller")
                self.rightController = vrDeviceService.getVRDevice("right-controller")
                self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
                self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
                vrImmersiveInteractionService.setDefaultInteractionsActive(1)
                self.multi = vrDeviceService.createInteraction("MultiButtonPadVoice")
                self.multi.setSupportedInteractionGroups(["NotesGroup"])
                self.pointer = vrDeviceService.getInteraction("Pointer")
                self.pointer.addSupportedInteractionGroup("NotesGroup")
                self.triggerRightPressed = self.multi.createControllerAction("right-trigger-pressed")
                self.executeAction = None
                self.timer = vrTimer()
                self.registry_key = "tool_voice_note"
                self.newRightCon = None
                self.voiceControllerConstraint = None

            def _find_or_load_voice_controller(self):
                try:
                    node = findNode("ControllerVoiceNote")
                    if node and not node.isNull():
                        return node
                except Exception:
                    pass
                try:
                    vred_dir = _get_vred_documents_dir()
                    if not vred_dir:
                        return None
                    filepath = os.path.join(vred_dir, 'ControllerVoiceNote.osb')
                    if not os.path.exists(filepath):
                        return None
                    node = loadGeometry(filepath)
                    try:
                        node.setName("ControllerVoiceNote")
                    except Exception:
                        pass
                    return node
                except Exception:
                    return None

            def _activate_voice_controller(self):
                self.newRightCon = self._find_or_load_voice_controller()
                if self.newRightCon:
                    try:
                        self.rightController.setVisible(0)
                    except Exception:
                        pass
                    try:
                        self.rightController.setEnabled(0)
                    except Exception:
                        pass
                    try:
                        self.newRightCon.setActive(1)
                    except Exception:
                        pass
                    try:
                        self.voiceControllerConstraint = vrConstraintService.createParentConstraint(
                            [self.rightController.getNode()], self.newRightCon, False
                        )
                    except Exception:
                        self.voiceControllerConstraint = None
                else:
                    try:
                        self.rightController.setVisible(1)
                    except Exception:
                        pass
                    try:
                        self.rightController.setEnabled(1)
                    except Exception:
                        pass

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
                except Exception:
                    pass
                try:
                    self.rightController.setEnabled(1)
                except Exception:
                    pass

            def distanceFunc(self):
                hover_node = None
                try:
                    hit = self.rightController.pick()
                except Exception:
                    hit = None
                if hit and hit.hasHit():
                    try:
                        node = hit.getNode()
                    except Exception:
                        node = None
                    if node:
                        try:
                            if vrMetadataService.hasTag(node, "voice_note_rect"):
                                hover_node = node
                        except Exception:
                            hover_node = None
                _set_hover_rect(hover_node)

            def on_trigger(self, action_obj=None, device_obj=None):
                _ = action_obj
                device = device_obj if device_obj else self.rightController
                if device:
                    try:
                        hit = device.pick()
                    except Exception:
                        hit = None
                    if hit and hit.hasHit():
                        try:
                            node = hit.getNode()
                        except Exception:
                            node = None
                        if node:
                            try:
                                if vrMetadataService.hasTag(node, "voice_note_rect"):
                                    if state['is_recording'] and state.get('current_rect') == node:
                                        _stop_recording()
                                    else:
                                        key = _get_rect_key(node)
                                        path = state['rect_audio_paths'].get(key)
                                        _play_audio(path)
                                    return
                            except Exception:
                                pass
                pos = _get_device_target_position(device)
                if state['is_recording']:
                    _stop_recording()
                else:
                    _start_recording(pos)

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
                self.multi.setSupportedInteractionGroups(["NotesGroup"])
                vrDeviceService.setActiveInteractionGroup("NotesGroup")
                self.teleport = vrDeviceService.getInteraction("Teleport")
                self.teleport.addSupportedInteractionGroup("NotesGroup")
                self.teleport.setControllerActionMapping("prepare", "right-{}-touched".format(_pad_input))
                self.teleport.setControllerActionMapping("abort", "right-{}-untouched".format(_pad_input))
                self.teleport.setControllerActionMapping("execute", "right-{}-pressed".format(_pad_input))
                self.pointer.setControllerActionMapping("prepare", "right-customtrigger-touched")
                self.pointer.setControllerActionMapping("abort", "disable")
                self.pointer.setControllerActionMapping("start", "right-trigger-pressed")
                self.pointer.setControllerActionMapping("execute", "right-trigger-released")
                try:
                    self.executeAction = self.pointer.getControllerAction("execute")
                    self.executeAction.signal().triggered.connect(self.on_trigger)
                except Exception:
                    self.executeAction = None
                self.timer.setActive(1)
                self.timer.connect(self.distanceFunc)
                self._activate_voice_controller()
                print("[AllTools] VoiceNotes enabled")

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
                    self.teleport.setControllerActionMapping("abort", "any-{}-untouched".format(_pad_input))
                    self.teleport.setControllerActionMapping("execute", "any-{}-pressed".format(_pad_input))
                except Exception:
                    pass
                try:
                    self.pointer.setControllerActionMapping("prepare", "any-customtrigger-touched")
                    self.pointer.setControllerActionMapping("abort", "any-customtrigger-untouched")
                    self.pointer.setControllerActionMapping("start", "any-customtrigger-pressed")
                    self.pointer.setControllerActionMapping("execute", "any-customtrigger-released")
                except Exception:
                    pass
                try:
                    if self.executeAction:
                        self.executeAction.signal().triggered.disconnect(self.on_trigger)
                except Exception:
                    pass
                try:
                    self.timer.setActive(0)
                except Exception:
                    pass
                try:
                    if state.get('is_recording'):
                        _stop_recording()
                except Exception:
                    pass
                self._deactivate_voice_controller()

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

    if _voice_notes_available:
        try:
            _tool_manager.register("voice_note", VoiceNotes())
            print("[AllTools] VoiceNotes registered")
        except Exception as e:
            print("[AllTools] Failed to register VoiceNotes: " + str(e))
    else:
        print("[AllTools] VoiceNotes skipped (PySide6 not available)")

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
    global refObject, switchNode, Cloned_ref_obj, noteCount
    global customFunctionsGroup
    global adjustControllerFound, notesControllerFound, clippingControllerFound, rotationControllerFound

    # 1. 禁用所有工具
    try:
        _tool_manager.disable_all()
    except Exception:
        pass

    # 2. 删除脚本创建/加载的所有场景节点
    _nodes_to_remove = [
        "WT-MR_Remote_controllers",   # Adjust controller .osb
        "VRControllerNotes_Notes",     # Notes controller .osb
        "VRController_Notes",          # Notes controller variant
        "Cloned_ref_obj",              # Notes cloned objects
        "VRED-VR-Custom-Fucntion",     # Custom function group
        "VRControllerClip",            # Section controller .osb
        "VRController_Clip",           # Section controller variant
        "ControllerDraw",              # Measure controller .osb
        "VR_Flashlight",               # Flashlight geometry
        "ControllerVoiceNote",         # Voice note controller .osb
        "Notes",                       # Notes switch node
        "VRControllerMove",
        "VRControllerSelect",
        "VRControllerNotes",
        "VRControllerDraw",
        "D_Tool",
        "D_Lines",
        "D_tempLine",
        "Group_html",
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
        switchNode = None
        Cloned_ref_obj = None
        noteCount = 0
        customFunctionsGroup = None
        adjustControllerFound = False
        notesControllerFound = False
        clippingControllerFound = False
        rotationControllerFound = False
    except Exception:
        pass

    # 8. 清空注册表并标记未初始化，允许重新注入
    vred_tool_registry = {}
    _tool_manager = _ToolManager()
    _all_tools_initialized = False

    print("[AllTools] Full cleanup complete. All tools disabled, all nodes removed, state reset.")

print("[AllTools] Script loaded. Available commands: switch_tool(name), disable_all_tools(), get_active_tool(), cleanup_all_tools()")
