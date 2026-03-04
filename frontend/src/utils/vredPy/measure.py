import os

global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

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
        self.enable()

    def _find_or_load_measure_controller(self):
        try:
            node = findNode("ControllerDraw")
            if node and not node.isNull():
                return node
        except Exception:
            pass

        try:
            base_dir = None
            try:
                base_dir = os.path.join(os.environ['USERPROFILE'], 'Documents')
            except Exception:
                try:
                    base_dir = os.path.join(os.environ['HOME'], 'Documents')
                except Exception:
                    base_dir = None

            if not base_dir:
                return None

            filepath = os.path.join(base_dir, 'Autodesk', 'Automotive', 'VRED', 'ControllerDraw.osb')
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

MeasureTool()
