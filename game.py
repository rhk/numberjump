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

# Modes available per tier
TIER_CONFIG = {
    "tiny": {
        "zones": [1, 3, 7, 9],
        "timeout": 9,
        "modes": ["jump"],
    },
    "junior": {
        "zones": list(range(1, 10)),
        "timeout": 6,
        "modes": ["jump", "math_add", "sequence"],
    },
    "challenge": {
        "zones": list(range(1, 10)),
        "timeout": 3,
        "modes": ["jump", "math_add", "math_sub", "sequence"],
    },
}

CONSECUTIVE_FRAMES_NEEDED = 3

TINY_SYMBOLS = {1: "★", 3: "●", 7: "◆", 9: "♥"}
TINY_CV2_LABELS = {1: "*", 3: "O", 7: "<>", 9: "<3"}


class State(Enum):
    WAITING = auto()
    DETECTING = auto()      # single-target (jump / math answer)
    SEQ_DETECTING = auto()  # sequence: hitting targets one by one
    SUCCESS = auto()
    FAIL = auto()


class Round:
    """Holds everything about the current round."""
    mode: str = "jump"
    target: int = 1             # for jump/math: the answer zone
    display_text: str = ""      # shown on screen
    seq_targets: list = None    # for sequence mode
    seq_index: int = 0          # which target in sequence we're on


