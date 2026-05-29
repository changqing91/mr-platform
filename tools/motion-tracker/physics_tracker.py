# ======================================================================
# VRED Kinematic Tracker (VRED 2027 API)
#
# Goal:
#   tracker-2 (locator) kinematically drives Cola
#   Cola collides with Console1 with visual highlight feedback
#
# Assumption:
#   Cola and Console1 are already configured in VRED Physics Editor.
# ======================================================================


class KinematicColaTracker:
    """
    Kinematically move Cola to follow tracker-2.
    No controller input is used.
    """

    def __init__(self):
        self._tracker_name = "tracker-2"
        self._cola_node_name = "Cola"
        self._console_node_name = "Console1"
        self._maintain_offset = True  # preserve initial offset between tracker and Cola

        self._tracker = None
        self._cola_node = None
        self._console_node = None

        self._active = False

        # ParentConstraint that drives Cola → tracker
        self._constraint = None

        # Kept for API compatibility (not used for tracking)
        self._max_step = 40.0

        # Collision highlight state
        self._highlight_active = False
        self._cola_scale_origin = None
        self._console_scale_origin = None
        self._highlight_scale_factor = 1.08

        self._sig_start = None
        self._sig_stop = None
        self._sig_cont = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def setup(self, tracker_name="tracker-2", cola_node_name="Cola",
              maintain_offset=False, console_node_name="Console1"):
        if self._active:
            self.stop()

        self._tracker_name = tracker_name
        self._cola_node_name = cola_node_name
        self._console_node_name = console_node_name
        self._maintain_offset = bool(maintain_offset)

        print("[KinematicColaTracker] Configured: {} -> '{}' (console='{}', maintain_offset={})".format(
            self._tracker_name, self._cola_node_name, self._console_node_name, self._maintain_offset))

    def set_tuning(self, max_step=None, highlight_scale_factor=None):
        if max_step is not None:
            try:
                self._max_step = float(max_step)
            except Exception:
                print("[KinematicColaTracker] WARNING: invalid max_step={}".format(max_step))

        if highlight_scale_factor is not None:
            try:
                self._highlight_scale_factor = float(highlight_scale_factor)
            except Exception:
                print("[KinematicColaTracker] WARNING: invalid highlight_scale_factor={}".format(highlight_scale_factor))

        print("[KinematicColaTracker] Tuning: max_step={}, highlight_scale_factor={}".format(
            self._max_step, self._highlight_scale_factor))

    def start(self):
        if self._active:
            print("[KinematicColaTracker] Already active")
            return

        if not self._resolve_scene_objects():
            return

        # Activate physics service for collision detection.
        try:
            if not vrPhysicsService.isActive():
                vrPhysicsService.setActive(True)
                print("[KinematicColaTracker] Physics service activated")
            try:
                vrPhysicsService.setPaused(False)
            except Exception:
                pass
        except Exception as e:
            print("[KinematicColaTracker] WARNING: physics service issue: " + str(e))
            # Continue even if physics fails — constraint tracking still works.

        # Create a ParentConstraint: Cola follows tracker node.
        # maintain_offset=True preserves the initial position difference so Cola
        # does not snap to the tracker's exact origin.
        try:
            tracker_node = self._tracker.getNode()
            self._constraint = vrConstraintService.createParentConstraint(
                [tracker_node], self._cola_node, self._maintain_offset)
            if not self._constraint:
                print("[KinematicColaTracker] ERROR: createParentConstraint returned None")
                return
            print("[KinematicColaTracker] ParentConstraint created (maintain_offset={})".format(
                self._maintain_offset))
        except Exception as e:
            print("[KinematicColaTracker] ERROR creating ParentConstraint: " + str(e))
            return

        self._connect_collision_signals()

        self._active = True
        print("[KinematicColaTracker] Started: '{}' follows '{}' via ParentConstraint".format(
            self._cola_node_name, self._tracker_name))

    def stop(self):
        if not self._active:
            return

        # Remove the ParentConstraint.
        if self._constraint is not None:
            try:
                vrConstraintService.removeConstraint(self._constraint)
            except Exception:
                pass
            self._constraint = None

        self._set_collision_highlight(False)
        self._disconnect_collision_signals()

        self._active = False
        self._tracker = None
        self._cola_node = None
        self._console_node = None

        print("[KinematicColaTracker] Stopped")

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    def status(self):
        print("[KinematicColaTracker] state={} tracker='{}' cola='{}' console='{}' tuning(max_step={}, highlight_scale_factor={})".format(
            "ACTIVE" if self._active else "stopped",
            self._tracker_name,
            self._cola_node_name,
            self._console_node_name,
            self._max_step,
            self._highlight_scale_factor,
        ))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _resolve_scene_objects(self):
        try:
            self._tracker = vrDeviceService.getVRDevice(self._tracker_name)
            if not self._tracker:
                print("[KinematicColaTracker] ERROR: tracker not found: " + self._tracker_name)
                return False
        except Exception as e:
            print("[KinematicColaTracker] ERROR getting tracker: " + str(e))
            return False

        try:
            self._cola_node = findNode(self._cola_node_name)
            if not self._cola_node:
                print("[KinematicColaTracker] ERROR: Cola node not found: " + self._cola_node_name)
                return False
        except Exception as e:
            print("[KinematicColaTracker] ERROR finding Cola node: " + str(e))
            return False

        try:
            self._console_node = findNode(self._console_node_name)
            if not self._console_node:
                print("[KinematicColaTracker] ERROR: Console node not found: " + self._console_node_name)
                return False
        except Exception as e:
            print("[KinematicColaTracker] ERROR finding Console node: " + str(e))
            return False

        return True

    def _try_get_scale_xyz(self, node):
        try:
            s = node.getScale()
            return (s.x(), s.y(), s.z())
        except Exception:
            return None

    def _try_set_scale_xyz(self, node, sx, sy, sz):
        try:
            node.setScale(sx, sy, sz)
            return True
        except Exception:
            return False

    def _set_collision_highlight(self, enable):
        if not self._cola_node or not self._console_node:
            return

        if enable and self._highlight_active:
            return
        if (not enable) and (not self._highlight_active):
            return

        if enable:
            if self._cola_scale_origin is None:
                self._cola_scale_origin = self._try_get_scale_xyz(self._cola_node)
            if self._console_scale_origin is None:
                self._console_scale_origin = self._try_get_scale_xyz(self._console_node)

            if self._cola_scale_origin is not None:
                self._try_set_scale_xyz(self._cola_node,
                                        self._cola_scale_origin[0] * self._highlight_scale_factor,
                                        self._cola_scale_origin[1] * self._highlight_scale_factor,
                                        self._cola_scale_origin[2] * self._highlight_scale_factor)
            if self._console_scale_origin is not None:
                self._try_set_scale_xyz(self._console_node,
                                        self._console_scale_origin[0] * self._highlight_scale_factor,
                                        self._console_scale_origin[1] * self._highlight_scale_factor,
                                        self._console_scale_origin[2] * self._highlight_scale_factor)

            self._highlight_active = True
            print("[KinematicColaTracker] Collision highlighting ON")
        else:
            if self._cola_scale_origin is not None:
                self._try_set_scale_xyz(self._cola_node,
                                        self._cola_scale_origin[0],
                                        self._cola_scale_origin[1],
                                        self._cola_scale_origin[2])
            if self._console_scale_origin is not None:
                self._try_set_scale_xyz(self._console_node,
                                        self._console_scale_origin[0],
                                        self._console_scale_origin[1],
                                        self._console_scale_origin[2])

            self._highlight_active = False
            print("[KinematicColaTracker] Collision highlighting OFF")

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
            self._set_collision_highlight(True)
            pts = info.getContactPoints()
            if pts:
                p = pts[0]
                print("[KinematicColaTracker] COLLISION START Cola<->Console1 at ({:.3f}, {:.3f}, {:.3f}), contacts={}".format(
                    p.x(), p.y(), p.z(), len(pts)))
            else:
                print("[KinematicColaTracker] COLLISION START Cola<->Console1")

        def on_collision_continues(info):
            if not _is_target_pair(info):
                return
            self._set_collision_highlight(True)

        def on_collision_stopped(info):
            if not _is_target_pair(info):
                return
            self._set_collision_highlight(False)
            print("[KinematicColaTracker] COLLISION STOP Cola<->Console1")

        try:
            self._sig_start = vrPhysicsService.collisionStarted.connect(on_collision_started)
            self._sig_cont = vrPhysicsService.collisionContinues.connect(on_collision_continues)
            self._sig_stop = vrPhysicsService.collisionStopped.connect(on_collision_stopped)
            print("[KinematicColaTracker] Collision callbacks connected")
        except Exception as e:
            print("[KinematicColaTracker] WARNING connecting collision callbacks: " + str(e))

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

