# ======================================================================
# VRED Physics Tracker (Refactored for VRED 2027 API)
#
# Goal:
#   tracker-2 (VR tracker) controls Cola (dynamic physics object)
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
    Drive a dynamic physics object (Cola) toward tracker-2 using force control.
    Collision with Console1 is reported via physics callbacks.
    """

    def __init__(self):
        self._tracker_name = "tracker-2"
        self._cola_node_name = "Cola"
        self._console_node_name = "Console1"

        self._tracker = None
        self._cola_node = None
        self._console_node = None
        self._cola_physics = None

        self._active = False

        self._timer = vrTimer()
        self._timer_connected = False

        # Force follower tuning
        self._gain = 80.0
        self._max_force = 6.0
        self._max_error = 0.20

        self._sig_start = None
        self._sig_stop = None
        self._sig_cont = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def setup(self, tracker_name="tracker-2", cola_node_name="Cola", console_node_name="Console1"):
        if self._active:
            self.stop()

        self._tracker_name = tracker_name
        self._cola_node_name = cola_node_name
        self._console_node_name = console_node_name

        print("[DynamicColaTracker] Configured: {} -> '{}' (target static: '{}')".format(
            self._tracker_name, self._cola_node_name, self._console_node_name))

    def set_tuning(self, gain=None, max_force=None, max_error=None):
        if gain is not None:
            try:
                self._gain = float(gain)
            except Exception:
                print("[DynamicColaTracker] WARNING: invalid gain={}".format(gain))
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

        print("[DynamicColaTracker] Tuning: gain={}, max_force={}, max_error={}".format(
            self._gain, self._max_force, self._max_error))

    def start(self):
        if self._active:
            print("[DynamicColaTracker] Already active")
            return

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
            # VelocityChange: more responsive tracker following and mass-independent.
            self._cola_physics.setForceMode(vrPhysicsTypes.ForceMode.VelocityChange)
            self._cola_physics.setForceWorldFrame(True)
            self._cola_physics.setForceEnabled(True)
            self._cola_physics.setForce(QVector3D(0.0, 0.0, 0.0))
        except Exception as e:
            print("[DynamicColaTracker] WARNING: force setup failed: " + str(e))

        if not self._timer_connected:
            self._timer.connect(self._update)
            self._timer_connected = True
        self._timer.setActive(1)

        self._connect_collision_signals()

        self._active = True
        print("[DynamicColaTracker] Started: tracker '{}' drives dynamic '{}'".format(
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
        except Exception:
            pass

        self._disconnect_collision_signals()

        self._active = False
        self._tracker = None
        self._cola_node = None
        self._console_node = None
        self._cola_physics = None

        print("[DynamicColaTracker] Stopped")

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    def status(self):
        print("[DynamicColaTracker] state={} tracker='{}' cola='{}' console='{}' tuning(gain={}, max_force={}, max_error={})".format(
            "ACTIVE" if self._active else "stopped",
            self._tracker_name,
            self._cola_node_name,
            self._console_node_name,
            self._gain,
            self._max_force,
            self._max_error,
        ))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _resolve_scene_objects(self):
        try:
            self._tracker = vrDeviceService.getVRDevice(self._tracker_name)
            if not self._tracker:
                print("[DynamicColaTracker] ERROR: tracker not found: " + self._tracker_name)
                return False
        except Exception as e:
            print("[DynamicColaTracker] ERROR getting tracker: " + str(e))
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

    def _tracker_scene_position(self):
        """
        Convert tracker tracking-space position (Y-up) to scene-space (Z-up):
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

        try:
            tx, ty, tz = self._tracker_scene_position()
            cur = getTransformNodeTranslation(self._cola_node, True)

            dx = tx - cur.x()
            dy = ty - cur.y()
            dz = tz - cur.z()

            # Limit per-axis error to avoid unstable force spikes.
            dx = max(min(dx, self._max_error), -self._max_error)
            dy = max(min(dy, self._max_error), -self._max_error)
            dz = max(min(dz, self._max_error), -self._max_error)

            fx = dx * self._gain
            fy = dy * self._gain
            fz = dz * self._gain

            # Cap per-axis force for numerical stability.
            fx = max(min(fx, self._max_force), -self._max_force)
            fy = max(min(fy, self._max_force), -self._max_force)
            fz = max(min(fz, self._max_force), -self._max_force)

            self._cola_physics.setForce(QVector3D(fx, fy, fz))
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
if globals().get('_cola_tracker') is not None:
    try:
        _cola_tracker.stop()
    except Exception:
        pass

_cola_tracker = DynamicColaTracker()


def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False,
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


def set_cola_dynamic_tuning(gain=None, max_step=None, max_force=None, max_error=None):
    """
    Set follower tuning.

    Compatibility:
      - old max_step maps to max_error.
    """
    if max_error is None and max_step is not None:
        max_error = max_step
    _cola_tracker.set_tuning(gain=gain, max_force=max_force, max_error=max_error)


def start_cola():
    _cola_tracker.start()


def stop_cola():
    _cola_tracker.stop()


def toggle_cola():
    _cola_tracker.toggle()


def physics_status():
    _cola_tracker.status()


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
print("[DynamicColaTracker] Use setup_cola('tracker-2', 'Cola', False, 'dynamic', 'Console1') then start_cola().")
