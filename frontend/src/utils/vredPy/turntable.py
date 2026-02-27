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
        self.ignoreStopOnce = False
        print("[Turntable] init begin")
        self.leftController = vrDeviceService.getVRDevice("left-controller")
        self.rightController = vrDeviceService.getVRDevice("right-controller")
        print("[Turntable] controllers", self.leftController, self.rightController)
        self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
        self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
        padCenter = vrdVirtualTouchpadButton('padcenter', 0.0, 0.5, 0.0, 360.0)
        padUpperLeft = vrdVirtualTouchpadButton('padupleft', 0.5, 1.0, 270.0, 330.0)
        padLowerLeft = vrdVirtualTouchpadButton('paddownleft', 0.5, 1.0, 210.0, 270.0)
        padUpperRight = vrdVirtualTouchpadButton('padupright', 0.5, 1.0, 30.0, 90.0)
        padLowerRight = vrdVirtualTouchpadButton('paddownright', 0.5, 1.0, 90.0, 150.0)
        self.rightController.addVirtualButton(padCenter, 'touchpad')
        self.rightController.addVirtualButton(padUpperLeft, 'touchpad')
        self.rightController.addVirtualButton(padLowerLeft, 'touchpad')
        self.rightController.addVirtualButton(padUpperRight, 'touchpad')
        self.rightController.addVirtualButton(padLowerRight, 'touchpad')
        multiButtonPadTurntable = vrDeviceService.createInteraction("MultiButtonPadTurntable")
        multiButtonPadTurntable.setSupportedInteractionGroups(["TurntableGroup"])
        self.leftUpperAction = multiButtonPadTurntable.createControllerAction("right-padupleft-pressed")
        self.leftLowerAction = multiButtonPadTurntable.createControllerAction("right-paddownleft-pressed")
        self.rightUpperAction = multiButtonPadTurntable.createControllerAction("right-padupright-pressed")
        self.rightLowerAction = multiButtonPadTurntable.createControllerAction("right-paddownright-pressed")
        self.centerAction = multiButtonPadTurntable.createControllerAction("right-padcenter-pressed")
        self.timer.connect(self.updateRotation)
        self.registry_key = "tool_turntable"
        print("[Turntable] init done")
        self.enable()
    def _resolve_target(self):
        print("[Turntable] resolve target begin")
        try:
            nodes = getSelectedNodes()
            if nodes and len(nodes) > 0:
                print("[Turntable] selected nodes", len(nodes))
                try:
                    print("[Turntable] selected node", nodes[0].getName())
                except Exception:
                    print("[Turntable] selected node")
                try:
                    if nodes[0].isNull():
                        print("[Turntable] selected node is null")
                        return None
                except Exception:
                    pass
                movable = self._get_movable(nodes[0])
                if movable:
                    return movable
                try:
                    print("[Turntable] selected fallback node", nodes[0].getName())
                except Exception:
                    print("[Turntable] selected fallback node")
                return nodes[0]
        except Exception:
            pass
        try:
            root = getRootNode()
            if root and not root.isNull():
                children = root.getChildren()
                if children and len(children) > 0:
                    print("[Turntable] root children", len(children))
                    movable_child = self._find_movable_in_list(children)
                    if movable_child:
                        return movable_child
        except Exception:
            pass
        try:
            nodes = getAllNodes()
            if nodes:
                print("[Turntable] all nodes", len(nodes))
                movable_node = self._find_movable_in_list(nodes)
                if movable_node:
                    return movable_node
        except Exception:
            pass
        print("[Turntable] resolve target none")
        return None
    def _get_movable(self, node):
        try:
            while node and not node.isNull():
                try:
                    print("[Turntable] inspect node", node.getName())
                except Exception:
                    print("[Turntable] inspect node")
                if hasNodeTag(node, 'Movable'):
                    try:
                        print("[Turntable] movable tag node", node.getName())
                    except Exception:
                        print("[Turntable] movable tag node")
                    return node
                if node.getName() == "Group" or node.getName() == "Transform":
                    try:
                        print("[Turntable] fallback group/transform", node.getName())
                    except Exception:
                        print("[Turntable] fallback group/transform")
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
            print("[Turntable] prepare node ref", nameString)
            vrSessionService.sendPython('"' + nameString + '"')
            vrSessionService.sendPython('nodeRef = findUniquePath("' + nameString + '")')
            self.nodeRefReady = True
        except Exception:
            self.nodeRefReady = False
    def enable(self):
        self.isEnabled = True
        print("[Turntable] enable")
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
        self.leftUpperAction.signal().triggered.connect(self.start_clockwise)
        self.leftLowerAction.signal().triggered.connect(self.start_clockwise)
        self.rightUpperAction.signal().triggered.connect(self.start_counterclockwise)
        self.rightLowerAction.signal().triggered.connect(self.start_counterclockwise)
        self.centerAction.signal().triggered.connect(self.stop_rotation)
        print("[Turntable] actions connected")
    def disable(self):
        self.isEnabled = False
        print("[Turntable] disable")
        try:
            if vred_tool_registry.get(self.registry_key) is self:
                del vred_tool_registry[self.registry_key]
        except Exception:
            pass
        try:
            self.leftUpperAction.signal().triggered.disconnect(self.start_clockwise)
        except Exception:
            pass
        try:
            self.leftLowerAction.signal().triggered.disconnect(self.start_clockwise)
        except Exception:
            pass
        try:
            self.rightUpperAction.signal().triggered.disconnect(self.start_counterclockwise)
        except Exception:
            pass
        try:
            self.rightLowerAction.signal().triggered.disconnect(self.start_counterclockwise)
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
    def start_clockwise(self, action=None, device=None):
        self.direction = 1
        print("[Turntable] start clockwise", action, device)
        self.start_rotation()
    def start_counterclockwise(self, action=None, device=None):
        self.direction = -1
        print("[Turntable] start counterclockwise", action, device)
        self.start_rotation()
    def start_rotation(self):
        print("[Turntable] start rotation")
        self.node = self._resolve_target()
        if not self.node:
            print("[Turntable] no target node")
            return
        try:
            if self.node.isNull():
                print("[Turntable] target node is null")
                return
            try:
                print("[Turntable] target node ready", self.node.getName())
            except Exception:
                print("[Turntable] target node ready")
        except Exception:
            pass
        self._prepare_node_ref()
        self.ignoreStopOnce = False
        self.timer.setActive(1)
    def stop_rotation(self, action=None, device=None):
        print("[Turntable] stop rotation", action, device)
        self.ignoreStopOnce = False
        self.timer.setActive(0)
    def updateRotation(self):
        if not self.node:
            print("[Turntable] update skipped no node")
            return
        try:
            if self.node.isNull():
                self.timer.setActive(0)
                print("[Turntable] update stopped node null")
                return
        except Exception:
            pass
        rot = getTransformNodeRotation(self.node)
        new_x = rot.x()
        new_y = rot.y()
        new_z = rot.z() + (self.speed * self.direction)
        print("[Turntable] update rotation", new_x, new_y, new_z, "dir", self.direction, "speed", self.speed)
        setTransformNodeRotation(self.node, new_x, new_y, new_z)
        if self.nodeRefReady:
            r = "%f,%f,%f" % (new_x, new_y, new_z)
            vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')

TurntableTool()
