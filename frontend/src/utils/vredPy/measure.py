class MeasureTool:
    def __init__(self):
        self.isEnabled = False
        self.active = False
        self.leftController = vrDeviceService.getVRDevice("left-controller")
        self.rightController = vrDeviceService.getVRDevice("right-controller")
        self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
        self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
        padCenter = vrdVirtualTouchpadButton('padcenter', 0.0, 0.5, 0.0, 360.0)
        self.rightController.addVirtualButton(padCenter, 'touchpad')
        multiButtonPadMeasure = vrDeviceService.createInteraction("MultiButtonPadMeasure")
        multiButtonPadMeasure.setSupportedInteractionGroups(["MeasureGroup"])
        teleport = vrDeviceService.getInteraction("Teleport")
        teleport.addSupportedInteractionGroup("MeasureGroup")
        teleport.setControllerActionMapping("prepare", "left-touchpad-touched")
        teleport.setControllerActionMapping("abort", "left-touchpad-untouched")
        teleport.setControllerActionMapping("execute", "left-touchpad-pressed")
        self.pointer = vrDeviceService.getInteraction("Pointer")
        self.pointer.addSupportedInteractionGroup("MeasureGroup")
        self.centerAction = multiButtonPadMeasure.createControllerAction("right-padcenter-pressed")
        self.enable()
    def enable(self):
        self.isEnabled = True
        vrDeviceService.setActiveInteractionGroup("MeasureGroup")
        self.centerAction.signal().triggered.connect(self.toggle)
        self.start_measure()
    def start_measure(self):
        if self.active:
            return
        self.active = True
        try:
            import vrMeasurementService
            vrMeasurementService.startMeasurement(vrMeasurementService.PointToPoint)
        except Exception:
            try:
                vrMeasurement.startMeasurement(0)
            except Exception:
                pass
    def stop_measure(self):
        if not self.active:
            return
        self.active = False
        try:
            import vrMeasurementService
            if hasattr(vrMeasurementService, "stopMeasurement"):
                vrMeasurementService.stopMeasurement()
            elif hasattr(vrMeasurementService, "endMeasurement"):
                vrMeasurementService.endMeasurement()
        except Exception:
            try:
                if hasattr(vrMeasurement, "stopMeasurement"):
                    vrMeasurement.stopMeasurement()
                elif hasattr(vrMeasurement, "endMeasurement"):
                    vrMeasurement.endMeasurement()
            except Exception:
                pass
    def toggle(self):
        if self.active:
            self.stop_measure()
        else:
            self.start_measure()

MeasureTool()
