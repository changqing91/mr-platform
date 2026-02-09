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
        self.enable()
    def enable(self):
        self.isEnabled = True
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
    def GridVis(self):
        self.gridVis = not self.gridVis
        setClippingShowGrid(1 if self.gridVis else 0)
    def PlaneVis(self):
        self.planeVis = not self.planeVis
        setClippingShowPlane(1 if self.planeVis else 0)
    def ContourVis(self):
        self.contourVis = not self.contourVis
        setClippingShowContour(1 if self.contourVis else 0)
    def constX(self):
        self.constXPressed = not self.constXPressed
        if self.constXPressed:
            setClippingPlaneRotation(0, 0, 90)
    def constY(self):
        self.constYPressed = not self.constYPressed
        if self.constYPressed:
            setClippingPlaneRotation(0, 90, 0)
    def constZ(self):
        self.constZPressed = not self.constZPressed
        if self.constZPressed:
            setClippingPlaneRotation(90, 0, 0)
    def ClippingState(self):
        if self.clipping == False:
            enableClippingPlane(1)
            self.clipping = True
        else:
            enableClippingPlane(0)
            self.clipping = False
    def trigger_right_pressed(self):
        if self.clipping == True:
            self.timer.setActive(1)
            self.timer.connect(self.trigger_right_pressed)
            self.currentPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
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
                self.originalPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                p = "%f,%f,%f" % (self.originalPos.x(), self.originalPos.y(), self.originalPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
                self.originalRot = getTransformNodeRotation(self.rightController.getNode())
                r = "%f,%f,%f" % (self.originalRot.x() + 90, self.originalRot.y(), self.originalRot.z())
                vrSessionService.sendPython("setClippingPlaneRotation(" + r + ")")
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
                self.originalPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
                p = "%f,%f,%f" % (self.originalPos.x(), self.originalPos.y(), self.originalPos.z())
                vrSessionService.sendPython("point = Pnt3f(" + p + ")")
                vrSessionService.sendPython("setClippingPlanePosition(point)")
SectionTool()
