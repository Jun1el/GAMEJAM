"""Cliente Pygame para "La vida da vueltas en Eduroam"."""

from __future__ import annotations

import argparse
import sys
import uuid
from typing import Any

try:
    import pygame
except ImportError:
    print("Pygame no está instalado. Ejecuta: python -m pip install pygame")
    raise SystemExit(1)

from network import DEFAULT_HOST, DEFAULT_PORT, Network, NetworkError


FPS = 30
HUD_HEIGHT = 205
PLAYER_SIZE = 20
START_WIDTH = 900
START_HEIGHT = 600

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
}


def parse_hex_color(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


class GameClient:
    def __init__(self, host: str, port: int, name: str) -> None:
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
            "Pulsa E  ·  Repara la conexión antes de que el indicador siga girando",
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

        width = len(self.tilemap[0]) * self.tile_size
        height = len(self.tilemap) * self.tile_size + HUD_HEIGHT
        self.screen = pygame.display.set_mode((width, height))
        self.status_message = "Conectado. WASD/flechas para moverte; E para reparar."
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
        interaction = response_payload.get("interaction")
        if interaction:
            self.status_message = interaction["message"]
            self.status_until = pygame.time.get_ticks() + 2500

    def _draw_map(self) -> None:
        assert self.screen is not None
        for row, tiles in enumerate(self.tilemap):
            for col, tile in enumerate(tiles):
                rect = pygame.Rect(
                    col * self.tile_size,
                    row * self.tile_size,
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
            center = (
                int((router["col"] + 0.5) * self.tile_size),
                int((router["row"] + 0.5) * self.tile_size),
            )
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
            rect = pygame.Rect(
                round(player["x"]),
                round(player["y"]),
                PLAYER_SIZE,
                PLAYER_SIZE,
            )
            color = parse_hex_color(player["color"])
            pygame.draw.rect(self.screen, color, rect, border_radius=5)
            border = (255, 255, 255) if int(key) == self.player_id else COLORS["background"]
            pygame.draw.rect(self.screen, border, rect, 2, border_radius=5)

            label = self.small_font.render(player["name"], True, COLORS["text"])
            self.screen.blit(label, label.get_rect(midbottom=(rect.centerx, rect.top - 2)))

    def _draw_hud(self) -> None:
        assert self.screen is not None
        map_height = len(self.tilemap) * self.tile_size
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
            f"{repaired}/{self.state.get('max_repaired', 5)}",
            True,
            COLORS["muted"],
        )
        self.screen.blit(info, (14, map_height + 107))

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
            newest = events[-1]
            if newest["id"] > self.last_event_id:
                self.last_event_id = newest["id"]
            event_text = newest["text"]
            self.screen.blit(
                self.font.render(event_text, True, COLORS["router_ready"]),
                (14, map_height + 143),
            )

        if pygame.time.get_ticks() < self.status_until:
            self.screen.blit(
                self.font.render(self.status_message, True, COLORS["text"]),
                (14, map_height + 169),
            )

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
            elif interact:
                self._exchange("interact", {})
            else:
                self._exchange("input", {} if game_over else self._inputs())

            assert self.screen is not None
            self.screen.fill(COLORS["background"])
            self._draw_map()
            self._draw_routers()
            self._draw_players()
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
    args = parser.parse_args()

    client = GameClient(args.host, args.port, args.name)
    try:
        client.run()
    except NetworkError as exc:
        print(f"Error de red: {exc}")
        raise SystemExit(1) from exc
    finally:
        client.close()


if __name__ == "__main__":
    main()
