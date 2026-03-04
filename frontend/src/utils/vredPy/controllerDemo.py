import os

# simple demo based on adjust.py: load a custom controller model
# and attach it to the right-hand device. the geometry lives under
# a Transform3D node named "WT-MR_Remote_controllers" once loaded.

class ControllerDemo:
    def __init__(self):
        self.rightController = vrDeviceService.getVRDevice("right-controller")
        # by default hide and optionally disable the built-in controller;
        # we'll flip visibility back in disable() if needed.
        try:
            self.rightController.setVisible(0)
        except Exception:
            pass
        try:
            self.rightController.setEnabled(0)
        except Exception:
            pass

        self.newController = None
        self.controllerConstraint = None

        self._load_custom_model()

    def _load_custom_model(self):
        # path given by the user, using Windows style - os.path handles it
        filepath = r"C:\Users\WhatTech\Documents\Autodesk\Automotive\VRED\controllerClip.osb"
        if not os.path.exists(filepath):
            print(f"[ControllerDemo] model not found at {filepath}")
            return

        try:
            self.newController = loadGeometry(filepath)
            # put it under a known name so scripts can find it
            try:
                self.newController.setName("WT-MR_Remote_controllers")
            except Exception:
                pass

            # hide the built-in representation and parent our mesh to it
            try:
                self.rightController.setVisible(0)
            except Exception:
                pass

            try:
                self.controllerConstraint = vrConstraintService.createParentConstraint(
                    [self.rightController.getNode()], self.newController, False
                )
            except Exception:
                self.controllerConstraint = None

            print("[ControllerDemo] custom controller loaded")
        except Exception as e:
            print(f"[ControllerDemo] failed to load custom controller: {e}")
            self.newController = None

    def disable(self):
        # restore original state
        try:
            if self.rightController:
                # make original controller visible and re-enable input
                try:
                    self.rightController.setVisible(1)
                except Exception:
                    pass
                try:
                    self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
                except Exception:
                    pass
                try:
                    self.rightController.setEnabled(1)
                except Exception:
                    pass
        except Exception:
            pass
        if self.controllerConstraint:
            try:
                vrConstraintService.deleteConstraint(self.controllerConstraint)
            except Exception:
                pass
            self.controllerConstraint = None
        if self.newController:
            try:
                self.newController.setActive(0)
            except Exception:
                pass
            self.newController = None


# instantiate demo when this module is executed
controller_demo = ControllerDemo()
print("controller demo executed")
