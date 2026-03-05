import os

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

rotationControllerFound = False
# rotationControllerFound = False
# try:
#     allRotNodes = getAllNodes()
#     for node in allRotNodes:
#         nodeName = node.getName()
#         if nodeName == "VRController_Rotation" or nodeName == "VRControllerRotation":
#             rotationControllerFound = True
#             break
# except Exception:
#     rotationControllerFound = False

# if not rotationControllerFound:
#     try:
#         base_dir = None
#         try:
#             base_dir = os.path.join(os.environ['USERPROFILE'], 'Documents')
#         except Exception:
#             try:
#                 base_dir = os.path.join(os.environ['HOME'], 'Documents')
#             except Exception:
#                 base_dir = None
#         if base_dir:
#             filepath = os.path.join(base_dir, 'Autodesk', 'Automotive', 'VRED')
#             filename = os.path.join(filepath, 'VRControllerRotation.osb')
#             if os.path.exists(filename):
#                 node = loadGeometry(filename)
#                 try:
#                     node.setName("VRControllerRotation")
#                 except Exception:
#                     pass
#                 rotationControllerFound = True
#     except Exception:
#         rotationControllerFound = False

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

        # touchpad/thumbstick: 左=逆时针, 右=顺时针, 用 touched 而非 pressed
        padLeft = vrdVirtualTouchpadButton('padleft', 0.3, 1.0, 180.0, 360.0)
        padRight = vrdVirtualTouchpadButton('padright', 0.3, 1.0, 0.0, 180.0)
        self.rightController.addVirtualButton(padLeft, _pad_input)
        self.rightController.addVirtualButton(padRight, _pad_input)

        self.multiButtonPad = vrDeviceService.createInteraction("MultiButtonPadTurntable")
        self.multiButtonPad.setSupportedInteractionGroups(["TurntableGroup"])

        # 保留 teleport 在左手
        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("TurntableGroup")
        teleport.setControllerActionMapping("prepare", "left-{}-touched".format(_pad_input))
        teleport.setControllerActionMapping("abort", "left-{}-untouched".format(_pad_input))
        teleport.setControllerActionMapping("execute", "left-{}-pressed".format(_pad_input))

        # 使用 Pointer 交互来处理 trigger
        self.pointer = vrDeviceService.getInteraction("Pointer")
        self.pointer.addSupportedInteractionGroup("TurntableGroup")

        # 摇杆拨动切换方向 (touched = 摆动即触发)
        self.leftTouched = self.multiButtonPad.createControllerAction("right-padleft-touched")
        self.rightTouched = self.multiButtonPad.createControllerAction("right-padright-touched")

        print("[Turntable] Interaction created and actions registered")

        self.registry_key = "tool_turntable"
        self.enable()

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
        print("[Turntable] _resolve_target called")

        # 1. 如果用户选中了节点，从选中节点向上找 Movable 祖先
        try:
            nodes = getSelectedNodes()
            print("[Turntable] selected nodes:", len(nodes) if nodes else 0)
            if nodes and len(nodes) > 0:
                try:
                    if nodes[0].isNull():
                        print("[Turntable] first selected node is null")
                        return None
                except Exception:
                    pass
                print("[Turntable] selected node name:", nodes[0].getName())
                movable = self._get_movable(nodes[0])
                result = movable if movable else nodes[0]
                print("[Turntable] returning selected node:", result.getName() if result else "None")
                return result
        except Exception as e:
            print("[Turntable] error getting selected nodes:", str(e))
            pass

        # 2. 没有选中节点时，直接用 vrMetadataService 查找所有带 Movable 标签的节点
        try:
            tagged = vrMetadataService.getObjectsWithTag('Movable')
            print("[Turntable] objects with Movable tag:", len(tagged) if tagged else 0)
            if tagged and len(tagged) > 0:
                for obj in tagged:
                    try:
                        if not obj.isNull():
                            name = obj.getName()
                            if "VRController" in name or "controller" in name.lower():
                                continue
                            print("[Turntable] found Movable-tagged node:", name)
                            return obj
                    except Exception:
                        continue
        except Exception as e:
            print("[Turntable] error querying Movable tag:", str(e))
            pass

        # 3. 兜底：从根节点子级中取第一个非控制器节点
        try:
            root = getRootNode()
            if root and not root.isNull():
                children = root.getChildren()
                print("[Turntable] fallback: root children count:", len(children) if children else 0)
                if children and len(children) > 0:
                    for child in children:
                        try:
                            if not child.isNull():
                                name = child.getName()
                                if "VRController" in name or "controller" in name.lower():
                                    continue
                                print("[Turntable] fallback: using root child:", name)
                                return child
                        except Exception:
                            continue
        except Exception as e:
            print("[Turntable] error in fallback:", str(e))
            pass

        print("[Turntable] no target found")
        return None

    def _get_movable(self, node):
        try:
            original_node = node
            while node and not node.isNull():
                name = node.getName()
                print("[Turntable] checking node:", name)
                if vrMetadataService.hasTag(node, 'Movable'):
                    print("[Turntable] found Movable tag on:", name)
                    return node
                if name in ("Group", "Transform"):
                    print("[Turntable] found Group/Transform:", name)
                    return node
                node = node.getParent()
            # 如果没找到特殊标记，返回原始节点
            print("[Turntable] no special tag found, returning original")
            return original_node
        except Exception as e:
            print("[Turntable] error in _get_movable:", str(e))
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
        print("[Turntable] Active interaction group set to TurntableGroup")
        
        # 使用 Pointer 的 start action 来处理 trigger 按下
        triggerStart = self.pointer.getControllerAction("start")
        triggerStart.signal().triggered.connect(self.on_trigger_toggle)
        
        self.leftTouched.signal().triggered.connect(self.set_counterclockwise)
        self.rightTouched.signal().triggered.connect(self.set_clockwise)
        print("[Turntable] Signal connections established")
        
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
            if hasattr(self, 'multiButtonPad') and self.multiButtonPad:
                vrDeviceService.deleteInteraction(self.multiButtonPad)
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
        print("[Turntable] direction: clockwise")

    def set_counterclockwise(self, action=None, device=None):
        self.direction = -1
        print("[Turntable] direction: counterclockwise")

    def on_trigger_toggle(self, action=None, device=None):
        print("[Turntable] trigger pressed, rotating:", self.rotating)
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
                print("[Turntable] node is null")
                return
        except Exception:
            pass
        
        print("[Turntable] target node found:", self.node.getName())
        self._prepare_node_ref()
        
        try:
            rot = getTransformNodeRotation(self.node)
            self.currentAngle = rot.z()
            print("[Turntable] initial angle:", self.currentAngle)
        except Exception as e:
            print("[Turntable] error getting rotation:", str(e))
            self.currentAngle = 0.0
            
        self.rotating = True
        self._start_timer()
        print("[Turntable] start rotation, dir:", self.direction, "timer active:", self.timer.isActive())

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
            print("[Turntable] rotating, angle:", self.currentAngle)
        except Exception as e:
            print("[Turntable] rotation error:", str(e))
            pass
            
        if self.nodeRefReady:
            try:
                r = "%f,%f,%f" % (rot.x(), rot.y(), self.currentAngle)
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
            except Exception:
                pass

TurntableTool()
