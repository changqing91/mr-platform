# MR Platform — all_tools.py 重构上下文

## 目标

将 `frontend/src/utils/vredPy/all_tools.py` 中所有工具特定的 OSB 文件引用，统一替换为单一 `\\192.168.7.80\upload\VRED\MMR_Stuff.osb`，并根据 `mrToolsInfo.txt` 交互文档更新所有工具的按钮交互逻辑。

**原则**：避免兜底逻辑，不增加不必要的代码量。

---

## 关键信息

| 项目 | 值 |
|------|-----|
| 目标文件 | `frontend/src/utils/vredPy/all_tools.py`（~3280行） |
| 新 OSB 路径 | `\\192.168.7.80\upload\VRED\MMR_Stuff.osb` |
| 右手控制器节点 | `MRcontrollerRight` |
| 左手控制器节点 | `MRcontrollerLeft` |
| UI 切换节点 | `CtrllrR_UI`（switch 节点，子节点顺序即 choice 索引） |
| 素材组节点 | `MR_Stuff` |
| 语音播放器节点 | `VoicePlayer` |
| 标注节点结构 | `Tags`（外层 group）→ `Tags`（内层 switch）→ Move/AlignCenter/Smile/Passed/Notice/AlignTo/Good/Flag/Cancel/MoreCurve |

---

## CtrllrR_UI Choice 索引表

| Index | 节点名 | 工具/状态 |
|-------|--------|-----------|
| 0 | ControllerDefault_R | 无工具激活时 |
| 1 | TagDefault_R | Notes 添加模式 |
| 2 | TagAdd_R | Notes 射线放置（备用） |
| 3 | TagDelete_R | Notes 删除模式 |
| 4 | TagMove_R | Notes 抓取移动中 |
| 5 | ClipPositive_R | SectionTool 正面 |
| 6 | ClipNegative_R | SectionTool 反面（B切换） |
| 7 | VoiceNoteDefault_R | VoiceNotes 默认 |
| 8 | VoiceNoteRecord_R | VoiceNotes A按住录音中 |
| 9 | VoiceNoteEraser_R | VoiceNotes B按住橡皮擦 |
| 10 | VoiceNoteMove_R | VoiceNotes Grip拖动中 |
| 11 | Transform_R | AdjustTool |
| 12 | Flashlight_R | FlashlightTool |
| 13 | Turntable_R | TurntableTool |
| 14 | MeasurementPtoP_R | MeasureTool |

---

## 进度状态

| 任务 | 状态 |
|------|------|
| VoiceNotes 全部修改 | ✅ 已完成 |
| Phase 1 模块级初始化（L38–L168） | ✅ 已完成 |
| AdjustTool.enable() | ✅ 已完成 |
| Notes class 重构 | ✅ 已完成 |
| SectionTool 修改 | ✅ 已完成 |
| TurntableTool 修改 | ✅ 已完成 |
| MeasureTool 修改 | ✅ 已完成 |
| FlashlightTool 修改 | ✅ 已完成 |
| cleanup_all_tools() 修改 | ✅ 已完成 |

---

## 已完成详情：VoiceNotes

| 修改点 | 内容 |
|--------|------|
| `__init__` | 新增 `aPressedAction`, `aReleasedAction`；新增 `_eraser_held = False` |
| `_ensure_voice_player_template()` | 改为 `findNode("VoicePlayer")` + `setActive(False)` + `setIsVRNode`，删除 OSB 文件加载 |
| `_find_or_load_voice_controller()` | 改为 `return findNode("MRcontrollerRight")` |
| `_activate_voice_controller()` | 统一激活：取位置 → `choice=7` → `setVisible(0)` → `setActive(1)` → 移位 → 约束；删除 if/else 分支 |
| `distanceFunc()` | 新增 `_eraser_held` 分支：靠近球体时 `deleteNode` + 清理5个dict |
| `on_a_pressed()` | 新增：`choice=8` + `_start_recording()` |
| `on_a_released()` | 新增：`_stop_recording()` + `choice=7` |
| `on_b_pressed()` | 改为：`_eraser_held=True` + `choice=9` |
| `on_b_released()` | 改为：`_eraser_held=False` + `choice=7` |
| `on_grip_pressed()` | 加 `choice=10` 在约束建立后 |
| `on_grip_released()` | 加 `choice=7` |
| `enable()` | 新增连接 `aPressedAction/aReleasedAction`；更新 print 文本 |
| `disable()` | 新增断开 `aPressedAction/aReleasedAction`；加 `_eraser_held=False` reset |

