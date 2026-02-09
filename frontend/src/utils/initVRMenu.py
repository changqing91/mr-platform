# =========================================
# VRED 2026 VR Radial Menu (Node/Agent Safe)
# Refactored for modularity and data-driven configuration
# =========================================

import math
import vrFileIO
from vrScenegraph import findNode
# from vrDeviceService import vrDeviceService
from vrInteractionManager import vrInteractionManager

# Try to access vrTimer
try:
    # In some VRED versions/contexts, vrTimer is a builtin.
    # In others, it might need import.
    # We check if it's already available.
    vrTimer
except NameError:
    try:
        from vrKernelServices import vrTimer
    except ImportError:
        # If imports fail, we might be in a context where it's not exposed as class
        # But let's proceed and hope it's injected later or accessible
        pass

# API Compatibility Wrapper
class VRDeviceServiceWrapper:
    @staticmethod
    def getControllerPosition(controller_id):
        # Fallback to legacy vrOpenVR if available, or mock
        try:
            import vrOpenVR
            # Note: vrOpenVR API differs, this is a placeholder attempt
            # In V1, usually tracked nodes are found in scenegraph
            # e.g. "OpenVR_Controller_Right"
            name = "OpenVR_Controller_Right" if controller_id == 1 else "OpenVR_Controller_Left"
            node = findNode(name)
            if node and node.isValid():
                return node.getWorldTranslation()
        except ImportError:
            pass
        return Pnt3f(0,0,0) # Return dummy if fail

    @staticmethod
    def getControllerRotation(controller_id):
        try:
            name = "OpenVR_Controller_Right" if controller_id == 1 else "OpenVR_Controller_Left"
            node = findNode(name)
            if node and node.isValid():
                return node.getWorldRotation()
        except:
            pass
        # Return identity rotation or similar dummy object that has getForwardVector
        # We need a mock object that has getForwardVector method if real one fails
        class MockRot:
            def getForwardVector(self):
                return Pnt3f(0, 1, 0) # Default forward
        return MockRot()

    @staticmethod
    def getAxisValue(axis_name):
        # Legacy controller input usually handled via vrJoystick or vrOpenVR
        # returning 0 as safe fallback
        return 0.0
    
    @staticmethod
    def connect(signal, slot):
        # Legacy signal connection often uses vrController
        try:
            import vrController
            if "GripPressed" in signal:
                # Map to legacy button IDs if possible, or skip
                # vrController.connect(vrController.LeftController, vrController.Grip, slot)
                pass
        except:
            pass

# Try to use V2 API, fallback to Wrapper
try:
    from vrDeviceService import vrDeviceService
except ImportError:
    print("Warning: vrDeviceService not found. Using legacy fallback wrapper.")
    vrDeviceService = VRDeviceServiceWrapper

# ---------- 配置数据 ----------
MENU_CONFIG = {
    "vpb_path": r"C:/Deploy/vred-node-agent/vpb/RadialMenu.vpb",
    "root_name": "RadialMenuRoot",
    "distance": 0.25,        # 菜单距离控制器的距离（米）
    "dead_zone": 0.2,        # 摇杆死区
    "scale_normal": 1.0,     # 正常缩放
    "scale_active": 1.15,    # 激活缩放
    "controller_id": 1       # 1 = Right, 0 = Left
}

# 按钮数据定义
# name: 用于日志或调试
# interaction: 对应的 VRED 交互模式名称
BUTTON_DATA = [
    {"name": "Measure",    "interaction": "Measure"},
    {"name": "Flashlight", "interaction": "Flashlight"},
    {"name": "Section",    "interaction": "Section"},
    {"name": "Turntable",  "interaction": "Turntable"}
]


