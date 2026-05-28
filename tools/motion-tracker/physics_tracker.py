# ======================================================================
# VRED Physics Hand Grab (VRED 2027 API)
#
# Goal:
#   Hand-visible controller (default: right-controller) grabs Cola
#   Cola is a dynamic physics object
#   Cola collides with Console1 (static physics object)
#
# Assumption:
#   Cola and Console1 are already configured in VRED Physics Editor.
# ======================================================================

try:
    from PySide6.QtGui import QVector3D
except ImportError:
    from PySide2.QtGui import QVector3D


class DynamicColaTracker:
    """
    Drive a dynamic physics object (Cola) using controller grab input.
    No transform write is used during follow; only physics force is applied.
    """

    def __init__(self):
        # Compatibility: keep old parameter name `tracker_name`, but default to controller device.
        self._tracker_name = "right-controller"
        self._cola_node_name = "Cola"
        self._console_node_name = "Console1"

        self._tracker = None
        self._cola_node = None
        self._console_node = None
        self._cola_physics = None

        self._active = False

        self._timer = vrTimer()
        self._timer_connected = False

        # Physics grab tuning
        self._gain = 22.0
        self._damping = 5.0
        self._max_force = 1.6
        self._max_error = 0.12
        self._reanchor_distance = 0.35
        self._deadzone = 0.004
        self._grab_threshold = 0.5

        # Grab state
        self._grab_active = False
        self._grip_held = False
        self._grab_offset = None
        self._prev_cola_pos = None
        self._velocity_dt = 1.0 / 90.0

        self._sig_start = None
        self._sig_stop = None
        self._sig_cont = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def setup(self, tracker_name="right-controller", cola_node_name="Cola", console_node_name="Console1"):
        if self._active:
            self.stop()

        self._tracker_name = tracker_name
        self._cola_node_name = cola_node_name
        self._console_node_name = console_node_name

        print("[DynamicColaTracker] Configured input '{}' -> '{}' (target static: '{}')".format(
            self._tracker_name, self._cola_node_name, self._console_node_name))

    def set_tuning(self, gain=None, damping=None, max_force=None, max_error=None,
                   reanchor_distance=None, deadzone=None, grab_threshold=None):
        if gain is not None:
            try:
                self._gain = float(gain)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid gain={}".format(gain))
        if damping is not None:
            try:
                self._damping = float(damping)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid damping={}".format(damping))
        if max_force is not None:
            try:
                self._max_force = float(max_force)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid max_force={}".format(max_force))
        if max_error is not None:
            try:
                self._max_error = float(max_error)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid max_error={}".format(max_error))
        if reanchor_distance is not None:
            try:
                self._reanchor_distance = float(reanchor_distance)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid reanchor_distance={}".format(reanchor_distance))
        if deadzone is not None:
            try:
                self._deadzone = float(deadzone)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid deadzone={}".format(deadzone))
        if grab_threshold is not None:
            try:
                self._grab_threshold = float(grab_threshold)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid grab_threshold={}".format(grab_threshold))

        print("[DynamicColaTracker] Tuning: gain={}, damping={}, max_force={}, max_error={}, reanchor_distance={}, deadzone={}, grab_threshold={}".format(
            self._gain, self._damping, self._max_force, self._max_error,
            self._reanchor_distance, self._deadzone, self._grab_threshold))

    def start(self):
        if self._active:
            print("[DynamicColaTracker] Already active")
            return

        self._configure_vr_hand_teleport_only()

        if not self._resolve_scene_objects():
            return

        try:
            if not vrPhysicsService.isActive():
                vrPhysicsService.setActive(True)
                print("[DynamicColaTracker] Physics service activated")
            try:
                vrPhysicsService.setPaused(False)
            except Exception:
                pass
        except Exception as e:
            print("[DynamicColaTracker] ERROR activating physics service: " + str(e))
            return

        if not self._validate_physics_editor_roles():
            return

        try:
            self._cola_physics = vrPhysicsService.getPhysicsObject(self._cola_node, True)
            if not self._cola_physics:
                print("[DynamicColaTracker] ERROR: failed to get Cola physics object")
                return
        except Exception as e:
            print("[DynamicColaTracker] ERROR: getPhysicsObject failed: " + str(e))
            return

        try:
            self._cola_physics.setForceMode(vrPhysicsTypes.ForceMode.VelocityChange)
            self._cola_physics.setForceWorldFrame(True)
            self._cola_physics.setForceEnabled(False)
            self._cola_physics.setGravityEnabled(True)
            self._cola_physics.setLinearDamping(1.2)
            self._cola_physics.setAngularDamping(0.8)
            self._cola_physics.setForce(QVector3D(0.0, 0.0, 0.0))
        except Exception as e:
            print("[DynamicColaTracker] WARNING: force setup failed: " + str(e))

        if not self._timer_connected:
            self._timer.connect(self._update)
            self._timer_connected = True
        self._timer.setActive(1)

        self._connect_collision_signals()

        self._active = True
        print("[DynamicColaTracker] Started: hold Grip/Squeeze on '{}' to grab '{}'".format(
            self._tracker_name, self._cola_node_name))

    def stop(self):
        if not self._active:
            return

        try:
            self._timer.setActive(0)
        except Exception:
            pass

        try:
            if self._cola_physics:
                self._cola_physics.setForce(QVector3D(0.0, 0.0, 0.0))
                self._cola_physics.setForceEnabled(False)
                try:
                    self._cola_physics.setGravityEnabled(True)
                except Exception:
                    pass
        except Exception:
            pass

        self._disconnect_collision_signals()

        self._active = False
        self._tracker = None
        self._cola_node = None
        self._console_node = None
        self._cola_physics = None
        self._grab_active = False
        self._grip_held = False
        self._grab_offset = None
        self._prev_cola_pos = None

        print("[DynamicColaTracker] Stopped")

    def begin_grab(self):
        if not self._active or not self._tracker or not self._cola_node or not self._cola_physics:
            return

        try:
            tx, ty, tz = self._tracker_scene_position()
            cur = getTransformNodeTranslation(self._cola_node, True)
            self._grab_offset = QVector3D(cur.x() - tx, cur.y() - ty, cur.z() - tz)
            self._prev_cola_pos = QVector3D(cur.x(), cur.y(), cur.z())
            self._grab_active = True
            self._cola_physics.setForceEnabled(True)
            self._cola_physics.setForce(QVector3D(0.0, 0.0, 0.0))
            print("[DynamicColaTracker] Grab started")
        except Exception as e:
            print("[DynamicColaTracker] WARNING: begin_grab failed: " + str(e))

    def release_grab(self):
        if not self._active or not self._cola_physics:
            return

        try:
            self._grab_active = False
            self._grab_offset = None
            self._prev_cola_pos = None
            self._cola_physics.setForce(QVector3D(0.0, 0.0, 0.0))
            self._cola_physics.setForceEnabled(False)
            print("[DynamicColaTracker] Grab released (Cola falls naturally)")
        except Exception as e:
            print("[DynamicColaTracker] WARNING: release_grab failed: " + str(e))

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    def status(self):
        print("[DynamicColaTracker] state={} grab={} gripHeld={} input='{}' cola='{}' console='{}' tuning(gain={}, damping={}, max_force={}, max_error={})".format(
            "ACTIVE" if self._active else "stopped",
            self._grab_active,
            self._grip_held,
            self._tracker_name,
            self._cola_node_name,
            self._console_node_name,
            self._gain,
            self._damping,
            self._max_force,
            self._max_error,
        ))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _configure_vr_hand_teleport_only(self):
        """
        VR mode preference:
          - hide controller models
          - keep hand rendering
          - keep Teleport/default interactions available
        """
        try:
            vrImmersiveInteractionService.setDefaultInteractionsActive(1)
        except Exception:
            pass

        try:
            teleport = vrDeviceService.getInteraction("Teleport")
            if teleport:
                try:
                    teleport.setActive(1)
                except Exception:
                    pass
        except Exception:
            pass

        hand_mode = None
        for mode_name in ("Visualization_Hand", "Visualization_HandOnly", "Visualization_OnlyHand"):
            if mode_name in globals():
                hand_mode = globals()[mode_name]
                break

        for dev_name in ("left-controller", "right-controller"):
            try:
                dev = vrDeviceService.getVRDevice(dev_name)
                if not dev:
                    continue
                if hand_mode is not None:
                    try:
                        dev.setVisualizationMode(hand_mode)
                    except Exception:
                        pass
            except Exception:
                pass

        for node_name in ("MRcontrollerLeft", "MRcontrollerRight"):
            try:
                node = findNode(node_name)
                if node:
                    node.setActive(0)
            except Exception:
                pass

        print("[DynamicColaTracker] VR mode set: hand + teleport (controllers hidden)")

    def _resolve_scene_objects(self):
        try:
            self._tracker = vrDeviceService.getVRDevice(self._tracker_name)
            if not self._tracker:
                print("[DynamicColaTracker] ERROR: input device not found: " + self._tracker_name)
                return False
        except Exception as e:
            print("[DynamicColaTracker] ERROR getting input device: " + str(e))
            return False

        try:
            self._cola_node = findNode(self._cola_node_name)
            if not self._cola_node:
                print("[DynamicColaTracker] ERROR: Cola node not found: " + self._cola_node_name)
                return False
        except Exception as e:
            print("[DynamicColaTracker] ERROR finding Cola node: " + str(e))
            return False

        try:
            self._console_node = findNode(self._console_node_name)
            if not self._console_node:
                print("[DynamicColaTracker] ERROR: Console node not found: " + self._console_node_name)
                return False
        except Exception as e:
            print("[DynamicColaTracker] ERROR finding Console node: " + str(e))
            return False

        return True

    def _validate_physics_editor_roles(self):
        """
        Require physics roles to be configured in Physics Editor:
          - Cola must be Dynamic
          - Console1 must be Static
        """
        try:
            dyn_names = {n.getName() for n in vrPhysicsService.getDynamicObjects()}
            static_names = {n.getName() for n in vrPhysicsService.getStaticObjects()}
        except Exception as e:
            print("[DynamicColaTracker] ERROR reading physics objects: " + str(e))
            return False

        cola_name = self._cola_node.getName()
        console_name = self._console_node.getName()

        if cola_name not in dyn_names:
            print("[DynamicColaTracker] ERROR: '{}' is not Dynamic in Physics Editor".format(cola_name))
            print("[DynamicColaTracker] Hint: set '{}' collider type to Dynamic in Physics Editor".format(cola_name))
            return False

        if console_name not in static_names:
            print("[DynamicColaTracker] ERROR: '{}' is not Static in Physics Editor".format(console_name))
            print("[DynamicColaTracker] Hint: set '{}' collider type to Static in Physics Editor".format(console_name))
            return False

        return True

    def _is_grab_pressed(self):
        if not self._tracker:
            return False

        for button in ("grip", "squeeze"):
            try:
                state = self._tracker.getButtonState(button)
                if not state:
                    continue
                if state.isPressed():
                    return True
                try:
                    if state.getPosition().x() >= self._grab_threshold:
                        return True
                except Exception:
                    pass
            except Exception:
                continue
        return False

    def _tracker_scene_position(self):
        """
        Convert tracking-space position (Y-up) to scene-space (Z-up):
          scene_x = -track_x
          scene_y = -track_z
          scene_z =  track_y
        """
        col = self._tracker.getTrackingMatrix().column(3)
        return -col.x(), -col.z(), col.y()

    def _update(self):
        if not self._active:
            return
        if not self._tracker or not self._cola_node or not self._cola_physics:
            return

        pressed = self._is_grab_pressed()
        if pressed and not self._grip_held:
            self._grip_held = True
            self.begin_grab()
        elif not pressed and self._grip_held:
            self._grip_held = False
            self.release_grab()

        if not self._grab_active or self._grab_offset is None:
            return

        try:
            tx, ty, tz = self._tracker_scene_position()
            cur = getTransformNodeTranslation(self._cola_node, True)

            # If tracking origin suddenly jumps, rebind grab offset to current pose.
            err_now_x = (tx + self._grab_offset.x()) - cur.x()
            err_now_y = (ty + self._grab_offset.y()) - cur.y()
            err_now_z = (tz + self._grab_offset.z()) - cur.z()
            if abs(err_now_x) > self._reanchor_distance or abs(err_now_y) > self._reanchor_distance or abs(err_now_z) > self._reanchor_distance:
                self._grab_offset = QVector3D(cur.x() - tx, cur.y() - ty, cur.z() - tz)
                self._prev_cola_pos = QVector3D(cur.x(), cur.y(), cur.z())
                self._cola_physics.setForce(QVector3D(0.0, 0.0, 0.0))
                return

            tx = tx + self._grab_offset.x()
            ty = ty + self._grab_offset.y()
            tz = tz + self._grab_offset.z()

            dx = tx - cur.x()
            dy = ty - cur.y()
            dz = tz - cur.z()

            if abs(dx) < self._deadzone:
                dx = 0.0
            if abs(dy) < self._deadzone:
                dy = 0.0
            if abs(dz) < self._deadzone:
                dz = 0.0

            dx = max(min(dx, self._max_error), -self._max_error)
            dy = max(min(dy, self._max_error), -self._max_error)
            dz = max(min(dz, self._max_error), -self._max_error)

            vx = 0.0
            vy = 0.0
            vz = 0.0
            if self._prev_cola_pos is not None and self._velocity_dt > 0.0:
                vx = (cur.x() - self._prev_cola_pos.x()) / self._velocity_dt
                vy = (cur.y() - self._prev_cola_pos.y()) / self._velocity_dt
                vz = (cur.z() - self._prev_cola_pos.z()) / self._velocity_dt

            fx = dx * self._gain - vx * self._damping
            fy = dy * self._gain - vy * self._damping
            fz = dz * self._gain - vz * self._damping

            fx = max(min(fx, self._max_force), -self._max_force)
            fy = max(min(fy, self._max_force), -self._max_force)
            fz = max(min(fz, self._max_force), -self._max_force)

            self._cola_physics.setForce(QVector3D(fx, fy, fz))
            self._prev_cola_pos = QVector3D(cur.x(), cur.y(), cur.z())
        except Exception as e:
            print("[DynamicColaTracker] WARNING update failed: " + str(e))

    def _connect_collision_signals(self):
        self._disconnect_collision_signals()

        cola_name = self._cola_node.getName() if self._cola_node else self._cola_node_name
        console_name = self._console_node.getName() if self._console_node else self._console_node_name

        def _is_target_pair(info):
            try:
                n1 = info.getCollidingRootNode1().getName()
                n2 = info.getCollidingRootNode2().getName()
                return (n1 == cola_name and n2 == console_name) or (n1 == console_name and n2 == cola_name)
            except Exception:
                return False

        def on_collision_started(info):
            if not _is_target_pair(info):
                return
            pts = info.getContactPoints()
            if pts:
                p = pts[0]
                print("[DynamicColaTracker] COLLISION START Cola<->Console1 at ({:.3f}, {:.3f}, {:.3f}), contacts={}".format(
                    p.x(), p.y(), p.z(), len(pts)))
            else:
                print("[DynamicColaTracker] COLLISION START Cola<->Console1")

        def on_collision_continues(info):
            if not _is_target_pair(info):
                return
            pts = info.getContactPoints()
            if pts:
                p = pts[0]
                print("[DynamicColaTracker] COLLISION CONTINUE Cola<->Console1 at ({:.3f}, {:.3f}, {:.3f})".format(
                    p.x(), p.y(), p.z()))

        def on_collision_stopped(info):
            if not _is_target_pair(info):
                return
            print("[DynamicColaTracker] COLLISION STOP Cola<->Console1")

        try:
            self._sig_start = vrPhysicsService.collisionStarted.connect(on_collision_started)
            self._sig_cont = vrPhysicsService.collisionContinues.connect(on_collision_continues)
            self._sig_stop = vrPhysicsService.collisionStopped.connect(on_collision_stopped)
            print("[DynamicColaTracker] Collision callbacks connected")
        except Exception as e:
            print("[DynamicColaTracker] WARNING connecting collision callbacks: " + str(e))

    def _disconnect_collision_signals(self):
        try:
            if self._sig_start is not None:
                vrPhysicsService.collisionStarted.disconnect(self._sig_start)
                self._sig_start = None
            if self._sig_cont is not None:
                vrPhysicsService.collisionContinues.disconnect(self._sig_cont)
                self._sig_cont = None
            if self._sig_stop is not None:
                vrPhysicsService.collisionStopped.disconnect(self._sig_stop)
                self._sig_stop = None
        except Exception:
            self._sig_start = None
            self._sig_cont = None
            self._sig_stop = None


