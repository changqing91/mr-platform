
export const RADIAL_MENU_CORE = `
try:
    # Try importing V2 API services
    import vrDeviceService
    import vrNodeService
    import vrImmersiveInteractionService
    import vrMeasurementService
    import vrClippingModule
    from PySide2 import QtCore

    class RadialMenuV2:
        def __init__(self):
            self.tools = []
            self.isVisible = False
            self.root = vrNodeService.createNode("RadialMenu_Root")
            self.root.setActive(False)
            self.controller = None
            
            # Simple text node for menu visualization
            self.menu_text = vrNodeService.createNode("RadialMenu_Text", "Text3D", self.root)
            self.menu_text.setFieldString("text", "MR Tools Menu")
            self.menu_text.setFieldFloat("height", 0.05)
            self.menu_text.setTranslation(0, 0.1, 0)
            
            # Register inputs
            self.left_device = vrDeviceService.getVRDevice("left-controller")
            self.right_device = vrDeviceService.getVRDevice("right-controller")
            
            # Use specific button names for OpenXR
            self.connect_device(self.left_device)
            self.connect_device(self.right_device)
            
            print("Radial Menu (V2) Initialized")

        def connect_device(self, device):
            if not device: return
            # Try connecting 'Menu' button (b_button/y_button or menu_button)
            device.setInteraction("Menu", "Pressed", self.on_menu_press)
            device.setInteraction("Menu", "Released", self.on_menu_release)

        def on_menu_press(self, action, device):
            self.controller = device
            self.show()

        def on_menu_release(self, action, device):
            self.execute_selection()
            self.hide()

        def add_tool(self, id, name, func_name):
            for t in self.tools:
                if t['id'] == id: return
            self.tools.append({'id': id, 'name': name, 'func': func_name})
            self.update_menu_text()

        def update_menu_text(self):
            text = "MR Tools:\\n"
            for t in self.tools:
                text += f"- {t['name']}\\n"
            self.menu_text.setFieldString("text", text)

        def show(self):
            if not self.controller: return
            mat = self.controller.getWorldTransformation()
            self.root.setWorldTransformation(mat)
            self.root.setActive(True)
            self.isVisible = True

        def hide(self):
            self.root.setActive(False)
            self.isVisible = False

        def execute_selection(self):
            if not self.tools: return
            # Default to first tool for now
            try:
                func = globals().get(self.tools[0]['func'])
                if func: func()
            except Exception as e:
                print(f"Tool execution failed: {e}")

    # Use V2
    RadialMenu = RadialMenuV2

except ImportError:
    print("V2 API not found, falling back to Legacy (V1)")
    import vrOpenVR
    
    # Legacy V1 Implementation
    class RadialMenuLegacy:
        def __init__(self):
            self.tools = []
            self.isVisible = False
            # V1 Node creation
            self.root = createNode("Transform")
            self.root.setName("RadialMenu_Root")
            self.root.setActive(False)
            
            # Try creating text safely
            self.menu_text = createNode("Text3D")
            # Check if valid (V1 specific check)
            try:
                if self.menu_text.isValid():
                    self.menu_text.setName("RadialMenu_Text")
                    self.root.addChild(self.menu_text)
                    
                    # V1 Set Fields (No setFields method)
                    self.menu_text.setFieldString("text", "MR Tools Menu")
                    self.menu_text.setFieldFloat("height", 0.05)
                    self.menu_text.setTranslation(0, 100, 0) # V1 units might be mm
                else:
                    print("Text3D node invalid")
                    self.menu_text = None
            except:
                print("Text3D creation failed completely")
                self.menu_text = None
            
            # Setup Controllers (V1 OpenVR)
            try:
                self.left_c = vrOpenVR.getController0()
                self.right_c = vrOpenVR.getController1()
                
                if self.left_c:
                    self.left_c.connectSignal("controllerMenuPressed", self.on_left_menu)
                    self.left_c.connectSignal("controllerMenuReleased", self.on_release)
                if self.right_c:
                    self.right_c.connectSignal("controllerMenuPressed", self.on_right_menu)
                    self.right_c.connectSignal("controllerMenuReleased", self.on_release)
            except Exception as e:
                print(f"Controller init error: {e}")
                
            self.active_controller = None
            print("Radial Menu (Legacy) Initialized")

        def on_left_menu(self):
            self.active_controller = self.left_c
            self.show()

        def on_right_menu(self):
            self.active_controller = self.right_c
            self.show()

        def on_release(self):
            self.execute_selection()
            self.hide()

        def add_tool(self, id, name, func_name):
            for t in self.tools:
                if t['id'] == id: return
            self.tools.append({'id': id, 'name': name, 'func': func_name})
            self.update_menu_text()

        def update_menu_text(self):
            if not self.menu_text: return
            text = "MR Tools:\\n"
            for t in self.tools:
                text += f"- {t['name']}\\n"
            try:
                self.menu_text.setFieldString("text", text)
            except:
                pass

        def show(self):
            if not self.active_controller: return
            # V1: Get Matrix from controller node
            self.root.setActive(True)
            self.isVisible = True
            
            # Try to snap to controller position
            try:
                # Assuming active_controller is a vrNodePtr or has getWorldTransform
                mat = self.active_controller.getWorldTransform()
                self.root.setWorldTransform(mat)
            except:
                pass

        def hide(self):
            self.root.setActive(False)
            self.isVisible = False

        def execute_selection(self):
            if not self.tools: return
            try:
                func = globals().get(self.tools[0]['func'])
                if func: func()
            except Exception as e:
                print(f"Tool execution failed: {e}")

    # Use Legacy
    RadialMenu = RadialMenuLegacy

try:
    # Singleton Initialization
    if 'radial_menu_instance' not in globals():
        radial_menu_instance = RadialMenu()
    print("Radial Menu Core Loaded")
except Exception as e:
    print(f"Radial Menu Init Error: {e}")
`;

export const TOOL_IMPLEMENTATIONS = {
    measure: `
def tool_measure():
    print("Starting Measure")
    try:
        import vrMeasurementService
        vrMeasurementService.startMeasurement(vrMeasurementService.PointToPoint)
    except:
        try:
            # V1 Fallback
            vrMeasurement.startMeasurement(0)
        except:
            print("Measure failed")
`,
    flashlight: `
def tool_flashlight():
    print("Toggle Flashlight")
    # Add light logic
`,
    section: `
def tool_section():
    print("Toggle Section")
    try:
        import vrClippingModule
        vrClippingModule.setClippingEnabled(True)
    except:
        print("Section failed")
`,
    turntable: `
def tool_turntable():
    print("Start Turntable")
`,
    adjust: `
def tool_adjust():
    print("Toggle Adjust")
    try:
        import vrImmersiveInteractionService
        vrImmersiveInteractionService.setManipulatorEnabled(True)
    except:
        print("Adjust failed (V2 required)")
`,
    voice_note: `
def tool_voice_note():
    print("Voice Note")
`,
    draw_note: `
def tool_draw_note():
    print("Start Drawing")
    try:
        import vrAnnotationService
        vrAnnotationService.startInteraction()
    except:
        try:
            # V1 Fallback
            vrAnnotation.start()
        except:
            print("Draw Note failed")
`
};
