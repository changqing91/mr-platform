# Motion Tracker — VRED 多 Tracker 动态绑定

将 Pico tracker（通过 SteamVR 绑定）的位置与旋转实时同步到 VRED 场景节点（如汽车座椅）。支持多 tracker 独立绑定，运行时动态配置，无需重新注入脚本。

---

## 注入脚本

在 VRED Python 控制台中执行以下命令注入脚本（任选一种方式）：

```python
# 方式 1：直接读取并执行
exec(open(r"\\<服务器路径>\motion_tracker.py").read())

# 方式 2：本地路径
exec(open(r"C:\path\to\motion_tracker.py").read())
```

注入成功后控制台打印：
```
[MotionTracker] Right-B toggle bound (Locomotion group)
[MotionTracker] Initialized. Use list_trackers(), bind(), start_tracking(), status().
```

重复注入时自动跳过（不会重复创建 Interaction）：
```
[MotionTracker] Already initialized, skipping re-init
```

---

## 快速开始

```python
# 1. 查看当前已连接的 tracker 设备
list_trackers()
# 输出示例：[MotionTracker] Connected trackers: tracker-1, tracker-2

# 2. 配置绑定关系（tracker 设备名 → VRED 场景节点名）
bind("tracker-1", "Chair")
bind("tracker-2", "SteeringWheel")   # 可选，支持多个

# 3. 启动追踪
start_tracking()
# 座椅节点立即吸附到 tracker-0 并实时跟随

# 4. 停止追踪
stop_tracking()
# 节点保持最后位置，约束解除

# 5. 查看当前状态
status()
```

---

## API 参考

### `list_trackers()`
枚举并返回当前已连接的 tracker 设备名列表（检测范围：`tracker-0` ~ `tracker-9`）。

```python
trackers = list_trackers()
# → ["tracker-1", "tracker-2"]
```

---

### `bind(tracker_name, node_name, maintain_offset=False)`
配置一条 tracker → 场景节点的绑定关系（不立即激活，需调用 `start_tracking()` 后生效）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `tracker_name` | str | VRED tracker 设备名，如 `"tracker-0"` |
| `node_name` | str | VRED 场景节点名，如 `"Chair"` |
| `maintain_offset` | bool | `False`（默认）= 激活时节点直接吸附到 tracker；`True` = 保留节点与 tracker 的初始位置偏移 |

```python
bind("tracker-1", "Chair")                        # 直接吸附
bind("tracker-1", "Chair", maintain_offset=True)  # 保留偏移
```

如果对同一个 tracker 再次调用 `bind()`，会先停止旧绑定再更新。

---

### `unbind(tracker_name)`
删除指定 tracker 的绑定（如当前已激活，自动先停止约束）。

```python
unbind("tracker-2")
```

---

### `start_tracking(tracker_name=None)`
激活约束，开始追踪。

```python
start_tracking()              # 激活所有已配置绑定
start_tracking("tracker-1")  # 仅激活指定 tracker
```

---

### `stop_tracking(tracker_name=None)`
解除约束，停止追踪。节点保持最后同步的位置与旋转。

```python
stop_tracking()              # 停止所有绑定
stop_tracking("tracker-2")  # 仅停止指定 tracker
```

---

### `toggle_tracking(tracker_name=None)`
切换开/关。若存在任意激活的绑定则全部停止，否则全部启动。

```python
toggle_tracking()   # 全局切换（也可按右手控制器 B 键触发）
```

---

### `status()`
打印所有绑定的当前状态。

```python
status()
# [MotionTracker] Current bindings:
#   tracker-1 -> 'Chair' [ACTIVE] (maintain_offset=False)
#   tracker-2 -> 'SteeringWheel' [stopped] (maintain_offset=False)
```

---

## 控制器按键

| 按键 | 功能 |
|------|------|
| 右手控制器 **B 键** | `toggle_tracking()` 全局切换所有绑定开/关 |

> **注意**：B 键绑定仅在 **Locomotion 交互组**（无工具激活时）生效，与 all_tools.py 中的工具按键不冲突。

---

## 坐标系说明

VRED 的 `ParentConstraint` 内部自动处理 **tracking Y-Up 空间 → scene Z-Up 空间**的坐标转换，与 MR 控制器可视化模型所用机制相同，无需手动换算轴向。同步内容包括**位置（Translation）和旋转（Rotation）**。

---

## 常见问题

**Q: `list_trackers()` 返回空列表？**  
确认 SteamVR 已识别到 Pico tracker 并完成角色绑定（Settings → Controllers → Manage Vive Trackers）。VRED 中 tracker 设备名与 SteamVR 角色绑定名称对应。

**Q: `start_tracking()` 后节点没有移动？**  
1. 调用 `status()` 确认绑定为 `ACTIVE`
2. 确认 `node_name` 与 VRED 场景树中节点名称完全一致（区分大小写）
3. 确认 tracker 设备在 VRED 中有效：`list_trackers()` 应包含该设备名

**Q: 想同时追踪多个节点？**  
多次调用 `bind()` 即可，每个 tracker 独立工作：
```python
bind("tracker-1", "Chair")
bind("tracker-2", "SteeringWheel")
start_tracking()
```

**Q: 如何在不停止其他追踪的情况下单独调整某一个？**  
```python
stop_tracking("tracker-2")
bind("tracker-2", "NewNodeName")
start_tracking("tracker-2")
```
