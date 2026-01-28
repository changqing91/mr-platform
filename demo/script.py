import time
import os,re
import vrKernelServices
from math import *

Cam = findNode("Perspective")
nodeTelePoint = findNode("TelePoint")
rightNode = findNode("MatrixRight")
leftNode = findNode("MatrixLeft")
flashlight=findNode("Light_ON")
markerRoot = findNode("Marker_Root")
clipPlane = findNode("ClipPlane")
End0 = findNode("End0")
End1 = findNode("End1")
RulerRoot = findNode("Ruler_Root")
View = findNode("View")
Arr = findNode("Arrow")
markingMenu = findNode("MarkingMenu")
unpickable_nodes = getNodesWithTag("_exclude")
teleport_nodes = getNodesWithTag("_teleport")
selectVariantSet("Tool_0")
selectNodeVariant("button_switch2","text_EXT")
selectMaterialVariant("Switch-PPT","Shader-PPT-1")
selectNodeVariant("Model","Model C")
currentPosRot = 0
#toolCounter = 0
Pre = 0
displayMode = 0
selectVariantSet("_TM off")
TM_viewpoint = 0
TM_closeup = 0
Model = 2
lightMode_P = 0
lightMode_J = 0
doorMode_PL = 0
doorMode_PR = 0
doorMode_JL = 0
doorMode_JR = 0
doorMode_FL = 0
doorMode_FR = 0
aniPlay = 0
gripScale = 2
choiceSwitch = None
point0 = None
point1 = None
posDraw = Pnt3f()
doDraw = false
showViewCube(0)
setSuperSampling(1)
setSuperSamplingQuality(VR_SS_QUALITY_MEDIUM)

def resetScene():
    selectVariantSet("Tool_0")
    selectVariantSet("Poesche_INT-black")
    selectVariantSet("Poesche_EXT-white")
    selectVariantSet("Stage_Reset")
    selectVariantSet("4_Studio white")
    selectVariantSet("db_button1")
    clipPlane.fields().setBool("on",false)
    flashlight.setActive(false)
    removeAllMeasurements()
    while markerRoot.getNChildren():
        markerRoot.subChild(markerRoot.getChild(0))
    while RulerRoot.getNChildren():
        RulerRoot.subChild(markerRoot.getChild(0))
    while markerRoot.getNChildren():
        Mat_Del = markerRoot.getChild(0).getMaterial()
        markerRoot.subChild(markerRoot.getChild(0))
        Mat_Del.sub(1)

    #selectVariantSet("EXT_1.1")
    #selectVariantSet("EXT_2.1")
    #selectVariantSet("INT_1.1")
    #selectVariantSet("INT_2.2")
    leftNode.setTranslation(0, 0, 0) 
    leftNode.setRotation(0, 0, 0) 
    rightNode.setTranslation(0, 0, 0) 
    rightNode.setRotation(0, 0, 0)
    #leftNode.setActive(false)
    #rightNode.setActive(false)
    
resetScene()

#----------------------------------------------------------------------

def reset():
    global currentOriginX, currentOriginY, currentOriginZ, currentPosRot, lookatX, lookatY
    setFromAtUp(-1, 0, 0, 0, 0, 1, 0, 0, 0, 1)
    setOpenVRTrackingOrigin( Pnt3f(0, 0, 0))
    currentOriginX = 0
    currentOriginY = 0
    currentOriginZ = 0
    currentPosRot = 0
    lookatX = 0
    lookatY = 1

reset()

timer = vrTimer(0.1)
timer.setActive(false)

def drawLine():
    global markerRoot
    global posDraw
    global doDraw
    posnewDraw = Pnt3f()
    c1Matrix = controller1.getWorldMatrix()
    posnewDraw = Pnt3f( c1Matrix[3], c1Matrix[7], c1Matrix[11])

    if(doDraw):
        newLine = createLine(posDraw.x(), posDraw.y(), posDraw.z(), posnewDraw.x(), posnewDraw.y(), posnewDraw.z(), 1, 0, 0)
        markerRoot.addChild(newLine)

    posDraw = posnewDraw
    doDraw = true


