"""Servidor autoritativo para "La vida da vueltas en Eduroam"."""

from __future__ import annotations

import argparse
import math
import random
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from network import (
    DEFAULT_PORT,
    ConnectionClosedError,
    NetworkError,
    ProtocolError,
    receive_message,
    send_message,
)


MAPA_UNI = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 2, 0, 0, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 2, 0, 2, 1],
    [1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1],
    [1, 1, 1, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 2, 1],
    [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1],
    [1, 2, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 0, 1],
    [1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1],
    [1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

# Coordenadas entregadas por el usuario, convertidas de fila/columna 1-based.
ROUTER_NAMES = {
    (1, 23): "FIGMM",
    (3, 7): "FIEE",
    (3, 13): "BIBLIOTECA",
    (3, 17): "COMEDOR",
    (3, 21): "FIEECS",
    (3, 25): "FIC",
    (3, 27): "FIA",
    (3, 29): "FIQT",
    (5, 3): "CTIC",
    (5, 29): "FIM",
    (7, 1): "FIIS",
    (7, 7): "FC",
    (7, 13): "ESTADIO UNI",
    (7, 21): "CENTRO MEDICO",
    (7, 25): "FAUA",
    (9, 3): "FIP",
    (9, 7): "ENTRADA",
    (9, 27): "SALIDA",
}

TILE_SIZE = 32
PLAYER_SIZE = 20
BASE_SPEED = 120.0
SERVER_TICK_RATE = 30
MAX_PLAYERS = 4
MAX_REPAIRED_ROUTERS = 5
ROUTER_ROTATION_SPEED = 90.0
REPAIR_MIN_ANGLE = 0.0
REPAIR_MAX_ANGLE = 10.0
INTERACTION_DISTANCE = TILE_SIZE * 1.35
KARMA_INTERVAL = 60.0
KARMA_DURATION = 10.0
PING_SPEED_MULTIPLIER = 0.25
FIBER_SPEED_MULTIPLIER = 2.0

PLAYER_COLORS = ["#4FC3F7", "#FF6F91", "#FFD166", "#A78BFA"]
SPAWN_TILES = [(2, 23), (3, 8), (7, 2), (7, 28)]


@dataclass
class Player:
    player_id: int
    name: str
    x: float
    y: float
    color: str
    repairs: int = 0
    inputs: dict[str, bool] = field(
        default_factory=lambda: {
            "up": False,
            "down": False,
            "left": False,
            "right": False,
        }
    )
    effect: str | None = None
    effect_until: float = 0.0


@dataclass
class Router:
    router_id: str
    row: int
    col: int
    name: str
    rotation: float
    repaired: bool = False
    repaired_by: int | None = None


class GameState:
    """Estado protegido y lógica autoritativa independiente de los sockets."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.lock = threading.RLock()
        self.rng = rng or random.Random()
        self.players: dict[int, Player] = {}
        self.routers: dict[str, Router] = {}
        self.next_player_id = 1
        self.next_karma_at = time.monotonic() + KARMA_INTERVAL
        self.event_sequence = 0
        self.events: list[dict[str, Any]] = []

        for row, tiles in enumerate(MAPA_UNI):
            for col, tile in enumerate(tiles):
                if tile == 2:
                    router_id = f"router_{row + 1}_{col + 1}"
                    self.routers[router_id] = Router(
                        router_id=router_id,
                        row=row,
                        col=col,
                        name=ROUTER_NAMES.get((row, col), router_id),
                        rotation=self.rng.uniform(0.0, 360.0),
                    )

    def _add_event(self, kind: str, text: str) -> None:
        self.event_sequence += 1
        self.events.append(
            {"id": self.event_sequence, "kind": kind, "text": text}
        )
        self.events = self.events[-20:]

    def add_player(self, name: str) -> Player | None:
        with self.lock:
            if len(self.players) >= MAX_PLAYERS:
                return None

            player_id = self.next_player_id
            self.next_player_id += 1
            row, col = SPAWN_TILES[(player_id - 1) % len(SPAWN_TILES)]
            player = Player(
                player_id=player_id,
                name=(name.strip() or f"Jugador {player_id}")[:20],
                x=col * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2,
                y=row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2,
                color=PLAYER_COLORS[(player_id - 1) % len(PLAYER_COLORS)],
            )
            self.players[player_id] = player
            self._add_event("join", f"{player.name} se conectó.")
            return player

    def remove_player(self, player_id: int) -> None:
        with self.lock:
            player = self.players.pop(player_id, None)
            if player:
                self._add_event("leave", f"{player.name} se desconectó.")

    def set_inputs(self, player_id: int, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise ProtocolError("El payload de input debe ser un objeto.")
        with self.lock:
            player = self.players.get(player_id)
            if not player:
                return
            for key in player.inputs:
                player.inputs[key] = payload.get(key) is True

    def _collides_with_wall(self, x: float, y: float) -> bool:
        left = int(x // TILE_SIZE)
        right = int((x + PLAYER_SIZE - 1) // TILE_SIZE)
        top = int(y // TILE_SIZE)
        bottom = int((y + PLAYER_SIZE - 1) // TILE_SIZE)

        for row in range(top, bottom + 1):
            for col in range(left, right + 1):
                if (
                    row < 0
                    or row >= len(MAPA_UNI)
                    or col < 0
                    or col >= len(MAPA_UNI[0])
                    or MAPA_UNI[row][col] == 1
                ):
                    return True
        return False

    def _move_player(self, player: Player, dt: float, now: float) -> None:
        if player.effect and now >= player.effect_until:
            player.effect = None
            player.effect_until = 0.0

        horizontal = int(player.inputs["right"]) - int(player.inputs["left"])
        vertical = int(player.inputs["down"]) - int(player.inputs["up"])
        if horizontal == 0 and vertical == 0:
            return

        length = math.hypot(horizontal, vertical)
        multiplier = 1.0
        if player.effect == "ping":
            multiplier = PING_SPEED_MULTIPLIER
        elif player.effect == "fiber":
            multiplier = FIBER_SPEED_MULTIPLIER

        distance = BASE_SPEED * multiplier * min(dt, 0.1)
        dx = horizontal / length * distance
        dy = vertical / length * distance

        next_x = player.x + dx
        if not self._collides_with_wall(next_x, player.y):
            player.x = next_x
        next_y = player.y + dy
        if not self._collides_with_wall(player.x, next_y):
            player.y = next_y

    def update(self, dt: float, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self.lock:
            for router in self.routers.values():
                router.rotation = (
                    router.rotation + ROUTER_ROTATION_SPEED * min(dt, 0.1)
                ) % 360.0
            for player in self.players.values():
                self._move_player(player, dt, now)
            if now >= self.next_karma_at:
                self._apply_karma(now)
                while self.next_karma_at <= now:
                    self.next_karma_at += KARMA_INTERVAL

    def _apply_karma(self, now: float) -> None:
        if len(self.players) < 2:
            return

        players = list(self.players.values())
        highest = max(player.repairs for player in players)
        top = self.rng.choice([p for p in players if p.repairs == highest])
        remaining = [p for p in players if p.player_id != top.player_id]
        lowest = min(player.repairs for player in remaining)
        bottom = self.rng.choice([p for p in remaining if p.repairs == lowest])

        top.effect = "ping"
        top.effect_until = now + KARMA_DURATION
        bottom.effect = "fiber"
        bottom.effect_until = now + KARMA_DURATION
        self._add_event(
            "karma",
            f"Karma: {top.name} recibió Ping 999ms y "
            f"{bottom.name} recibió Fibra Óptica.",
        )

    def interact(self, player_id: int) -> tuple[bool, str]:
        with self.lock:
            player = self.players.get(player_id)
            if not player:
                return False, "Jugador inexistente."

            center_x = player.x + PLAYER_SIZE / 2
            center_y = player.y + PLAYER_SIZE / 2
            nearby = [
                router
                for router in self.routers.values()
                if not router.repaired
                and math.hypot(
                    center_x - (router.col + 0.5) * TILE_SIZE,
                    center_y - (router.row + 0.5) * TILE_SIZE,
                )
                <= INTERACTION_DISTANCE
            ]
            if not nearby:
                return False, "No hay un router caído suficientemente cerca."

            router = min(
                nearby,
                key=lambda item: math.hypot(
                    center_x - (item.col + 0.5) * TILE_SIZE,
                    center_y - (item.row + 0.5) * TILE_SIZE,
                ),
            )
            if not REPAIR_MIN_ANGLE <= router.rotation <= REPAIR_MAX_ANGLE:
                return (
                    False,
                    f"{router.name}: mala sincronización "
                    f"({router.rotation:.0f}°).",
                )

            repaired = [item for item in self.routers.values() if item.repaired]
            if len(repaired) >= MAX_REPAIRED_ROUTERS:
                broken = self.rng.choice(repaired)
                broken.repaired = False
                broken.repaired_by = None
                self._add_event(
                    "cycle",
                    f"El ciclo del lag derribó el router de {broken.name}.",
                )

            router.repaired = True
            router.repaired_by = player_id
            player.repairs += 1
            text = f"{player.name} reparó el router de {router.name}."
            self._add_event("repair", text)
            return True, text

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        now = time.monotonic() if now is None else now
        with self.lock:
            return {
                "players": {
                    str(player_id): {
                        "id": player.player_id,
                        "name": player.name,
                        "x": round(player.x, 2),
                        "y": round(player.y, 2),
                        "color": player.color,
                        "repairs": player.repairs,
                        "effect": player.effect,
                        "effect_remaining": round(
                            max(0.0, player.effect_until - now), 1
                        ),
                    }
                    for player_id, player in self.players.items()
                },
                "routers": {
                    router_id: {
                        "id": router.router_id,
                        "row": router.row,
                        "col": router.col,
                        "name": router.name,
                        "rotation": round(router.rotation, 1),
                        "repaired": router.repaired,
                    }
                    for router_id, router in self.routers.items()
                },
                "events": list(self.events),
                "karma_in": round(max(0.0, self.next_karma_at - now), 1),
                "max_repaired": MAX_REPAIRED_ROUTERS,
            }


class GameServer:
    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.game = GameState()
        self.running = threading.Event()
        self.server_socket: socket.socket | None = None

    def _update_loop(self) -> None:
        tick = 1.0 / SERVER_TICK_RATE
        previous = time.monotonic()
        while self.running.is_set():
            started = time.monotonic()
            self.game.update(started - previous, started)
            previous = started
            time.sleep(max(0.0, tick - (time.monotonic() - started)))

    def _client_loop(
        self, connection: socket.socket, address: tuple[str, int]
    ) -> None:
        player: Player | None = None
        try:
            first = receive_message(connection)
            if first.get("type") != "join":
                raise ProtocolError("El primer mensaje debe ser de tipo 'join'.")
            payload = first.get("payload")
            name = payload.get("name", "") if isinstance(payload, dict) else ""
            player = self.game.add_player(str(name))
            if player is None:
                send_message(
                    connection,
                    {"type": "error", "payload": {"message": "Servidor lleno."}},
                )
                return

            send_message(
                connection,
                {
                    "type": "welcome",
                    "payload": {
                        "player_id": player.player_id,
                        "map": MAPA_UNI,
                        "tile_size": TILE_SIZE,
                        "repair_window": [
                            REPAIR_MIN_ANGLE,
                            REPAIR_MAX_ANGLE,
                        ],
                        "state": self.game.snapshot(),
                    },
                    "request_id": first.get("request_id"),
                },
            )
            print(f"[+] {player.name} ({address[0]}:{address[1]})")

            while self.running.is_set():
                message = receive_message(connection)
                message_type = message.get("type")
                interaction_result: dict[str, Any] | None = None

                if message_type == "input":
                    self.game.set_inputs(player.player_id, message.get("payload"))
                elif message_type == "interact":
                    success, text = self.game.interact(player.player_id)
                    interaction_result = {"success": success, "message": text}
                elif message_type == "disconnect":
                    break
                else:
                    raise ProtocolError(
                        f"Tipo de mensaje desconocido: {message_type!r}."
                    )

                send_message(
                    connection,
                    {
                        "type": "state",
                        "payload": {
                            "state": self.game.snapshot(),
                            "interaction": interaction_result,
                        },
                        "request_id": message.get("request_id"),
                    },
                )
        except (ConnectionClosedError, NetworkError, OSError) as exc:
            print(f"[!] Cliente {address[0]}:{address[1]}: {exc}")
        finally:
            if player:
                self.game.remove_player(player.player_id)
            try:
                connection.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(MAX_PLAYERS)
        self.running.set()
        threading.Thread(target=self._update_loop, daemon=True).start()
        print(f"Servidor escuchando en {self.host}:{self.port}")

        try:
            while self.running.is_set():
                connection, address = self.server_socket.accept()
                threading.Thread(
                    target=self._client_loop,
                    args=(connection, address),
                    daemon=True,
                ).start()
        except KeyboardInterrupt:
            print("\nCerrando servidor...")
        finally:
            self.running.clear()
            if self.server_socket:
                self.server_socket.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    GameServer(args.host, args.port).serve_forever()


if __name__ == "__main__":
    main()
