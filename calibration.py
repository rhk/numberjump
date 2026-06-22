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

    _font_path = (
        pygame.font.match_font("dejavusans")
        or pygame.font.match_font("freesans")
        or pygame.font.match_font("unifont")
    )
    def _f(size):
        return pygame.font.Font(_font_path, size) if _font_path else pygame.font.SysFont(None, size)

    font_large = _f(38)
    font_med   = _f(26)
    font_small = _f(22)

    BG_TOP     = (12, 10, 35)
    BG_BOT     = (28, 18, 58)
    ACCENT     = (74, 158, 255)
    SUCCESS_C  = (74, 255, 160)

    def draw_gradient():
        w, h = screen.get_size()
        for y in range(h):
            t = y / h
            r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
            g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
            b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
            pygame.draw.line(screen, (r, g, b), (0, y), (w, y))

    corners = []      # stored in original 640×480 camera coords
    done = False

    # Display feed scaled down to fit: title(50) + feed(420) + panel(88) + gaps = ~580 < 600
    DISP_W, DISP_H = 560, 420
    feed_x = (WINDOW_W - DISP_W) // 2   # 120
    feed_y = 52

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
                    fx = mx - feed_x
                    fy = my - feed_y
                    if 0 <= fx < DISP_W and 0 <= fy < DISP_H:
                        # Scale back to original camera resolution for accurate transform
                        fx_orig = fx * FEED_W / DISP_W
                        fy_orig = fy * FEED_H / DISP_H
                        corners.append([fx_orig, fy_orig])
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                if len(corners) == 4:
                    done = True

        frame = None
        if cam_type is not None:
            frame = _grab_frame(cam_type, cam)

        draw_gradient()

        # ── Title ─────────────────────────────────────────────────────
        title_surf = font_large.render(
            strings.get("calibration_title", "Calibration"), True, (255, 255, 255)
        )
        screen.blit(title_surf, (WINDOW_W // 2 - title_surf.get_width() // 2, 10))

        # ── Camera feed with border ────────────────────────────────────
        border_col = SUCCESS_C if len(corners) == 4 else ACCENT
        border_rect = pygame.Rect(feed_x - 3, feed_y - 3, DISP_W + 6, DISP_H + 6)
        pygame.draw.rect(screen, border_col, border_rect, border_radius=10)

        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_small = cv2.resize(frame_rgb, (DISP_W, DISP_H))
            feed_surf = pygame.surfarray.make_surface(frame_small.swapaxes(0, 1))
            screen.blit(feed_surf, (feed_x, feed_y))
        else:
            pygame.draw.rect(screen, (25, 20, 50), (feed_x, feed_y, DISP_W, DISP_H),
                             border_radius=8)
            no_cam = font_med.render("No camera", True, (200, 80, 80))
            screen.blit(no_cam, (feed_x + DISP_W // 2 - no_cam.get_width() // 2,
                                  feed_y + DISP_H // 2 - no_cam.get_height() // 2))

        # ── Corner markers: map from camera coords back to display coords ─
        drawn = [
            (int(c[0] * DISP_W / FEED_W) + feed_x,
             int(c[1] * DISP_H / FEED_H) + feed_y)
            for c in corners
        ]
        if len(drawn) > 1:
            # Dashed line: draw short segments
            pts = drawn + ([drawn[0]] if len(drawn) == 4 else [])
            for k in range(len(pts) - 1):
                x1, y1 = pts[k]
                x2, y2 = pts[k + 1]
                segs = 10
                for s in range(segs):
                    if s % 2 == 0:
                        tx1 = x1 + (x2 - x1) * s / segs
                        ty1 = y1 + (y2 - y1) * s / segs
                        tx2 = x1 + (x2 - x1) * (s + 1) / segs
                        ty2 = y1 + (y2 - y1) * (s + 1) / segs
                        pygame.draw.line(screen, ACCENT, (int(tx1), int(ty1)),
                                         (int(tx2), int(ty2)), 2)
        for i, pt in enumerate(drawn):
            # Outer white ring then filled circle
            pygame.draw.circle(screen, (255, 255, 255), pt, 11)
            pygame.draw.circle(screen, (255, 120, 40), pt, 8)
            lbl = font_small.render(str(i + 1), True, (255, 255, 0))
            screen.blit(lbl, (pt[0] + 13, pt[1] - 10))

        # ── Instructions panel (below feed) ───────────────────────────
        panel_y = feed_y + DISP_H + 8
        panel_rect = pygame.Rect(feed_x, panel_y, DISP_W, 80)
        pygame.draw.rect(screen, (20, 16, 50), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (50, 40, 90), panel_rect, 1, border_radius=10)

        if len(corners) < 4:
            instr = strings.get("calibration_instructions", "Click 4 corners of the mat")
            instr_surf = font_med.render(instr, True, (180, 180, 220))
            screen.blit(instr_surf, (panel_rect.x + 16, panel_y + 14))
        else:
            done_surf = font_med.render(
                strings.get("calibration_done", "Done! Press ENTER"), True, SUCCESS_C
            )
            screen.blit(done_surf, (panel_rect.centerx - done_surf.get_width() // 2, panel_y + 14))

        # ── Progress pips ─────────────────────────────────────────────
        pip_r   = 8
        pip_gap = 24
        total_pip_w = 4 * (pip_r * 2) + 3 * (pip_gap - pip_r * 2)
        pip_start_x = panel_rect.centerx - total_pip_w // 2 + pip_r
        pip_y = panel_y + 58
        for k in range(4):
            cx = pip_start_x + k * pip_gap
            if k < len(corners):
                pygame.draw.circle(screen, SUCCESS_C, (cx, pip_y), pip_r)
            else:
                pygame.draw.circle(screen, (30, 24, 60), (cx, pip_y), pip_r)
                pygame.draw.circle(screen, (80, 70, 130), (cx, pip_y), pip_r, 2)

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