def deleteLines():
    global markerRoot
    while markerRoot.getNChildren():
        Mat_Del = markerRoot.getChild(0).getMaterial()
        markerRoot.subChild(markerRoot.getChild(0))
        Mat_Del.sub(1)


def createVoiceAnnotation():
    global markerRoot
    voiceNode = findNode("RulerPost")
    if voiceNode.isValid():
        newNode = cloneNode(voiceNode, 1)
        newNode.setName("VoiceAnnotation")
        newNode.setTransformMatrix(controller1.getWorldMatrix(), false)
        markerRoot.addChild(newNode)
        print("Voice Annotation created")


def triggerSensor(node,contr):
    if node.hasAttachment("TouchSensorAttachment"):
        touchAttachment = node.getAttachment("TouchSensorAttachment")
        acc = vrFieldAccess(touchAttachment)
        if acc.isValid():
            variantSetName = acc.getMString("variantSets")
            for vset in variantSetName:
                #selectVariantSet(vset)
                contr.triggerHapticPulse(0,1000)
        return
    parentNode = node.getParent()
    if parentNode.isValid():
        triggerSensor( parentNode,contr)
        
        
def getNormalizedDirection(x, y):
    inVec = Vec2f(x, y)
    rescale = 1.0 / sqrt( inVec.x() * inVec.x() + inVec.y() * inVec.y())
    return Vec2f( inVec.x() * rescale, inVec.y() * rescale)


def markingMenuPos(hmdPos,contrPos):
    VecY = Vec3f(-contrPos.x() + hmdPos.x(), -contrPos.y() + hmdPos.y(), -contrPos.z() + hmdPos.z())
    rescaleY = 1.0 / sqrt( VecY.x() * VecY.x() + VecY.y() * VecY.y() + VecY.z() * VecY.z())
    VecYN = Vec3f(VecY.x() * rescaleY, VecY.y() * rescaleY, VecY.z() * rescaleY)
    VecX = Vec3f(-VecYN.y(), VecYN.x(), 0)
    rescaleX = 1.0 / sqrt( VecX.x() * VecX.x() + VecX.y() * VecX.y() + VecX.z() * VecX.z())
    VecXN = Vec3f(VecX.x() * rescaleX, VecX.y() * rescaleX, VecX.z() * rescaleX)
    VecZN = Vec3f(VecXN.y() * VecYN.z() - VecXN.z() * VecYN.y(), VecXN.z() * VecYN.x() - VecXN.x() * VecYN.z(), VecXN.x() * VecYN.y() - VecXN.y() * VecYN.x())
    return VecXN, VecYN, VecZN


def jumpTelePort(newTelePort):
    global currentOriginX, currentOriginY, currentOriginZ, currentPosRot, lookatX, lookatY, deltaLookatX, deltaLookatY

    posCenter = newTelePort.getWorldTranslation()
    camCenter = getCamNode(-1).getWorldTranslation()

    viewRot = newTelePort.getWorldRotation()
    camRot = getCamNode(-1).getWorldRotation()

    deltaPosRot = -camRot[2] + viewRot[2]
    newPosRot = camRot[2] - viewRot[2] + currentPosRot

    lookatX = sin(newPosRot*pi/180)
    lookatY = cos(newPosRot*pi/180)
    deltaLookatX = cos(deltaPosRot*pi/180)
    deltaLookatY = sin(deltaPosRot*pi/180)

    newOriginX = posCenter[0] - (camCenter[0] - currentOriginX)*deltaLookatX + (camCenter[1] - currentOriginY)*deltaLookatY
    newOriginY = posCenter[1] - (camCenter[0] - currentOriginX)*deltaLookatY - (camCenter[1] - currentOriginY)*deltaLookatX
    if (pickedNode0.getParent().getName()[:12] == "TelePort_INT"):
        newOriginZ = 1100 - camCenter[2] + currentOriginZ
    else:
        newOriginZ = 0

    setFromAtUp(-1, newOriginX, newOriginY, newOriginZ, newOriginX + lookatX, newOriginY + lookatY, newOriginZ, 0, 0, 1)

    currentOriginX = newOriginX
    currentOriginY = newOriginY
    currentOriginZ = newOriginZ
    currentPosRot = newPosRot
