"""Entry point for numberjump."""
import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pygame

import lang as lang_module
from calibration import CALIBRATION_FILE, load_calibration, run_calibration, run_color_training
from game import Game

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

WINDOW_W, WINDOW_H = 800, 600

# ── Palette ────────────────────────────────────────────────────────────────
BG_TOP    = (12, 10, 35)
BG_BOT    = (28, 18, 58)
WHITE     = (255, 255, 255)
GREY_MED  = (160, 160, 200)
GREY_DIM  = (90, 90, 130)
GOLD      = (255, 210, 80)
BLUE_ACC  = (74, 158, 255)
GREEN_ACC = (74, 255, 160)
ORANGE_ACC = (255, 120, 60)


def _resolve_font(size: int) -> pygame.font.Font:
    path = (
        pygame.font.match_font("dejavusans")
        or pygame.font.match_font("freesans")
        or pygame.font.match_font("unifont")
    )
    return pygame.font.Font(path, size) if path else pygame.font.SysFont(None, size)


def draw_gradient_bg(surface: pygame.Surface):
    w, h = surface.get_size()
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (w, y))


def draw_card(surface: pygame.Surface, rect: pygame.Rect, color=(30, 24, 60), border=(60, 50, 110), radius=18):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, 2, border_radius=radius)


def draw_button(surface: pygame.Surface, rect: pygame.Rect, hovered: bool,
                accent: tuple, radius=16):
    if hovered:
        bg = accent
        border = WHITE
    else:
        bg = (30, 24, 60)
        border = accent
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    pygame.draw.rect(surface, border, rect, 2, border_radius=radius)
    if hovered:
        # subtle glow: draw a slightly larger rect with low-alpha colour first
        glow = pygame.Surface((rect.w + 12, rect.h + 12), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*accent, 60), glow.get_rect(), border_radius=radius + 4)
        surface.blit(glow, (rect.x - 6, rect.y - 6))


