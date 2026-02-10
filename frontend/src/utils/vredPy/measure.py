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
        self.enable()
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

MeasureTool()