#----------------------------------------------------------------------
#Left Controller
def trigger0Pressed():
    global View
    controller0.setPickingAxis(1)
    controller0.showPickingAxis(true)
    pickedNode, pickedPos, pickedNormal, pickedUV = controller0.pickNodeEx()
    callAllPickingPressed(pickedNode, pickedPos, pickedNormal, pickedUV)

    nodeHMD = getCamNode(-1).getWorldTransform()
    x = View.getNChildren()
    for i in range(x):
        viewNode = View.getChild(i)
        viewNodeT = viewNode.getWorldTransform()
        if (abs(nodeHMD[3] - viewNodeT[3]) < 600) and (abs(nodeHMD[7] - viewNodeT[7]) < 600):
            hideNode(viewNode)
        else:
            showNode(viewNode)
    showNode(View)
    print("trigger0Pressed")


def trigger0Released():
    global currentOriginX, currentOriginY, currentOriginZ, lookatX, lookatY, choiceSwitch, nodeTelePoint
    controller0.showPickingAxis(false)
    triggerSensor(pickedNode0, controller0)
    pickedNode, pickedPos, pickedNormal, pickedUV = controller0.pickNodeEx()
    callAllPickingReleased(pickedNode, pickedPos, pickedNormal, pickedUV)

    nodeHMD = getCamNode(-1).getWorldTransform()
    parentView = pickedNode0.getParent()

    if (parentView.getName()[:8] == "TelePort"):
        jumpTelePort(parentView)
    elif hasNodeTag(pickedNode0,"_ground"):
        newOriginX = pick.x() - nodeHMD[3] + currentOriginX
        newOriginY = pick.y() - nodeHMD[7] + currentOriginY
        newOriginZ = 0

        setFromAtUp(-1, newOriginX, newOriginY, newOriginZ, newOriginX + lookatX, newOriginY + lookatY, newOriginZ, 0, 0, 1)

        currentOriginX = newOriginX
        currentOriginY = newOriginY
        currentOriginZ = newOriginZ

    nodeTelePoint.setActive(false)
    hideNode(View)
    if choiceSwitch:
        choiceSwitch.fields().setInt32("choice", 0)
    print("trigger0Released")


def touchpad0Pressed():
    print("touchpad0Pressed")


def touchpad0Released():
    print("touchpad0Released")
    
    
def grip0Pressed():
    global gripX, gripY, gripZ
    gripX = (controller0.getWorldMatrix())[3]
    gripY = (controller0.getWorldMatrix())[7]
    gripZ = (controller0.getWorldMatrix())[11]
    print("grip0Pressed")


def grip0Released():
    print("grip0Released")


def menuButton0Pressed():
    selectVariantSet("Teleport_toggle")
    print("menuButton0Pressed")


def menuButton0Released():
    print("menuButton0Released")


