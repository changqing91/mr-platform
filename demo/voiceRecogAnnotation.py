def tool_voice_note():
    # try:
    #     from PySide2 import QtCore, QtMultimedia, QtGui
    #     qt_binding = "pyside2"
    # except Exception:
    #     try:
    #         from PySide6 import QtCore, QtMultimedia, QtGui
    #         qt_binding = "pyside6"
    #     except Exception as e:
    #         print("Voice note unavailable:", e)
    #         return
    try:
        from PySide6 import QtCore, QtMultimedia, QtGui
        qt_binding = "pyside6"
    except Exception as e:
        print("Voice note unavailable:", e)
        return
    import os
    import datetime
    import tempfile
    global voice_note_state
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
            'trigger_action': None,
            'trigger_interaction': None,
            'trigger_connected': False,
            'trigger_timer': None,
            'trigger_last_pressed': {},
            'ray_enabled': {},
            'rect_audio_paths': {},
            'rect_base_scales': {},
            'hover_rect': None,
            'hover_scale': 1.2
        }
    state = voice_note_state
    state['player'] = None
    def ensure_recorder():
        if state['recorder'] is not None:
            return state['recorder']
        if state['qt_binding'] == "pyside2" and hasattr(QtMultimedia, "QAudioRecorder"):
            state['recorder'] = QtMultimedia.QAudioRecorder()
            return state['recorder']
        state['audio_input'] = QtMultimedia.QAudioInput()
        state['recorder'] = QtMultimedia.QMediaRecorder()
        state['capture_session'] = QtMultimedia.QMediaCaptureSession()
        state['capture_session'].setAudioInput(state['audio_input'])
        state['capture_session'].setRecorder(state['recorder'])
        return state['recorder']
    def ensure_player():
        print(0)
        print(state['player'])
        # if state['player'] is not None:
        #     return state['player']
        print(1)
        state['player'] = QtMultimedia.QMediaPlayer()
        print(2)
        try:
            state['player'].setVolume(100)
            print(3)
        except Exception:
            pass
        print(4)
        print(state['qt_binding'])
        print(5)
        if state['qt_binding'] == "pyside6":
            state['audio_output'] = QtMultimedia.QAudioOutput()
            print(4)
            print(state['audio_output'])
            try:
                print(1)
                outputs = QtMultimedia.QMediaDevices.audioOutputs()
                hmd_keywords = ["vr", "vive", "valve", "index", "oculus", "rift", "openxr", "reverb", "wmr", "headset", "headphones"]
                preferred = os.getenv("VOICE_NOTE_AUDIO_DEVICE", "").strip().lower()
                chosen = None
                names = []
                print(outputs)
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
                        if name:
                            names.append(name)
                        if preferred and name and preferred in name.lower():
                            chosen = dev
                            break
                        if name and any(k in name.lower() for k in hmd_keywords):
                            chosen = dev
                            break
                    except Exception:
                        pass
                print(names)
                if names:
                    print("Audio outputs:", ", ".join(names))
                print(chosen)
                if chosen is None:
                    for dev in outputs:
                        try:
                            if dev.isDefault():
                                chosen = dev
                                break
                        except Exception:
                            pass
                if chosen:
                    try:
                        state['audio_output'].setDevice(chosen)
                        try:
                            chosen_name = ""
                            try:
                                chosen_name = chosen.description()
                            except Exception:
                                pass
                            if not chosen_name:
                                try:
                                    chosen_name = chosen.deviceName()
                                except Exception:
                                    chosen_name = ""
                            if chosen_name:
                                print("Using audio output:", chosen_name)
                        except Exception:
                            pass
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
    def get_camera_target():
        cam = vrCameraService.getActiveCamera(True)
        if cam:
            fa = cam.getFromAtUpWorld()
            if fa:
                pos = fa.getAt()
                if pos:
                    return pos
                return fa.getFrom()
        return None
    def get_device_position(device):
        if not device:
            return None
        try:
            matrix = device.getTrackingMatrix()
            if matrix:
                col = matrix.column(3)
                try:
                    return col.toVector3D()
                except Exception:
                    return QtGui.QVector3D(col.x(), col.y(), col.z())
        except Exception:
            pass
        try:
            node = device.getNode()
            if node:
                matrix = node.getWorldTransform()
                col = matrix.column(3)
                try:
                    return col.toVector3D()
                except Exception:
                    return QtGui.QVector3D(col.x(), col.y(), col.z())
        except Exception:
            pass
        return None
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
        return get_device_position(device)
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
    def format_label(text):
        if text:
            return "🎤 " + text
        return "🎤"
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
            print("false")
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
        pos = position if position else get_camera_target()
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
        if pos and rect:
            try:
                rect.setWorldTranslation(pos)
            except Exception:
                try:
                    rect.setTranslation(pos)
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
                    annotation.setText(format_label(text))
                    annotation.setSceneNode(rect)
                    annotation.setAnchored(True)
                    if pos:
                        annotation.setPosition(pos)
                    annotation.setBackgroundColor(QtGui.QColor(20, 20, 24, 200))
                    annotation.setLineColor(QtGui.QColor(0, 0, 0, 0))
                    annotation.setFontColor(QtGui.QColor(245, 245, 245))
                    annotation.setSize(1.1)
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
        print("Voice note recording")
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
                    state['current_annotation'].setText(format_label(state['current_label']))
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
        print("Voice note recorded")
    def ensure_trigger_binding():
        if state.get('trigger_connected'):
            return
        interaction_name = "VoiceNoteTrigger"
        interaction = vrDeviceService.createInteraction(interaction_name)
        try:
            interaction.addSupportedInteractionGroup("default")
        except Exception:
            pass
        action = interaction.createControllerAction("any-trigger-pressed")
        state['trigger_action'] = action
        state['trigger_interaction'] = interaction
        def on_trigger(action_obj=None, device_obj=None):
            print("Trigger pressed")
            device = device_obj
            if device:
                try:
                    hit = device.pick()
                except Exception:
                    hit = None
                if hit and hit.hasHit():
                    try:
                        node = hit.getNode()
                        print(1)
                        print(node)
                    except Exception:
                        node = None
                    if node:
                        try:
                            if vrMetadataService.hasTag(node, "voice_note_rect"):
                                if state['is_recording'] and state.get('current_rect') == node:
                                    stop_recording()
                                else:
                                    print(4)
                                    key = get_rect_key(node)
                                    path = state['rect_audio_paths'].get(key)
                                    play_audio(path)
                                return
                        except Exception:
                            return
            pos = get_device_target_position(device)
            if state['is_recording']:
                stop_recording()
            else:
                start_recording(pos)
        try:
            action.signal().triggered.connect(on_trigger)
            state['trigger_connected'] = True
            vrDeviceService.activateInteraction(interaction_name)
        except Exception:
            def on_device_action(action_obj, device_obj):
                if action_obj and state.get('trigger_action') and action_obj.getName() == state['trigger_action'].getName():
                    on_trigger(action_obj, device_obj)
            vrDeviceService.deviceActionTriggered.connect(on_device_action)
            state['trigger_connected'] = True
            vrDeviceService.activateInteraction(interaction_name)
    def ensure_trigger_polling():
        if state.get('trigger_timer'):
            return
        def ensure_device_ray(device, key):
            if state['ray_enabled'].get(key):
                return
            try:
                device.enableRay("z")
                state['ray_enabled'][key] = True
            except Exception:
                state['ray_enabled'][key] = False
        def poll_trigger():
            devices = []
            try:
                connected = vrDeviceService.getConnectedVRDevices()
                if connected:
                    devices.extend(connected)
            except Exception:
                pass
            if not devices:
                devices = [
                    vrDeviceService.getVRDevice("left-controller"),
                    vrDeviceService.getVRDevice("right-controller")
                ]
            seen = set()
            hover_node = None
            for device in devices:
                if not device:
                    continue
                key_id = id(device)
                if key_id in seen:
                    continue
                seen.add(key_id)
                try:
                    name = device.getName()
                except Exception:
                    name = None
                key = name if name else str(key_id)
                ensure_device_ray(device, key)
                if hover_node is None:
                    try:
                        hover_hit = device.pick()
                    except Exception:
                        hover_hit = None
                    if hover_hit and hover_hit.hasHit():
                        try:
                            hover_node = hover_hit.getNode()
                        except Exception:
                            hover_node = None
                        if hover_node:
                            try:
                                if not vrMetadataService.hasTag(hover_node, "voice_note_rect"):
                                    hover_node = None
                            except Exception:
                                hover_node = None
                last_pressed = state['trigger_last_pressed'].get(key, False)
                pressed = False
                try:
                    button_state = device.getButtonState("trigger")
                    if button_state:
                        pressed = button_state.isPressed()
                except Exception:
                    pressed = False
                if pressed and not last_pressed:
                    handled = False
                    try:
                        hit = device.pick()
                        print(hit)
                    except Exception:
                        hit = None
                    if hit and hit.hasHit():
                        try:
                            node = hit.getNode()
                            print(node)
                        except Exception:
                            node = None
                        if node:
                            try:
                                print(2)
                                print(node)
                                if vrMetadataService.hasTag(node, "voice_note_rect"):
                                    if state['is_recording'] and state.get('current_rect') == node:
                                        stop_recording()
                                    else:
                                        print(3)
                                        key = get_rect_key(node)
                                        path = state['rect_audio_paths'].get(key)
                                        print(path)
                                        play_audio(path)
                                    handled = True
                            except Exception:
                                handled = True
                    if not handled:
                        pos = get_device_target_position(device)
                        if state['is_recording']:
                            stop_recording()
                        else:
                            start_recording(pos)
                state['trigger_last_pressed'][key] = pressed
            set_hover_rect(hover_node)
        timer = vrTimer(0.04, False)
        timer.connect(poll_trigger)
        timer.setActive(True)
        state['trigger_timer'] = timer
    ensure_trigger_binding()
    ensure_trigger_polling()
    if state['is_recording']:
        stop_recording()
        return
