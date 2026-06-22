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
HUD_HEIGHT = 150
PLAYER_SIZE = 20

COLORS = {
    "background": (13, 20, 32),
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
        self.repair_window = (0.0, 10.0)
        self.state: dict[str, Any] = {}
        self.last_event_id = 0
        self.status_message = "Conectando..."
        self.status_until = 0
        self.request_counter = 0

        pygame.init()
        pygame.display.set_caption("La vida da vueltas en Eduroam")
        self.screen: pygame.Surface | None = None
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 16)
        self.small_font = pygame.font.SysFont("consolas", 11)
        self.title_font = pygame.font.SysFont("consolas", 20, bold=True)

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
        self.screen.blit(info, (14, map_height + 38))

        players = sorted(
            self.state.get("players", {}).values(),
            key=lambda player: (-player["repairs"], player["name"]),
        )
        scoreboard = "  |  ".join(
            f"{player['name']}: {player['repairs']}"
            + (
                f" [{player['effect']} {player['effect_remaining']:.1f}s]"
                if player["effect"]
                else ""
            )
            for player in players
        )
        self.screen.blit(
            self.font.render(scoreboard, True, COLORS["text"]),
            (14, map_height + 66),
        )

        events = self.state.get("events", [])
        if events:
            newest = events[-1]
            if newest["id"] > self.last_event_id:
                self.last_event_id = newest["id"]
            event_text = newest["text"]
            self.screen.blit(
                self.font.render(event_text, True, COLORS["router_ready"]),
                (14, map_height + 94),
            )

        if pygame.time.get_ticks() < self.status_until:
            self.screen.blit(
                self.font.render(self.status_message, True, COLORS["text"]),
                (14, map_height + 120),
            )

    def run(self) -> None:
        self.connect()
        running = True
        while running:
            interact = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_e:
                        interact = True

            if not running:
                break

            if interact:
                self._exchange("interact", {})
            else:
                self._exchange("input", self._inputs())

            assert self.screen is not None
            self.screen.fill(COLORS["background"])
            self._draw_map()
            self._draw_routers()
            self._draw_players()
            self._draw_hud()
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
    parser.add_argument("--name", default="Jugador UNI")
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