def _open_camera():
    try:
        from picamera2 import Picamera2
        cam = Picamera2()
        cam.configure(cam.create_preview_configuration(
            main={"size": (640, 480), "format": "BGR888"}
        ))
        cam.start()
        return "picamera2", cam
    except Exception:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            return "cv2", cap
        return None, None


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
    def __init__(
        self,
        lang: str,
        tier: str,
        strings: dict,
        transform_matrix: Optional[np.ndarray],
    ):
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
        self.round = Round()
        self.timer_start: float = 0.0
        self.consecutive_correct: int = 0
        self.state_entered: float = time.time()
        self.last_zone: Optional[int] = None
        self.last_debug_frame = None

        self.font_huge = pygame.font.SysFont(None, 72)
        self.font_large = pygame.font.SysFont(None, 48)
        self.font_med = pygame.font.SysFont(None, 36)
        self.font_small = pygame.font.SysFont(None, 28)
        self.font_symbol = pygame.font.SysFont(None, 200)

        self.cam_type, self.cam = _open_camera()
        if self.cam_type is None:
            logger.warning("No camera available")

    def cleanup(self):
        if self.cam_type is not None:
            _release_camera(self.cam_type, self.cam)

    def _s(self, key: str) -> str:
        return self.strings.get(key, key)

    # ------------------------------------------------------------------ #
    # Round generation                                                     #
    # ------------------------------------------------------------------ #

    def _pick_zone(self, exclude: int = None) -> int:
        zones = self.config["zones"]
        choices = [z for z in zones if z != exclude] if exclude and len(zones) > 1 else zones
        return random.choice(choices)

    def _new_round(self) -> Round:
        r = Round()
        r.mode = random.choice(self.config["modes"])
        zones = self.config["zones"]

        if r.mode == "jump":
            r.target = self._pick_zone(self.round.target if self.round else None)
            if self.tier == "tiny":
                r.display_text = TINY_SYMBOLS.get(r.target, str(r.target))
            else:
                r.display_text = f"{self._s('prompt_prefix')} {r.target}"

        elif r.mode in ("math_add", "math_sub"):
            # Pick answer first, then build equation
            r.target = self._pick_zone()
            answer = r.target
            if r.mode == "math_add":
                a = random.randint(1, answer - 1) if answer > 1 else 1
                b = answer - a
                r.display_text = f"{a} + {b} = ?"
                self.audio.prompt_math(a, "+", b)
            else:  # math_sub
                # a - b = answer  →  a = answer + b, b in 1..4
                b = random.randint(1, min(4, 9 - answer))
                a = answer + b
                r.display_text = f"{a} - {b} = ?"
                self.audio.prompt_math(a, "-", b)
            return r  # audio already fired

        elif r.mode == "sequence":
            count = 3
            pool = list(zones)
            random.shuffle(pool)
            r.seq_targets = pool[:count]
            r.seq_index = 0
            r.target = r.seq_targets[0]
            nums = " → ".join(str(z) for z in r.seq_targets)
            r.display_text = f"{self._s('seq_prompt')}: {nums}"
            self.audio.prompt_sequence(r.seq_targets)
            return r

        # Fire audio for jump mode (math_add/sub fire their own above)
        self.audio.prompt_jump(r.target)
        return r

    # ------------------------------------------------------------------ #
    # State machine                                                        #
    # ------------------------------------------------------------------ #

    def _enter_state(self, state: State):
        self.state = state
        self.state_entered = time.time()

    def _time_in_state(self) -> float:
        return time.time() - self.state_entered

    def _start_round(self):
        self.round = self._new_round()
        self.consecutive_correct = 0
        self.timer_start = time.time()
        if self.round.mode == "sequence":
            self._enter_state(State.SEQ_DETECTING)
        else:
            self._enter_state(State.DETECTING)

    def _update_state(self, zone: Optional[int]):
        timeout = self.config["timeout"]

        if self.state == State.WAITING:
            pass

        elif self.state == State.DETECTING:
            elapsed = time.time() - self.timer_start
            if elapsed >= timeout:
                self.audio.play("timeout")
                self.streak = 0
                self._enter_state(State.FAIL)
                return

            if zone == self.round.target:
                self.consecutive_correct += 1
                if self.consecutive_correct >= CONSECUTIVE_FRAMES_NEEDED:
                    self._on_success()
            else:
                self.consecutive_correct = 0

        elif self.state == State.SEQ_DETECTING:
            elapsed = time.time() - self.timer_start
            if elapsed >= timeout * len(self.round.seq_targets):
                self.audio.play("timeout")
                self.streak = 0
                self._enter_state(State.FAIL)
                return

            if zone == self.round.target:
                self.consecutive_correct += 1
                if self.consecutive_correct >= CONSECUTIVE_FRAMES_NEEDED:
                    self.consecutive_correct = 0
                    self.round.seq_index += 1
                    if self.round.seq_index >= len(self.round.seq_targets):
                        self._on_success()
                    else:
                        self.round.target = self.round.seq_targets[self.round.seq_index]
                        self.audio.play_number(self.round.target)
            else:
                self.consecutive_correct = 0

        elif self.state == State.SUCCESS:
            if self._time_in_state() >= 1.2:
                self._start_round()

        elif self.state == State.FAIL:
            if self._time_in_state() >= 1.5:
                self._start_round()

    def _on_success(self):
        self.score += 1
        self.streak += 1
        self.audio.play("success")
        if self.streak % 3 == 0:
            self.audio.play("streak")
        self._enter_state(State.SUCCESS)

    # ------------------------------------------------------------------ #
    # Main loop                                                            #
    # ------------------------------------------------------------------ #

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
                    elif event.key == pygame.K_r:
                        if self.state == State.WAITING:
                            from calibration import run_calibration
                            _release_camera(self.cam_type, self.cam)
                            calib = run_calibration(screen, self.strings)
                            self.transform_matrix = np.array(calib["transform"], dtype=np.float64)
                            self.cam_type, self.cam = _open_camera()

            frame = _grab_frame(self.cam_type, self.cam) if self.cam_type else None
            zone = None
            debug_frame = None
            if frame is not None:
                zone, centroid = self.tracker.find_zone(frame, self.transform_matrix)
                cv2_labels = TINY_CV2_LABELS if self.tier == "tiny" else None
                debug_frame = self.tracker.get_debug_frame(
                    frame, self.transform_matrix, zone, centroid, zone_labels=cv2_labels
                )
                self.last_zone = zone
                self.last_debug_frame = debug_frame

            self._update_state(zone)
            self._draw(screen, debug_frame, zone)
            pygame.display.flip()
            clock.tick(30)

        self.cleanup()

    # ------------------------------------------------------------------ #
    # Drawing                                                              #
    # ------------------------------------------------------------------ #

    def _draw(self, screen: pygame.Surface, debug_frame, zone: Optional[int]):
        screen.fill((20, 20, 40))

        # Prompt text
        if self.state == State.WAITING:
            prompt_text = f"{self._s('press_enter')}  —  {self._s('waiting')}"
            color = (200, 200, 255)
        elif self.state in (State.DETECTING, State.SEQ_DETECTING) and self.tier == "tiny":
            prompt_text = ""
            color = (255, 255, 100)
        elif self.state in (State.DETECTING, State.SEQ_DETECTING):
            if self.round.mode == "sequence":
                done = self.round.seq_index
                total = len(self.round.seq_targets)
                remaining = " → ".join(
                    str(z) for z in self.round.seq_targets[done:]
                )
                prompt_text = f"{self._s('seq_prompt')}: {remaining}"
            else:
                prompt_text = self.round.display_text
            color = (255, 255, 100)
        elif self.state == State.SUCCESS:
            prompt_text = self._s("correct")
            color = (100, 255, 100)
        elif self.state == State.FAIL:
            prompt_text = self._s("timeout")
            color = (255, 100, 100)
        else:
            prompt_text, color = "", (255, 255, 255)

        prompt_surf = self.font_huge.render(prompt_text, True, color)
        screen.blit(prompt_surf, (WINDOW_W // 2 - prompt_surf.get_width() // 2, 20))

        if self.state == State.WAITING:
            hint = self.font_small.render("R = recalibrate", True, (120, 120, 160))
            screen.blit(hint, (WINDOW_W // 2 - hint.get_width() // 2, 80))

        if self.tier == "tiny" and self.state == State.DETECTING and self.round:
            sym = TINY_SYMBOLS.get(self.round.target, "?")
            sym_surf = self.font_symbol.render(sym, True, (255, 255, 100))
            screen.blit(sym_surf, (WINDOW_W // 2 - sym_surf.get_width() // 2,
                                   WINDOW_H // 2 - sym_surf.get_height() // 2))

        # Camera feed
        feed_x = (WINDOW_W - FEED_W) // 2
        feed_y = 120
        if debug_frame is not None:
            feed_rgb = cv2.cvtColor(debug_frame, cv2.COLOR_BGR2RGB)
            feed_small = cv2.resize(feed_rgb, (FEED_W, FEED_H))
            feed_surf = pygame.surfarray.make_surface(feed_small.swapaxes(0, 1))
            screen.blit(feed_surf, (feed_x, feed_y))
        else:
            pygame.draw.rect(screen, (40, 40, 60), (feed_x, feed_y, FEED_W, FEED_H))
            no_cam = self.font_med.render("No camera", True, (180, 80, 80))
            screen.blit(no_cam, (feed_x + FEED_W // 2 - no_cam.get_width() // 2,
                                 feed_y + FEED_H // 2))

        # Sequence progress dots
        if self.state == State.SEQ_DETECTING and self.round.seq_targets:
            dot_y = feed_y + FEED_H + 18
            spacing = 30
            total = len(self.round.seq_targets)
            start_x = WINDOW_W // 2 - (total - 1) * spacing // 2
            for i, z in enumerate(self.round.seq_targets):
                cx = start_x + i * spacing
                if i < self.round.seq_index:
                    col = (100, 255, 100)   # done
                elif i == self.round.seq_index:
                    col = (255, 255, 0)     # current
                else:
                    col = (80, 80, 80)      # upcoming
                pygame.draw.circle(screen, col, (cx, dot_y), 10)
                lbl = self.font_small.render(str(z), True, (255, 255, 255))
                screen.blit(lbl, (cx - lbl.get_width() // 2, dot_y + 14))

        # Timer bar
        if self.state in (State.DETECTING, State.SEQ_DETECTING):
            elapsed = time.time() - self.timer_start
            max_time = self.config["timeout"] * (
                len(self.round.seq_targets) if self.round.mode == "sequence" else 1
            )
            ratio = max(0.0, 1.0 - elapsed / max_time)
            bar_y = feed_y + FEED_H + (44 if self.state == State.SEQ_DETECTING else 4)
            pygame.draw.rect(screen, (60, 60, 60), (feed_x, bar_y, FEED_W, 12))
            bar_col = (100, 255, 100) if ratio > 0.5 else (255, 200, 0) if ratio > 0.25 else (255, 60, 60)
            pygame.draw.rect(screen, bar_col, (feed_x, bar_y, int(FEED_W * ratio), 12))

        # Score / streak
        bottom_y = WINDOW_H - 80
        score_surf = self.font_large.render(f"{self._s('score')}: {self.score}", True, (200, 200, 255))
        streak_surf = self.font_large.render(f"{self._s('streak')}: {self.streak}", True, (255, 220, 100))
        screen.blit(score_surf, (80, bottom_y))
        screen.blit(streak_surf, (WINDOW_W - 80 - streak_surf.get_width(), bottom_y))

        # Detected zone
        if zone is not None:
            zone_label = TINY_SYMBOLS.get(zone, str(zone)) if self.tier == "tiny" else str(zone)
            zt = self.font_med.render(f"{self._s('detecting')} {zone_label}", True, (180, 255, 180))
        else:
            zt = self.font_med.render(self._s("detecting"), True, (140, 140, 140))
        screen.blit(zt, (WINDOW_W // 2 - zt.get_width() // 2, bottom_y + 40))