---

## 待完成详情

### Phase 1 — 模块级初始化（L38–L168）

**删除以下全部内容：**
- `_get_vred_documents_dir()` 函数（L41–L53）
- Adjust控制器查找/加载块（查 `WT-MR_Remote_controllers`，加载 `ControllerBase.osb`）
- Notes资源块：`notesController/goodBadNotes/mainCustomFuncGroup/customFunctionsGroup` 变量及相关 for 循环、OSB加载、`allFuncNames/addChilds` 逻辑
- Section控制器查找/加载块（查 `VRController_Clip/VRControllerClip`，加载 `VRControllerClip.osb`）
- `refObject = findNode("Notes").getChild(0)` / `switchNode = findNode("Notes")` 旧引用

**新增以下内容（替换上述删除部分）：**
```python
_MMR_OSB_PATH = r"\\192.168.7.80\upload\VRED\MMR_Stuff.osb"

_mmrLoaded = False
try:
    for node in getAllNodes():
        if node.getName() == "MRcontrollerRight":
            _mmrLoaded = True
            break
except Exception:
    pass

if not _mmrLoaded:
    loadGeometry(_MMR_OSB_PATH)
    findNode("MRcontrollerLeft").setActive(0)
    findNode("MRcontrollerRight").setActive(0)

adjustControllerFound = True
notesControllerFound = True
clippingControllerFound = True
rotationControllerFound = True

# 左手控制器约束
_mrLeft = findNode("MRcontrollerLeft")
_leftCtrl = vrDeviceService.getVRDevice("left-controller")
_mrLeft.setActive(1)
vrConstraintService.createParentConstraint([_leftCtrl.getNode()], _mrLeft, False)

# Notes 节点引用
try:
    _tagsOuter = findNode("Tags")
    switchNode = _tagsOuter.getChild(0)   # inner Tags switch
    refObject = switchNode.getChild(0)    # first child (Move)
except Exception:
    refObject = None
    switchNode = None

noteCount = 0
try:
    Cloned_ref_obj = findNode("Cloned_ref_obj")
except Exception:
    Cloned_ref_obj = createNode('Group', 'Cloned_ref_obj')
```

---

### AdjustTool.enable()

**替换** `if adjustControllerFound:` 整个条件块：
```python
self.newRightCon = findNode("MRcontrollerRight")
findNode("CtrllrR_UI").fields().setInt32("choice", 11)
self.rightController.setVisible(0)
self.rightController.setEnabled(0)
self.newRightCon.setActive(1)
controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
self.AdjustControllerConstraint = vrConstraintService.createParentConstraint(
    [self.rightController.getNode()], self.newRightCon, False)
```

---

### Notes class（图形标注）

**`__init__` 修改：**
- 删除 `leftTriggerPressed`, `leftGripPressed`, `padUpTouched`, `padDownTouched` actions
- 保留 `gripPressed`，新增 `gripReleasedAction`
- 新增 `aPressedAction = createControllerAction("right-a-pressed")`
- 新增 `bPressedAction = createControllerAction("right-b-pressed")`
- 删除 `self.changeView = False`
- 新增 `self.grabConstraint = None`

**`enable()` 修改：**
- 控制器激活：`findNode("MRcontrollerRight")` + `choice=1`（删除 `if notesControllerFound:` 块）
- 信号连接：`aPressedAction→toggleDeleteMode`, `bPressedAction→ChangeNote`, `gripPressed→grabNote`, `gripReleasedAction→releaseNote`
- 删除：`leftTriggerPressed→ChangeNote`, `leftGripPressed→changeNoteView`, 旧 `gripPressed→deleteNote`, `padUpTouched/padDownTouched` 连接

**`disable()` 修改：**
- 断开新 actions，删除旧 actions 的断开，删除 `neutralNotes()` 调用

**新增方法 `toggleDeleteMode()`：**
```python
def toggleDeleteMode(self):
    global refObject
    refObject_node = vrNodeService.getNodeFromId(refObject.getID())
    if not self.deleteNoteIsActive:
        self.deleteNoteIsActive = True
        findNode("CtrllrR_UI").fields().setInt32("choice", 3)
        refObject_node.getParent().setVisibilityFlag(False)
    else:
        self.deleteNoteIsActive = False
        findNode("CtrllrR_UI").fields().setInt32("choice", 1)
        refObject_node.getParent().setVisibilityFlag(True)
```