_cola_tracker = KinematicColaTracker()


def setup_cola(tracker_name="tracker-2", cola_node_name="Cola", maintain_offset=False,
               follow_mode="kinematic", console_node_name="Console1"):
    """
    Configure kinematic cola tracking.

    Compatibility notes:
      - follow_mode is forced to kinematic.
    """
    if str(follow_mode).strip().lower() != "kinematic":
        print("[KinematicColaTracker] WARNING: follow_mode='{}' requested, forced to 'kinematic'".format(follow_mode))

    _cola_tracker.setup(tracker_name, cola_node_name, maintain_offset, console_node_name)


def set_cola_follow_mode(follow_mode):
    """Kept for compatibility. Kinematic mode is mandatory in this script."""
    if str(follow_mode).strip().lower() != "kinematic":
        print("[KinematicColaTracker] WARNING: only kinematic mode is supported in this script")
    else:
        print("[KinematicColaTracker] mode=kinematic")


def set_cola_kinematic_tuning(max_step=None, highlight_scale_factor=None):
    _cola_tracker.set_tuning(max_step=max_step, highlight_scale_factor=highlight_scale_factor)


def set_cola_dynamic_tuning(gain=None, damping=None, max_step=None, max_force=None,
                            max_error=None, reanchor_distance=None, deadzone=None,
                            grab_threshold=None):
    """Compatibility shim: map old max_step onto kinematic tuning."""
    _ = (gain, damping, max_force, max_error, reanchor_distance, deadzone, grab_threshold)
    _cola_tracker.set_tuning(max_step=max_step)


