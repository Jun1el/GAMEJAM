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
MUSIC_EXTENSIONS = (".ogg", ".wav", ".mp3")
MUSIC_STEMS = ("background", "music", "theme", "bgm", "campus_loop")


class AudioManager:
    """Reproduce efectos de sonido cargados desde ``assets/``."""

    def __init__(self, enabled: bool = True, music_enabled: bool = True) -> None:
        self.enabled = enabled and pygame is not None
        self.music_enabled = self.enabled and music_enabled
        self.sounds: dict[str, "pygame.mixer.Sound"] = {}
        self.music_path: str | None = None
        self.music_playing = False
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
            normalized_stem = stem.lower()
            if normalized_stem in MUSIC_STEMS:
                if extension.lower() in MUSIC_EXTENSIONS:
                    self.music_path = self.music_path or os.path.join(
                        ASSETS_DIR, filename
                    )
                continue
            if extension.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                self.sounds[normalized_stem] = pygame.mixer.Sound(
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

    def play_music(self, volume: float = 0.28) -> None:
        """Reproduce musica ambiental en bucle si existe un archivo compatible."""
        if not self.music_enabled or not self.music_path or self.music_playing:
            return
        try:
            pygame.mixer.music.load(self.music_path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
            pygame.mixer.music.play(loops=-1, fade_ms=1200)
            self.music_playing = True
        except pygame.error:
            self.music_path = None

    def stop_music(self) -> None:
        """Detiene la musica de fondo si estaba sonando."""
        if not self.enabled or not self.music_playing:
            return
        try:
            pygame.mixer.music.fadeout(350)
        except pygame.error:
            pass
        self.music_playing = False
