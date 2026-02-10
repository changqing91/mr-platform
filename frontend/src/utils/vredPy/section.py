import os

global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

clippingControllerFound = False
try:
    allClipNodes = getAllNodes()
    for node in allClipNodes:
        nodeName = node.getName()
        if nodeName == "VRController_Clip" or nodeName == "VRControllerClip":
            clippingControllerFound = True
            break
except Exception:
    clippingControllerFound = False

if not clippingControllerFound:
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
            filename = os.path.join(filepath, 'VRControllerClip.osb')
            if os.path.exists(filename):
                node = loadGeometry(filename)
                try:
                    node.setName("VRControllerClip")
                except Exception:
                    pass
                clippingControllerFound = True
    except Exception:
        clippingControllerFound = False

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
        self.rightController.addVirtualButton(padCenter, 'touchpad')
        self.rightController.addVirtualButton(padUpperLeft, 'touchpad')
        self.rightController.addVirtualButton(padLowerLeft, 'touchpad')
        self.rightController.addVirtualButton(padUp, 'touchpad')
        self.rightController.addVirtualButton(padUpperRight, 'touchpad')
        self.rightController.addVirtualButton(padLowerRight, 'touchpad')
        self.rightController.addVirtualButton(padDown, 'touchpad')
        multiButtonPadClip = vrDeviceService.createInteraction("MultiButtonPadClip")
        multiButtonPadClip.setSupportedInteractionGroups(["ClipGroup"])
        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("ClipGroup")
        teleport.setControllerActionMapping("prepare", "left-touchpad-touched")
        teleport.setControllerActionMapping("abort", "left-touchpad-untouched")
        teleport.setControllerActionMapping("execute", "left-touchpad-pressed")
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
        if self.clipping == False:
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
        if self.clipping == True:
            self.timer.setActive(1)
            self.timer.connect(self.trigger_right_pressed)
            try:
                node = self.newRightCon if self.newRightCon else self.rightController.getNode()
            except Exception:
                node = None
            if not node:
                return
            self.currentPos = getTransformNodeTranslation(node, 1)
            if self.constXPressed == True:
                p = "%f,%f,%f" % (self.currentPos.x(), self.originalPos.y(), self.originalPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
            elif self.constYPressed == True:
                p = "%f,%f,%f" % (self.originalPos.x(), self.currentPos.y(), self.originalPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
            elif self.constZPressed == True:
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
        if self.clipping == True:
            self.timer.setActive(0)
            if self.constXPressed == True and self.constYPressed == True:
                p = "%f,%f,%f" % (self.currentPos.x(), self.currentPos.y(), self.originalPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
            elif self.constYPressed == True and self.constZPressed == True:
                p = "%f,%f,%f" % (self.originalPos.x(), self.currentPos.y(), self.currentPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
            elif self.constXPressed == True and self.constZPressed == True:
                p = "%f,%f,%f" % (self.currentPos.x(), self.originalPos.y(), self.currentPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
            elif self.constXPressed == True:
                p = "%f,%f,%f" % (self.currentPos.x(), self.originalPos.y(), self.originalPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
            elif self.constYPressed == True:
                p = "%f,%f,%f" % (self.originalPos.x(), self.currentPos.y(), self.originalPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
            elif self.constZPressed == True:
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
SectionTool()
