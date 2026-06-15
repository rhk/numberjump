"""Startup calibration: click 4 corners of mat to compute perspective transform."""
import json
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pygame

logger = logging.getLogger(__name__)

CALIBRATION_FILE = Path(__file__).parent / "calibration.json"
WINDOW_W, WINDOW_H = 800, 600
FEED_W, FEED_H = 640, 480


def _open_camera():
    """Try picamera2 first, fall back to cv2.VideoCapture."""
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.configure(cam.create_preview_configuration(main={"size": (FEED_W, FEED_H), "format": "BGR888"}))
        cam.start()
        return ("picamera2", cam)
    except Exception:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, FEED_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FEED_H)
            return ("cv2", cap)
        return (None, None)


def _grab_frame(cam_type, cam):
    if cam_type == "picamera2":
        return cam.capture_array()
    elif cam_type == "cv2":
        ret, frame = cam.read()
        return frame if ret else None
    return None


def _release_camera(cam_type, cam):
    if cam_type == "picamera2":
        cam.stop()
    elif cam_type == "cv2":
        cam.release()


def load_calibration() -> Optional[dict]:
    """Load calibration.json if it exists."""
    if CALIBRATION_FILE.exists():
        with CALIBRATION_FILE.open() as f:
            data = json.load(f)
        return data
    return None


def save_calibration(corners: list, transform: list) -> None:
    data = {"corners": corners, "transform": transform}
    with CALIBRATION_FILE.open("w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Calibration saved to {CALIBRATION_FILE}")


def run_calibration(screen: pygame.Surface, strings: dict) -> dict:
    """
    Show live camera feed. User clicks 4 corners (TL, TR, BR, BL).
    Returns calibration dict with 'corners' and 'transform'.
    """
    cam_type, cam = _open_camera()

    font_large = pygame.font.SysFont(None, 40)
    font_small = pygame.font.SysFont(None, 28)

    corners = []
    done = False

    # Feed surface offset inside window
    feed_x = (WINDOW_W - FEED_W) // 2
    feed_y = 80

    clock = pygame.time.Clock()

    while not done:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                raise SystemExit
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if len(corners) < 4:
                    mx, my = event.pos
                    # Convert to feed-local coords
                    fx = mx - feed_x
                    fy = my - feed_y
                    if 0 <= fx < FEED_W and 0 <= fy < FEED_H:
                        corners.append([fx, fy])
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if len(corners) == 4:
                    done = True

        # Grab frame
        frame = None
        if cam_type is not None:
            frame = _grab_frame(cam_type, cam)

        screen.fill((30, 30, 30))

        # Title
        title_surf = font_large.render(strings.get("calibration_title", "Calibration"), True, (255, 255, 255))
        screen.blit(title_surf, (WINDOW_W // 2 - title_surf.get_width() // 2, 20))

        # Camera feed
        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            feed_surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
            screen.blit(feed_surf, (feed_x, feed_y))
        else:
            pygame.draw.rect(screen, (50, 50, 50), (feed_x, feed_y, FEED_W, FEED_H))
            no_cam = font_small.render("No camera", True, (200, 100, 100))
            screen.blit(no_cam, (feed_x + 10, feed_y + 10))

        # Draw clicked corners and connecting lines
        drawn = [(c[0] + feed_x, c[1] + feed_y) for c in corners]
        for i, pt in enumerate(drawn):
            pygame.draw.circle(screen, (255, 100, 0), pt, 8)
            label = font_small.render(str(i + 1), True, (255, 255, 0))
            screen.blit(label, (pt[0] + 10, pt[1] - 10))
        if len(drawn) > 1:
            pygame.draw.lines(screen, (255, 100, 0), len(drawn) == 4, drawn, 2)

        # Instructions
        instructions = strings.get("calibration_instructions", "Click 4 corners")
        for i, line in enumerate(instructions.split("\n")):
            surf = font_small.render(line, True, (200, 200, 200))
            screen.blit(surf, (20, feed_y + FEED_H + 10 + i * 28))

        if len(corners) == 4:
            done_surf = font_small.render(strings.get("calibration_done", "Done! Press ENTER"), True, (100, 255, 100))
            screen.blit(done_surf, (20, feed_y + FEED_H + 70))

        # Corner count
        count_surf = font_small.render(f"Corners: {len(corners)}/4", True, (180, 180, 180))
        screen.blit(count_surf, (WINDOW_W - 160, 20))

        pygame.display.flip()
        clock.tick(30)

    if cam_type is not None:
        _release_camera(cam_type, cam)

    # Compute perspective transform
    src = np.float32(corners)
    dst = np.float32([[0, 0], [640, 0], [640, 480], [0, 480]])
    M = cv2.getPerspectiveTransform(src, dst)

    calib = {
        "corners": corners,
        "transform": M.tolist(),
    }
    save_calibration(corners, M.tolist())
    return calib