def controller0Moved():
    global pickedNode0
    leftNode.setTransformMatrix( controller0.getWorldMatrix(), false)
    if controller0.isTriggerPressed():
        global nodeTelePoint, pick, choiceSwitch

        nodeTelePoint.setActive(false)
        cmat0 = controller0.getWorldMatrix()
        rayOri = Pnt3f(cmat0[3], cmat0[7], cmat0[11])
        rayDir = Vec3f(-cmat0[2], -cmat0[6], -cmat0[10])
        for node in unpickable_nodes:
            node.setActive(false)
        for node in teleport_nodes:
            node.setActive(false)
        intersection = getSceneIntersection(-1, rayOri, rayDir)
        pickedNode, pickedPos, pickedNormal, pickedUV = controller0.pickNodeEx()
        callAllPickingMoved(pickedNode, pickedPos, pickedNormal, pickedUV, 1)
        for node in unpickable_nodes:
            node.setActive(true)
        for node in teleport_nodes:
            node.setActive(true)
        pickedNode0 = intersection[0]
        pick = intersection[1]
        parentView = pickedNode0.getParent()
        if hasNodeTag(pickedNode0,"_ground"):
            nodeTelePoint.setActive(true)
            Arr.setRotation(0, 0, getCamNode(-1).getWorldRotation()[2])
            nodeTelePoint.setTranslation(pick.x(),pick.y(),100)
            if choiceSwitch:
                choiceSwitch.fields().setInt32("choice", 0)
        elif (parentView.getName()[:8] == "TelePort"):
            nodeTelePoint.setActive(false)
            choiceSwitch = parentView.getChild('Choice')
            choiceSwitch.fields().setInt32("choice", 1)
        else:
            nodeTelePoint.setActive(false)
            if choiceSwitch:
                choiceSwitch.fields().setInt32("choice", 0)

    elif controller0.isTouchpadPressed():
        global currentOriginX, currentOriginY, currentOriginZ, currentPosRot, lookatX, lookatY, deltaLookatX, deltaLookatY

        touchPos = controller0.getTouchpadPosition()
        moveScaleForward = -10.0 * touchPos.y()
        moveScaleSideways = -10.0 * touchPos.x()
        camPos = getCamNode(-1).getWorldTransform()
        camDirForward = getNormalizedDirection( -camPos[2], camPos[6])
        #camDirForward = getNormalizedDirection( controller1.getWorldMatrix())
        camDirSideways = Vec2f( -camDirForward.y(), camDirForward.x())
        newPos = Pnt3f(currentOriginX - moveScaleForward * camDirForward.x() - moveScaleSideways * camDirSideways.x(), currentOriginY + moveScaleForward*camDirForward.y() + moveScaleSideways * camDirSideways.y(), currentOriginZ)
        setFromAtUp(-1, newPos.x(), newPos.y(), newPos.z(), newPos.x() + lookatX, newPos.y() + lookatY, newPos.z(), 0, 0, 1)
        currentOriginX = newPos.x()
        currentOriginY = newPos.y()
        currentOriginZ = newPos.z()
        
                
    elif controller0.isGripPressed():
        global gripX, gripY, gripZ
        gripX_new = (controller0.getWorldMatrix())[3]
        gripY_new = (controller0.getWorldMatrix())[7]
        gripZ_new = (controller0.getWorldMatrix())[11]
        currentOriginX += gripScale * (gripX - gripX_new)
        currentOriginY += gripScale * (gripY - gripY_new)
        currentOriginZ += gripScale * (gripZ - gripZ_new)
        setFromAtUp(-1, currentOriginX, currentOriginY, currentOriginZ, currentOriginX + lookatX, currentOriginY + lookatY, currentOriginZ, 0, 0, 1)
        gripX = gripScale * gripX - (gripScale - 1) * gripX_new
        gripY = gripScale * gripY - (gripScale - 1) * gripY_new
        gripZ = gripScale * gripZ - (gripScale - 1) * gripZ_new

#----------------------------------------------------------------------
#Right Controller

def trigger1Pressed():
    controller1.setPickingAxis(1)
    controller1.showPickingAxis(true)
    pickedNode, pickedPos, pickedNormal, pickedUV = controller1.pickNodeEx()
    callAllPickingPressed(pickedNode, pickedPos, pickedNormal, pickedUV)
    print("trigger1Pressed")

def trigger1Released():
    controller1.showPickingAxis(false)
    triggerSensor(pickedNode1,controller1)
    pickedNode, pickedPos, pickedNormal, pickedUV = controller1.pickNodeEx()
    callAllPickingReleased(pickedNode, pickedPos, pickedNormal, pickedUV)
    print("trigger1Released")

