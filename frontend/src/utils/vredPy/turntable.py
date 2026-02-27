import os

global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

rotationControllerFound = False
try:
    allRotNodes = getAllNodes()
    for node in allRotNodes:
        nodeName = node.getName()
        if nodeName == "VRController_Rotation" or nodeName == "VRControllerRotation":
            rotationControllerFound = True
            break
except Exception:
    rotationControllerFound = False

if not rotationControllerFound:
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
            filename = os.path.join(filepath, 'VRControllerRotation.osb')
            if os.path.exists(filename):
                node = loadGeometry(filename)
                try:
                    node.setName("VRControllerRotation")
                except Exception:
                    pass
                rotationControllerFound = True
    except Exception:
        rotationControllerFound = False

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

        # touchpad: 左=逆时针, 右=顺时针, 用 touched 而非 pressed
        padLeft = vrdVirtualTouchpadButton('padleft', 0.3, 1.0, 180.0, 360.0)
        padRight = vrdVirtualTouchpadButton('padright', 0.3, 1.0, 0.0, 180.0)
        self.rightController.addVirtualButton(padLeft, 'touchpad')
        self.rightController.addVirtualButton(padRight, 'touchpad')

        multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadTurntable")
        multiButtonPad.setSupportedInteractionGroups(["TurntableGroup"])

        # 保留 teleport 在左手
        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("TurntableGroup")
        teleport.setControllerActionMapping("prepare", "left-touchpad-touched")
        teleport.setControllerActionMapping("abort", "left-touchpad-untouched")
        teleport.setControllerActionMapping("execute", "left-touchpad-pressed")

        # 摇杆拨动切换方向 (touched = 摆动即触发)
        self.leftTouched = multiButtonPad.createControllerAction("right-padleft-touched")
        self.rightTouched = multiButtonPad.createControllerAction("right-padright-touched")

        # trigger: 按一次启动，再按一次停止
        self.triggerAction = multiButtonPad.createControllerAction("right-trigger-pressed")

        self.registry_key = "tool_turntable"
        self.enable()

    def _resolve_target(self):
        try:
            nodes = getSelectedNodes()
            if nodes and len(nodes) > 0:
                try:
                    if nodes[0].isNull():
                        return None
                except Exception:
                    pass
                movable = self._get_movable(nodes[0])
                return movable if movable else nodes[0]
        except Exception:
            pass
        try:
            root = getRootNode()
            if root and not root.isNull():
                children = root.getChildren()
                if children and len(children) > 0:
                    movable = self._find_movable_in_list(children)
                    if movable:
                        return movable
        except Exception:
            pass
        try:
            nodes = getAllNodes()
            if nodes:
                movable = self._find_movable_in_list(nodes)
                if movable:
                    return movable
        except Exception:
            pass
        return None

    def _get_movable(self, node):
        try:
            while node and not node.isNull():
                if hasNodeTag(node, 'Movable'):
                    return node
                if node.getName() in ("Group", "Transform"):
                    return node
                node = node.getParent()
        except Exception:
            pass
        return None

    def _find_movable_in_list(self, nodes):
        try:
            for node in nodes:
                movable = self._get_movable(node)
                if movable:
                    return movable
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
        self.leftTouched.signal().triggered.connect(self.set_counterclockwise)
        self.rightTouched.signal().triggered.connect(self.set_clockwise)
        self.triggerAction.signal().triggered.connect(self.on_trigger_toggle)
        if rotationControllerFound:
            try:
                try:
                    self.newRightCon = findNode("VRController_Rotation")
                except Exception:
                    self.newRightCon = None
                if not self.newRightCon:
                    try:
                        self.newRightCon = findNode("VRControllerRotation")
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
                    self.RotationControllerConstraint = vrConstraintService.createParentConstraint([self.rightController.getNode()], self.newRightCon, False)
                except Exception:
                    self.RotationControllerConstraint = None

    def disable(self):
        self.isEnabled = False
        self.stop_rotation()
        try:
            if vred_tool_registry.get(self.registry_key) is self:
                del vred_tool_registry[self.registry_key]
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
            self.triggerAction.signal().triggered.disconnect(self.on_trigger_toggle)
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
            if self.RotationControllerConstraint:
                vrConstraintService.deleteConstraint(self.RotationControllerConstraint)
                self.RotationControllerConstraint = None
        except Exception:
            pass

    def set_clockwise(self, action=None, device=None):
        self.direction = 1
        print("[Turntable] direction: clockwise")

    def set_counterclockwise(self, action=None, device=None):
        self.direction = -1
        print("[Turntable] direction: counterclockwise")

    def on_trigger_toggle(self, action=None, device=None):
        if self.rotating:
            self.stop_rotation()
        else:
            self.start_rotation()

    def start_rotation(self):
        self.node = self._resolve_target()
        if not self.node:
            print("[Turntable] no target node")
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
        print("[Turntable] start rotation, dir:", self.direction)

    def stop_rotation(self):
        if self.rotating:
            print("[Turntable] stop rotation")
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

TurntableTool()
