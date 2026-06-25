"""Cliente Pygame para "La vida da vueltas en Eduroam"."""

from __future__ import annotations

import argparse
import math
import sys
import uuid
from typing import Any

try:
    import pygame
except ImportError:
    print("Pygame no está instalado. Ejecuta: python -m pip install pygame")
    raise SystemExit(1)

from audio import AudioManager
from network import DEFAULT_HOST, DEFAULT_PORT, Network, NetworkError


FPS = 30

# Asocia el campo ``kind`` de los eventos del servidor con un efecto de audio.
# Los nombres deben coincidir con los archivos de ``assets/`` (sin extensión).
EVENT_SOUNDS = {
    "repair": "repair",
    "damage": "fail",
    "chicken": "pickup",
    "bomb": "bomb",
    "victory": "misioncomplete",
}
HUD_HEIGHT = 205
PLAYER_SIZE = 20
START_WIDTH = 900
START_HEIGHT = 600
GAME_WIDTH = 1100
GAME_HEIGHT = 760
VIEWPORT_HEIGHT = GAME_HEIGHT - HUD_HEIGHT

COLORS = {
    "background": (13, 20, 32),
    "background_light": (21, 35, 55),
    "uni_blue": (0, 83, 155),
    "uni_blue_light": (20, 135, 210),
    "accent": (255, 196, 61),
    "wall": (35, 48, 67),
    "wall_edge": (52, 71, 96),
    "floor": (208, 218, 225),
    "floor_line": (188, 201, 210),
    "router_down": (231, 76, 60),
    "router_ready": (255, 209, 102),
    "router_up": (39, 174, 96),
    "text": (238, 242, 245),
    "muted": (164, 174, 186),
    "hud": (18, 27, 42),
    "panel": (22, 34, 52),
    "input": (12, 24, 40),
    "victory": (39, 174, 96),
    "defeat": (231, 76, 60),
    "health": (230, 76, 76),
    "fatigue": (245, 166, 35),
    "chicken": (255, 179, 71),
    "bomb": (28, 28, 32),
    "explosion": (255, 105, 45),
    "medical": (75, 220, 145),
    "professor": (190, 120, 255),
    "food_bad": (135, 200, 70),
}


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