# ======================================================================
# Singleton & module API
# ======================================================================
_prev_cola_tracker = globals().get('_cola_tracker')
if _prev_cola_tracker is not None:
    try:
        _prev_cola_tracker.stop()
    except Exception:
        pass

_cola_tracker = DynamicColaTracker()


def setup_cola(tracker_name="right-controller", cola_node_name="Cola", maintain_offset=False,
               follow_mode="dynamic", console_node_name="Console1"):
    """
    Configure dynamic cola tracking.

    Compatibility notes:
      - maintain_offset is ignored in dynamic force mode.
      - follow_mode must be "dynamic" for physical collision response.
    """
    if maintain_offset:
        print("[DynamicColaTracker] WARNING: maintain_offset is ignored in dynamic mode")
    if str(follow_mode).strip().lower() != "dynamic":
        print("[DynamicColaTracker] WARNING: follow_mode='{}' requested, forced to 'dynamic'".format(follow_mode))

    _cola_tracker.setup(tracker_name, cola_node_name, console_node_name)


def set_cola_follow_mode(follow_mode):
    """Kept for compatibility. Dynamic mode is mandatory for physical collision response."""
    if str(follow_mode).strip().lower() != "dynamic":
        print("[DynamicColaTracker] WARNING: only dynamic mode is supported in this refactored script")
    else:
        print("[DynamicColaTracker] mode=dynamic")


