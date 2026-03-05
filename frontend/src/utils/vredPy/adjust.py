import os
import math

_pad_input = 'touchpad'
_grip_input = 'grip'
try:
    _xr = getattr(vrImmersiveInteractionService, 'getOpenXRRuntime', None)
    if _xr and _xr():
        _pad_input = 'thumbstick'
        _grip_input = 'squeeze'
except Exception:
    pass

global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

adjustControllerFound = False
try:
    allAdjustNodes = getAllNodes()
    for node in allAdjustNodes:
        nodeName = node.getName()
        if nodeName == "WT-MR_Remote_controllers":
            adjustControllerFound = True
            break
except Exception:
    adjustControllerFound = False

if not adjustControllerFound:
    try:
        base_dir = None
        try:
            base_dir = os.path.join(os.environ['USERPROFILE'], 'Documents')
        except Exception:
            try:
                base_dir = os.path.join(os.environ['HOME'], 'Documents')
            except Exception:
                base_dir = None
        if base_dir:
            filepath = os.path.join(base_dir, 'Autodesk', 'Automotive', 'VRED', 'ControllerBase.osb')
            if os.path.exists(filepath):
                node = loadGeometry(filepath)
                try:
                    node.setName("WT-MR_Remote_controllers")
                except Exception:
                    pass
                adjustControllerFound = True
    except Exception:
        adjustControllerFound = False

class AdjustTool:
    """
    地平面移动工具 (XY 为地平面, Z 为上下)

    交互方式:
    - trigger 按住 + 移动控制器: 物体跟随控制器在地平面上移动 (锁 Z, 锁 X/Y 旋转, 保留 Z 旋转)
    - 摇杆左右拨动: 物体绕 Z 轴旋转 (精细调整朝向)
    - 摇杆前后拨动: 物体沿摄像机视线方向在地平面上前进/后退 (精细调整位置)
    """
    def __init__(self):
        self.isEnabled = False
        self.node = None
        self.startMoveFlag = False
        self.nodeRefReady = False
        self.timer = vrTimer()
        self.timerConnected = False
        # 摇杆状态
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

        # 摇杆: 上下左右 (用 touched 事件, 拨动即触发)
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

        # 摇杆 touched/untouched
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
        self.enable()

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
        """获取摄像机在地平面 (XY) 上的前方向量 (归一化)"""
        try:
            cam = vrCameraService.getActiveCamera(True)
            if not cam:
                return (0.0, 1.0)
            camNode = cam.getCameraNode()
            if not camNode or camNode.isNull():
                return (0.0, 1.0)
            camRot = getTransformNodeRotation(camNode)
            # 摄像机绕 Z 轴的旋转角度决定了在 XY 平面上的朝向
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
        # 1. 用户选中的节点
        try:
            nodes = getSelectedNodes()
            if nodes and len(nodes) > 0 and not nodes[0].isNull():
                self.node = self.getMovable(nodes[0])
                self._prepare_node_ref()
                return
        except Exception:
            pass
        # 2. 用 vrMetadataService 直接查找带 Movable 标签的节点
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
        # 3. 兜底：根节点第一个非控制器子节点
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
        # 1. trigger 拖拽: 锁 Z 高度, 保留 Z 轴旋转
        if self.startMoveFlag and self.node and not self.node.isNull():
            pos = getTransformNodeTranslation(self.node, 1)
            rot = getTransformNodeRotation(self.node)
            setTransformNodeTranslation(self.node, pos.x(), pos.y(), self.originalNodePos.z(), 1)
            setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), rot.z())
            self._sync_transform()
            return

        # 2. 摇杆: 精细移动和旋转
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

        # 前后: 沿摄像机视线方向在地平面上移动
        if self.stickForward or self.stickBackward:
            fx, fy = self._get_camera_forward_xy()
            direction = self.moveSpeed if self.stickForward else -self.moveSpeed
            setTransformNodeTranslation(self.node, pos.x() + fx * direction, pos.y() + fy * direction, pos.z(), 1)
            moved = True

        # 左右: 绕 Z 轴旋转
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

    # --- 摇杆事件 (touched/untouched) ---
    def on_up_touched(self, action=None, device=None):
        self._ensure_node()
        self.stickForward = True
        print("[Adjust] stick forward")
    def on_up_untouched(self, action=None, device=None):
        self.stickForward = False
    def on_down_touched(self, action=None, device=None):
        self._ensure_node()
        self.stickBackward = True
        print("[Adjust] stick backward")
    def on_down_untouched(self, action=None, device=None):
        self.stickBackward = False
    def on_left_touched(self, action=None, device=None):
        self._ensure_node()
        self.stickLeft = True
        print("[Adjust] stick left")
    def on_left_untouched(self, action=None, device=None):
        self.stickLeft = False
    def on_right_touched(self, action=None, device=None):
        self._ensure_node()
        self.stickRight = True
        print("[Adjust] stick right")
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

        # 摇杆信号
        self.padUpTouched.signal().triggered.connect(self.on_up_touched)
        self.padUpUntouched.signal().triggered.connect(self.on_up_untouched)
        self.padDownTouched.signal().triggered.connect(self.on_down_touched)
        self.padDownUntouched.signal().triggered.connect(self.on_down_untouched)
        self.padLeftTouched.signal().triggered.connect(self.on_left_touched)
        self.padLeftUntouched.signal().triggered.connect(self.on_left_untouched)
        self.padRightTouched.signal().triggered.connect(self.on_right_touched)
        self.padRightUntouched.signal().triggered.connect(self.on_right_untouched)

        # timer
        if not self.timerConnected:
            self.timer.connect(self.updateLoop)
            self.timerConnected = True
        self.timer.setActive(1)

        if adjustControllerFound:
            try:
                try:
                    self.newRightCon = findNode("WT-MR_Remote_controllers")
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

adjust = AdjustTool()
print("executed")