class GameClient:
    def __init__(
        self, host: str, port: int, name: str, audio_enabled: bool = True
    ) -> None:
        self.network = Network(host, port, timeout=5.0)
        self.name = name
        self.player_id: int | None = None
        self.tilemap: list[list[int]] = []
        self.tile_size = 32
        self.repair_window = (0.0, 90.0)
        self.state: dict[str, Any] = {}
        self.last_event_id = 0
        self.status_message = "Conectando..."
        self.status_until = 0
        self.request_counter = 0
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.damage_flash_until = 0
        self.last_food_event_sequence = 0

        pygame.init()
        pygame.display.set_caption("La vida da vueltas en Eduroam")
        self.screen: pygame.Surface | None = pygame.display.set_mode(
            (START_WIDTH, START_HEIGHT)
        )
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 11)
        self.title_font = pygame.font.SysFont("consolas", 20, bold=True)
        self.menu_title_font = pygame.font.SysFont("arial", 42, bold=True)
        self.menu_subtitle_font = pygame.font.SysFont("arial", 22, bold=True)
        self.menu_font = pygame.font.SysFont("arial", 18)
        self.audio = AudioManager(enabled=audio_enabled)

    def _draw_signal(self, center: tuple[int, int], pulse: float) -> None:
        """Dibuja una señal Wi-Fi animada para la portada."""
        assert self.screen is not None
        for index, radius in enumerate((42, 72, 102)):
            alpha = max(45, 150 - index * 25)
            layer = pygame.Surface((radius * 2 + 8, radius * 2 + 8), pygame.SRCALPHA)
            pygame.draw.arc(
                layer,
                (*COLORS["uni_blue_light"], alpha),
                layer.get_rect().inflate(-8, -8),
                0.15 + pulse,
                2.99 + pulse,
                6,
            )
            self.screen.blit(layer, layer.get_rect(center=center))
        pygame.draw.circle(self.screen, COLORS["accent"], center, 9)

    def _draw_start_screen(
        self, name_active: bool, play_hovered: bool, pulse: float
    ) -> tuple[pygame.Rect, pygame.Rect]:
        assert self.screen is not None
        self.screen.fill(COLORS["background"])

        for y in range(0, START_HEIGHT, 40):
            shade = 18 + y // 45
            pygame.draw.line(
                self.screen,
                (shade, shade + 9, shade + 20),
                (0, y),
                (START_WIDTH, y),
            )

        self._draw_signal((755, 112), pulse)
        pygame.draw.rect(
            self.screen,
            COLORS["uni_blue"],
            pygame.Rect(0, 0, 12, START_HEIGHT),
        )

        uni = self.menu_subtitle_font.render(
            "UNIVERSIDAD NACIONAL DE INGENIERÍA", True, COLORS["uni_blue_light"]
        )
        self.screen.blit(uni, (55, 45))

        title = self.menu_title_font.render(
            "LA VIDA DA VUELTAS", True, COLORS["text"]
        )
        self.screen.blit(title, (55, 88))
        eduroam = self.menu_title_font.render("EN EDUROAM", True, COLORS["accent"])
        self.screen.blit(eduroam, (55, 137))

        problem = (
            "La conexión Eduroam está fallando en distintos puntos del campus. "
            "Recorre la UNI, sincroniza los routers y mantén la red funcionando."
        )
        words = problem.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if self.menu_font.size(candidate)[0] > 690:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
        for index, line in enumerate(lines):
            rendered = self.menu_font.render(line, True, COLORS["muted"])
            self.screen.blit(rendered, (57, 205 + index * 25))

        panel = pygame.Rect(55, 295, 790, 130)
        pygame.draw.rect(self.screen, COLORS["panel"], panel, border_radius=14)
        pygame.draw.rect(
            self.screen, COLORS["background_light"], panel, 2, border_radius=14
        )
        mission = self.menu_subtitle_font.render(
            "TU MISIÓN", True, COLORS["accent"]
        )
        self.screen.blit(mission, (75, 315))
        instructions = [
            "WASD / Flechas  ·  Muévete por el campus",
            "Acércate a un router rojo  ·  Espera a que se vuelva amarillo",
            "E repara/recoge pollo  ·  Q consume tu pollo a la brasa",
        ]
        for index, text in enumerate(instructions):
            rendered = self.menu_font.render(text, True, COLORS["text"])
            self.screen.blit(rendered, (75, 350 + index * 25))

        name_label = self.font.render("NOMBRE DEL JUGADOR", True, COLORS["muted"])
        self.screen.blit(name_label, (55, 458))
        name_rect = pygame.Rect(55, 482, 500, 52)
        pygame.draw.rect(self.screen, COLORS["input"], name_rect, border_radius=9)
        pygame.draw.rect(
            self.screen,
            COLORS["uni_blue_light"] if name_active else COLORS["wall_edge"],
            name_rect,
            2,
            border_radius=9,
        )
        display_name = self.name or "Escribe tu nombre"
        name_color = COLORS["text"] if self.name else COLORS["muted"]
        name_surface = self.menu_font.render(display_name, True, name_color)
        name_position = (name_rect.x + 15, name_rect.y + 15)
        self.screen.blit(name_surface, name_position)
        if name_active and int(pulse * 2) % 2 == 0:
            caret_x = (
                name_position[0] + self.menu_font.size(self.name)[0] + 2
                if self.name
                else name_position[0]
            )
            pygame.draw.line(
                self.screen,
                COLORS["accent"],
                (caret_x, name_rect.y + 12),
                (caret_x, name_rect.bottom - 12),
                2,
            )

        play_rect = pygame.Rect(585, 482, 260, 52)
        button_color = (
            COLORS["uni_blue_light"] if play_hovered else COLORS["uni_blue"]
        )
        pygame.draw.rect(self.screen, button_color, play_rect, border_radius=9)
        play = self.menu_subtitle_font.render(
            "CONECTAR A EDUROAM", True, COLORS["text"]
        )
        self.screen.blit(play, play.get_rect(center=play_rect.center))

        footer = self.small_font.render(
            "Hasta 4 jugadores  ·  Servidor autoritativo  ·  ESC para salir",
            True,
            COLORS["muted"],
        )
        self.screen.blit(footer, footer.get_rect(center=(START_WIDTH // 2, 570)))
        return name_rect, play_rect

    def show_start_screen(self) -> bool:
        """Muestra la portada y devuelve True cuando el jugador decide entrar."""
        name_active = True
        elapsed = 0.0

        while True:
            mouse_position = pygame.mouse.get_pos()
            play_hovered = pygame.Rect(585, 482, 260, 52).collidepoint(
                mouse_position
            )
            name_rect, play_rect = self._draw_start_screen(
                name_active, play_hovered, elapsed
            )
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
                    if event.key == pygame.K_RETURN and self.name.strip():
                        self.name = self.name.strip()
                        return True
                    if name_active:
                        if event.key == pygame.K_BACKSPACE:
                            self.name = self.name[:-1]
                        elif event.unicode.isprintable() and len(self.name) < 20:
                            self.name += event.unicode
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    name_active = name_rect.collidepoint(event.pos)
                    if play_rect.collidepoint(event.pos) and self.name.strip():
                        self.name = self.name.strip()
                        return True

            elapsed += self.clock.tick(FPS) / 1000.0

    def _next_request_id(self) -> str:
        self.request_counter += 1
        return f"{uuid.uuid4().hex[:8]}-{self.request_counter}"

    def connect(self) -> None:
        self.network.connect()
        response = self.network.request(
            {
                "type": "join",
                "payload": {"name": self.name},
                "request_id": self._next_request_id(),
            }
        )
        if response.get("type") == "error":
            payload = response.get("payload", {})
            raise NetworkError(payload.get("message", "El servidor rechazó la conexión."))
        if response.get("type") != "welcome":
            raise NetworkError("El servidor no envió el mensaje de bienvenida.")

        payload = response["payload"]
        self.player_id = int(payload["player_id"])
        self.tilemap = payload["map"]
        self.tile_size = int(payload["tile_size"])
        self.repair_window = tuple(payload["repair_window"])
        self.state = payload["state"]
        existing_events = self.state.get("events", [])
        if existing_events:
            self.last_event_id = existing_events[-1]["id"]

        self.screen = pygame.display.set_mode((GAME_WIDTH, GAME_HEIGHT))
        self.status_message = (
            "WASD para moverte · E repara/recoge pollo · Q consume pollo."
        )
        self.status_until = pygame.time.get_ticks() + 5000

    def _inputs(self) -> dict[str, bool]:
        keys = pygame.key.get_pressed()
        return {
            "up": keys[pygame.K_w] or keys[pygame.K_UP],
            "down": keys[pygame.K_s] or keys[pygame.K_DOWN],
            "left": keys[pygame.K_a] or keys[pygame.K_LEFT],
            "right": keys[pygame.K_d] or keys[pygame.K_RIGHT],
        }

    def _exchange(self, message_type: str, payload: dict[str, Any]) -> None:
        previous_player = self.state.get("players", {}).get(str(self.player_id), {})
        previous_health = float(previous_player.get("health", 100))
        response = self.network.request(
            {
                "type": message_type,
                "payload": payload,
                "request_id": self._next_request_id(),
            }
        )
        if response.get("type") != "state":
            raise NetworkError("Respuesta inesperada del servidor.")
        response_payload = response.get("payload", {})
        self.state = response_payload.get("state", self.state)
        current_player = self.state.get("players", {}).get(str(self.player_id), {})
        current_health = float(current_player.get("health", previous_health))
        if current_health < previous_health:
            self.damage_flash_until = pygame.time.get_ticks() + 260
        interaction = response_payload.get("interaction")
        if interaction:
            self.status_message = interaction["message"]
            self.status_until = pygame.time.get_ticks() + 2500
        self._process_audio_events()

    def _process_audio_events(self) -> None:
        """Reproduce un efecto por cada evento del servidor aún no escuchado."""
        events = self.state.get("events", [])
        for event in events:
            if event["id"] <= self.last_event_id:
                continue
            self._play_event_sound(event)
        if events:
            self.last_event_id = max(self.last_event_id, events[-1]["id"])

    def _play_event_sound(self, event: dict[str, Any]) -> None:
        kind = event.get("kind")
        if kind == "mission":
            # El mismo 'kind' anuncia el inicio y el fin de la misión; solo
            # suena la fanfarria cuando una misión se completa.
            if "completada" in event.get("text", "").lower():
                self.audio.play("misioncomplete")
            return
        sound = EVENT_SOUNDS.get(kind)
        if sound:
            self.audio.play(sound)

    def _update_camera(self) -> None:
        if self.player_id is None:
            return
        player = self.state.get("players", {}).get(str(self.player_id))
        if not player:
            return
        world_width = len(self.tilemap[0]) * self.tile_size
        world_height = len(self.tilemap) * self.tile_size
        target_x = player["x"] + PLAYER_SIZE / 2 - GAME_WIDTH / 2
        target_y = player["y"] + PLAYER_SIZE / 2 - VIEWPORT_HEIGHT / 2
        self.camera_x = max(0.0, min(target_x, max(0, world_width - GAME_WIDTH)))
        self.camera_y = max(
            0.0, min(target_y, max(0, world_height - VIEWPORT_HEIGHT))
        )

    def _world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        return round(x - self.camera_x), round(y - self.camera_y)

    def _point_visible(self, x: float, y: float, margin: int = 40) -> bool:
        screen_x, screen_y = self._world_to_screen(x, y)
        return (
            -margin <= screen_x <= GAME_WIDTH + margin
            and -margin <= screen_y <= VIEWPORT_HEIGHT + margin
        )

    def _draw_map(self) -> None:
        assert self.screen is not None
        first_col = max(0, int(self.camera_x // self.tile_size))
        last_col = min(
            len(self.tilemap[0]),
            int((self.camera_x + GAME_WIDTH) // self.tile_size) + 2,
        )
        first_row = max(0, int(self.camera_y // self.tile_size))
        last_row = min(
            len(self.tilemap),
            int((self.camera_y + VIEWPORT_HEIGHT) // self.tile_size) + 2,
        )
        for row in range(first_row, last_row):
            for col in range(first_col, last_col):
                tile = self.tilemap[row][col]
                x, y = self._world_to_screen(
                    col * self.tile_size, row * self.tile_size
                )
                rect = pygame.Rect(
                    x,
                    y,
                    self.tile_size,
                    self.tile_size,
                )
                if tile == 1:
                    pygame.draw.rect(self.screen, COLORS["wall"], rect)
                    pygame.draw.rect(self.screen, COLORS["wall_edge"], rect, 1)
                else:
                    pygame.draw.rect(self.screen, COLORS["floor"], rect)
                    pygame.draw.rect(self.screen, COLORS["floor_line"], rect, 1)

    def _draw_routers(self) -> None:
        assert self.screen is not None
        minimum, maximum = self.repair_window
        target_router = self.state.get("mission", {}).get("target_router")
        for router in self.state.get("routers", {}).values():
            world_center = (
                (router["col"] + 0.5) * self.tile_size,
                (router["row"] + 0.5) * self.tile_size,
            )
            if not self._point_visible(*world_center):
                continue
            center = self._world_to_screen(*world_center)
            rotation = float(router["rotation"])
            ready = minimum <= rotation <= maximum
            if router["repaired"]:
                color = COLORS["router_up"]
            elif ready:
                color = COLORS["router_ready"]
            else:
                color = COLORS["router_down"]

            radius = max(7, self.tile_size // 3)
            if router["id"] == target_router:
                pulse = 3 + int((pygame.time.get_ticks() / 180) % 4)
                pygame.draw.circle(
                    self.screen,
                    COLORS["accent"],
                    center,
                    radius + pulse + 4,
                    3,
                )
            pygame.draw.circle(self.screen, color, center, radius)
            pygame.draw.circle(self.screen, COLORS["background"], center, radius, 2)
            direction = pygame.Vector2(radius - 2, 0).rotate(-rotation)
            pygame.draw.line(
                self.screen,
                COLORS["background"],
                center,
                (center[0] + direction.x, center[1] + direction.y),
                2,
            )
            label = self.small_font.render(router["name"], True, COLORS["text"])
            label_rect = label.get_rect(midtop=(center[0], center[1] + radius + 1))
            self.screen.blit(label, label_rect)

    def _draw_players(self) -> None:
        assert self.screen is not None
        for key, player in self.state.get("players", {}).items():
            screen_x, screen_y = self._world_to_screen(player["x"], player["y"])
            if not (
                -PLAYER_SIZE <= screen_x <= GAME_WIDTH
                and -PLAYER_SIZE <= screen_y <= VIEWPORT_HEIGHT
            ):
                continue
            rect = pygame.Rect(
                screen_x,
                screen_y,
                PLAYER_SIZE,
                PLAYER_SIZE,
            )
            color = parse_hex_color(player["color"])
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            border = (255, 255, 255) if int(key) == self.player_id else COLORS["background"]
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=5)
            if player.get("invulnerable_remaining", 0) > 0:
                pygame.draw.circle(
                    self.screen,
                    COLORS["uni_blue_light"],
                    rect.center,
                    PLAYER_SIZE,
                    2,
                )

            label = self.small_font.render(player["name"], True, COLORS["text"])
            self.screen.blit(label, label.get_rect(midbottom=(rect.centerx, rect.top - 2)))

    def _draw_bombs(self) -> None:
        assert self.screen is not None
        for bomb in self.state.get("bombs", {}).values():
            world_center = (
                (bomb["col"] + 0.5) * self.tile_size,
                (bomb["row"] + 0.5) * self.tile_size,
            )
            if not self._point_visible(*world_center, margin=80):
                continue
            center = self._world_to_screen(*world_center)
            if bomb["exploded"]:
                radius = int(self.tile_size * 2 * 0.9)
                pygame.draw.circle(
                    self.screen, COLORS["explosion"], center, radius, 5
                )
                pygame.draw.circle(
                    self.screen, COLORS["router_ready"], center, radius // 2, 3
                )
                continue
            remaining = float(bomb["time_remaining"])
            pulse = 3 if int(remaining * 6) % 2 else 0
            pygame.draw.circle(
                self.screen, COLORS["bomb"], center, self.tile_size // 3 + pulse
            )
            pygame.draw.circle(
                self.screen,
                COLORS["defeat"] if remaining < 1.0 else COLORS["accent"],
                center,
                self.tile_size // 3 + pulse,
                3,
            )
            fuse_end = (center[0] + 9, center[1] - 12)
            pygame.draw.line(self.screen, COLORS["accent"], center, fuse_end, 3)

    def _draw_facilities(self) -> None:
        assert self.screen is not None
        pulse = 2 + int((pygame.time.get_ticks() / 220) % 3)
        for facility in self.state.get("facilities", {}).values():
            world_center = (
                (facility["col"] + 0.5) * self.tile_size,
                (facility["row"] + 0.5) * self.tile_size,
            )
            if not self._point_visible(*world_center):
                continue
            center = self._world_to_screen(*world_center)
            active = facility.get("active", True)
            if facility["type"] == "food":
                color = COLORS["chicken"] if active else COLORS["muted"]
                pygame.draw.circle(self.screen, color, center, 14 + pulse, 2)
                pygame.draw.ellipse(
                    self.screen,
                    color,
                    pygame.Rect(center[0] - 12, center[1] - 8, 19, 16),
                )
                pygame.draw.line(
                    self.screen,
                    COLORS["text"],
                    (center[0] + 4, center[1] + 5),
                    (center[0] + 13, center[1] + 12),
                    4,
                )
                pygame.draw.circle(
                    self.screen, COLORS["text"], (center[0] + 15, center[1] + 14), 3
                )
            else:
                color = COLORS["medical"]
                box = pygame.Rect(center[0] - 14, center[1] - 14, 28, 28)
                pygame.draw.rect(self.screen, color, box, border_radius=6)
                pygame.draw.rect(self.screen, COLORS["text"], box, 2, border_radius=6)
                pygame.draw.rect(
                    self.screen,
                    COLORS["text"],
                    pygame.Rect(center[0] - 3, center[1] - 9, 6, 18),
                )
                pygame.draw.rect(
                    self.screen,
                    COLORS["text"],
                    pygame.Rect(center[0] - 9, center[1] - 3, 18, 6),
                )
            label = self.small_font.render(
                facility["name"], True, COLORS["text"]
            )
            self.screen.blit(label, label.get_rect(midtop=(center[0], center[1] + 18)))

    def _facility_state_by_name(self, name: str) -> dict[str, Any] | None:
        return next(
            (
                facility
                for facility in self.state.get("facilities", {}).values()
                if facility["name"] == name
            ),
            None,
        )

    def _location_state_by_name(self, name: str) -> dict[str, Any] | None:
        if name == "PROF. MONTALVO":
            return self.state.get("professor")
        facility = self._facility_state_by_name(name)
        if facility:
            return facility
        return next(
            (
                router
                for router in self.state.get("routers", {}).values()
                if router["name"] == name
            ),
            None,
        )

    def _draw_professor(self) -> None:
        assert self.screen is not None
        professor = self.state.get("professor")
        if not professor:
            return
        world_center = (
            (professor["col"] + 0.5) * self.tile_size,
            (professor["row"] + 0.5) * self.tile_size,
        )
        if not self._point_visible(*world_center):
            return
        center = self._world_to_screen(*world_center)
        pygame.draw.circle(self.screen, COLORS["professor"], center, 13)
        pygame.draw.circle(self.screen, COLORS["text"], center, 13, 2)
        pygame.draw.circle(
            self.screen, COLORS["background"], (center[0] - 4, center[1] - 2), 2
        )
        pygame.draw.circle(
            self.screen, COLORS["background"], (center[0] + 4, center[1] - 2), 2
        )
        pygame.draw.line(
            self.screen,
            COLORS["background"],
            (center[0] - 5, center[1] + 5),
            (center[0] + 5, center[1] + 5),
            2,
        )
        label = self.small_font.render("PROF. MONTALVO", True, COLORS["professor"])
        self.screen.blit(label, label.get_rect(midtop=(center[0], center[1] + 16)))

    def _draw_side_quest(self) -> None:
        assert self.screen is not None
        quest = self.state.get("side_quest", {})
        if not quest:
            return
        status = quest.get("status", "available")
        owner_id = quest.get("owner_id")
        local_owner = owner_id == self.player_id
        if status == "available":
            title = "PROF. MONTALVO TIENE UNA PRÁCTICA"
            detail = "Acércate y pulsa E para aceptar."
        elif status == "active" and local_owner:
            title = f"EXTRA: {quest.get('title', '')}"
            detail = (
                f"{quest.get('description', '')}  "
                f"{quest.get('progress', 0)}/{quest.get('goal', 1)} · "
                f"{quest.get('time_remaining', 0):.0f}s"
            )
        elif status == "active":
            title = "PRÁCTICA DE MONTALVO EN CURSO"
            detail = "Otro estudiante intenta salvar su promedio."
        elif status == "completed":
            title = "PRÁCTICA APROBADA"
            detail = "Prof. Montalvo registró la nota... probablemente."
        else:
            title = "PRÁCTICA CERRADA"
            detail = "Se agotó el tiempo de entrega."
        panel = pygame.Rect(14, 12, 430, 58)
        pygame.draw.rect(self.screen, (14, 22, 36, 225), panel, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["professor"], panel, 2, border_radius=8)
        self.screen.blit(
            self.small_font.render(title, True, COLORS["professor"]),
            (panel.x + 10, panel.y + 8),
        )
        self.screen.blit(
            self.small_font.render(detail[:66], True, COLORS["text"]),
            (panel.x + 10, panel.y + 31),
        )

    def _draw_food_event_alert(self) -> None:
        assert self.screen is not None
        event = self.state.get("food_event", {})
        event_type = event.get("type", "normal")
        if event_type == "normal":
            return
        labels = {
            "double": ("¡DOBLEEE!", COLORS["chicken"]),
            "triple": ("¡TRIPLEEE!", COLORS["accent"]),
            "fly": ("¡MENÚ CON MOSCA!", COLORS["food_bad"]),
        }
        label, color = labels[event_type]
        pulse = 1.0 + 0.08 * abs(math.sin(pygame.time.get_ticks() / 140))
        font = pygame.font.SysFont("arial", int(34 * pulse), bold=True)
        text = font.render(label, True, color)
        shadow = font.render(label, True, COLORS["background"])
        center = (GAME_WIDTH // 2, 36)
        self.screen.blit(shadow, shadow.get_rect(center=(center[0] + 3, center[1] + 3)))
        self.screen.blit(text, text.get_rect(center=center))
        remaining = self.small_font.render(
            f"Comedor especial por {event.get('time_remaining', 0):.0f}s",
            True,
            COLORS["text"],
        )
        self.screen.blit(remaining, remaining.get_rect(center=(center[0], 62)))

    def _draw_minimap(self) -> None:
        assert self.screen is not None
        minimap = pygame.Rect(GAME_WIDTH - 270, 12, 255, 100)
        pygame.draw.rect(self.screen, (8, 15, 25), minimap, border_radius=8)
        pygame.draw.rect(self.screen, COLORS["wall_edge"], minimap, 2, border_radius=8)
        scale_x = minimap.width / len(self.tilemap[0])
        scale_y = minimap.height / len(self.tilemap)

        for row, tiles in enumerate(self.tilemap):
            for col, tile in enumerate(tiles):
                if tile == 1:
                    pygame.draw.rect(
                        self.screen,
                        COLORS["wall"],
                        pygame.Rect(
                            minimap.x + int(col * scale_x),
                            minimap.y + int(row * scale_y),
                            max(1, int(scale_x + 1)),
                            max(1, int(scale_y + 1)),
                        ),
                    )

        target_id = self.state.get("mission", {}).get("target_router")
        for name, color in (
            ("COMEDOR", COLORS["chicken"]),
            ("CENTRO MEDICO", COLORS["medical"]),
        ):
            facility = self._facility_state_by_name(name)
            if facility:
                pygame.draw.circle(
                    self.screen,
                    color,
                    (
                        minimap.x + int((facility["col"] + 0.5) * scale_x),
                        minimap.y + int((facility["row"] + 0.5) * scale_y),
                    ),
                    4,
                )
        if target_id:
            router = self.state.get("routers", {}).get(target_id)
            if router:
                pygame.draw.circle(
                    self.screen,
                    COLORS["accent"],
                    (
                        minimap.x + int((router["col"] + 0.5) * scale_x),
                        minimap.y + int((router["row"] + 0.5) * scale_y),
                    ),
                    5,
                    2,
                )
        professor = self.state.get("professor")
        if professor:
            pygame.draw.circle(
                self.screen,
                COLORS["professor"],
                (
                    minimap.x + int((professor["col"] + 0.5) * scale_x),
                    minimap.y + int((professor["row"] + 0.5) * scale_y),
                ),
                3,
            )
        for bomb in self.state.get("bombs", {}).values():
            pygame.draw.circle(
                self.screen,
                COLORS["defeat"],
                (
                    minimap.x + int((bomb["col"] + 0.5) * scale_x),
                    minimap.y + int((bomb["row"] + 0.5) * scale_y),
                ),
                2,
            )
        for player in self.state.get("players", {}).values():
            pygame.draw.circle(
                self.screen,
                parse_hex_color(player["color"]),
                (
                    minimap.x
                    + int((player["x"] / self.tile_size + 0.5) * scale_x),
                    minimap.y
                    + int((player["y"] / self.tile_size + 0.5) * scale_y),
                ),
                3,
            )

        view_rect = pygame.Rect(
            minimap.x + int(self.camera_x / self.tile_size * scale_x),
            minimap.y + int(self.camera_y / self.tile_size * scale_y),
            max(2, int(GAME_WIDTH / self.tile_size * scale_x)),
            max(2, int(VIEWPORT_HEIGHT / self.tile_size * scale_y)),
        )
        pygame.draw.rect(self.screen, COLORS["text"], view_rect, 1)

    def _draw_navigation_arrows(self) -> None:
        assert self.screen is not None
        targets: list[tuple[str, dict[str, Any] | None, tuple[int, int, int]]] = [
            ("POLLO", self._facility_state_by_name("COMEDOR"), COLORS["chicken"]),
            (
                "SALUD",
                self._facility_state_by_name("CENTRO MEDICO"),
                COLORS["medical"],
            ),
        ]
        side_quest = self.state.get("side_quest", {})
        if side_quest.get("status") == "available":
            targets.append(
                ("MONTALVO", self.state.get("professor"), COLORS["professor"])
            )
        elif (
            side_quest.get("status") == "active"
            and side_quest.get("owner_id") == self.player_id
            and side_quest.get("target")
        ):
            targets.append(
                (
                    "EXTRA",
                    self._location_state_by_name(side_quest["target"]),
                    COLORS["professor"],
                )
            )
        target_id = self.state.get("mission", {}).get("target_router")
        if target_id:
            targets.insert(
                0,
                (
                    "MISIÓN",
                    self.state.get("routers", {}).get(target_id),
                    COLORS["accent"],
                ),
            )

        for label, router, color in targets:
            if not router:
                continue
            world_x = (router["col"] + 0.5) * self.tile_size
            world_y = (router["row"] + 0.5) * self.tile_size
            if self._point_visible(world_x, world_y, margin=0):
                continue
            raw_x, raw_y = self._world_to_screen(world_x, world_y)
            point = pygame.Vector2(raw_x, raw_y)
            center = pygame.Vector2(GAME_WIDTH / 2, VIEWPORT_HEIGHT / 2)
            direction = point - center
            if direction.length_squared() == 0:
                continue
            direction = direction.normalize()
            arrow_center = pygame.Vector2(
                max(45, min(GAME_WIDTH - 45, raw_x)),
                max(45, min(VIEWPORT_HEIGHT - 45, raw_y)),
            )
            tip = arrow_center + direction * 15
            side = pygame.Vector2(-direction.y, direction.x) * 9
            pygame.draw.polygon(
                self.screen,
                color,
                [tip, arrow_center - direction * 10 + side, arrow_center - direction * 10 - side],
            )
            text = self.small_font.render(label, True, color)
            self.screen.blit(text, text.get_rect(center=(arrow_center.x, arrow_center.y + 19)))

    def _draw_hud(self) -> None:
        assert self.screen is not None
        map_height = VIEWPORT_HEIGHT
        hud_rect = pygame.Rect(0, map_height, self.screen.get_width(), HUD_HEIGHT)
        pygame.draw.rect(self.screen, COLORS["hud"], hud_rect)

        title = self.title_font.render(
            "LA VIDA DA VUELTAS EN EDUROAM", True, COLORS["text"]
        )
        self.screen.blit(title, (14, map_height + 10))

        mission = self.state.get("mission", {})
        table_width = 330
        content_width = self.screen.get_width() - table_width - 44
        mission_title = (
            f"MISIÓN {mission.get('number', 1)}/{mission.get('total', 4)}: "
            f"{mission.get('title', 'Preparando campaña')}"
        )
        self.screen.blit(
            self.font.render(mission_title, True, COLORS["accent"]),
            (14, map_height + 38),
        )
        self.screen.blit(
            self.small_font.render(
                mission.get("description", ""), True, COLORS["text"]
            ),
            (14, map_height + 61),
        )

        progress = float(mission.get("progress", 0))
        goal = float(mission.get("goal", 1))
        time_remaining = float(mission.get("time_remaining", 0))
        bar_rect = pygame.Rect(14, map_height + 82, min(360, content_width - 230), 14)
        pygame.draw.rect(self.screen, COLORS["input"], bar_rect, border_radius=7)
        fill_width = int(bar_rect.width * min(1.0, progress / max(1.0, goal)))
        if fill_width:
            pygame.draw.rect(
                self.screen,
                COLORS["uni_blue_light"],
                pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height),
                border_radius=7,
            )
        progress_text = self.small_font.render(
            f"Progreso: {progress:g}/{goal:g}  ·  Tiempo: {time_remaining:.1f}s",
            True,
            COLORS["muted"],
        )
        self.screen.blit(progress_text, (385, map_height + 82))

        karma = self.state.get("karma_in", 0)
        repaired = sum(
            1 for router in self.state.get("routers", {}).values() if router["repaired"]
        )
        info = self.font.render(
            f"Karma en {karma:.1f}s  |  Routers activos: "
            f"{repaired}/{self.state.get('max_repaired', 5)}  |  "
            f"Pollo en Comedor: {self.state.get('chicken_stock', 0)}/"
            f"{self.state.get('chicken_max_stock', 3)}",
            True,
            COLORS["muted"],
        )
        self.screen.blit(info, (14, map_height + 107))

        local_player = self.state.get("players", {}).get(str(self.player_id), {})
        health = float(local_player.get("health", 100))
        max_health = float(local_player.get("max_health", 100))
        fatigue = float(local_player.get("fatigue", 0))
        for x, value, maximum, color, label in (
            (14, health, max_health, COLORS["health"], "VIDA"),
            (220, fatigue, 100, COLORS["fatigue"], "CANSANCIO"),
        ):
            bar = pygame.Rect(x + 72, map_height + 133, 115, 12)
            pygame.draw.rect(self.screen, COLORS["input"], bar, border_radius=6)
            width = int(bar.width * min(1.0, value / max(1.0, maximum)))
            if width:
                pygame.draw.rect(
                    self.screen,
                    color,
                    pygame.Rect(bar.x, bar.y, width, bar.height),
                    border_radius=6,
                )
            self.screen.blit(
                self.small_font.render(f"{label} {value:.0f}", True, COLORS["text"]),
                (x, map_height + 132),
            )
        pickup_cooldown = float(
            local_player.get("chicken_pickup_cooldown", 0)
        )
        portions = int(local_player.get("chicken_portions", 0))
        if portions > 0:
            chicken_text = (
                f"POLLO: {portions} PORCIÓN"
                f"{'ES' if portions != 1 else ''} [Q]"
            )
            if local_player.get("chicken_contaminated"):
                chicken_text = "POLLO: MENÚ CON MOSCA [Q]"
        elif pickup_cooldown > 0:
            chicken_text = f"POLLO: RECARGA {pickup_cooldown:.1f}s"
        else:
            chicken_text = "POLLO: DISPONIBLE EN COMEDOR"
        boost = float(local_player.get("chicken_boost_remaining", 0))
        speed = float(local_player.get("speed_multiplier", 1))
        self.screen.blit(
            self.small_font.render(
                f"{chicken_text}  ·  Velocidad x{speed:.2f}"
                + (f" ({boost:.1f}s)" if boost else ""),
                True,
                COLORS["chicken"] if local_player.get("has_chicken") else COLORS["muted"],
            ),
            (430, map_height + 132),
        )
        chicken_icon_x = 414
        chicken_icon_y = map_height + 139
        pygame.draw.circle(
            self.screen,
            COLORS["chicken"] if local_player.get("has_chicken") else COLORS["wall_edge"],
            (chicken_icon_x, chicken_icon_y),
            7,
        )
        pygame.draw.circle(
            self.screen, COLORS["text"], (chicken_icon_x + 7, chicken_icon_y + 5), 3
        )
        players = sorted(
            self.state.get("players", {}).values(),
            key=lambda player: (-player["repairs"], player["name"].lower()),
        )
        table_rect = pygame.Rect(
            self.screen.get_width() - table_width - 14,
            map_height + 10,
            table_width,
            142,
        )
        pygame.draw.rect(self.screen, COLORS["panel"], table_rect, border_radius=10)
        pygame.draw.rect(
            self.screen, COLORS["wall_edge"], table_rect, 1, border_radius=10
        )
        self.screen.blit(
            self.font.render("CLASIFICACIÓN Y KARMA", True, COLORS["accent"]),
            (table_rect.x + 12, table_rect.y + 9),
        )
        achievements = local_player.get("achievements", [])
        achievement_text = self.small_font.render(
            f"LOGROS {len(achievements)}/{self.state.get('achievement_total', 9)}",
            True,
            COLORS["professor"],
        )
        self.screen.blit(
            achievement_text,
            (table_rect.right - achievement_text.get_width() - 12, table_rect.y + 12),
        )
        headers = self.small_font.render(
            "#   JUGADOR             REP.   ESTADO", True, COLORS["muted"]
        )
        self.screen.blit(headers, (table_rect.x + 12, table_rect.y + 34))
        for rank, player in enumerate(players, start=1):
            if player["effect"] == "ping":
                effect = "PING"
                row_color = COLORS["defeat"]
            elif player["effect"] == "fiber":
                effect = "FIBRA"
                row_color = COLORS["victory"]
            elif rank == 1 and len(players) > 1:
                effect = "LÍDER"
                row_color = COLORS["router_ready"]
            elif rank == len(players) and len(players) > 1:
                effect = "ÚLTIMO"
                row_color = COLORS["uni_blue_light"]
            else:
                effect = "-"
                row_color = COLORS["text"]
            name = player["name"][:16]
            row_text = f"{rank:<3} {name:<19} {player['repairs']:<6} {effect}"
            self.screen.blit(
                self.small_font.render(row_text, True, row_color),
                (table_rect.x + 12, table_rect.y + 51 + (rank - 1) * 21),
            )

        events = self.state.get("events", [])
        if events:
            event_text = events[-1]["text"]
            self.screen.blit(
                self.font.render(event_text, True, COLORS["router_ready"]),
                (14, map_height + 156),
            )

        if pygame.time.get_ticks() < self.status_until:
            self.screen.blit(
                self.font.render(self.status_message, True, COLORS["text"]),
                (14, map_height + 180),
            )

    def _draw_damage_flash(self) -> None:
        assert self.screen is not None
        if pygame.time.get_ticks() >= self.damage_flash_until:
            return
        overlay = pygame.Surface((GAME_WIDTH, VIEWPORT_HEIGHT), pygame.SRCALPHA)
        overlay.fill((220, 35, 35, 70))
        self.screen.blit(overlay, (0, 0))

    def _end_button_rects(self) -> tuple[pygame.Rect, pygame.Rect]:
        assert self.screen is not None
        center_x = self.screen.get_width() // 2
        center_y = self.screen.get_height() // 2
        return (
            pygame.Rect(center_x - 225, center_y + 82, 210, 52),
            pygame.Rect(center_x + 15, center_y + 82, 210, 52),
        )

    def _draw_end_overlay(self) -> None:
        assert self.screen is not None
        status = self.state.get("game_status")
        if status not in {"victory", "defeat"}:
            return

        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((5, 10, 18, 215))
        self.screen.blit(overlay, (0, 0))

        center_x = self.screen.get_width() // 2
        center_y = self.screen.get_height() // 2
        victory = status == "victory"
        color = COLORS["victory"] if victory else COLORS["defeat"]
        heading = "¡EDUROAM ESTABILIZADO!" if victory else "CONEXIÓN PERDIDA"
        title = self.menu_title_font.render(heading, True, color)
        self.screen.blit(title, title.get_rect(center=(center_x, center_y - 95)))

        result = self.menu_font.render(
            self.state.get("result_message", ""), True, COLORS["text"]
        )
        self.screen.blit(result, result.get_rect(center=(center_x, center_y - 35)))

        subtitle = self.font.render(
            "El equipo puede reiniciar la campaña o salir del juego.",
            True,
            COLORS["muted"],
        )
        self.screen.blit(subtitle, subtitle.get_rect(center=(center_x, center_y + 5)))

        restart_rect, exit_rect = self._end_button_rects()
        mouse = pygame.mouse.get_pos()
        for rect, label, base_color in (
            (restart_rect, "REINICIAR [R]", COLORS["uni_blue"]),
            (exit_rect, "SALIR [ESC]", COLORS["wall"]),
        ):
            draw_color = (
                COLORS["uni_blue_light"] if rect.collidepoint(mouse) else base_color
            )
            pygame.draw.rect(self.screen, draw_color, rect, border_radius=9)
            text = self.menu_subtitle_font.render(label, True, COLORS["text"])
            self.screen.blit(text, text.get_rect(center=rect.center))

    def run(self) -> None:
        if not self.show_start_screen():
            return
        self.connect()
        running = True
        while running:
            interact = False
            consume_chicken = False
            restart = False
            game_over = self.state.get("game_status") in {"victory", "defeat"}
            restart_rect, exit_rect = self._end_button_rects()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif game_over and event.key in (pygame.K_r, pygame.K_RETURN):
                        restart = True
                    elif not game_over and event.key == pygame.K_e:
                        interact = True
                    elif not game_over and event.key == pygame.K_q:
                        consume_chicken = True
                elif (
                    game_over
                    and event.type == pygame.MOUSEBUTTONDOWN
                    and event.button == 1
                ):
                    if restart_rect.collidepoint(event.pos):
                        restart = True
                    elif exit_rect.collidepoint(event.pos):
                        running = False

            if not running:
                break

            if restart:
                self._exchange("restart", {})
            elif consume_chicken:
                self._exchange("consume_chicken", {})
            elif interact:
                self._exchange("interact", {})
            else:
                self._exchange("input", {} if game_over else self._inputs())

            assert self.screen is not None
            self._update_camera()
            self.screen.fill(COLORS["background"])
            self.screen.set_clip(pygame.Rect(0, 0, GAME_WIDTH, VIEWPORT_HEIGHT))
            self._draw_map()
            self._draw_routers()
            self._draw_facilities()
            self._draw_professor()
            self._draw_bombs()
            self._draw_players()
            self._draw_navigation_arrows()
            self._draw_minimap()
            self._draw_side_quest()
            self._draw_food_event_alert()
            self._draw_damage_flash()
            self.screen.set_clip(None)
            self._draw_hud()
            self._draw_end_overlay()
            pygame.display.flip()
            self.clock.tick(FPS)

    def close(self) -> None:
        try:
            if self.network.connected:
                self.network.send(
                    {
                        "type": "disconnect",
                        "payload": {},
                        "request_id": self._next_request_id(),
                    }
                )
        except NetworkError:
            pass
        finally:
            self.network.close()
            pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--name", default="")
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Desactiva los efectos de sonido (útil en entornos sin audio).",
    )
    args = parser.parse_args()

    client = GameClient(
        args.host, args.port, args.name, audio_enabled=not args.no_audio
    )
    try:
        client.run()
    except NetworkError as exc:
        print(f"Error de red: {exc}")
        raise SystemExit(1) from exc
    finally:
        client.close()


if __name__ == "__main__":
    main()