def touchpad1Pressed():
    print("touchpad1Pressed")
    if tool ==0:
        return
    elif tool ==1:
        timer.setActive(true)
        touchPos1 = controller1.getTouchpadPosition()
        if touchPos1.y() > -0.6:
            timer.setActive(true)
        else:
            deleteLines()
    elif tool ==2:
        global flashlight
        flashlight.setActive(true)
    elif tool ==5:
        touchPos5 = controller1.getTouchpadPosition()
        if touchPos5.y() > -0.2:
            Ruler = findNode("RulerPost")
            cloneNode(Ruler, 1)
            moveNode(getSelectedNode(), rightNode, RulerRoot)
            getSelectedNode().setTransformMatrix(controller1.getWorldMatrix(), false)
        else:
            if RulerRoot.getNChildren():
                RulerRoot.subChild(RulerRoot.getChild(RulerRoot.getNChildren() - 1))
    elif tool ==6:
        touchPos6 = controller1.getTouchpadPosition()
        if touchPos6.y() > -0.2:
            controller1.setPickingAxis(1)
            controller1.showPickingAxis(true)
    elif tool == 7:
        print("Start Voice Recording")
        controller1.triggerHapticPulse(0, 500)
            
def touchpad1Released():
    print("touchpad1Released")
    if tool ==1:
        global doDraw
        timer.setActive(false)
        doDraw = false
    elif tool == 2:
        global flashlight
        flashlight.setActive(false)
    elif tool == 3:
        findNode("Section_Yellow").setActive(true)
        findNode("Section_White").setActive(true)
    elif tool == 4:
        touchPos5 = controller1.getTouchpadPosition()
        if touchPos5.y() > 0.5:
            selectVariantSet("Stage_Reset")
        else:
            if touchPos5.x() < -0.6:
                selectVariantSet("Stage_Clockwise")
            elif touchPos5.x() > 0.6:
                selectVariantSet("Stage_Counter")
            else:
                selectVariantSet("Stage_Pause")
    elif tool == 6:
        touchPos6 = controller1.getTouchpadPosition()
        if touchPos6.y() > -0.2:
            global Meas,point0,point1   
            if Meas == 0:
                point0 = intersection6
                Meas = 1
            elif Meas == 1:
                point1 = intersection6
                createPointPointMeasurement(point0[0], point0[1], point1[0], point1[1])
                End0.setActive(0)
                End1.setActive(0)
                Meas = 0
            controller1.showPickingAxis(false)
        else:
            removeSelectedMeasurement()
            Meas = 0
    elif tool == 7:
        print("Stop Voice Recording")
        createVoiceAnnotation()
            
        
def grip1Pressed():
    global controller1Pos0, VecXN, VecYN, VecZN, oldtoolCounter
    oldtoolCounter = -1
    nodeHMD = Vec3f((getCamNode(-1).getWorldTransform())[3], (getCamNode(-1).getWorldTransform())[7], (getCamNode(-1).getWorldTransform())[11])
    controller1Pos0 = Vec3f((controller1.getWorldMatrix())[3], (controller1.getWorldMatrix())[7], (controller1.getWorldMatrix())[11])
    VecXN, VecYN, VecZN = markingMenuPos(nodeHMD, controller1Pos0)
    matrix = (VecXN.x(), VecYN.x(), VecZN.x(), controller1Pos0.x(), VecXN.y(), VecYN.y(), VecZN.y(), controller1Pos0.y(), VecXN.z(), VecYN.z(), VecZN.z(), controller1Pos0.z(), 0, 0, 0, 1)
    markingMenu.setTransformMatrix(matrix, False)
    markingMenu.setActive(True)
    print("grip1Pressed")

def grip1Released():
    markingMenu.setActive(False)
    print("grip1Released")

def menuButton1Pressed():
    print("menuButton1Released")
    

def menuButton1Released():
    print("menuButton1Released")

