"""Game loop and state machine for numberjump."""
import logging
import random
import time
from enum import Enum, auto
from typing import Optional

import cv2
import numpy as np
import pygame

from audio import AudioPlayer
from tracker import Tracker

logger = logging.getLogger(__name__)

WINDOW_W, WINDOW_H = 800, 600
FEED_W, FEED_H = 400, 300

TIER_CONFIG = {
    "tiny": {"zones": [1, 2, 3], "timeout": 9},
    "junior": {"zones": list(range(1, 10)), "timeout": 6},
    "challenge": {"zones": list(range(1, 10)), "timeout": 3},
}

CONSECUTIVE_FRAMES_NEEDED = 3


class State(Enum):
    WAITING = auto()
    PROMPTING = auto()
    DETECTING = auto()
    SUCCESS = auto()
    FAIL = auto()


def _open_camera():
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.configure(cam.create_preview_configuration(main={"size": (640, 480), "format": "BGR888"}))
        cam.start()
        return ("picamera2", cam)
    except Exception:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
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


class Game:
    def __init__(self, lang: str, tier: str, strings: dict, transform_matrix: Optional[np.ndarray]):
        self.lang = lang
        self.tier = tier
        self.strings = strings
        self.transform_matrix = transform_matrix
        self.config = TIER_CONFIG[tier]

        self.audio = AudioPlayer(lang)
        self.tracker = Tracker()

        self.state = State.WAITING
        self.score = 0
        self.streak = 0
        self.target_zone: Optional[int] = None
        self.timer_start: float = 0.0
        self.consecutive_correct: int = 0
        self.state_entered: float = time.time()
        self.last_zone: Optional[int] = None
        self.last_centroid = None
        self.last_debug_frame = None

        # Fonts
        self.font_huge = pygame.font.SysFont(None, 72)
        self.font_large = pygame.font.SysFont(None, 48)
        self.font_med = pygame.font.SysFont(None, 36)
        self.font_small = pygame.font.SysFont(None, 28)

        # Camera
        self.cam_type, self.cam = _open_camera()
        if self.cam_type is None:
            logger.warning("No camera available")

    def cleanup(self):
        if self.cam_type is not None:
            _release_camera(self.cam_type, self.cam)

    def _s(self, key: str) -> str:
        return self.strings.get(key, key)

    def _pick_target(self) -> int:
        zones = self.config["zones"]
        if self.target_zone and len(zones) > 1:
            choices = [z for z in zones if z != self.target_zone]
        else:
            choices = zones
        return random.choice(choices)

    def _enter_state(self, state: State):
        self.state = state
        self.state_entered = time.time()

    def _time_in_state(self) -> float:
        return time.time() - self.state_entered

    def run(self, screen: pygame.Surface):
        clock = pygame.time.Clock()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_RETURN:
                        if self.state == State.WAITING:
                            self._start_round()

            # Grab camera frame
            frame = None
            if self.cam_type is not None:
                frame = _grab_frame(self.cam_type, self.cam)

            # Run tracker
            zone, centroid = None, None
            debug_frame = None
            if frame is not None:
                zone, centroid = self.tracker.find_zone(frame, self.transform_matrix)
                debug_frame = self.tracker.get_debug_frame(frame, self.transform_matrix, zone, centroid)
                self.last_zone = zone
                self.last_centroid = centroid
                self.last_debug_frame = debug_frame

            # State logic
            self._update_state(zone)

            # Draw
            self._draw(screen, debug_frame, zone)
            pygame.display.flip()
            clock.tick(30)

        self.cleanup()

    def _start_round(self):
        self.target_zone = self._pick_target()
        self.consecutive_correct = 0
        self.timer_start = time.time()
        self.audio.play_number(self.target_zone)
        self._enter_state(State.DETECTING)

    def _update_state(self, zone: Optional[int]):
        if self.state == State.WAITING:
            pass

        elif self.state == State.DETECTING:
            elapsed = time.time() - self.timer_start
            timeout = self.config["timeout"]

            if elapsed >= timeout:
                self.audio.play("timeout")
                self.streak = 0
                self._enter_state(State.FAIL)
                return

            if zone == self.target_zone:
                self.consecutive_correct += 1
                if self.consecutive_correct >= CONSECUTIVE_FRAMES_NEEDED:
                    self.score += 1
                    self.streak += 1
                    self.audio.play("success")
                    if self.streak > 0 and self.streak % 3 == 0:
                        self.audio.play("streak")
                    self._enter_state(State.SUCCESS)
            else:
                self.consecutive_correct = 0

        elif self.state == State.SUCCESS:
            if self._time_in_state() >= 1.5:
                self._start_round()

        elif self.state == State.FAIL:
            if self._time_in_state() >= 1.5:
                # Re-prompt same target after timeout, new target after wrong
                same = True  # timeout case — keep target
                self.consecutive_correct = 0
                self.timer_start = time.time()
                self.audio.play_number(self.target_zone)
                self._enter_state(State.DETECTING)

    def _draw(self, screen: pygame.Surface, debug_frame, zone: Optional[int]):
        screen.fill((20, 20, 40))

        # --- TOP: prompt text ---
        if self.state == State.WAITING:
            prompt_text = f"{self._s('press_enter')} — {self._s('waiting')}"
            color = (200, 200, 255)
        elif self.state in (State.DETECTING,):
            prompt_text = f"{self._s('prompt_prefix')} {self.target_zone}!"
            color = (255, 255, 100)
        elif self.state == State.SUCCESS:
            prompt_text = self._s("correct")
            color = (100, 255, 100)
        elif self.state == State.FAIL:
            prompt_text = self._s("timeout")
            color = (255, 100, 100)
        else:
            prompt_text = ""
            color = (255, 255, 255)

        prompt_surf = self.font_huge.render(prompt_text, True, color)
        screen.blit(prompt_surf, (WINDOW_W // 2 - prompt_surf.get_width() // 2, 20))

        # --- MIDDLE: camera feed ---
        feed_x = (WINDOW_W - FEED_W) // 2
        feed_y = 120
        if debug_frame is not None:
            feed_rgb = cv2.cvtColor(debug_frame, cv2.COLOR_BGR2RGB)
            feed_small = cv2.resize(feed_rgb, (FEED_W, FEED_H))
            feed_surf = pygame.surfarray.make_surface(feed_small.swapaxes(0, 1))
            screen.blit(feed_surf, (feed_x, feed_y))
        else:
            pygame.draw.rect(screen, (40, 40, 60), (feed_x, feed_y, FEED_W, FEED_H))
            no_cam_surf = self.font_med.render("No camera", True, (180, 80, 80))
            screen.blit(no_cam_surf, (feed_x + FEED_W // 2 - no_cam_surf.get_width() // 2, feed_y + FEED_H // 2))

        # Timer bar
        if self.state == State.DETECTING:
            elapsed = time.time() - self.timer_start
            timeout = self.config["timeout"]
            ratio = max(0.0, 1.0 - elapsed / timeout)
            bar_w = FEED_W
            bar_h = 12
            bar_x = feed_x
            bar_y = feed_y + FEED_H + 4
            pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
            bar_color = (100, 255, 100) if ratio > 0.5 else (255, 200, 0) if ratio > 0.25 else (255, 60, 60)
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, int(bar_w * ratio), bar_h))

        # --- BOTTOM: score + streak ---
        bottom_y = WINDOW_H - 80
        score_surf = self.font_large.render(f"{self._s('score')}: {self.score}", True, (200, 200, 255))
        streak_surf = self.font_large.render(f"{self._s('streak')}: {self.streak}", True, (255, 220, 100))
        screen.blit(score_surf, (80, bottom_y))
        screen.blit(streak_surf, (WINDOW_W - 80 - streak_surf.get_width(), bottom_y))

        # Detected zone indicator
        if zone is not None:
            zone_surf = self.font_med.render(f"{self._s('detecting')} {zone}", True, (180, 255, 180))
        else:
            zone_surf = self.font_med.render(self._s("detecting"), True, (140, 140, 140))
        screen.blit(zone_surf, (WINDOW_W // 2 - zone_surf.get_width() // 2, bottom_y + 40))
