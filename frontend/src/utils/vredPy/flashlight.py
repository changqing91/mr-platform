import os
from vrScenegraph import *
from vrController import *
from vrNodePtr import *
from vrNodeUtils import *
from vrFileIO import *

class Flashlight:
    def __init__(self):
        self.geo = None
        self.trans = None
        self.flashlight_handle = None
        self.on = False
        self.hand_node = None
        self.active_controller = None
        self.is_left_side = False
        try:
            self.hand_node = vrDeviceService.getVRDevice("right-controller").getNode()
            self.active_controller = vrDeviceService.getVRDevice("right-controller")
        except Exception:
            self.hand_node = None
            self.active_controller = None
        try:
            vrHMDService.hmdStatusWillChange.connect(self.__on_hmd_status_will_change)
        except Exception:
            pass
        self.switch_on()

    def switch_on(self):
        if self.on:
            return
        if not self.hand_node:
            return
        self.get_geo().setActive(True)
        self.on = True
        self.constraint = vrConstraintService.createParentConstraint([self.hand_node], self.geo, False)
        self.constraint.setVisualizationVisible(False)
        if self.active_controller:
            self.active_controller.signal().moved.connect(self.update_flashlight)
            self.visualization_mode = self.active_controller.getVisualizationMode()
            self.adjust_flashlight(self.active_controller)

    def switch_off(self):
        if not self.on:
            return
        try:
            self.get_geo().setActive(False)
        except Exception:
            pass
        self.on = False
        try:
            vrConstraintService.deleteConstraint(self.constraint)
        except Exception:
            pass
        if self.active_controller:
            try:
                self.active_controller.signal().moved.disconnect(self.update_flashlight)
            except Exception:
                pass

    def get_geo(self):
        if self.geo is not None and self.geo.isValid():
            return self.geo
        self.create_geo()
        return self.geo

    def create_geo(self):
        for node in findNodes("VR_Flashlight"):
            node.getParent().subChild(node)
        root_node = getInternalRootNode()
        self.geo = createNode("Transform3D", "VR_Flashlight", root_node, False)
        self.trans = createNode("Transform3D", "FlashlightPos", self.geo, False)
        self.load_model()
        try:
            self.flashlight_handle = vrNodeService.findNode("Housing_02", False, False, self.trans)
        except Exception:
            self.flashlight_handle = None
        self.geo.setActive(False)
        setIsVRNode(self.trans, True)
        setIsVRNode(self.geo, True)

    def load_model(self):
        model_path = self.get_controller_osb_path()
        if model_path:
            nodes = loadOSB([model_path])
        else:
            nodes = []
        for node in nodes:
            self.trans.addChild(node)

    def get_controller_osb_path(self):
        base_dir = None
        try:
            base_dir = os.path.join(os.environ["USERPROFILE"], "Documents")
        except Exception:
            try:
                base_dir = os.path.join(os.environ["HOME"], "Documents")
            except Exception:
                base_dir = None
        if not base_dir:
            return None
        filepath = os.path.join(base_dir, "Autodesk", "Automotive", "VRED")
        filename = os.path.join(filepath, "VRControllerFlashlight.osb")
        if os.path.exists(filename):
            return filename
        return None

    def update_flashlight(self, device):
        try:
            if device.getVisualizationMode() != self.visualization_mode:
                self.adjust_flashlight(device)
                self.visualization_mode = device.getVisualizationMode()
        except Exception:
            pass

    def adjust_flashlight(self, device):
        try:
            if device.getVisualizationMode() == 1:
                self.set_hand_transform()
                if self.flashlight_handle:
                    self.flashlight_handle.setVisibilityFlag(True)
            else:
                self.set_controller_transform()
                if self.flashlight_handle:
                    self.flashlight_handle.setVisibilityFlag(False)
        except Exception:
            pass

    def set_hand_transform(self):
        if self.is_left_side:
            setTransformNodeTranslation(self.trans, -17, -5, 60, False)
            setTransformNodeRotation(self.trans, 180, 10, 0)
        else:
            setTransformNodeTranslation(self.trans, 17, -5, 60, False)
            setTransformNodeRotation(self.trans, 180, -10, 0)

    def set_controller_transform(self):
        setTransformNodeTranslation(self.trans, 0, -50, 50, False)
        setTransformNodeRotation(self.trans, 110, 0, 0)

    def __on_hmd_status_will_change(self, active):
        if not active:
            self.switch_off()

Flashlight()