def controller1Moved():
    global pickedNode1
    global tool
    rightNode.setTransformMatrix(controller1.getWorldMatrix(), false)
    if controller1.isTriggerPressed():
        cmat1 = controller1.getWorldMatrix()
        for node in unpickable_nodes:
            node.setActive(False)
        rayOri = Pnt3f(cmat1[3], cmat1[7], cmat1[11])
        rayDir = Vec3f(-cmat1[2], -cmat1[6], -cmat1[10])
        intersection = getSceneIntersection(-1,rayOri, rayDir)
        pickedNode, pickedPos, pickedNormal, pickedUV = controller1.pickNodeEx()
        callAllPickingMoved(pickedNode, pickedPos, pickedNormal, pickedUV, 1)
        for node in unpickable_nodes:
            node.setActive(True)        
        pickedNode1 = intersection[0]

    if controller1.isTouchpadPressed():
        if tool == 0:
            screenshot_path = os.path.join(os.path.expanduser('~'), "Pictures")
            num = str(time.localtime( time.time() ))
            TIME0 = re.findall(r'\d+', num)
            TIME1 = "".join(TIME0[0:6])
            screenshotName = "\VredVR_" + TIME1 + ".png"
            createScreenshot(screenshot_path + screenshotName)
        elif tool == 1:
            timer.connect("drawLine()")
        elif tool == 3:
            global clipPlane
            touchPos = controller1.getTouchpadPosition()
            if touchPos.y() > -0.2:
                matrixTransform = findNode("Transform")
                clipPlane.fields().setFieldContainerId("beacon", matrixTransform.getID())
                clipPos = controller1.getWorldMatrix()
                if touchPos.x() > 0:
                    clipPos_P = [clipPos[2],clipPos[1],-clipPos[0],clipPos[3],clipPos[6],clipPos[5],-clipPos[4],clipPos[7],clipPos[10],clipPos[9],-clipPos[8],clipPos[11],clipPos[14],clipPos[13],-clipPos[12],clipPos[15]]
                    matrixTransform.setTransformMatrix(clipPos_P,false)
                    findNode("Section_Yellow").setActive(true)
                    findNode("Section_White").setActive(false)
                else:
                    clipPos_N = [-clipPos[2],clipPos[1],clipPos[0],clipPos[3],-clipPos[6],clipPos[5],clipPos[4],clipPos[7],-clipPos[10],clipPos[9],clipPos[8],clipPos[11],-clipPos[14],clipPos[13],clipPos[12],clipPos[15]]
                    matrixTransform.setTransformMatrix(clipPos_N,false)
                    findNode("Section_Yellow").setActive(false)
                    findNode("Section_White").setActive(true)
                clipPlane.fields().setBool("on",true)
            else:
                clipPlane.fields().setBool("on",false)
        elif tool == 6:
            if controller1.getTouchpadPosition().y() > -0.2:
                global intersection6
                cmat2 = controller1.getWorldMatrix()
                rayOri = Pnt3f(cmat2[3], cmat2[7], cmat2[11])
                rayDir = Vec3f(-cmat2[2], -cmat2[6], -cmat2[10])
                if Meas == 0:
                    End0.setActive(0)
                    intersection6 = getSceneIntersection(-1,rayOri, rayDir)
                    End0.setActive(1)
                    setTransformNodeTranslation(End0, intersection6[1].x(), intersection6[1].y(), intersection6[1].z(), 1)
                elif Meas == 1:
                    End1.setActive(0)
                    intersection6 = getSceneIntersection(-1,rayOri, rayDir)
                    End1.setActive(1)
                    setTransformNodeTranslation(End1, intersection6[1].x(), intersection6[1].y(), intersection6[1].z(), 1)
                    
    if controller1.isGripPressed():
        global oldtoolCounter
        controller1Pos = Vec3f((controller1.getWorldMatrix())[3], (controller1.getWorldMatrix())[7], (controller1.getWorldMatrix())[11])
        PosVec = Vec3f(controller1Pos.x() - controller1Pos0.x(), controller1Pos.y() - controller1Pos0.y(), controller1Pos.z() - controller1Pos0.z())
        PosInprod = PosVec.x() * VecYN.x() + PosVec.y() * VecYN.y() + PosVec.z() * VecYN.z()
        PosProjXZ = Vec3f(PosVec.x() - VecYN.x() * PosInprod, PosVec.y() - VecYN.y() * PosInprod, PosVec.z() - VecYN.z() * PosInprod)
        PosProjXZlen = sqrt(PosProjXZ.x() ** 2 + PosProjXZ.y() ** 2 + PosProjXZ.z() ** 2)
        if 150 < PosProjXZlen < 250:
            PosProjXZN = Vec3f(PosProjXZ.x()/PosProjXZlen, PosProjXZ.y()/PosProjXZlen, PosProjXZ.z()/PosProjXZlen)
            PosNOutprod = Vec3f(- VecZN.y() * PosProjXZN.z() + VecZN.z() * PosProjXZN.y(), -VecZN.x() * PosProjXZN.z() + VecZN.z() * PosProjXZN.x(), -VecZN.x() * PosProjXZN.y() + VecZN.y() * PosProjXZN.x())
            PosNOutIn = PosNOutprod.x() * VecYN.x() + PosNOutprod.y() * VecYN.y() + PosNOutprod.z() * VecYN.z()
            if PosNOutIn < 0:
                Posangle = degrees(acos(- VecZN.x() * PosProjXZN.x() - VecZN.y() * PosProjXZN.y() - VecZN.z() * PosProjXZN.z()))
            else:
                Posangle = 360 - degrees(acos(- VecZN.x() * PosProjXZN.x() - VecZN.y() * PosProjXZN.y() - VecZN.z() * PosProjXZN.z()))
            divi = 8
            toolCounter = int((Posangle + 180/divi)/(360/divi)) % divi
            print(toolCounter)
            selectVariantSet("Tool_" +str(toolCounter))
            if toolCounter == 7:
                tool = 7
            if not toolCounter == oldtoolCounter:
                controller1.triggerHapticPulse(0,1000)
                oldtoolCounter = toolCounter
        elif PosProjXZlen < 100:
            oldtoolCounter = -1
   
