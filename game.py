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
from calibration import run_calibration, run_color_training
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
        hsv_lower: Optional[tuple] = None,
        hsv_upper: Optional[tuple] = None,
    ):
        self.lang = lang
        self.tier = tier
        self.strings = strings
        self.transform_matrix = transform_matrix
        self.config = TIER_CONFIG[tier]

        self.audio = AudioPlayer(lang)
        tracker_kwargs = {}
        if hsv_lower is not None:
            tracker_kwargs["hsv_lower"] = hsv_lower
        if hsv_upper is not None:
            tracker_kwargs["hsv_upper"] = hsv_upper
        self.tracker = Tracker(**tracker_kwargs)

        self.state = State.WAITING
        self.score = 0
        self.streak = 0
        self.round = Round()
        self.timer_start: float = 0.0
        self.consecutive_correct: int = 0
        self.state_entered: float = time.time()
        self.last_zone: Optional[int] = None
        self.last_debug_frame = None

        # Resolve a Unicode-capable font path (DejaVu Sans covers ★ ● ◆ ♥)
        _font_path = (
            pygame.font.match_font("dejavusans")
            or pygame.font.match_font("freesans")
            or pygame.font.match_font("unifont")
        )
        self._font_path = _font_path
        def _f(size):
            return pygame.font.Font(_font_path, size) if _font_path else pygame.font.SysFont(None, size)
        self.font_huge   = _f(56)
        self.font_large  = _f(38)
        self.font_med    = _f(32)
        self.font_small  = _f(24)
        self.font_symbol = _f(200)

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
        if self.tier == "tiny":
            # TODO: record sym_star/sym_ball/sym_diamond/sym_heart clips per language
            self.audio.play_number(r.target)
        else:
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
        # Start the countdown only once the prompt audio has finished playing,
        # so the timer doesn't run while the question is still being read out.
        self.timer_start = max(time.time(), self.audio.prompt_finish_time)
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
                            _release_camera(self.cam_type, self.cam)
                            try:
                                calib = run_calibration(screen, self.strings)
                                self.transform_matrix = np.array(calib["transform"], dtype=np.float64)
                            except Exception:
                                pass  # user cancelled or calibration failed — keep old transform
                            try:
                                color = run_color_training(screen, self.strings)
                                self.tracker.hsv_lower = np.array(color["hsv_lower"], dtype=np.uint8)
                                self.tracker.hsv_upper = np.array(color["hsv_upper"], dtype=np.uint8)
                            except Exception:
                                pass  # user cancelled or training failed — keep old colour
                            self.cam_type, self.cam = _open_camera()

            frame = _grab_frame(self.cam_type, self.cam) if self.cam_type else None
            zone = None
            debug_frame = None
            if frame is not None:
                zone, centroid = self.tracker.find_zone(frame, self.transform_matrix)
                if self.tier == "tiny" and zone not in TINY_SYMBOLS:
                    zone, centroid = None, None
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

    # ------------------------------------------------------------------ #
    # Drawing helpers                                                      #
    # ------------------------------------------------------------------ #

    _BG_TOP  = (12, 10, 35)
    _BG_BOT  = (28, 18, 58)

    def _draw_gradient_bg(self, surface: pygame.Surface):
        w, h = surface.get_size()
        for y in range(h):
            t = y / h
            r = int(self._BG_TOP[0] + (self._BG_BOT[0] - self._BG_TOP[0]) * t)
            g = int(self._BG_TOP[1] + (self._BG_BOT[1] - self._BG_TOP[1]) * t)
            b = int(self._BG_TOP[2] + (self._BG_BOT[2] - self._BG_TOP[2]) * t)
            pygame.draw.line(surface, (r, g, b), (0, y), (w, y))

    @staticmethod
    def _draw_pill(surface, rect, fill, border, radius=None):
        if radius is None:
            radius = rect.h // 2
        pygame.draw.rect(surface, fill,   rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, 2, border_radius=radius)

    def _render_text_fitted(self, text: str, color: tuple, max_size: int, max_width: int) -> pygame.Surface:
        if self._font_path:
            surf = pygame.font.Font(self._font_path, max_size).render(text, True, color)
        else:
            surf = pygame.font.SysFont(None, max_size).render(text, True, color)
        if surf.get_width() > max_width:
            scale = max_width / surf.get_width()
            surf = pygame.transform.smoothscale(surf, (max_width, int(surf.get_height() * scale)))
        return surf

    @staticmethod
    def _draw_card(surface, rect, fill=(25, 20, 55), border=(60, 50, 110), radius=14):
        pygame.draw.rect(surface, fill,   rect, border_radius=radius)
        pygame.draw.rect(surface, border, rect, 2, border_radius=radius)

    # ------------------------------------------------------------------ #
    # Main draw                                                            #
    # ------------------------------------------------------------------ #

    def _draw(self, screen: pygame.Surface, debug_frame, zone: Optional[int]):
        self._draw_gradient_bg(screen)

        # ── State colours ─────────────────────────────────────────────
        if self.state == State.WAITING:
            prompt_text = self._s('press_enter')
            prompt_color = (200, 200, 255)
            feed_border  = (60, 50, 110)
        elif self.state in (State.DETECTING, State.SEQ_DETECTING) and self.tier == "tiny":
            prompt_text  = ""
            prompt_color = (255, 255, 100)
            feed_border  = (255, 255, 100)
        elif self.state in (State.DETECTING, State.SEQ_DETECTING):
            if self.round.mode == "sequence":
                done = self.round.seq_index
                remaining = " → ".join(
                    str(z) for z in self.round.seq_targets[done:]
                )
                prompt_text = f"{self._s('seq_prompt')}: {remaining}"
            else:
                prompt_text = self.round.display_text
            prompt_color = (255, 230, 80)
            feed_border  = (255, 230, 80)
        elif self.state == State.SUCCESS:
            prompt_text  = self._s("correct")
            prompt_color = (74, 255, 160)
            feed_border  = (74, 255, 160)
        elif self.state == State.FAIL:
            prompt_text  = self._s("timeout")
            prompt_color = (255, 90, 90)
            feed_border  = (255, 90, 90)
        else:
            prompt_text, prompt_color, feed_border = "", (255, 255, 255), (60, 50, 110)

        # ── Prompt card ───────────────────────────────────────────────
        card_pad_x, card_pad_y = 24, 10
        card_bottom = 10  # will be updated below
        if prompt_text:
            prompt_surf = self._render_text_fitted(prompt_text, prompt_color, 56, WINDOW_W - 48)
            card_w = prompt_surf.get_width()  + card_pad_x * 2
            card_h = prompt_surf.get_height() + card_pad_y * 2
            card_rect = pygame.Rect(WINDOW_W // 2 - card_w // 2, 8, card_w, card_h)
            self._draw_card(screen, card_rect)
            screen.blit(prompt_surf, (card_rect.x + card_pad_x, card_rect.y + card_pad_y))
            card_bottom = card_rect.bottom

        hint_bottom = card_bottom
        if self.state == State.WAITING:
            hint = self.font_small.render("R = recalibrate", True, (90, 90, 130))
            hint_y = card_bottom + 4
            screen.blit(hint, (WINDOW_W // 2 - hint.get_width() // 2, hint_y))
            hint_bottom = hint_y + hint.get_height()

        # ── Camera feed ───────────────────────────────────────────────
        feed_x = (WINDOW_W - FEED_W) // 2
        feed_y = hint_bottom + 6
        if self.tier != "tiny":
            feed_rect = pygame.Rect(feed_x - 3, feed_y - 3, FEED_W + 6, FEED_H + 6)
            pygame.draw.rect(screen, feed_border, feed_rect, border_radius=10)
            if debug_frame is not None:
                feed_rgb   = cv2.cvtColor(debug_frame, cv2.COLOR_BGR2RGB)
                feed_small = cv2.resize(feed_rgb, (FEED_W, FEED_H))
                feed_surf  = pygame.surfarray.make_surface(feed_small.swapaxes(0, 1))
                # Clip to rounded rect
                clip_surf = pygame.Surface((FEED_W, FEED_H), pygame.SRCALPHA)
                clip_surf.blit(feed_surf, (0, 0))
                mask_surf = pygame.Surface((FEED_W, FEED_H), pygame.SRCALPHA)
                mask_surf.fill((0, 0, 0, 0))
                pygame.draw.rect(mask_surf, (255, 255, 255, 255),
                                 mask_surf.get_rect(), border_radius=8)
                clip_surf.blit(mask_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                screen.blit(clip_surf, (feed_x, feed_y))
            else:
                pygame.draw.rect(screen, (30, 25, 55), (feed_x, feed_y, FEED_W, FEED_H),
                                 border_radius=8)
                no_cam = self.font_med.render(self._s("no_camera") if "no_camera" in self.strings else "No camera",
                                              True, (180, 80, 80))
                screen.blit(no_cam, (feed_x + FEED_W // 2 - no_cam.get_width() // 2,
                                     feed_y + FEED_H // 2 - no_cam.get_height() // 2))

        # ── Large symbol (tiny mode) ───────────────────────────────────
        if self.tier == "tiny" and self.state in (State.DETECTING, State.SEQ_DETECTING) and self.round:
            sym = TINY_SYMBOLS.get(self.round.target, "?")
            # Subtle pulsing halo
            pulse = pygame.time.get_ticks() % 1000 > 500
            halo_r = 140 if pulse else 120
            pygame.draw.circle(screen, (50, 40, 100),
                               (WINDOW_W // 2, WINDOW_H // 2), halo_r)
            sym_surf = self.font_symbol.render(sym, True, (255, 230, 80))
            screen.blit(sym_surf, (WINDOW_W // 2 - sym_surf.get_width() // 2,
                                   WINDOW_H // 2 - sym_surf.get_height() // 2))

        # ── Sequence progress dots ─────────────────────────────────────
        if self.state == State.SEQ_DETECTING and self.round.seq_targets:
            dot_y    = feed_y + FEED_H + 26
            dot_r    = 14
            spacing  = dot_r * 3 + 8
            total    = len(self.round.seq_targets)
            start_x  = WINDOW_W // 2 - (total - 1) * spacing // 2
            for i, z in enumerate(self.round.seq_targets):
                cx = start_x + i * spacing
                if i < self.round.seq_index:
                    col, outline = (74, 255, 160), (74, 255, 160)
                    pygame.draw.circle(screen, col, (cx, dot_y), dot_r)
                elif i == self.round.seq_index:
                    col, outline = (255, 230, 80), (255, 230, 80)
                    pygame.draw.circle(screen, col, (cx, dot_y), dot_r)
                else:
                    pygame.draw.circle(screen, (20, 15, 50),  (cx, dot_y), dot_r)
                    pygame.draw.circle(screen, (80, 70, 130), (cx, dot_y), dot_r, 2)
                lbl = self.font_small.render(str(z), True, (255, 255, 255))
                screen.blit(lbl, (cx - lbl.get_width() // 2, dot_y + dot_r + 4))

        # ── Timer bar (pill) ──────────────────────────────────────────
        if self.state in (State.DETECTING, State.SEQ_DETECTING):
            elapsed  = time.time() - self.timer_start
            max_time = self.config["timeout"] * (
                len(self.round.seq_targets) if self.round.mode == "sequence" else 1
            )
            ratio    = max(0.0, min(1.0, 1.0 - elapsed / max_time))
            bar_y    = feed_y + FEED_H + (76 if self.state == State.SEQ_DETECTING else 8)
            bar_h    = 16
            bar_rect = pygame.Rect(feed_x, bar_y, FEED_W, bar_h)
            # Track
            pygame.draw.rect(screen, (35, 28, 65), bar_rect, border_radius=bar_h // 2)
            # Fill
            if ratio > 0:
                bar_col = (74, 255, 160) if ratio > 0.5 else (255, 200, 50) if ratio > 0.25 else (255, 80, 80)
                fill_rect = pygame.Rect(feed_x, bar_y, int(FEED_W * ratio), bar_h)
                pygame.draw.rect(screen, bar_col, fill_rect, border_radius=bar_h // 2)

        # ── Score / streak badges ─────────────────────────────────────
        bottom_y  = WINDOW_H - 72
        pad_x, pad_y = 16, 8

        score_text  = f"{self._s('score')}: {self.score}"
        streak_text = f"{self._s('streak')}: {self.streak}"
        score_surf  = self.font_large.render(score_text,  True, (200, 200, 255))
        streak_surf = self.font_large.render(streak_text, True, (255, 210, 80))

        for surf, x_anchor, align in [
            (score_surf,  60,              "left"),
            (streak_surf, WINDOW_W - 60,  "right"),
        ]:
            sw = surf.get_width() + pad_x * 2
            sh = surf.get_height() + pad_y * 2
            bx = x_anchor if align == "left" else x_anchor - sw
            badge = pygame.Rect(bx, bottom_y, sw, sh)
            self._draw_pill(screen, badge, (25, 20, 55), (60, 50, 110))
            screen.blit(surf, (bx + pad_x, bottom_y + pad_y))

        # ── Detected zone label (only shown when a zone is active) ────
        if zone is not None:
            zone_label = TINY_SYMBOLS.get(zone, str(zone)) if self.tier == "tiny" else str(zone)
            zt = self.font_small.render(f"{self._s('detecting')} {zone_label}", True, (74, 255, 160))
            screen.blit(zt, (WINDOW_W // 2 - zt.get_width() // 2, WINDOW_H - 28))
