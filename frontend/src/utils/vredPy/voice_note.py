try:
    from PySide6 import QtCore, QtMultimedia, QtGui
    qt_binding = "pyside6"
except Exception:
    qt_binding = None

if qt_binding:
    global vred_tool_registry
    if 'vred_tool_registry' not in globals():
        vred_tool_registry = {}
    import os
    import datetime
    import tempfile
    if 'voice_note_state' not in globals() or voice_note_state.get('qt_binding') != qt_binding:
        voice_note_state = {
            'qt_binding': qt_binding,
            'recorder': None,
            'player': None,
            'audio_input': None,
            'audio_output': None,
            'capture_session': None,
            'is_recording': False,
            'last_audio_path': None,
            'current_rect': None,
            'last_rect': None,
            'current_annotation': None,
            'current_label': None,
            'current_audio_path': None,
            'rect_audio_paths': {},
            'rect_base_scales': {},
            'hover_rect': None,
            'hover_scale': 1.2
        }
    state = voice_note_state
    def ensure_recorder():
        if state['recorder'] is not None:
            return state['recorder']
        if state['qt_binding'] == "pyside2" and hasattr(QtMultimedia, "QAudioRecorder"):
            state['recorder'] = QtMultimedia.QAudioRecorder()
            return state['recorder']
        state['audio_input'] = QtMultimedia.QAudioInput()
        try:
            inputs = QtMultimedia.QMediaDevices.audioInputs()
            preferred_input = os.getenv("VOICE_NOTE_AUDIO_INPUT", "").strip().lower()
            chosen_input = None
            input_keywords = [
                "alvr",
                "virtual audio",
                "virtual-audio",
                "virtualaudio",
                "audio cable",
                "virtual audio cable",
                "cable",
                "vb-audio",
                "vac",
                "microphone",
                "mic"
            ]
            for dev in inputs:
                try:
                    name = ""
                    try:
                        name = dev.description()
                    except Exception:
                        pass
                    if not name:
                        try:
                            name = dev.deviceName()
                        except Exception:
                            name = ""
                    lowered = name.lower() if name else ""
                    if preferred_input and lowered and preferred_input in lowered:
                        chosen_input = dev
                        break
                    if lowered and any(k in lowered for k in input_keywords):
                        chosen_input = dev
                        break
                except Exception:
                    pass
            if chosen_input is None:
                for dev in inputs:
                    try:
                        if dev.isDefault():
                            chosen_input = dev
                            break
                    except Exception:
                        pass
            if chosen_input is None:
                try:
                    if len(inputs) == 1:
                        chosen_input = inputs[0]
                except Exception:
                    pass
            if chosen_input:
                try:
                    state['audio_input'].setDevice(chosen_input)
                except Exception:
                    pass
        except Exception:
            pass
        state['recorder'] = QtMultimedia.QMediaRecorder()
        state['capture_session'] = QtMultimedia.QMediaCaptureSession()
        state['capture_session'].setAudioInput(state['audio_input'])
        state['capture_session'].setRecorder(state['recorder'])
        return state['recorder']
    def ensure_player():
        state['player'] = QtMultimedia.QMediaPlayer()
        try:
            state['player'].setVolume(100)
        except Exception:
            pass
        if state['qt_binding'] == "pyside6":
            state['audio_output'] = QtMultimedia.QAudioOutput()
            try:
                outputs = QtMultimedia.QMediaDevices.audioOutputs()
                preferred = os.getenv("VOICE_NOTE_AUDIO_DEVICE", "").strip().lower()
                chosen = None
                keywords = [
                    "alvr",
                    "virtual audio",
                    "virtual-audio",
                    "virtualaudio",
                    "audio cable",
                    "virtual audio cable",
                    "cable",
                    "vb-audio",
                    "vac",
                    "vr",
                    "vive",
                    "valve",
                    "index",
                    "oculus",
                    "rift",
                    "openxr",
                    "reverb",
                    "wmr",
                    "headset",
                    "headphones"
                ]
                for dev in outputs:
                    try:
                        name = ""
                        try:
                            name = dev.description()
                        except Exception:
                            pass
                        if not name:
                            try:
                                name = dev.deviceName()
                            except Exception:
                                name = ""
                        lowered = name.lower() if name else ""
                        if preferred and lowered and preferred in lowered:
                            chosen = dev
                            break
                        if lowered and any(k in lowered for k in keywords):
                            chosen = dev
                            break
                    except Exception:
                        pass
                if chosen is None:
                    for dev in outputs:
                        try:
                            if dev.isDefault():
                                chosen = dev
                                break
                        except Exception:
                            pass
                if chosen is None:
                    try:
                        if len(outputs) == 1:
                            chosen = outputs[0]
                    except Exception:
                        pass
                if chosen:
                    try:
                        state['audio_output'].setDevice(chosen)
                    except Exception:
                        pass
                try:
                    state['audio_output'].setVolume(1.0)
                except Exception:
                    pass
            except Exception:
                pass
            state['player'].setAudioOutput(state['audio_output'])
        return state['player']
    def get_device_pick_position(device):
        if not device:
            return None
        try:
            hit = device.pick()
            if hit and hit.hasHit():
                point = hit.getPoint()
                if point:
                    try:
                        normal = hit.getNormal()
                        if normal and normal.length() > 0.0001:
                            return point + normal.normalized() * 0.01
                    except Exception:
                        pass
                    return point
        except Exception:
            pass
        return None
    def get_device_target_position(device):
        pos = get_device_pick_position(device)
        if pos:
            return pos
        try:
            matrix = device.getTrackingMatrix()
            if matrix:
                col = matrix.column(3)
                origin = QtGui.QVector3D(col.x(), col.y(), col.z())
                axis = matrix.column(2)
                forward = QtGui.QVector3D(axis.x(), axis.y(), axis.z())
                if forward.length() > 0.0001:
                    return origin + forward.normalized() * 2.0
        except Exception:
            pass
        return None
    def get_rect_key(node):
        if not node:
            return None
        try:
            key = node.getUniquePath()
            if key:
                return key
        except Exception:
            pass
        try:
            name = node.getName()
            if name:
                return name
        except Exception:
            pass
        return str(id(node))
    def store_rect_scale(rect):
        if not rect:
            return
        key = get_rect_key(rect)
        if not key:
            return
        if key in state['rect_base_scales']:
            return
        try:
            base = rect.getScale()
        except Exception:
            base = QtGui.QVector3D(1.0, 1.0, 1.0)
        state['rect_base_scales'][key] = base
    def apply_rect_scale(rect, scale):
        if not rect or not scale:
            return
        try:
            rect.setScale(scale)
            return
        except Exception:
            pass
        try:
            rect.setWorldScale(scale)
        except Exception:
            pass
    def set_hover_rect(node):
        if node == state.get('hover_rect'):
            return
        prev = state.get('hover_rect')
        if prev:
            prev_key = get_rect_key(prev)
            base = state['rect_base_scales'].get(prev_key)
            if base:
                apply_rect_scale(prev, base)
        state['hover_rect'] = node
        if node:
            key = get_rect_key(node)
            base = state['rect_base_scales'].get(key)
            if not base:
                try:
                    base = node.getScale()
                except Exception:
                    base = QtGui.QVector3D(1.0, 1.0, 1.0)
                state['rect_base_scales'][key] = base
            factor = state.get('hover_scale', 1.2)
            scale = QtGui.QVector3D(base.x() * factor, base.y() * factor, base.z() * factor)
            apply_rect_scale(node, scale)
    def play_audio(path):
        if not path or not os.path.exists(path):
            return False
        player = ensure_player()
        url = QtCore.QUrl.fromLocalFile(path)
        if hasattr(QtMultimedia.QMediaPlayer, "setSource"):
            player.setSource(url)
        else:
            player.setMedia(QtMultimedia.QMediaContent(url))
        player.play()
        return True
    def create_rectangle(text, position=None):
        root = vrScenegraphService.getRootNode()
        size = QtGui.QVector2D(360.0, 220.0)
        color = QtGui.QColor(28, 28, 32)
        rect = None
        annotation = None
        try:
            rect = vrGeometryService.createPlane(root, size, 1, 1, color)
        except Exception:
            rect = None
        if rect:
            try:
                rect.setName(text)
            except Exception:
                pass
            try:
                cam = vrCameraService.getActiveCamera(True)
                aim = vrConstraintService.createAimConstraint([cam], [], rect)
                if aim:
                    aim.setVisualizationVisible(False)
            except Exception:
                pass
            store_rect_scale(rect)
        if position and rect:
            try:
                rect.setWorldTranslation(position)
            except Exception:
                try:
                    rect.setTranslation(position)
                except Exception:
                    pass
        if rect:
            try:
                vrMetadataService.addTags([rect], ["voice_note_rect"])
            except Exception:
                pass
            if text:
                try:
                    annotation = vrAnnotationService.createAnnotation(text)
                    annotation.setText(text)
                    annotation.setSceneNode(rect)
                    annotation.setAnchored(True)
                    if position:
                        annotation.setPosition(position)
                except Exception:
                    annotation = None
        return rect, annotation
    def start_recording(position=None):
        base_dir = os.path.join(tempfile.gettempdir(), "vred_voice_notes")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "voice_note_" + ts + ".wav"
        path = os.path.join(base_dir, filename)
        recorder = ensure_recorder()
        recorder.setOutputLocation(QtCore.QUrl.fromLocalFile(path))
        label = "语音标注 " + ts
        rect, annotation = create_rectangle(label + " 录音中", position)
        recorder.record()
        state['is_recording'] = True
        state['current_rect'] = rect
        state['current_annotation'] = annotation
        state['current_audio_path'] = path
        state['current_label'] = label
        if rect:
            key = get_rect_key(rect)
            if key:
                state['rect_audio_paths'][key] = path
    def stop_recording():
        recorder = ensure_recorder()
        recorder.stop()
        state['is_recording'] = False
        if state['current_rect']:
            old_key = get_rect_key(state['current_rect'])
            try:
                state['current_rect'].setName(state['current_label'])
            except Exception:
                pass
            if state['current_annotation']:
                try:
                    state['current_annotation'].setText(state['current_label'])
                except Exception:
                    pass
            new_key = get_rect_key(state['current_rect'])
            if old_key and new_key and old_key != new_key:
                if old_key in state['rect_audio_paths']:
                    state['rect_audio_paths'][new_key] = state['rect_audio_paths'].pop(old_key)
                if old_key in state['rect_base_scales']:
                    state['rect_base_scales'][new_key] = state['rect_base_scales'].pop(old_key)
            state['last_rect'] = state['current_rect']
        state['last_audio_path'] = state.get('current_audio_path')
        state['current_rect'] = None
        state['current_annotation'] = None
        state['current_audio_path'] = None
        state['current_label'] = None
    class VoiceNotes:
        def __init__(self):
            self.leftController = vrDeviceService.getVRDevice("left-controller")
            self.rightController = vrDeviceService.getVRDevice("right-controller")
            self.leftController.setVisualizationMode(Visualization_ControllerAndHand)
            self.rightController.setVisualizationMode(Visualization_ControllerAndHand)
            vrImmersiveInteractionService.setDefaultInteractionsActive(1)
            self.multi = vrDeviceService.createInteraction("MultiButtonPadVoice")
            self.multi.setSupportedInteractionGroups(["NotesGroup"])
            self.pointer = vrDeviceService.getInteraction("Pointer")
            self.pointer.addSupportedInteractionGroup("NotesGroup")
            self.triggerRightPressed = self.multi.createControllerAction("right-trigger-pressed")
            self.timer = vrTimer()
            self.registry_key = "tool_voice_note"
            self.enable()
        def distanceFunc(self):
            hover_node = None
            try:
                hit = self.rightController.pick()
            except Exception:
                hit = None
            if hit and hit.hasHit():
                try:
                    node = hit.getNode()
                except Exception:
                    node = None
                if node:
                    try:
                        if vrMetadataService.hasTag(node, "voice_note_rect"):
                            hover_node = node
                    except Exception:
                        hover_node = None
            set_hover_rect(hover_node)
        def on_trigger(self, action_obj=None, device_obj=None):
            _ = action_obj
            device = device_obj if device_obj else self.rightController
            if device:
                try:
                    hit = device.pick()
                except Exception:
                    hit = None
                if hit and hit.hasHit():
                    try:
                        node = hit.getNode()
                    except Exception:
                        node = None
                    if node:
                        try:
                            if vrMetadataService.hasTag(node, "voice_note_rect"):
                                if state['is_recording'] and state.get('current_rect') == node:
                                    stop_recording()
                                else:
                                    key = get_rect_key(node)
                                    path = state['rect_audio_paths'].get(key)
                                    play_audio(path)
                                return
                        except Exception:
                            pass
            pos = get_device_target_position(device)
            if state['is_recording']:
                stop_recording()
            else:
                start_recording(pos)
        def enable(self):
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
            self.triggerRightPressed.signal().triggered.connect(self.on_trigger)
            self.timer.setActive(1)
            self.timer.connect(self.distanceFunc)
        def disable(self):
            try:
                if vred_tool_registry.get(self.registry_key) is self:
                    del vred_tool_registry[self.registry_key]
            except Exception:
                pass
            try:
                self.triggerRightPressed.signal().triggered.disconnect(self.on_trigger)
            except Exception:
                pass
            try:
                self.timer.setActive(0)
            except Exception:
                pass
            try:
                if state.get('is_recording'):
                    stop_recording()
            except Exception:
                pass
    VoiceNotes()
    print("executed")
