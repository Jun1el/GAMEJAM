"""Genera los iconos PNG del juego en ``assets/`` usando Pygame.

Se ejecuta sin ventana (modo *headless*) para poder correr en cualquier
entorno. Vuelve a ejecutarlo si quieres regenerar el arte; el cliente carga los
PNG automáticamente mediante :class:`sprites.SpriteManager`.

    python generate_sprites.py
"""

from __future__ import annotations

import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
from pygame import gfxdraw

pygame.init()

S = 128  # Resolución base; el cliente reescala a la medida que necesite.
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def _surface() -> pygame.Surface:
    return pygame.Surface((S, S), pygame.SRCALPHA)


def _disc(surf: pygame.Surface, x: float, y: float, r: float, color) -> None:
    """Círculo relleno con bordes suavizados."""
    gfxdraw.filled_circle(surf, int(x), int(y), int(r), color)
    gfxdraw.aacircle(surf, int(x), int(y), int(r), color)


def _save(surf: pygame.Surface, name: str) -> None:
    pygame.image.save(surf, os.path.join(ASSETS_DIR, f"{name}.png"))
    print(f"  generado  assets/{name}.png")


def make_powerup_shield() -> pygame.Surface:
    surf = _surface()
    blue = (90, 180, 255)
    dark = (38, 108, 178)
    light = (175, 218, 255)
    shield = [(64, 16), (108, 36), (108, 66), (64, 114), (20, 66), (20, 36)]
    pygame.draw.polygon(surf, blue, shield)
    pygame.draw.polygon(surf, dark, shield, 6)
    inner = [(64, 30), (96, 44), (96, 64), (64, 100), (32, 64), (32, 44)]
    pygame.draw.polygon(surf, light, inner, 4)
    pygame.draw.lines(surf, (255, 255, 255), False, [(46, 62), (60, 80), (88, 44)], 8)
    return surf


def make_powerup_instant_repair() -> pygame.Surface:
    surf = _surface()
    green = (80, 220, 130)
    dark = (38, 150, 84)
    pad = (185, 246, 208)
    band = pygame.Surface((110, 52), pygame.SRCALPHA)
    rect = band.get_rect()
    pygame.draw.rect(band, green, rect, border_radius=22)
    pygame.draw.rect(band, dark, rect, 5, border_radius=22)
    pygame.draw.rect(band, pad, pygame.Rect(34, 10, 42, 32), border_radius=8)
    for hx in (16, 94):
        for hy in (16, 36):
            pygame.draw.circle(band, dark, (hx, hy), 4)
    band = pygame.transform.rotate(band, 28)
    surf.blit(band, band.get_rect(center=(64, 64)))
    return surf


def make_powerup_freeze() -> pygame.Surface:
    surf = _surface()
    cyan = (140, 230, 245)
    white = (232, 250, 255)
    cx, cy = 64, 64
    for k in range(6):
        angle = math.radians(k * 60)
        ex = cx + 44 * math.cos(angle)
        ey = cy + 44 * math.sin(angle)
        pygame.draw.line(surf, cyan, (cx, cy), (ex, ey), 7)
        for fraction, length in ((0.55, 16), (0.78, 12)):
            bx = cx + 44 * fraction * math.cos(angle)
            by = cy + 44 * fraction * math.sin(angle)
            for delta in (40, -40):
                a2 = angle + math.radians(delta)
                pygame.draw.line(
                    surf, cyan, (bx, by),
                    (bx + length * math.cos(a2), by + length * math.sin(a2)), 5,
                )
    _disc(surf, cx, cy, 9, white)
    return surf


def make_chicken() -> pygame.Surface:
    surf = _surface()
    meat = (168, 102, 56)
    meat_dark = (120, 70, 38)
    meat_light = (205, 145, 92)
    bone = (246, 241, 230)
    pygame.draw.line(surf, bone, (70, 58), (40, 104), 16)
    _disc(surf, 38, 108, 12, bone)
    _disc(surf, 51, 97, 11, bone)
    _disc(surf, 76, 52, 36, meat)
    pygame.draw.circle(surf, meat_dark, (76, 52), 36, 5)
    _disc(surf, 66, 40, 10, meat_light)
    return surf