**新增方法 `grabNote()`：**
```python
def grabNote(self, action=None, device=None):
    global Cloned_ref_obj
    right_node = self.rightController.getNode()
    best, best_dist = None, float('inf')
    try:
        for i in range(Cloned_ref_obj.getNChildren()):
            child = Cloned_ref_obj.getChild(i)
            pos = getTransformNodeTranslation(child, 1)
            hand = getTransformNodeTranslation(right_node, 1)
            dx = pos.x()-hand.x(); dy = pos.y()-hand.y(); dz = pos.z()-hand.z()
            d = math.sqrt(dx*dx+dy*dy+dz*dz)
            if d < best_dist:
                best_dist, best = d, child
    except Exception:
        pass
    if best:
        self.grabConstraint = vrConstraintService.createParentConstraint([right_node], best, True)
        findNode("CtrllrR_UI").fields().setInt32("choice", 4)
```

**新增方法 `releaseNote()`：**
```python
def releaseNote(self, action=None, device=None):
    if self.grabConstraint:
        vrConstraintService.deleteConstraint(self.grabConstraint)
        self.grabConstraint = None
    findNode("CtrllrR_UI").fields().setInt32("choice", 3 if self.deleteNoteIsActive else 1)
```

**改写图标方法：**
```python
def iconsNotesTrashOn(self):
    findNode("CtrllrR_UI").fields().setInt32("choice", 3)
def iconsNotesTrashOff(self):
    findNode("CtrllrR_UI").fields().setInt32("choice", 1)
def iconsNotesConstraint(self):
    findNode("CtrllrR_UI").fields().setInt32("choice", 1)
def iconsNotesRay(self):
    findNode("CtrllrR_UI").fields().setInt32("choice", 2)
```

**删除方法：** `changeNoteView`, `onControllerNotesMapping`, `onRayNotesMapping`, `neutralNotes`, `defaultNotesMappings`

---

### SectionTool

**`__init__` 新增：**
```python
self.aPressedAction = multiButtonPadClip.createControllerAction("right-a-pressed")
self.bPressedAction = multiButtonPadClip.createControllerAction("right-b-pressed")
```

**`enable()` 修改：**
- 新增连接：`aPressedAction→ClippingState`, `bPressedAction→toggleClipDir`
- 替换控制器激活块（删除 `if clippingControllerFound:` 嵌套），使用统一模式（choice=5）

**`disable()` 修改：**
- 新增断开 `aPressedAction/bPressedAction`
- 删除 `if clippingControllerFound: setSwitchMaterialChoice(...)` 块

**新增方法 `toggleClipDir()`：**
```python
def toggleClipDir(self, action=None, device=None):
    try:
        cur = findNode("CtrllrR_UI").fields().getInt32("choice")
        findNode("CtrllrR_UI").fields().setInt32("choice", 6 if cur == 5 else 5)
    except Exception:
        pass
```

**删除所有 `setSwitchMaterialChoice("C_C_*")` 调用：**
- `GridVis()`, `PlaneVis()`, `ContourVis()`, `ClippingState()`, `clipX/Y/ZConstraintON/OFF` 中各处

---

### TurntableTool

**`__init__` 新增：**
```python
self.aPressedAction = self.multiButtonPad.createControllerAction("right-a-pressed")
self.aReleasedAction = self.multiButtonPad.createControllerAction("right-a-released")
self.bPressedAction = self.multiButtonPad.createControllerAction("right-b-pressed")
self.originalAngle = 0.0
```

**`enable()` 修改：**
- 删除 `triggerStart→on_trigger_toggle` 连接
- 新增：`aPressedAction→start_rotation`, `aReleasedAction→stop_rotation`, `bPressedAction→restore_rotation`
- 替换控制器激活（`_find_node_by_names` → `findNode("MRcontrollerRight")`，choice=13）
- 激活后记录：`self.originalAngle = getTransformNodeRotation(self.node).z()`

**`disable()` 修改：**
- 删除 `triggerStart` 相关；新增断开 `aPressedAction/aReleasedAction/bPressedAction`

