import math
def roundup(x):
    return int(math.ceil(x / 15.0)) * 15

class AdjustTool:
    def __init__(self):
        self.isEnabled = False
        self.node = None
        self.startMoveFlag = False
        self.snapping = False
        self.constXPressed = False
        self.constYPressed = False
        self.constZPressed = False
        self.timer = vrTimer()
        self.leftController = vrDeviceService.getVRDevice("left-controller")
        self.rightController = vrDeviceService.getVRDevice("right-controller")
        self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
        self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
        vrImmersiveInteractionService.setDefaultInteractionsActive(1)
        padCenter = vrdVirtualTouchpadButton('padcenter', 0.0, 0.5, 0.0, 360.0)
        padUpperLeft = vrdVirtualTouchpadButton('padupleft', 0.5, 1.0, 270.0, 330.0)
        padLowerLeft = vrdVirtualTouchpadButton('paddownleft', 0.5, 1.0, 210.0, 270.0)
        padUp = vrdVirtualTouchpadButton('padup', 0.5, 1.0, 330.0, 30.0)
        padLowerRight = vrdVirtualTouchpadButton('paddownright', 0.5, 1.0, 90.0, 150.0)
        padDown = vrdVirtualTouchpadButton('paddown', 0.5, 1.0, 150.0, 210.0)
        self.rightController.addVirtualButton(padCenter, 'touchpad')
        self.rightController.addVirtualButton(padUpperLeft, 'touchpad')
        self.rightController.addVirtualButton(padLowerLeft, 'touchpad')
        self.rightController.addVirtualButton(padUp, 'touchpad')
        self.rightController.addVirtualButton(padLowerRight, 'touchpad')
        self.rightController.addVirtualButton(padDown, 'touchpad')
        multiButtonPadAdjust = vrDeviceService.createInteraction("MultiButtonPadAdjust")
        multiButtonPadAdjust.setSupportedInteractionGroups(["AdjustGroup"])
        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("AdjustGroup")
        teleport.setControllerActionMapping("prepare", "left-touchpad-touched")
        teleport.setControllerActionMapping("abort", "left-touchpad-untouched")
        teleport.setControllerActionMapping("execute", "left-touchpad-pressed")
        self.pointer = vrDeviceService.getInteraction("Pointer")
        self.pointer.addSupportedInteractionGroup("AdjustGroup")
        self.leftDownAction = multiButtonPadAdjust.createControllerAction("right-paddownleft-pressed")
        self.upAction = multiButtonPadAdjust.createControllerAction("right-padup-pressed")
        self.rightDownAction = multiButtonPadAdjust.createControllerAction("right-paddownright-pressed")
        self.centerAction = multiButtonPadAdjust.createControllerAction("right-padcenter-pressed")
        self.enable()
    def getMovable(self, node):
        while not node.isNull():
            if hasNodeTag(node, 'Movable'):
                return node
            if node.getName() == "Group" or node.getName() == "Transform":
                break
            node = node.getParent()
        return node
    def constraintCheckFunction(self):
        if self.startMoveFlag and self.node and not self.node.isNull():
            self.currentNodePos = getTransformNodeTranslation(self.node, 1)
            self.currentNodeRot = getTransformNodeRotation(self.node)
            if self.constXPressed and self.constYPressed:
                t = "%f,%f,%f" % (self.currentNodePos.x(), self.currentNodePos.y(), self.originalNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                r = "%f,%f,%f" % (self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                setTransformNodeTranslation(self.node, self.currentNodePos.x(), self.currentNodePos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constYPressed and self.constZPressed:
                t = "%f,%f,%f" % (self.originalNodePos.x(), self.currentNodePos.y(), self.currentNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                r = "%f,%f,%f" % (self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                setTransformNodeTranslation(self.node, self.originalNodePos.x(), self.currentNodePos.y(), self.currentNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constXPressed and self.constZPressed:
                t = "%f,%f,%f" % (self.currentNodePos.x(), self.originalNodePos.y(), self.currentNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                r = "%f,%f,%f" % (self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                setTransformNodeTranslation(self.node, self.currentNodePos.x(), self.originalNodePos.y(), self.currentNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constXPressed:
                t = "%f,%f,%f" % (self.currentNodePos.x(), self.originalNodePos.y(), self.originalNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                r = "%f,%f,%f" % (self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                setTransformNodeTranslation(self.node, self.currentNodePos.x(), self.originalNodePos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constYPressed:
                t = "%f,%f,%f" % (self.originalNodePos.x(), self.currentNodePos.y(), self.originalNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                r = "%f,%f,%f" % (self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                setTransformNodeTranslation(self.node, self.originalNodePos.x(), self.currentNodePos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constZPressed:
                t = "%f,%f,%f" % (self.originalNodePos.x(), self.originalNodePos.y(), self.currentNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                r = "%f,%f,%f" % (self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                setTransformNodeTranslation(self.node, self.originalNodePos.x(), self.originalNodePos.y(), self.currentNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.snapping:
                self.currentNodeRot = getTransformNodeRotation(self.node)
                x = roundup(self.currentNodeRot.x())
                y = roundup(self.currentNodeRot.y())
                z = roundup(self.currentNodeRot.z())
                r = "%f,%f,%f" % (x, y, z)
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
                setTransformNodeRotation(self.node, x, y, z)
                t = "%f,%f,%f" % (self.currentNodePos.x(), self.currentNodePos.y(), self.currentNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
            else:
                t = "%f,%f,%f" % (self.currentNodePos.x(), self.currentNodePos.y(), self.currentNodePos.z())
                vrSessionService.sendPython('setTransformNodeTranslation(nodeRef, ' + t + ', True)')
                r = "%f,%f,%f" % (self.currentNodeRot.x(), self.currentNodeRot.y(), self.currentNodeRot.z())
                vrSessionService.sendPython('setTransformNodeRotation(nodeRef, ' + r + ')')
    def startMove(self, action, device):
        self.node = self.getMovable(device.pick().getNode())
        if not self.node.isNull():
            self.originalNodeRot = getTransformNodeRotation(self.node)
            self.constraint = vrConstraintService.createParentConstraint([device.getNode()], self.node, True)
            self.originalNodePos = getTransformNodeTranslation(self.node, 1)
            self.startMoveFlag = True
            mypath = getUniquePath(self.node)
            nameString = "%s" % mypath
            vrSessionService.sendPython('"' + nameString + '"')
            vrSessionService.sendPython('nodeRef = findUniquePath("' + nameString + '")')
    def stopMove(self, action, device):
        if not self.node == None and not self.node.isNull():
            self.finalNodePos = getTransformNodeTranslation(self.node, 1)
            self.finalNodeRot = getTransformNodeRotation(self.node)
            if self.constXPressed and self.constYPressed:
                setTransformNodeTranslation(self.node, self.currentNodePos.x(), self.currentNodePos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constYPressed and self.constZPressed:
                setTransformNodeTranslation(self.node, self.originalNodePos.x(), self.currentNodePos.y(), self.currentNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constXPressed and self.constZPressed:
                setTransformNodeTranslation(self.node, self.currentNodePos.x(), self.originalNodePos.y(), self.currentNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constXPressed:
                setTransformNodeTranslation(self.node, self.currentNodePos.x(), self.originalNodePos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constYPressed:
                setTransformNodeTranslation(self.node, self.originalNodePos.x(), self.currentNodePos.y(), self.originalNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.constZPressed:
                setTransformNodeTranslation(self.node, self.originalNodePos.x(), self.originalNodePos.y(), self.currentNodePos.z(), 1)
                setTransformNodeRotation(self.node, self.originalNodeRot.x(), self.originalNodeRot.y(), self.originalNodeRot.z())
            elif self.snapping:
                self.currentNodeRot = getTransformNodeRotation(self.node)
                x = roundup(self.currentNodeRot.x())
                y = roundup(self.currentNodeRot.y())
                z = roundup(self.currentNodeRot.z())
                setTransformNodeRotation(self.node, x, y, z)
            vrConstraintService.deleteConstraint(self.constraint)
            self.startMoveFlag = False
    def constX(self):
        self.constXPressed = not self.constXPressed
    def constY(self):
        self.constYPressed = not self.constYPressed
    def constZ(self):
        self.constZPressed = not self.constZPressed
    def constCenter(self):
        self.snapping = not self.snapping
    def enable(self):
        self.isEnabled = True
        vrDeviceService.setActiveInteractionGroup("AdjustGroup")
        self.leftDownAction.signal().triggered.connect(self.constX)
        self.upAction.signal().triggered.connect(self.constY)
        self.rightDownAction.signal().triggered.connect(self.constZ)
        self.centerAction.signal().triggered.connect(self.constCenter)
        start = self.pointer.getControllerAction("start")
        start.signal().triggered.connect(self.startMove)
        execute = self.pointer.getControllerAction("execute")
        execute.signal().triggered.connect(self.stopMove)
        self.timer.setActive(1)
        self.timer.connect(self.constraintCheckFunction)

adjust = AdjustTool()
print("executed")