def set_cola_dynamic_tuning(gain=None, damping=None, max_step=None, max_force=None,
                            max_error=None, reanchor_distance=None, deadzone=None,
                            grab_threshold=None):
    """
    Set follower tuning.

    Compatibility:
      - old max_step maps to max_error.
    """
    if max_error is None and max_step is not None:
        max_error = max_step
    _cola_tracker.set_tuning(gain=gain, damping=damping, max_force=max_force,
                             max_error=max_error, reanchor_distance=reanchor_distance,
                             deadzone=deadzone, grab_threshold=grab_threshold)


def set_grab_input_device(device_name="right-controller"):
    """Set grab input device, e.g. right-controller or left-controller."""
    _cola_tracker._tracker_name = str(device_name)
    print("[DynamicColaTracker] Grab input device set to '{}'".format(_cola_tracker._tracker_name))


def start_cola():
    _cola_tracker.start()


def stop_cola():
    _cola_tracker.stop()


def toggle_cola():
    _cola_tracker.toggle()


def grab_cola():
    """Start physics grab manually."""
    _cola_tracker.begin_grab()


def release_cola():
    """Release physics grab manually."""
    _cola_tracker.release_grab()


def physics_status():
    _cola_tracker.status()


def vr_hand_teleport_only():
    """Apply VR visualization policy: hide controllers, keep hand + teleport."""
    _cola_tracker._configure_vr_hand_teleport_only()


# Compatibility stubs for previous API surface.
def setup_transform(*args, **kwargs):
    print("[DynamicColaTracker] setup_transform removed in refactored script")


def start_transform():
    print("[DynamicColaTracker] start_transform removed in refactored script")


def stop_transform():
    print("[DynamicColaTracker] stop_transform removed in refactored script")


def toggle_transform():
    print("[DynamicColaTracker] toggle_transform removed in refactored script")


print("[DynamicColaTracker] Initialized.")
print("[DynamicColaTracker] Use setup_cola('right-controller', 'Cola', False, 'dynamic', 'Console1') then start_cola().")

# Auto-run on script load.
try:
    setup_cola("right-controller", "Cola", False, "dynamic", "Console1")
    set_cola_dynamic_tuning(gain=22.0, damping=5.0, max_force=1.6,
                            max_error=0.12, reanchor_distance=0.35,
                            deadzone=0.004, grab_threshold=0.5)
    start_cola()
    print("[DynamicColaTracker] Auto setup+start executed (hold Grip/Squeeze to grab Cola).")
except Exception as e:
    print("[DynamicColaTracker] Auto start failed: " + str(e))
