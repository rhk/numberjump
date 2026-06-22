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


def show_language_selection(screen: pygame.Surface, default_strings: dict) -> str:
    """Show language selection screen, return 'fi' or 'en'."""
    font_title = pygame.font.SysFont(None, 72)
    font_btn = pygame.font.SysFont(None, 56)

    btn_fi = pygame.Rect(150, 250, 200, 100)
    btn_en = pygame.Rect(450, 250, 200, 100)

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

        screen.fill((20, 20, 40))
        title = font_title.render(default_strings.get("select_language", "Select language"), True, (255, 255, 255))
        screen.blit(title, (WINDOW_W // 2 - title.get_width() // 2, 120))

        mouse = pygame.mouse.get_pos()
        for rect, label, color_hover in [(btn_fi, "Suomi", (80, 160, 255)), (btn_en, "English", (80, 200, 120))]:
            color = color_hover if rect.collidepoint(mouse) else (60, 60, 100)
            pygame.draw.rect(screen, color, rect, border_radius=12)
            pygame.draw.rect(screen, (200, 200, 255), rect, 3, border_radius=12)
            lbl = font_btn.render(label, True, (255, 255, 255))
            screen.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.centery - lbl.get_height() // 2))

        pygame.display.flip()
        clock.tick(30)


def show_tier_selection(screen: pygame.Surface, strings: dict) -> str:
    """Show tier selection screen, return 'tiny', 'junior', or 'challenge'."""
    font_title = pygame.font.SysFont(None, 60)
    font_btn = pygame.font.SysFont(None, 44)

    tiers = [
        ("tiny", strings.get("tier_tiny", "Tiny")),
        ("junior", strings.get("tier_junior", "Junior")),
        ("challenge", strings.get("tier_challenge", "Challenge")),
    ]

    buttons = []
    for i, (key, label) in enumerate(tiers):
        rect = pygame.Rect(200, 180 + i * 120, 400, 90)
        buttons.append((key, label, rect))

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
                for key, label, rect in buttons:
                    if rect.collidepoint(event.pos):
                        return key

        screen.fill((20, 20, 40))
        title = font_title.render(strings.get("select_tier", "Select level"), True, (255, 255, 255))
        screen.blit(title, (WINDOW_W // 2 - title.get_width() // 2, 80))

        mouse = pygame.mouse.get_pos()
        colors = [(80, 160, 255), (80, 220, 120), (255, 120, 80)]
        for (key, label, rect), col in zip(buttons, colors):
            bg = col if rect.collidepoint(mouse) else (50, 50, 80)
            pygame.draw.rect(screen, bg, rect, border_radius=12)
            pygame.draw.rect(screen, (200, 200, 255), rect, 3, border_radius=12)
            lbl = font_btn.render(label, True, (255, 255, 255))
            screen.blit(lbl, (rect.centerx - lbl.get_width() // 2, rect.centery - lbl.get_height() // 2))

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
        # Load Finnish strings as default for the selection screen
        try:
            default_strings = lang_module.load("fi")
        except Exception:
            default_strings = {"select_language": "Select language"}
        lang_code = show_language_selection(screen, default_strings)

    strings = lang_module.load(lang_code)
    pygame.display.set_caption(strings.get("title", "NumberJump"))

    # Tier selection
    if args.tier:
        tier = args.tier
    else:
        tier = show_tier_selection(screen, strings)

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

    # Start game
    game = Game(lang=lang_code, tier=tier, strings=strings, transform_matrix=transform_matrix,
                hsv_lower=hsv_lower, hsv_upper=hsv_upper)
    game.run(screen)

    pygame.quit()


if __name__ == "__main__":
    main()
