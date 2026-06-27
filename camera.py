"""Shared camera access for calibration and gameplay.

Both the colour-training screen and the game open the camera independently, so
the capture settings MUST come from one place — otherwise the HSV colour learnt
during training would be sampled under different camera settings than the game
sees, and detection would drift. Keep all camera tuning here.

On a USB webcam (the `cv2` path) we lock the auto-adjust features that make
HSV-blob tracking unreliable: auto white balance (shifts hue), autofocus (hunts
and blurs), and — best-effort — auto exposure. We also cap the capture buffer to
one frame to avoid latency from stale buffered frames. The picamera2 (Raspberry
Pi CSI) path is left untouched.
"""
import logging

import cv2

logger = logging.getLogger(__name__)

# Capture resolution — matches the perspective-warp target and the Pi 3 budget.
FEED_W, FEED_H = 640, 480

# V4L2 "manual exposure" flag for CAP_PROP_AUTO_EXPOSURE. The values are
# backend-specific; 0.25 selects manual mode on the common Linux/V4L2 backend
# (0.75 would be auto). Setting this best-effort and verifying the frame still
# has signal lets us lock exposure where supported and fall back where not.
_V4L2_EXPOSURE_MANUAL = 0.25
_V4L2_EXPOSURE_AUTO = 0.75


def _try_set(cap, prop, value, name):
    """Best-effort property set; UVC drivers silently reject unsupported props."""
    try:
        cap.set(prop, value)
    except Exception:
        logger.debug("Camera property %s not settable", name)


def _frame_has_signal(cap) -> bool:
    """Grab a frame and check it isn't (near-)black — used to validate exposure lock."""
    ret, frame = cap.read()
    if not ret or frame is None:
        return False
    return float(frame.mean()) > 8.0


def _tune_webcam(cap) -> None:
    """Apply USB-webcam tuning. Each step is best-effort and never fatal."""
    _try_set(cap, cv2.CAP_PROP_FRAME_WIDTH, FEED_W, "width")
    _try_set(cap, cv2.CAP_PROP_FRAME_HEIGHT, FEED_H, "height")
    # Low latency: keep only the freshest frame, not a backlog.
    _try_set(cap, cv2.CAP_PROP_BUFFERSIZE, 1, "buffersize")
    # Request a usable frame rate (README's top-priority factor).
    _try_set(cap, cv2.CAP_PROP_FPS, 30, "fps")
    # Stop focus hunting that blurs the sock and shifts its colour.
    _try_set(cap, cv2.CAP_PROP_AUTOFOCUS, 0, "autofocus")
    # Lock white balance — the single biggest HSV-hue stability win for webcams.
    _try_set(cap, cv2.CAP_PROP_AUTO_WB, 0, "auto_wb")

    # Exposure lock (best-effort). Forcing a blind exposure value risks a black
    # frame on an unknown webcam, so we switch to manual mode but leave the
    # driver's current exposure value in place, then verify the frame still has
    # signal. If it goes dark or the property isn't honoured, revert to auto.
    try:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, _V4L2_EXPOSURE_MANUAL)
        # Warm up a couple of frames so the mode change takes effect.
        for _ in range(2):
            cap.read()
        if _frame_has_signal(cap):
            logger.info("Camera: exposure locked (manual)")
        else:
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, _V4L2_EXPOSURE_AUTO)
            logger.info("Camera: exposure lock produced a dark frame — reverted to auto")
    except Exception:
        logger.info("Camera: exposure lock unsupported — using auto exposure")


def open_camera():
    """Open the camera. Try picamera2 (Pi CSI) first, else USB webcam via cv2.

    Returns (cam_type, cam) where cam_type is "picamera2", "cv2", or None.
    """
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.configure(cam.create_preview_configuration(
            main={"size": (FEED_W, FEED_H), "format": "BGR888"}
        ))
        cam.start()
        logger.info("Camera: opened via picamera2")
        return "picamera2", cam
    except Exception:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            _tune_webcam(cap)
            logger.info("Camera: opened via cv2.VideoCapture(0)")
            return "cv2", cap
        logger.warning("Camera: no camera available")
        return None, None


def grab_frame(cam_type, cam):
    if cam_type == "picamera2":
        return cam.capture_array()
    elif cam_type == "cv2":
        ret, frame = cam.read()
        return frame if ret else None
    return None


def release_camera(cam_type, cam):
    if cam_type == "picamera2":
        cam.stop()
    elif cam_type == "cv2":
        cam.release()