#----------------------------------------------------------------------

def resetInt():
    vrImmersiveInteractionService.setDefaultInteractionsActive(True)
    vrImmersiveInteractionService.setInteractionActive("Teleport", False)
    vrImmersiveInteractionService.setInteractionActive("Pointer", False)
    
#----------------------------------------------------------------------


keyD = vrKey(Key_D) # D Set display to Vive
keyD.connect("setDisplayMode(VR_DISPLAY_OPEN_VR); reset(); resetInt()")

keyE = vrKey(Key_E) # E Set display back to standard
keyE.connect("setDisplayMode(VR_DISPLAY_STANDARD); reset()")

#----------------------------------------------------------------------
controller0 = vrOpenVRController("Controller0")

controller0.connectSignal("triggerPressed", trigger0Pressed)
controller0.connectSignal("triggerReleased", trigger0Released)
controller0.connectSignal("touchpadPressed", touchpad0Pressed)
controller0.connectSignal("touchpadReleased", touchpad0Released)
controller0.connectSignal("gripPressed", grip0Pressed)
controller0.connectSignal("gripReleased", grip0Released)
controller0.connectSignal("menuButtonPressed", menuButton0Pressed)
controller0.connectSignal("menuButtonReleased", menuButton0Released)
controller0.connectSignal("controllerMoved", controller0Moved)

#----------------------------------------------------------------------

controller1 = vrOpenVRController("Controller1")

controller1.connectSignal("triggerPressed", trigger1Pressed)
controller1.connectSignal("triggerReleased", trigger1Released)
controller1.connectSignal("touchpadPressed", touchpad1Pressed)
controller1.connectSignal("touchpadReleased", touchpad1Released)
controller1.connectSignal("gripPressed", grip1Pressed)
controller1.connectSignal("gripReleased", grip1Released)
controller1.connectSignal("menuButtonPressed", menuButton1Pressed)
controller1.connectSignal("menuButtonReleased", menuButton1Released)
controller1.connectSignal("controllerMoved", controller1Moved)