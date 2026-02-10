import random

global vred_tool_registry
if 'vred_tool_registry' not in globals():
    vred_tool_registry = {}

notesControllerFound = False
mainCustomFuncGroup = False

notesController = 0
goodBadNotes = 0
allNotesNodes = getAllNodes()
for node in allNotesNodes:
    allNotesNodeName = node.getName()
    if allNotesNodeName == "VRController_Notes":
        notesController += 1
    elif allNotesNodeName == "Notes":
        goodBadNotes += 1
    elif allNotesNodeName == "VRED-VR-Custom-Fucntion":
        mainCustomFuncGroup = True
        customFunctionsGroup = node

if notesController == 0:
    import os
    myDocuments = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Documents')
    filepath = myDocuments + "\\Autodesk\\Automotive\\VRED"
    filename = "\\VRControllerNotes"
    if os.path.exists(filepath + str(filename) + ".osb"):
        node = loadGeometry(filepath + str(filename) + ".osb")
        node.setName("VRControllerNotes")
        notesControllerFound = True
    else:
        notesControllerFound = False
else:
    notesControllerFound = True

if goodBadNotes == 0:
    import os
    myDocuments = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Documents')
    filepath = myDocuments + "\\Autodesk\\Automotive\\VRED"
    filename = "\\VRControllerNotes_Notes"
    node = loadGeometry(filepath + str(filename) + ".osb")
    node.setName("VRControllerNotes_Notes")
    createNode("Group", "Cloned_ref_obj")

if not mainCustomFuncGroup:
    customFunctionsGroup = createNode('Group', 'VRED-VR-Custom-Fucntion')

allFucnNames = [
    "VRControllerMove",
    "VRControllerSelect",
    "VRControllerNotes",
    "VRControllerDraw",
    "VRControllerNotes_Notes",
    "Cloned_ref_obj",
    "D_Tool",
    "D_Lines",
    "D_tempLine",
    "Group_html"
]

allNodeFuncname = getAllNodes()
for node in allNodeFuncname:
    nodeName = node.getName()
    if nodeName in allFucnNames:
        addChilds(customFunctionsGroup, [node])

refObject = findNode("Notes").getChild(0)
switch = findNode("Notes")
count = 0
Cloned_ref_obj = findNode("Cloned_ref_obj")

