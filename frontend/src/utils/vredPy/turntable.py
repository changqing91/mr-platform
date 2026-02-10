global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

class TurntableTool:
    def __init__(self):
        self.isEnabled = False
        self.direction = 1
        self.speed = 1.0
        self.node = None
        self.nodeRefReady = False
        self.timer = vrTimer()
        self.leftController = vrDeviceService.getVRDevice("left-controller")
        self.rightController = vrDeviceService.getVRDevice("right-controller")
        self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
        self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
        padCenter = vrdVirtualTouchpadButton('padcenter', 0.0, 0.5, 0.0, 360.0)
        padUpperLeft = vrdVirtualTouchpadButton('padupleft', 0.5, 1.0, 270.0, 330.0)
        padUpperRight = vrdVirtualTouchpadButton('padupright', 0.5, 1.0, 30.0, 90.0)
        self.rightController.addVirtualButton(padCenter, 'touchpad')
        self.rightController.addVirtualButton(padUpperLeft, 'touchpad')
        self.rightController.addVirtualButton(padUpperRight, 'touchpad')
        multiButtonPadTurntable = vrDeviceService.createInteraction("MultiButtonPadTurntable")
        multiButtonPadTurntable.setSupportedInteractionGroups(["TurntableGroup"])
        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("TurntableGroup")
        teleport.setControllerActionMapping("prepare", "left-touchpad-touched")
        teleport.setControllerActionMapping("abort", "left-touchpad-untouched")
        teleport.setControllerActionMapping("execute", "left-touchpad-pressed")
        self.pointer = vrDeviceService.getInteraction("Pointer")
        self.pointer.addSupportedInteractionGroup("TurntableGroup")
        self.leftAction = multiButtonPadTurntable.createControllerAction("right-padupleft-pressed")
        self.rightAction = multiButtonPadTurntable.createControllerAction("right-padupright-pressed")
        self.centerAction = multiButtonPadTurntable.createControllerAction("right-padcenter-pressed")
        self.timer.connect(self.updateRotation)
        self.registry_key = "tool_turntable"
        self.enable()
    def _resolve_target(self):
        try:
            nodes = getSelectedNodes()
            if nodes and len(nodes) > 0:
                return self._get_movable(nodes[0])
        except Exception:
            pass
        try:
            root = getRootNode()
            if root and not root.isNull():
                children = root.getChildren()
                if children and len(children) > 0:
                    movable_child = self._find_movable_in_list(children)
                    if movable_child:
                        return movable_child
        except Exception:
            pass
        try:
            nodes = getAllNodes()
            if nodes:
                movable_node = self._find_movable_in_list(nodes)
                if movable_node:
                    return movable_node
        except Exception:
            pass
        return None
    def _get_movable(self, node):
        try:
            while node and not node.isNull():
                if hasNodeTag(node, 'Movable'):
                    return node
                if node.getName() == "Group" or node.getName() == "Transform":
                    break
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
        self.leftAction.signal().triggered.connect(self.start_clockwise)
        self.rightAction.signal().triggered.connect(self.start_counterclockwise)
        self.centerAction.signal().triggered.connect(self.stop_rotation)
    def disable(self):
        self.isEnabled = False
        try:
            if vred_tool_registry.get(self.registry_key) is self:
                del vred_tool_registry[self.registry_key]
        except Exception:
            pass
        try:
            self.leftAction.signal().triggered.disconnect(self.start_clockwise)
        except Exception:
            pass
        try:
            self.rightAction.signal().triggered.disconnect(self.start_counterclockwise)
        except Exception:
            pass
        try:
            self.centerAction.signal().triggered.disconnect(self.stop_rotation)
        except Exception:
            pass
        try:
            self.timer.setActive(0)
        except Exception:
            pass
    def start_clockwise(self):
        self.direction = 1
        self.start_rotation()
    def start_counterclockwise(self):
        self.direction = -1
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
        self.timer.setActive(1)
    def stop_rotation(self):
        self.timer.setActive(0)
    def updateRotation(self):
        if not self.node:
            return
        try:
            if self.node.isNull():
                self.timer.setActive(0)
                return
        except Exception:
            pass
        rot = getTransformNodeRotation(self.node)
        new_x = rot.x()
        new_y = rot.y()
        new_z = rot.z() + (self.speed * self.direction)
        setTransformNodeRotation(self.node, new_x, new_y, new_z)
        if self.nodeRefReady:
            r = "%f,%f,%f" % (new_x, new_y, new_z)
            vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')

TurntableTool()
