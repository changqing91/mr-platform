import os
import math

global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

adjustControllerFound = False
try:
    allAdjustNodes = getAllNodes()
    for node in allAdjustNodes:
        nodeName = node.getName()
        if nodeName == "VRController_Move" or nodeName == "VRControllerMove":
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
            filepath = os.path.join(base_dir, 'Autodesk', 'Automotive', 'VRED')
            filename = os.path.join(filepath, 'VRControllerMove.osb')
            if os.path.exists(filename):
                node = loadGeometry(filename)
                try:
                    node.setName("VRControllerMove")
                except Exception:
                    pass
                adjustControllerFound = True
    except Exception:
        adjustControllerFound = False

class AdjustTool:
    def __init__(self):
        self.isEnabled = False
        self.node = None
        self.startMoveFlag = False
        self.nodeRefReady = False
        self.timer = vrTimer()
        self.timerConnected = False
        # 摇杆状态: 'none', 'forward', 'backward', 'left', 'right'
        self.stickState = 'none'
        self.moveSpeed = 5.0       # 前进后退速度 (mm/帧)
        self.rotateSpeed = 1.0     # 旋转速度 (度/帧)

        self.leftController = vrDeviceService.getVRDevice("left-controller")
        self.rightController = vrDeviceService.getVRDevice("right-controller")
        self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
        self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
        vrImmersiveInteractionService.setDefaultInteractionsActive(1)

        # 摇杆四个方向
        padUp = vrdVirtualTouchpadButton('padup', 0.5, 1.0, 330.0, 30.0)
        padDown = vrdVirtualTouchpadButton('paddown', 0.5, 1.0, 150.0, 210.0)
        padLeft = vrdVirtualTouchpadButton('padleft', 0.5, 1.0, 210.0, 330.0)
        padRight = vrdVirtualTouchpadButton('padright', 0.5, 1.0, 30.0, 150.0)
        self.rightController.addVirtualButton(padUp, 'touchpad')
        self.rightController.addVirtualButton(padDown, 'touchpad')
        self.rightController.addVirtualButton(padLeft, 'touchpad')
        self.rightController.addVirtualButton(padRight, 'touchpad')

        multiButtonPadAdjust = vrDeviceService.createInteraction("MultiButtonPadAdjust")
        multiButtonPadAdjust.setSupportedInteractionGroups(["AdjustGroup"])

        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("AdjustGroup")
        teleport.setControllerActionMapping("prepare", "left-touchpad-touched")
        teleport.setControllerActionMapping("abort", "left-touchpad-untouched")
        teleport.setControllerActionMapping("execute", "left-touchpad-pressed")

        self.pointer = vrDeviceService.getInteraction("Pointer")
        self.pointer.addSupportedInteractionGroup("AdjustGroup")

        # 摇杆方向 pressed/released
        self.upPressed = multiButtonPadAdjust.createControllerAction("right-padup-pressed")
        self.upReleased = multiButtonPadAdjust.createControllerAction("right-padup-released")
        self.downPressed = multiButtonPadAdjust.createControllerAction("right-paddown-pressed")
        self.downReleased = multiButtonPadAdjust.createControllerAction("right-paddown-released")
        self.leftPressed = multiButtonPadAdjust.createControllerAction("right-padleft-pressed")
        self.leftReleased = multiButtonPadAdjust.createControllerAction("right-padleft-released")
        self.rightPressed = multiButtonPadAdjust.createControllerAction("right-padright-pressed")
        self.rightReleased = multiButtonPadAdjust.createControllerAction("right-padright-released")

        self.registry_key = "tool_adjust"
        self.newRightCon = None
        self.AdjustControllerConstraint = None
        self.enable()

    def getMovable(self, node):
        while not node.isNull():
            if hasNodeTag(node, 'Movable'):
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

    def constraintCheckFunction(self):
        # trigger 拖拽中：锁 Z 高度，保留 Z 轴旋转 (XY 为地平面，Z 为上下)
        if self.startMoveFlag and self.node and not self.node.isNull():
            pos = getTransformNodeTranslation(self.node, 1)
            rot = getTransformNodeRotation(self.node)
            setTransformNodeTranslation(self.node, pos.x(), pos.y(), self.originalNodePos.z(), 1)
            setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), rot.z())
            self._sync_transform()
            return

        # 摇杆控制：前后平移 / 左右旋转
        if self.stickState == 'none' or not self.node:
            return
        try:
            if self.node.isNull():
                return
        except Exception:
            return

        rot = getTransformNodeRotation(self.node)
        pos = getTransformNodeTranslation(self.node, 1)

        if self.stickState == 'forward' or self.stickState == 'backward':
            # 沿对象当前 Z 轴旋转朝向在 XY 地平面上前进/后退
            angle_rad = math.radians(rot.z())
            direction = self.moveSpeed if self.stickState == 'forward' else -self.moveSpeed
            dx = -math.sin(angle_rad) * direction
            dy = math.cos(angle_rad) * direction
            setTransformNodeTranslation(self.node, pos.x() + dx, pos.y() + dy, pos.z(), 1)
        elif self.stickState == 'left':
            setTransformNodeRotation(self.node, rot.x(), rot.y(), rot.z() + self.rotateSpeed)
        elif self.stickState == 'right':
            setTransformNodeRotation(self.node, rot.x(), rot.y(), rot.z() - self.rotateSpeed)

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

    # --- 摇杆事件 ---
    def on_stick_forward(self, action=None, device=None):
        self._ensure_node()
        self.stickState = 'forward'
    def on_stick_backward(self, action=None, device=None):
        self._ensure_node()
        self.stickState = 'backward'
    def on_stick_left(self, action=None, device=None):
        self._ensure_node()
        self.stickState = 'left'
    def on_stick_right(self, action=None, device=None):
        self._ensure_node()
        self.stickState = 'right'
    def on_stick_release(self, action=None, device=None):
        self.stickState = 'none'

    def _ensure_node(self):
        # 摇杆操作时如果还没有目标节点，自动查找
        if self.node and not self.node.isNull():
            return
        try:
            nodes = getSelectedNodes()
            if nodes and len(nodes) > 0 and not nodes[0].isNull():
                self.node = self.getMovable(nodes[0])
                self._prepare_node_ref()
                return
        except Exception:
            pass
        try:
            root = getRootNode()
            if root and not root.isNull():
                children = root.getChildren()
                if children and len(children) > 0:
                    for child in children:
                        movable = self.getMovable(child)
                        if movable and not movable.isNull():
                            self.node = movable
                            self._prepare_node_ref()
                            return
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
        vrDeviceService.setActiveInteractionGroup("AdjustGroup")

        start = self.pointer.getControllerAction("start")
        start.signal().triggered.connect(self.startMove)
        execute = self.pointer.getControllerAction("execute")
        execute.signal().triggered.connect(self.stopMove)

        # 摇杆信号
        self.upPressed.signal().triggered.connect(self.on_stick_forward)
        self.upReleased.signal().triggered.connect(self.on_stick_release)
        self.downPressed.signal().triggered.connect(self.on_stick_backward)
        self.downReleased.signal().triggered.connect(self.on_stick_release)
        self.leftPressed.signal().triggered.connect(self.on_stick_left)
        self.leftReleased.signal().triggered.connect(self.on_stick_release)
        self.rightPressed.signal().triggered.connect(self.on_stick_right)
        self.rightReleased.signal().triggered.connect(self.on_stick_release)

        # timer
        if not self.timerConnected:
            self.timer.connect(self.constraintCheckFunction)
            self.timerConnected = True
        self.timer.setActive(1)

        if adjustControllerFound:
            try:
                try:
                    self.newRightCon = findNode("VRController_Move")
                except Exception:
                    self.newRightCon = None
                if not self.newRightCon:
                    try:
                        self.newRightCon = findNode("VRControllerMove")
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
                    self.AdjustControllerConstraint = vrConstraintService.createParentConstraint([self.rightController.getNode()], self.newRightCon, False)
                except Exception:
                    self.AdjustControllerConstraint = None
        else:
            try:
                self.rightController.setVisible(1)
            except Exception:
                pass

    def disable(self):
        try:
            self.isEnabled = False
            self.startMoveFlag = False
            self.stickState = 'none'
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
            self.upPressed.signal().triggered.disconnect(self.on_stick_forward)
        except Exception:
            pass
        try:
            self.upReleased.signal().triggered.disconnect(self.on_stick_release)
        except Exception:
            pass
        try:
            self.downPressed.signal().triggered.disconnect(self.on_stick_backward)
        except Exception:
            pass
        try:
            self.downReleased.signal().triggered.disconnect(self.on_stick_release)
        except Exception:
            pass
        try:
            self.leftPressed.signal().triggered.disconnect(self.on_stick_left)
        except Exception:
            pass
        try:
            self.leftReleased.signal().triggered.disconnect(self.on_stick_release)
        except Exception:
            pass
        try:
            self.rightPressed.signal().triggered.disconnect(self.on_stick_right)
        except Exception:
            pass
        try:
            self.rightReleased.signal().triggered.disconnect(self.on_stick_release)
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

adjust = AdjustTool()
print("executed")