**新增方法 `restore_rotation()`：**
```python
def restore_rotation(self, action=None, device=None):
    if self.node:
        try:
            rot = getTransformNodeRotation(self.node)
            setTransformNodeRotation(self.node, rot.x(), rot.y(), self.originalAngle)
            self.currentAngle = self.originalAngle
        except Exception:
            pass
```

**删除方法：** `on_trigger_toggle`, `_find_node_by_names`

---

### MeasureTool

**`_find_or_load_measure_controller()` 全部替换：**
```python
def _find_or_load_measure_controller(self):
    return findNode("MRcontrollerRight")
```

**`_activate_measure_controller()` 替换：**
```python
def _activate_measure_controller(self):
    self.newRightCon = self._find_or_load_measure_controller()
    controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
    findNode("CtrllrR_UI").fields().setInt32("choice", 14)
    self.rightController.setVisible(0)
    self.rightController.setEnabled(0)
    self.newRightCon.setActive(1)
    self.measureControllerConstraint = vrConstraintService.createParentConstraint(
        [self.rightController.getNode()], self.newRightCon, False)
```

---

### FlashlightTool

**`__init__` 修改：**
- 删除 `self.triggerRightPressed = ...createControllerAction("right-trigger-pressed")`
- 新增：
```python
self.aPressedAction = self.multiButtonPad.createControllerAction("right-a-pressed")
self.bPressedAction = self.multiButtonPad.createControllerAction("right-b-pressed")
```

**删除方法：** `get_controller_osb_path()`, `load_model()`

**`create_geo()` 修改：**
- 删除 `self.load_model()` 调用及 `self.flashlight_handle = vrNodeService.findNode(...)` 查找

**新增方法（替代 `toggle_light()`）：**
```python
def switch_on_light(self, action=None, device=None):
    if self.lightNode is None:
        self._create_spotlight()
    if self.lightNode:
        self.lightNode.setOn(True)
        self.lightOn = True

def switch_off_light(self, action=None, device=None):
    if self.lightNode:
        self.lightNode.setOn(False)
        self.lightOn = False
```

**`_find_or_load_flashlight_controller()` 全部替换：**
```python
def _find_or_load_flashlight_controller(self):
    return findNode("MRcontrollerRight")
```

**`_activate_flashlight_controller()` 替换：**
```python
def _activate_flashlight_controller(self):
    self.newRightCon = self._find_or_load_flashlight_controller()
    controllerPos = getTransformNodeTranslation(self.rightController.getNode(), 1)
    findNode("CtrllrR_UI").fields().setInt32("choice", 12)
    self.rightController.setVisible(0)
    self.newRightCon.setActive(1)
    setTransformNodeTranslation(self.newRightCon, controllerPos.x(), controllerPos.y(), controllerPos.z(), True)
    self.flashlightControllerConstraint = vrConstraintService.createParentConstraint(
        [self.rightController.getNode()], self.newRightCon, False)
```

**`enable()` 修改：**
- 删除 `triggerRightPressed.signal().triggered.connect(self.toggle_light)`
- 新增：`aPressedAction→switch_on_light`, `bPressedAction→switch_off_light`

**`disable()` 修改：**
- 删除 `triggerRightPressed` 断开，新增 `aPressedAction/bPressedAction` 断开

---

### cleanup_all_tools()

**`_nodes_to_remove` 替换为：**
```python
_nodes_to_remove = [
    "MRcontrollerLeft",
    "MRcontrollerRight",
    "MR_Stuff",
    "Cloned_ref_obj",
    "VR_Flashlight",
]
```

**变量重置块（global 声明及重置）替换为：**
```python
try:
    refObject = None
    switchNode = None
    Cloned_ref_obj = None
    noteCount = 0
except Exception:
    pass
```
删除 `customFunctionsGroup`, `adjustControllerFound=False` 等（不再需要）。

---

## 执行顺序建议

1. **Phase 1 init** (L38–L168) — 建立 MMR_Stuff 加载基础
2. **AdjustTool.enable()** — 简单替换
3. **MeasureTool** — 两处方法替换
4. **FlashlightTool** — 删除旧方法 + 两处新方法
5. **TurntableTool** — 按钮重映射 + restore方法
6. **SectionTool** — 新增按钮 + 删除所有 `setSwitchMaterialChoice`
7. **Notes** — 最复杂，大量重构
8. **cleanup_all_tools()** — 节点列表替换