def show_language_selection(screen: pygame.Surface, default_strings: dict) -> str:
    """Show language selection screen, return 'fi' or 'en'."""
    font_logo  = _resolve_font(80)
    font_sub   = _resolve_font(28)
    font_btn   = _resolve_font(48)
    font_hint  = _resolve_font(22)

    btn_w, btn_h = 260, 110
    gap = 40
    total_w = btn_w * 2 + gap
    left_x = WINDOW_W // 2 - total_w // 2
    btn_y  = 320
    btn_fi = pygame.Rect(left_x, btn_y, btn_w, btn_h)
    btn_en = pygame.Rect(left_x + btn_w + gap, btn_y, btn_w, btn_h)

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if btn_fi.collidepoint(event.pos):
                    return "fi"
                if btn_en.collidepoint(event.pos):
                    return "en"

        draw_gradient_bg(screen)

        # Logo
        logo = font_logo.render("NumberJump", True, GOLD)
        screen.blit(logo, (WINDOW_W // 2 - logo.get_width() // 2, 100))

        # Subtitle
        sub_text = default_strings.get("select_language", "Select language")
        sub = font_sub.render(sub_text, True, GREY_MED)
        screen.blit(sub, (WINDOW_W // 2 - sub.get_width() // 2, 200))

        # Buttons
        mouse = pygame.mouse.get_pos()
        for rect, label, accent in [
            (btn_fi, "Suomi",   BLUE_ACC),
            (btn_en, "English", GREEN_ACC),
        ]:
            hov = rect.collidepoint(mouse)
            draw_button(screen, rect, hov, accent)
            text_col = (15, 10, 40) if hov else WHITE
            lbl = font_btn.render(label, True, text_col)
            screen.blit(lbl, (rect.centerx - lbl.get_width() // 2,
                               rect.centery - lbl.get_height() // 2))

        # Footer hint
        hint = font_hint.render("ESC to quit", True, GREY_DIM)
        screen.blit(hint, (WINDOW_W // 2 - hint.get_width() // 2, WINDOW_H - 40))

        pygame.display.flip()
        clock.tick(30)


def show_tier_selection(screen: pygame.Surface, strings: dict) -> str:
    """Show tier selection screen, return 'tiny', 'junior', or 'challenge'."""
    font_title = _resolve_font(52)
    font_name  = _resolve_font(42)
    font_desc  = _resolve_font(22)

    tier_data = [
        ("tiny",      strings.get("tier_tiny",      "Tiny"),
         "Ages 3-6 · Shapes",  BLUE_ACC),
        ("junior",    strings.get("tier_junior",    "Junior"),
         "Ages 6-10 · Numbers", GREEN_ACC),
        ("challenge", strings.get("tier_challenge", "Challenge"),
         "Ages 10+ · Math",    ORANGE_ACC),
    ]

    btn_w, btn_h = 500, 96
    start_y = 190
    spacing = btn_h + 22
    buttons = []
    for i, (key, label, desc, accent) in enumerate(tier_data):
        rect = pygame.Rect(WINDOW_W // 2 - btn_w // 2, start_y + i * spacing, btn_w, btn_h)
        buttons.append((key, label, desc, accent, rect))

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for key, label, desc, accent, rect in buttons:
                    if rect.collidepoint(event.pos):
                        return key

        draw_gradient_bg(screen)

        # Title
        title = font_title.render(strings.get("select_tier", "Select level"), True, WHITE)
        screen.blit(title, (WINDOW_W // 2 - title.get_width() // 2, 100))

        mouse = pygame.mouse.get_pos()
        for key, label, desc, accent, rect in buttons:
            hov = rect.collidepoint(mouse)
            draw_button(screen, rect, hov, accent)

            # Accent bar on left edge when idle
            if not hov:
                bar = pygame.Rect(rect.x + 2, rect.y + 10, 4, rect.h - 20)
                pygame.draw.rect(screen, accent, bar, border_radius=2)

            text_col = (15, 10, 40) if hov else WHITE
            desc_col  = (15, 10, 40) if hov else GREY_MED

            name_surf = font_name.render(label, True, text_col)
            desc_surf = font_desc.render(desc,  True, desc_col)

            name_y = rect.centery - name_surf.get_height() // 2 - 10
            desc_y = rect.centery + name_surf.get_height() // 2 - 8

            screen.blit(name_surf, (rect.centerx - name_surf.get_width() // 2, name_y))
            screen.blit(desc_surf, (rect.centerx - desc_surf.get_width() // 2, desc_y))

        pygame.display.flip()
        clock.tick(30)


def main():
    parser = argparse.ArgumentParser(description="NumberJump — floor movement game for kids")
    parser.add_argument("--lang", choices=["fi", "en"], default=None, help="Language (default: show selection screen)")
    parser.add_argument("--tier", choices=["tiny", "junior", "challenge"], default=None)
    parser.add_argument("--recalibrate", action="store_true", help="Force re-calibration even if calibration.json exists")
    parser.add_argument("--retrain-color", action="store_true", help="Force color re-training even if color is already saved")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), pygame.SCALED | pygame.RESIZABLE)
    pygame.display.set_caption("NumberJump")

    # Language selection
    if args.lang:
        lang_code = args.lang
    else:
        try:
            default_strings = lang_module.load("fi")
        except Exception:
            default_strings = {"select_language": "Select language"}
        lang_code = show_language_selection(screen, default_strings)

    strings = lang_module.load(lang_code)
    pygame.display.set_caption(strings.get("title", "NumberJump"))

    # Calibration
    transform_matrix = None
    calib = None
    if not args.recalibrate:
        calib = load_calibration()
        if calib is not None:
            transform_matrix = np.array(calib["transform"], dtype=np.float64)
            logger.info("Loaded existing calibration.")
        else:
            calib = run_calibration(screen, strings)
            transform_matrix = np.array(calib["transform"], dtype=np.float64)
    else:
        calib = run_calibration(screen, strings)
        transform_matrix = np.array(calib["transform"], dtype=np.float64)

    # Color training
    hsv_lower = None
    hsv_upper = None
    if args.retrain_color or calib is None or "hsv_lower" not in calib:
        color_data = run_color_training(screen, strings)
        hsv_lower = tuple(color_data["hsv_lower"])
        hsv_upper = tuple(color_data["hsv_upper"])
    else:
        hsv_lower = tuple(calib["hsv_lower"])
        hsv_upper = tuple(calib["hsv_upper"])
        logger.info(f"Loaded existing color: lower={hsv_lower} upper={hsv_upper}")

    # Game loop — ESC in-game returns here to re-pick the level; ESC on the
    # level-selection screen (or closing the window) exits the app entirely.
    first_round = True
    while True:
        if args.tier and first_round:
            tier = args.tier
        else:
            tier = show_tier_selection(screen, strings)
        first_round = False

        game = Game(lang=lang_code, tier=tier, strings=strings, transform_matrix=transform_matrix,
                    hsv_lower=hsv_lower, hsv_upper=hsv_upper)
        result = game.run(screen)
        if result != "menu":
            break

    pygame.quit()


if __name__ == "__main__":
    main()
