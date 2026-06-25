"""Gestor de audio del cliente.

Carga los efectos disponibles en ``assets/`` y los reproduce por nombre. El
gestor tolera la ausencia de archivos o de dispositivo de sonido para que el
juego siga funcionando en entornos sin audio (por ejemplo, pruebas headless).
"""

from __future__ import annotations

import os

try:
    import pygame
except ImportError:  # pragma: no cover - el cliente ya valida pygame
    pygame = None  # type: ignore[assignment]


ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SUPPORTED_EXTENSIONS = (".wav", ".ogg")


class AudioManager:
    """Reproduce efectos de sonido cargados desde ``assets/``."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and pygame is not None
        self.sounds: dict[str, "pygame.mixer.Sound"] = {}
        if not self.enabled:
            return

        try:
            pygame.mixer.init()
        except pygame.error:
            self.enabled = False
            return

        if not os.path.isdir(ASSETS_DIR):
            return

        for filename in sorted(os.listdir(ASSETS_DIR)):
            stem, extension = os.path.splitext(filename)
            if extension.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                self.sounds[stem.lower()] = pygame.mixer.Sound(
                    os.path.join(ASSETS_DIR, filename)
                )
            except pygame.error:
                continue

    def play(self, name: str, volume: float = 0.7) -> None:
        """Reproduce el efecto ``name`` si existe y el audio está activo."""
        if not self.enabled:
            return
        sound = self.sounds.get(name.lower())
        if sound is None:
            return
        sound.set_volume(max(0.0, min(1.0, volume)))
        sound.play()