class VRRadialMenu:
    def __init__(self, config, buttons):
        self.config = config
        self.buttons = buttons
        self.slice_count = len(buttons)
        
        # 运行时状态
        self.menu_visible = False
        self.selected_index = -1
        self.menu_root = None
        self.slices = []
        
        # 初始化
        if self._load_scene():
            self._init_input()
            # self._start_loop()
            print(f"✔ VR Radial Menu initialized with {self.slice_count} items.")
        else:
            print("✘ VR Radial Menu initialization failed.")

    def _load_scene(self):
        """加载 VPB 文件并查找节点"""
        print(f"Loading menu from: {self.config['vpb_path']}")
        try:
            ok = vrFileIO.load(self.config['vpb_path'])
            if not ok:
                print("Error: Failed to load VPB file.")
                return False

            self.menu_root = findNode(self.config['root_name'])
            if not self.menu_root:
                print(f"Error: Root node '{self.config['root_name']}' not found.")
                return False

            self.menu_root.setVisible(False)

            # 查找切片节点 (假设命名为 Slice_0, Slice_1, ...)
            self.slices = []
            for i in range(self.slice_count):
                node_name = f"Slice_{i}"
                n = findNode(node_name)
                if not n:
                    print(f"Warning: Slice node '{node_name}' not found.")
                    # 如果找不到对应的几何体，可能导致后续操作失败，这里选择返回 False 或者是容错处理
                    # 这里为了健壮性，如果关键 UI 缺失，则初始化失败
                    return False
                self.slices.append(n)
            
            return True

        except Exception as e:
            print(f"Exception during scene load: {e}")
            return False

    def _init_input(self):
        """绑定控制器事件"""
        vrDeviceService.connect("controllerGripPressed", self._on_grip_pressed)
        vrDeviceService.connect("controllerGripReleased", self._on_grip_released)
        vrDeviceService.connect("controllerTriggerPressed", self._on_trigger_pressed)

    def _start_loop(self):
        """连接到主循环"""
        # connectToMainLoop(self._update)
        # Use vrTimer for update loop
        self.timer = vrTimer()
        self.timer.connect(self._update)
        self.timer.setActive(True)

    def _highlight_slice(self, idx):
        """高亮选中的切片"""
        scale_normal = self.config['scale_normal']
        scale_active = self.config['scale_active']
        
        for i, s in enumerate(self.slices):
            scale = scale_active if i == idx else scale_normal
            s.setScale(scale, scale, scale)

    def _axis_to_slice(self, x, y):
        """根据摇杆坐标计算切片索引"""
        if abs(x) < self.config['dead_zone'] and abs(y) < self.config['dead_zone']:
            return -1
        
        # 计算角度 (0 到 2pi)
        angle = (math.atan2(y, x) + 2 * math.pi) % (2 * math.pi)
        
        # 每个切片的角度范围
        step = 2 * math.pi / self.slice_count
        
        # 计算索引
        return int(angle / step) % self.slice_count

    def _activate_tool(self, idx):
        """激活选中的工具"""
        if 0 <= idx < len(self.buttons):
            item = self.buttons[idx]
            interaction = item.get("interaction")
            name = item.get("name")
            
            print(f"Activate tool [{idx}]: {name}")
            if interaction:
                vrInteractionManager.setCurrentInteraction(interaction)

    def _update(self):
        """每帧更新逻辑"""
        if not self.menu_visible or not self.menu_root:
            return

        cid = self.config['controller_id']
        
        # 更新菜单位置跟随控制器
        pos = vrDeviceService.getControllerPosition(cid)
        rot = vrDeviceService.getControllerRotation(cid)
        
        fwd = rot.getForwardVector()
        dist = self.config['distance']
        p = pos + fwd * dist

        self.menu_root.setWorldTranslation(p.x(), p.y(), p.z())
        self.menu_root.setWorldRotation(rot)

        # 处理摇杆输入
        x = vrDeviceService.getAxisValue("ThumbstickX")
        y = vrDeviceService.getAxisValue("ThumbstickY")

        idx = self._axis_to_slice(x, y)
        if idx != self.selected_index:
            self.selected_index = idx
            self._highlight_slice(idx)

    # ---------- 事件回调 ----------
    
    def _on_grip_pressed(self):
        self.menu_visible = True
        if self.menu_root:
            self.menu_root.setVisible(True)

    def _on_grip_released(self):
        self.menu_visible = False
        self.selected_index = -1
        if self.menu_root:
            self.menu_root.setVisible(False)
        self._highlight_slice(-1)

    def _on_trigger_pressed(self):
        if self.menu_visible and self.selected_index >= 0:
            self._activate_tool(self.selected_index)


# ---------- 入口 ----------

# 创建实例
# 可以根据需要在这里修改配置或从外部文件读取 JSON
radial_menu = VRRadialMenu(MENU_CONFIG, BUTTON_DATA)