def start_cola():
    _cola_tracker.start()


def stop_cola():
    _cola_tracker.stop()


def toggle_cola():
    _cola_tracker.toggle()


def physics_status():
    _cola_tracker.status()


# Compatibility stubs for removed API surface.
def set_grab_input_device(*args, **kwargs):
    _ = (args, kwargs)
    print("[KinematicColaTracker] set_grab_input_device removed (no controller input)")


def grab_cola():
    print("[KinematicColaTracker] grab_cola removed (no controller input)")


def release_cola():
    print("[KinematicColaTracker] release_cola removed (no controller input)")


def vr_hand_teleport_only():
    print("[KinematicColaTracker] vr_hand_teleport_only removed (no controller flow)")


def setup_transform(*args, **kwargs):
    print("[KinematicColaTracker] setup_transform removed in this script")


def start_transform():
    print("[KinematicColaTracker] start_transform removed in this script")


def stop_transform():
    print("[KinematicColaTracker] stop_transform removed in this script")


def toggle_transform():
    print("[KinematicColaTracker] toggle_transform removed in this script")


print("[KinematicColaTracker] Initialized.")
print("[KinematicColaTracker] Use setup_cola('tracker-2', 'Cola', True, 'kinematic', 'Console1') then start_cola().")

# Auto-run on script load.
try:
    setup_cola("tracker-2", "Cola", True, "kinematic", "Console1")
    set_cola_kinematic_tuning(highlight_scale_factor=1.08)
    start_cola()
    print("[KinematicColaTracker] Auto setup+start executed.")
except Exception as e:
    print("[KinematicColaTracker] Auto start failed: " + str(e))
