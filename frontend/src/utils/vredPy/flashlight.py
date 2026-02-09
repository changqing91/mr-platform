import os
global flashlight_state
if 'flashlight_state' not in globals():
    flashlight_state = {
        'light': None,
        'constraint': None,
        'controller_constraint': None,
        'controller_node': None,
        'enabled': False
    }

class Flashlight:
    def __init__(self):
        self.state = flashlight_state
        self.right_controller = None
        try:
            self.right_controller = vrDeviceService.getVRDevice("right-controller")
        except Exception:
            self.right_controller = None
        self.ensure_controller_model()
        self.toggle()
    def ensure_controller_model(self):
        if self.state['controller_node']:
            return self.state['controller_node']
        controller_node = None
        try:
            controller_node = findNode("VRControllerFlashlight")
        except Exception:
            controller_node = None
        if controller_node and hasattr(controller_node, "isNull"):
            try:
                if controller_node.isNull():
                    controller_node = None
            except Exception:
                pass
        if not controller_node:
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
                    filename = os.path.join(filepath, 'VRControllerFlashlight.osb')
                    if os.path.exists(filename):
                        controller_node = loadGeometry(filename)
                        try:
                            controller_node.setName("VRControllerFlashlight")
                        except Exception:
                            pass
            except Exception:
                controller_node = None
        self.state['controller_node'] = controller_node
        return controller_node
    def ensure_light(self):
        if self.state['light']:
            return self.state['light']
        light = None
        parent = None
        controller_node = self.ensure_controller_model()
        try:
            parent = vrLightService.getLightRoot()
        except Exception:
            try:
                parent = vrScenegraphService.getRootNode()
            except Exception:
                parent = None
        try:
            light = vrLightService.createLight("Flashlight", "SpotLight", parent)
        except Exception:
            try:
                light = createNode("SpotLight", "Flashlight")
                if parent:
                    addChilds(parent, [light])
            except Exception:
                light = None
        if light and controller_node:
            try:
                addChilds(controller_node, [light])
            except Exception:
                pass
        self.state['light'] = light
        if self.state['light']:
            try:
                self.state['light'].setVisible(False)
            except Exception:
                pass
            try:
                self.state['light'].fields().setFloat("intensity", 8.0)
            except Exception:
                pass
            try:
                self.state['light'].fields().setFloat("coneAngle", 28.0)
            except Exception:
                pass
            try:
                self.state['light'].fields().setFloat("softAngle", 12.0)
            except Exception:
                pass
        return self.state['light']
    def disable(self):
        try:
            if self.state['constraint']:
                vrConstraintService.deleteConstraint(self.state['constraint'])
        except Exception:
            pass
        self.state['constraint'] = None
        try:
            if self.state['controller_constraint']:
                vrConstraintService.deleteConstraint(self.state['controller_constraint'])
        except Exception:
            pass
        self.state['controller_constraint'] = None
        try:
            self.state['light'].setVisible(False)
        except Exception:
            pass
        try:
            self.state['light'].setActive(False)
        except Exception:
            pass
        try:
            if self.state['controller_node']:
                self.state['controller_node'].setActive(0)
        except Exception:
            pass
        if self.right_controller:
            try:
                self.right_controller.setVisible(1)
            except Exception:
                pass
        self.state['enabled'] = False
    def enable(self):
        controller_node = None
        if self.right_controller:
            try:
                controller_node = self.right_controller.getNode()
            except Exception:
                controller_node = None
        model_node = self.ensure_controller_model()
        if controller_node:
            try:
                self.state['constraint'] = vrConstraintService.createParentConstraint([controller_node], self.state['light'], False)
            except Exception:
                self.state['constraint'] = None
        if controller_node and model_node:
            try:
                self.right_controller.setVisible(0)
            except Exception:
                pass
            try:
                model_node.setActive(1)
            except Exception:
                pass
            try:
                controller_pos = getTransformNodeTranslation(controller_node, 1)
                setTransformNodeTranslation(model_node, controller_pos.x(), controller_pos.y(), controller_pos.z(), True)
            except Exception:
                pass
            try:
                self.state['controller_constraint'] = vrConstraintService.createParentConstraint([controller_node], model_node, False)
            except Exception:
                self.state['controller_constraint'] = None
        try:
            self.state['light'].setVisible(True)
        except Exception:
            pass
        try:
            self.state['light'].setActive(True)
        except Exception:
            pass
        self.state['enabled'] = True
    def toggle(self):
        print("Toggle Flashlight")
        if not self.ensure_light():
            print("Flashlight failed")
            return
        if self.state['enabled']:
            self.disable()
            return
        self.enable()

Flashlight()
