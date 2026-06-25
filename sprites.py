"""Gestor de sprites del cliente.

Carga los iconos PNG disponibles en ``assets/`` y los entrega escalados (con
caché) por nombre. Espeja la filosofía de :class:`audio.AudioManager`: tolera la
ausencia de archivos o de imágenes para que el juego siga funcionando con el
dibujo procedural de respaldo cuando un sprite no existe.
"""

from __future__ import annotations

import os

try:
    import pygame
except ImportError:  # pragma: no cover - el cliente ya valida pygame
    pygame = None  # type: ignore[assignment]


ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


class SpriteManager:
    """Carga y entrega iconos PNG escalados desde ``assets/``."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled and pygame is not None
        self.sprites: dict[str, "pygame.Surface"] = {}
        # Cachea cada combinación (nombre, tamaño, tinte) ya escalada.
        self._cache: dict[tuple[str, int, tuple[int, int, int] | None], "pygame.Surface"] = {}
        if not self.enabled:
            return
        if not os.path.isdir(ASSETS_DIR):
            return

        for filename in sorted(os.listdir(ASSETS_DIR)):
            stem, extension = os.path.splitext(filename)
            if extension.lower() != ".png":
                continue
            try:
                surface = pygame.image.load(os.path.join(ASSETS_DIR, filename))
            except pygame.error:
                continue
            # ``convert_alpha`` requiere un modo de vídeo activo; el cliente ya
            # creó la ventana antes de instanciar el gestor.
            try:
                surface = surface.convert_alpha()
            except pygame.error:
                pass
            self.sprites[stem.lower()] = surface

    def has(self, name: str) -> bool:
        return name.lower() in self.sprites

    def get(
        self,
        name: str,
        size: int,
        tint: tuple[int, int, int] | None = None,
    ) -> "pygame.Surface | None":
        """Devuelve el sprite ``name`` escalado a ``size`` px (o ``None``).

        Si se indica ``tint`` el icono se multiplica por ese color, útil para
        reutilizar un sprite en blanco con el color de cada equipo o estado.
        """
        if not self.enabled:
            return None
        base = self.sprites.get(name.lower())
        if base is None:
            return None
        key = (name.lower(), int(size), tint)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        scaled = pygame.transform.smoothscale(base, (int(size), int(size)))
        if tint is not None:
            scaled = scaled.copy()
            scaled.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._cache[key] = scaled
        return scaled