class Notes:
    def __init__(self):
        self.isEnabled = False
        self.activeNode = None
        self.upbuttonIsActive = False
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

        multiButtonPadNotes = vrDeviceService.createInteraction("MultiButtonPadNotes")
        multiButtonPadNotes.setSupportedInteractionGroups(["NotesGroup"])

        self.leftUpperActionNotes = multiButtonPadNotes.createControllerAction("right-padupleft-pressed")
        self.leftDownActionNotes = multiButtonPadNotes.createControllerAction("right-paddownleft-pressed")
        self.upActionNotes = multiButtonPadNotes.createControllerAction("right-padup-pressed")
        self.downActionNotes = multiButtonPadNotes.createControllerAction("right-paddown-pressed")
        self.rightUpperActionNotes = multiButtonPadNotes.createControllerAction("right-padupright-pressed")
        self.rightDownActionNotes = multiButtonPadNotes.createControllerAction("right-paddownright-pressed")
        self.centerActionNotes = multiButtonPadNotes.createControllerAction("right-padcenter-pressed")

        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("NotesGroup")
        teleport.setControllerActionMapping("prepare", "left-touchpad-touched")
        teleport.setControllerActionMapping("abort", "left-touchpad-untouched")
        teleport.setControllerActionMapping("execute", "left-touchpad-pressed")

        self.pointer = vrDeviceService.getInteraction("Pointer")
        self.pointer.addSupportedInteractionGroup("NotesGroup")

        self.triggerRightPressed = multiButtonPadNotes.createControllerAction("right-trigger-pressed")
        self.deleteNoteIsActive = False
        self.changeView = False

        self.registry_key = "tool_draw_note"
        self.enable()

    def distanceFunc(self):
        global refObject
        handPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
        refObject.setActive(0)
        intersectionRay = self.rightController.pick()
        hitpoint = intersectionRay.getPoint()
        hitNode = intersectionRay.getNode()
        hitNode = toNode(hitNode.getObjectId())
        interPosRay = Pnt3f(hitpoint.x(), hitpoint.y(), hitpoint.z())
        refObject.setActive(1)

        self.activeNode = hitNode
        vrConstraintService.createOrientationConstraint([self.rightController.getNode()], refObject)
        if not self.changeView:
            setTransformNodeTranslation(refObject, handPos.x(), handPos.y(), handPos.z(), 1)
        else:
            setTransformNodeTranslation(refObject, interPosRay.x(), interPosRay.y(), interPosRay.z(), 1)

    def enable(self):
        global refObject
        global switch
        global notesControllerFound
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
        vrDeviceService.setActiveInteractionGroup("NotesGroup")

        self.leftUpperActionNotes.signal().triggered.connect(self.sizeDown)
        self.upActionNotes.signal().triggered.connect(self.ChangeNote)
        self.downActionNotes.signal().triggered.connect(self.deleteNote)
        self.rightUpperActionNotes.signal().triggered.connect(self.sizeUp)
        self.centerActionNotes.signal().triggered.connect(self.changeNoteView)

        refObject_node = vrNodeService.getNodeFromId(refObject.getID())
        refObject_node.getChild(0).setVisibilityFlag(True)

        refObject = switch.getChild(0)
        switch.fields().setInt32("choice", 0)

        if notesControllerFound:
            self.newRightCon = findNode("VRController_Notes")
            self.rightController.setVisible(0)
            self.newRightCon.setActive(1)
            controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
            setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
            self.NoteControllerConstraint = vrConstraintService.createParentConstraint([self.rightController.getNode()], self.newRightCon, False)
        else:
            self.rightController.setVisible(1)

        self.deleteNoteIsActive = False
        self.changeView = False
        self.iconsNotesTrashOff()
        self.triggerRightPressed.signal().triggered.connect(self.trigger_right_pressed)
        self.timer.setActive(1)
        self.timer.connect(self.distanceFunc)

        if self.changeView == False:
            self.iconsNotesConstraint()
            refObject_node.getParent().setVisibilityFlag(True)
            self.onControllerNotesMapping()
        else:
            self.iconsNotesRay()
            self.onRayNotesMapping()
    def disable(self):
        self.isEnabled = False
        try:
            if vred_tool_registry.get(self.registry_key) is self:
                del vred_tool_registry[self.registry_key]
        except Exception:
            pass
        try:
            self.leftUpperActionNotes.signal().triggered.disconnect(self.sizeDown)
        except Exception:
            pass
        try:
            self.upActionNotes.signal().triggered.disconnect(self.ChangeNote)
        except Exception:
            pass
        try:
            self.downActionNotes.signal().triggered.disconnect(self.deleteNote)
        except Exception:
            pass
        try:
            self.rightUpperActionNotes.signal().triggered.disconnect(self.sizeUp)
        except Exception:
            pass
        try:
            self.centerActionNotes.signal().triggered.disconnect(self.changeNoteView)
        except Exception:
            pass
        try:
            self.triggerRightPressed.signal().triggered.disconnect(self.trigger_right_pressed)
        except Exception:
            pass
        try:
            self.timer.setActive(0)
        except Exception:
            pass
        try:
            self.neutralNotes()
        except Exception:
            pass
        try:
            if hasattr(self, 'NoteControllerConstraint') and self.NoteControllerConstraint:
                vrConstraintService.deleteConstraint(self.NoteControllerConstraint)
                self.NoteControllerConstraint = None
        except Exception:
            pass
        try:
            if hasattr(self, 'newRightCon') and self.newRightCon:
                self.newRightCon.setActive(0)
        except Exception:
            pass
        try:
            self.rightController.setVisible(1)
        except Exception:
            pass

    def trigger_right_pressed(self):
        global refObject
        global Cloned_ref_obj
        nodeNum = random.randint(0, 1000000)
        if not self.activeNode.getName() == "VRMenuPanel":
            if self.deleteNoteIsActive:
                node = self.activeNode.getParent().getParent()
                nodeName = "%s" % node.getName()
                if hasNodeTag(node.getParent(), 'Cloned Note'):
                    vrSessionService.sendPython('deleteNode(findNode("' + nodeName + '"),True)')
            else:
                nameRefObject = refObject.getName()
                current_position = getTransformNodeTranslation(refObject, True)
                current_rotation = getTransformNodeRotation(refObject)
                current_scale = getTransformNodeScale(refObject)

                nameString = "%s" % nameRefObject
                posString = "%f,%f,%f" % (current_position.x(), current_position.y(), current_position.z())
                rotString = "%f,%f,%f" % (current_rotation.x(), current_rotation.y(), current_rotation.z())
                scaleString = "%f,%f,%f" % (current_scale.x(), current_scale.y(), current_scale.z())

                vrSessionService.sendPython('clonedRef = cloneNode(findNode("' + nameString + '"), False)')

                clonedNewName = nameString + '_' + str(nodeNum)

                vrSessionService.sendPython('clonedRef.setName("' + clonedNewName + '")')
                vrSessionService.sendPython('moveNode(clonedRef, refObject, Cloned_ref_obj)')
                vrSessionService.sendPython('setTransformNodeRotation(clonedRef, ' + rotString + ')')
                vrSessionService.sendPython('setTransformNodeTranslation(clonedRef, ' + posString + ', True)')
                vrSessionService.sendPython('setTransformNodeScale(clonedRef, ' + scaleString + ')')
                vrSessionService.sendPython('addNodeTag(Cloned_ref_obj, "Cloned Note")')

    def deleteNote(self):
        global refObject
        refObject_node = vrNodeService.getNodeFromId(refObject.getID())
        if not self.deleteNoteIsActive:
            self.iconsNotesTrashOn()
            refObject_node.getParent().setVisibilityFlag(False)
            self.deleteNoteIsActive = True
            self.onRayNotesMapping()
        else:
            self.deleteNoteIsActive = False
            self.iconsNotesTrashOff()
            refObject_node.getParent().setVisibilityFlag(True)
            self.defaultNotesMappings()

    def sizeUp(self):
        global refObject
        currentsize = getTransformNodeScale(refObject)
        ref_Parent = vrNodeService.getNodeFromId(refObject.getParent().getID())
        switch_child = ref_Parent.getChildren()
        for current_note in switch_child:
            setTransformNodeScale(current_note, currentsize.x() * 1.2, currentsize.y() * 1.2, currentsize.z() * 1.2)

    def sizeDown(self):
        global refObject
        currentsize = getTransformNodeScale(refObject)
        ref_Parent = vrNodeService.getNodeFromId(refObject.getParent().getID())
        switch_child = ref_Parent.getChildren()
        for current_note in switch_child:
            setTransformNodeScale(current_note, currentsize.x() / 1.2, currentsize.y() / 1.2, currentsize.z() / 1.2)

    def changeNoteView(self):
        global refObject
        if not self.deleteNoteIsActive:
            if not self.changeView:
                self.iconsNotesRay()
                self.changeView = True
                self.onRayNotesMapping()
            else:
                self.changeView = False
                self.iconsNotesConstraint()
                self.onControllerNotesMapping()

    def ChangeNote(self):
        global refObject
        global count
        global switch

        refObject.getParent()
        hello = vrNodeService.getNodeFromId(refObject.getParent().getID())
        all_child = hello.getChildren()

        if not self.upbuttonIsActive:
            index = count % len(all_child)
            count += 1
            refObject = switch.getChild(index)
            switch.fields().setInt32("choice", index)
        else:
            self.upbuttonIsActive = False

    def iconsNotesTrashOn(self):
        global notesControllerFound
        if notesControllerFound == True:
            setSwitchMaterialChoice("C_N_Icon_Minus", 0)
            setSwitchMaterialChoice("C_N_Icon_Next", 0)
            setSwitchMaterialChoice("C_N_Icon_Plus", 0)
            setSwitchMaterialChoice("C_N_Icon_Trash", 2)

    def iconsNotesTrashOff(self):
        global notesControllerFound
        if notesControllerFound == True:
            setSwitchMaterialChoice("C_N_Icon_Minus", 1)
            setSwitchMaterialChoice("C_N_Icon_Next", 1)
            setSwitchMaterialChoice("C_N_Icon_Plus", 1)
            setSwitchMaterialChoice("C_N_Icon_Trash", 1)

    def iconsNotesConstraint(self):
        global notesControllerFound
        if notesControllerFound == True:
            setSwitchMaterialChoice("C_N_Icon_Notes", 2)

    def iconsNotesRay(self):
        global notesControllerFound
        if notesControllerFound == True:
            setSwitchMaterialChoice("C_N_Icon_Notes", 1)

    def neutralNotes(self):
        self.pointer.setControllerActionMapping("prepare", "any-customtrigger-touched")
        self.pointer.setControllerActionMapping("abort", "any-customtrigger-untouched")
        self.pointer.setControllerActionMapping("start", "any-customtrigger-pressed")
        self.pointer.setControllerActionMapping("execute", "any-customtrigger-released")

    def onControllerNotesMapping(self):
        self.pointer.setControllerActionMapping("prepare", "disable")
        self.pointer.setControllerActionMapping("abort", "any-customtrigger-untouched")
        self.pointer.setControllerActionMapping("start", "any-customtrigger-pressed")
        self.pointer.setControllerActionMapping("execute", "any-customtrigger-released")

    def onRayNotesMapping(self):
        self.pointer.setControllerActionMapping("prepare", "right-customtrigger-touched")
        self.pointer.setControllerActionMapping("abort", "disable")
        self.pointer.setControllerActionMapping("start", "right-customtrigger-pressed")
        self.pointer.setControllerActionMapping("execute", "right-customtrigger-released")

    def defaultNotesMappings(self):
        if self.changeView == False:
            self.onControllerNotesMapping()
        else:
            self.onRayNotesMapping()

notes = Notes()
print("executed")