def make_medical() -> pygame.Surface:
    surf = _surface()
    box = (240, 248, 248)
    green = (75, 205, 135)
    rect = pygame.Rect(20, 20, 88, 88)
    pygame.draw.rect(surf, box, rect, border_radius=18)
    pygame.draw.rect(surf, green, rect, 6, border_radius=18)
    pygame.draw.rect(surf, green, pygame.Rect(56, 38, 16, 52), border_radius=4)
    pygame.draw.rect(surf, green, pygame.Rect(38, 56, 52, 16), border_radius=4)
    return surf


def make_professor() -> pygame.Surface:
    surf = _surface()
    skin = (238, 205, 175)
    hair = (60, 45, 40)
    dark = (35, 30, 30)
    suit = (110, 80, 160)
    pygame.draw.ellipse(surf, suit, pygame.Rect(28, 92, 72, 42))
    pygame.draw.polygon(surf, (232, 210, 120), [(64, 96), (57, 120), (71, 120)])
    _disc(surf, 64, 58, 30, skin)
    pygame.draw.arc(surf, hair, pygame.Rect(34, 26, 60, 60), 0.2, math.pi - 0.2, 11)
    pygame.draw.circle(surf, dark, (52, 58), 9, 3)
    pygame.draw.circle(surf, dark, (76, 58), 9, 3)
    pygame.draw.line(surf, dark, (61, 58), (67, 58), 3)
    pygame.draw.arc(surf, dark, pygame.Rect(52, 62, 24, 20), math.pi + 0.35, 2 * math.pi - 0.35, 3)
    return surf


def make_router() -> pygame.Surface:
    """Router en tonos claros para teñirlo con el color de estado."""
    surf = _surface()
    body = (236, 240, 245)
    edge = (120, 130, 140)
    pygame.draw.line(surf, body, (44, 64), (30, 24), 7)
    pygame.draw.line(surf, body, (84, 64), (98, 24), 7)
    _disc(surf, 30, 22, 6, body)
    _disc(surf, 98, 22, 6, body)
    rect = pygame.Rect(30, 58, 68, 40)
    pygame.draw.rect(surf, body, rect, border_radius=10)
    pygame.draw.rect(surf, edge, rect, 4, border_radius=10)
    for lx in (46, 64, 82):
        pygame.draw.circle(surf, edge, (lx, 78), 5, 2)
    return surf


def make_player() -> pygame.Surface:
    """Silueta de estudiante en blanco para teñir con el color del equipo."""
    surf = _surface()
    body = (245, 245, 245)
    shade = (180, 180, 180)
    dark = (90, 90, 90)
    _disc(surf, 64, 40, 20, body)
    pygame.draw.circle(surf, dark, (64, 40), 20, 4)
    torso = pygame.Rect(38, 58, 52, 54)
    pygame.draw.rect(surf, body, torso, border_radius=16)
    pygame.draw.rect(surf, dark, torso, 4, border_radius=16)
    pygame.draw.rect(surf, shade, pygame.Rect(52, 58, 8, 50))
    return surf


SPRITES = {
    "powerup_shield": make_powerup_shield,
    "powerup_instant_repair": make_powerup_instant_repair,
    "powerup_freeze": make_powerup_freeze,
    "chicken": make_chicken,
    "medical": make_medical,
    "professor": make_professor,
    "router": make_router,
    "player": make_player,
}


def main() -> None:
    os.makedirs(ASSETS_DIR, exist_ok=True)
    print(f"Generando {len(SPRITES)} iconos en assets/ ...")
    for name, factory in SPRITES.items():
        _save(factory(), name)
    print("Listo.")


if __name__ == "__main__":
    main()
