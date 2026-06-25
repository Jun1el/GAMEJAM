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


BASE_MAPA_UNI = [
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

BASE_ROUTER_NAMES = {
    (1, 23): "FIGMM",
    (3, 7): "FIEE",
    (3, 13): "BIBLIOTECA",
    (3, 21): "FIEECS",
    (3, 25): "FIC",
    (3, 27): "FIA",
    (3, 29): "FIQT",
    (5, 3): "CTIC",
    (5, 29): "FIM",
    (7, 1): "FIIS",
    (7, 7): "FC",
    (7, 13): "ESTADIO UNI",
    (7, 25): "FAUA",
    (9, 3): "FIP",
    (9, 7): "ENTRADA",
    (9, 27): "SALIDA",
}

BASE_FACILITY_NAMES = {
    (3, 17): ("COMEDOR", "food"),
    (7, 21): ("CENTRO MEDICO", "medical"),
}


def _expand_map() -> list[list[int]]:
    """Duplica la geometría sin duplicar los routers de cada facultad."""
    expanded: list[list[int]] = []
    for base_row_index, base_row in enumerate(BASE_MAPA_UNI):
        upper: list[int] = []
        lower: list[int] = []
        for base_col_index, tile in enumerate(base_row):
            if tile == 1:
                upper.extend((1, 1))
                lower.extend((1, 1))
            elif tile == 2:
                upper.extend((0, 0))
                lower.extend(
                    (0, 0)
                    if (base_row_index, base_col_index) in BASE_FACILITY_NAMES
                    else (0, 2)
                )
            else:
                upper.extend((0, 0))
                lower.extend((0, 0))
        expanded.extend((upper, lower))
    return expanded


MAPA_UNI = _expand_map()
ROUTER_NAMES = {
    (row * 2 + 1, col * 2 + 1): name
    for (row, col), name in BASE_ROUTER_NAMES.items()
}
FACILITY_NAMES = {
    (row * 2 + 1, col * 2 + 1): (name, facility_type)
    for (row, col), (name, facility_type) in BASE_FACILITY_NAMES.items()
}

TILE_SIZE = 32
PLAYER_SIZE = 20
BASE_SPEED = 120.0
SERVER_TICK_RATE = 30
MAX_PLAYERS = 4
MAX_REPAIRED_ROUTERS = 5
ROUTER_ROTATION_SPEED = 90.0
REPAIR_MIN_ANGLE = 0.0
REPAIR_MAX_ANGLE = 90.0
INTERACTION_DISTANCE = TILE_SIZE * 1.35
KARMA_INTERVAL = 60.0
KARMA_DURATION = 10.0
PING_SPEED_MULTIPLIER = 0.25
FIBER_SPEED_MULTIPLIER = 2.0
MAX_HEALTH = 100.0
MAX_FATIGUE = 100.0
REPAIR_FATIGUE = 15.0
FAILED_REPAIR_DAMAGE = 10.0
MIN_FATIGUE_SPEED = 0.5
CHICKEN_HEAL = 25.0
CHICKEN_FATIGUE_RECOVERY = 50.0
CHICKEN_SPEED_MULTIPLIER = 1.35
CHICKEN_BOOST_DURATION = 8.0
CHICKEN_MAX_STOCK = 3
CHICKEN_RESTOCK_INTERVAL = 20.0
CHICKEN_PICKUP_COOLDOWN = 15.0
FOOD_EVENT_MIN_INTERVAL = 60.0
FOOD_EVENT_MAX_INTERVAL = 90.0
FOOD_EVENT_DURATION = 20.0
SIDE_QUEST_DURATION = 120.0
MEDICAL_HEAL_PER_SECOND = 12.0
MEDICAL_DAMAGE_COOLDOWN = 2.0
BOMB_MIN_INTERVAL = 12.0
BOMB_MAX_INTERVAL = 18.0
BOMB_FUSE = 3.0
BOMB_DAMAGE = 30.0
BOMB_RADIUS = TILE_SIZE * 2.0
BOMB_MAX_ACTIVE = 3
BOMB_EXPLOSION_DISPLAY = 0.6
SAFE_ZONE_RADIUS_TILES = 3.0
RESPAWN_INVULNERABILITY = 3.0
MAX_TOTAL_SPEED_MULTIPLIER = 2.5
POWERUP_MIN_INTERVAL = 22.0
POWERUP_MAX_INTERVAL = 38.0
POWERUP_LIFETIME = 25.0
POWERUP_MAX_ACTIVE = 2
POWERUP_PICKUP_DISTANCE = TILE_SIZE * 0.9
SHIELD_DURATION = 8.0
LAG_FREEZE_DURATION = 12.0
POWERUP_KINDS = ("shield", "instant_repair", "freeze")

PLAYER_COLORS = ["#4FC3F7", "#FF6F91", "#FFD166", "#A78BFA"]
SPAWN_TILES = [(row * 2 + 1, col * 2 + 1) for row, col in [
    (2, 23), (3, 8), (7, 2), (7, 28)
]]
CRITICAL_ROUTE_LENGTH = 4
MISSION_DURATIONS = [120.0, 180.0, 150.0, 120.0]
COVERAGE_HOLD_TIME = 15.0
BLACKOUT_HOLD_TIME = 10.0

MISSIONS = [
    {
        "id": "diagnosis",
        "title": "Diagnóstico del campus",
        "description": "Reparen 3 routers diferentes para localizar las fallas.",
        "goal": 3,
    },
    {
        "id": "critical_route",
        "title": "Ruta crítica",
        "description": "Reparen los routers indicados en el orden mostrado.",
        "goal": CRITICAL_ROUTE_LENGTH,
    },
    {
        "id": "coverage",
        "title": "Cobertura UNI",
        "description": (
            "Activen 1 router por zona (superior, central e inferior) y "
            "mantengan los 3 verdes durante 15 segundos."
        ),
        "goal": COVERAGE_HOLD_TIME,
    },
    {
        "id": "blackout",
        "title": "Apagón general",
        "description": (
            "Activen 5 routers y manténganlos estables durante 10 segundos."
        ),
        "goal": BLACKOUT_HOLD_TIME,
    },
]

SIDE_QUESTS = [
    {
        "id": "control_sorpresa",
        "title": "Control sorpresa",
        "description": "Repara 2 routers antes de que el Prof. Montalvo revise la lista.",
        "goal": 2,
        "kind": "repairs",
    },
    {
        "id": "no_era_para_hoy",
        "title": "No era para hoy",
        "description": "Ve a SALIDA y regresa con el Prof. Montalvo.",
        "goal": 2,
        "kind": "route",
        "route": ["SALIDA", "PROF. MONTALVO"],
    },
    {
        "id": "vuelta_del_silabo",
        "title": "La vuelta del sílabo",
        "description": "Visita BIBLIOTECA, COMEDOR y CENTRO MEDICO en ese orden.",
        "goal": 3,
        "kind": "route",
        "route": ["BIBLIOTECA", "COMEDOR", "CENTRO MEDICO"],
    },
]

ACHIEVEMENTS = {
    "primera_vuelta": ("Primera vuelta", "Reparaste tu primer router."),
    "doble_uni": ("¡DOBLEEE!", "Recogiste el legendario menú doble."),
    "triple_uni": ("¡TRIPLEEE!", "Encontraste el rarísimo menú triple."),
    "menu_con_mosca": ("Proteína extra", "Sobreviviste al menú con mosca."),
    "paciente_modelo": (
        "Paciente modelo",
        "Te recuperaste por completo en el Centro Médico.",
    ),
    "alumno_montalvo": (
        "Aprobado por Montalvo",
        "Completaste su misión secundaria absurda.",
    ),
    "tour_uni": ("Tour UNI", "Reparaste routers en ocho lugares diferentes."),
    "raton_biblioteca": (
        "Ratón de biblioteca",
        "Reparaste la conexión de la Biblioteca.",
    ),
    "estadio_agotado": (
        "Tiempo suplementario",
        "Reparaste el Estadio UNI con al menos 60 de cansancio.",
    ),
}

PROFESSOR_ROW = 11
PROFESSOR_COL = 9


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
    health: float = MAX_HEALTH
    fatigue: float = 0.0
    chicken_portions: int = 0
    chicken_contaminated: bool = False
    next_chicken_pickup_at: float = 0.0
    chicken_boost_until: float = 0.0
    invulnerable_until: float = 0.0
    healing_blocked_until: float = 0.0
    instant_repairs: int = 0
    repaired_locations: set[str] = field(default_factory=set)
    achievements: set[str] = field(default_factory=set)


@dataclass
class Router:
    router_id: str
    row: int
    col: int
    name: str
    rotation: float
    repaired: bool = False
    repaired_by: int | None = None


@dataclass(frozen=True)
class Facility:
    facility_id: str
    row: int
    col: int
    name: str
    facility_type: str


@dataclass
class Bomb:
    bomb_id: int
    row: int
    col: int
    explode_at: float
    exploded_at: float | None = None


@dataclass
class PowerUp:
    powerup_id: int
    row: int
    col: int
    kind: str
    expires_at: float


class GameState:
    """Estado protegido y lógica autoritativa independiente de los sockets."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.lock = threading.RLock()
        self.rng = rng or random.Random()
        self.players: dict[int, Player] = {}
        self.routers: dict[str, Router] = {}
        self.facilities: dict[str, Facility] = {}
        self.next_player_id = 1
        self.next_karma_at = time.monotonic() + KARMA_INTERVAL
        self.event_sequence = 0
        self.events: list[dict[str, Any]] = []
        self.game_status = "playing"
        self.result_message = ""
        self.mission_index = 0
        self.mission_started_at: float | None = None
        self.mission_deadline: float | None = None
        self.mission_repaired: set[str] = set()
        self.route_progress = 0
        self.critical_route: list[str] = []
        self.hold_started_at: float | None = None
        self.chicken_stock = CHICKEN_MAX_STOCK
        self.next_chicken_restock_at = time.monotonic() + CHICKEN_RESTOCK_INTERVAL
        self.bombs: dict[int, Bomb] = {}
        self.next_bomb_id = 1
        self.next_bomb_at = time.monotonic() + self.rng.uniform(
            BOMB_MIN_INTERVAL, BOMB_MAX_INTERVAL
        )
        self.powerups: dict[int, PowerUp] = {}
        self.next_powerup_id = 1
        self.next_powerup_at = time.monotonic() + self.rng.uniform(
            POWERUP_MIN_INTERVAL, POWERUP_MAX_INTERVAL
        )
        self.lag_freeze_until = 0.0
        self.food_event = "normal"
        self.food_event_until = 0.0
        self.next_food_event_at = time.monotonic() + self.rng.uniform(
            FOOD_EVENT_MIN_INTERVAL, FOOD_EVENT_MAX_INTERVAL
        )
        self.food_event_sequence = 0
        self.side_quest = dict(self.rng.choice(SIDE_QUESTS))
        self.side_quest_status = "available"
        self.side_quest_owner_id: int | None = None
        self.side_quest_progress = 0
        self.side_quest_deadline: float | None = None

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
        for (row, col), (name, facility_type) in FACILITY_NAMES.items():
            facility_id = f"facility_{facility_type}"
            self.facilities[facility_id] = Facility(
                facility_id=facility_id,
                row=row,
                col=col,
                name=name,
                facility_type=facility_type,
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
            if self.mission_started_at is None and self.game_status == "playing":
                self._begin_mission(0, time.monotonic())
            return player

    def remove_player(self, player_id: int) -> None:
        with self.lock:
            player = self.players.pop(player_id, None)
            if player:
                self._add_event("leave", f"{player.name} se desconectó.")
                if (
                    self.side_quest_status == "active"
                    and self.side_quest_owner_id == player_id
                ):
                    self.side_quest_status = "available"
                    self.side_quest_owner_id = None
                    self.side_quest_progress = 0
                    self.side_quest_deadline = None

    def set_inputs(self, player_id: int, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise ProtocolError("El payload de input debe ser un objeto.")
        with self.lock:
            player = self.players.get(player_id)
            if not player:
                return
            for key in player.inputs:
                player.inputs[key] = payload.get(key) is True

    def _router_by_name(self, name: str) -> Router:
        return next(router for router in self.routers.values() if router.name == name)

    def _facility_by_name(self, name: str) -> Facility:
        return next(
            facility for facility in self.facilities.values() if facility.name == name
        )

    def _place_player_at_spawn(self, player: Player, index: int = 0) -> None:
        row, col = SPAWN_TILES[index % len(SPAWN_TILES)]
        player.x = col * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2
        player.y = row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2

    def _place_player_at_router(self, player: Player, router_name: str) -> None:
        router = self._router_by_name(router_name)
        player.x = router.col * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2
        player.y = router.row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2

    @staticmethod
    def _player_center(player: Player) -> tuple[float, float]:
        return player.x + PLAYER_SIZE / 2, player.y + PLAYER_SIZE / 2

    def _near_facility(self, player: Player, facility_name: str) -> bool:
        facility = self._facility_by_name(facility_name)
        center_x, center_y = self._player_center(player)
        return (
            math.hypot(
                center_x - (facility.col + 0.5) * TILE_SIZE,
                center_y - (facility.row + 0.5) * TILE_SIZE,
            )
            <= INTERACTION_DISTANCE
        )

    def _near_professor(self, player: Player) -> bool:
        center_x, center_y = self._player_center(player)
        return (
            math.hypot(
                center_x - (PROFESSOR_COL + 0.5) * TILE_SIZE,
                center_y - (PROFESSOR_ROW + 0.5) * TILE_SIZE,
            )
            <= INTERACTION_DISTANCE
        )

    def _near_named_location(self, player: Player, name: str) -> bool:
        if name == "PROF. MONTALVO":
            return self._near_professor(player)
        try:
            router = self._router_by_name(name)
            center_x, center_y = self._player_center(player)
            return (
                math.hypot(
                    center_x - (router.col + 0.5) * TILE_SIZE,
                    center_y - (router.row + 0.5) * TILE_SIZE,
                )
                <= INTERACTION_DISTANCE
            )
        except StopIteration:
            return self._near_facility(player, name)

    def _unlock_achievement(self, player: Player, achievement_id: str) -> None:
        if achievement_id in player.achievements:
            return
        player.achievements.add(achievement_id)
        title, _ = ACHIEVEMENTS[achievement_id]
        self._add_event(
            "achievement",
            f"¡Logro secreto de {player.name}: {title}!",
        )

    def _accept_side_quest(
        self, player: Player, now: float
    ) -> tuple[bool, str] | None:
        if not self._near_professor(player):
            return None
        if self.side_quest_status == "available":
            self.side_quest_status = "active"
            self.side_quest_owner_id = player.player_id
            self.side_quest_progress = 0
            self.side_quest_deadline = now + SIDE_QUEST_DURATION
            text = (
                f"Prof. Montalvo: «{self.side_quest['title']}». "
                f"{self.side_quest['description']}"
            )
            self._add_event("professor", text)
            return True, text
        if self.side_quest_owner_id == player.player_id:
            if self.side_quest_status == "completed":
                return False, "Prof. Montalvo: «Ya aprobaste. No abuses de la nota»."
            if self.side_quest_status == "failed":
                return False, "Prof. Montalvo: «La próxima revisa el aula virtual»."
            return False, "Prof. Montalvo: «La práctica sigue pendiente»."
        return False, "Prof. Montalvo ya encargó la práctica a otro estudiante."

    def _complete_side_quest(self, player: Player) -> None:
        self.side_quest_status = "completed"
        self.side_quest_deadline = None
        player.fatigue = max(0.0, player.fatigue - 40.0)
        self._unlock_achievement(player, "alumno_montalvo")
        self._add_event(
            "professor",
            f"Prof. Montalvo aprobó a {player.name} y le redujo 40 de cansancio.",
        )

    def _update_side_quest(self, now: float) -> None:
        if self.side_quest_status != "active":
            return
        if self.side_quest_deadline is not None and now >= self.side_quest_deadline:
            self.side_quest_status = "failed"
            self._add_event(
                "professor",
                "Prof. Montalvo cerró la práctica: se agotó el tiempo.",
            )
            return
        player = self.players.get(self.side_quest_owner_id or -1)
        if not player or self.side_quest.get("kind") != "route":
            return
        route = self.side_quest.get("route", [])
        if (
            self.side_quest_progress < len(route)
            and self._near_named_location(player, route[self.side_quest_progress])
        ):
            self.side_quest_progress += 1
            if self.side_quest_progress >= int(self.side_quest["goal"]):
                self._complete_side_quest(player)

    def _start_food_event(self, now: float) -> None:
        roll = self.rng.random()
        if roll < 0.65:
            self.food_event = "double"
            alert = "¡DOBLEEE! El Comedor entrega dos porciones."
        elif roll < 0.75:
            self.food_event = "triple"
            alert = "¡TRIPLEEE! Hoy la bandeja desafía la economía."
        else:
            self.food_event = "fly"
            alert = "¡MENÚ CON MOSCA! Come bajo tu propio riesgo."
        self.food_event_until = now + FOOD_EVENT_DURATION
        self.food_event_sequence += 1
        self._add_event("food_event", alert)

    def _update_food_event(self, now: float) -> None:
        if self.food_event != "normal" and now >= self.food_event_until:
            self.food_event = "normal"
            self.food_event_until = 0.0
        if now >= self.next_food_event_at:
            self._start_food_event(now)
            self.next_food_event_at = now + self.rng.uniform(
                FOOD_EVENT_MIN_INTERVAL, FOOD_EVENT_MAX_INTERVAL
            )

    def _speed_multiplier(self, player: Player, now: float) -> float:
        fatigue_multiplier = max(
            MIN_FATIGUE_SPEED,
            1.0 - 0.5 * min(MAX_FATIGUE, player.fatigue) / MAX_FATIGUE,
        )
        karma_multiplier = 1.0
        if player.effect == "ping":
            karma_multiplier = PING_SPEED_MULTIPLIER
        elif player.effect == "fiber":
            karma_multiplier = FIBER_SPEED_MULTIPLIER
        chicken_multiplier = (
            CHICKEN_SPEED_MULTIPLIER
            if now < player.chicken_boost_until
            else 1.0
        )
        return min(
            MAX_TOTAL_SPEED_MULTIPLIER,
            fatigue_multiplier * karma_multiplier * chicken_multiplier,
        )

    def _respawn_player(self, player: Player, now: float) -> None:
        self._place_player_at_router(player, "ENTRADA")
        player.health = MAX_HEALTH
        player.repairs = 0
        player.instant_repairs = 0
        player.chicken_portions = 0
        player.chicken_contaminated = False
        player.chicken_boost_until = 0.0
        player.invulnerable_until = now + RESPAWN_INVULNERABILITY
        player.healing_blocked_until = now + MEDICAL_DAMAGE_COOLDOWN
        self._add_event(
            "respawn",
            f"{player.name} perdió la conexión y reapareció en Entrada.",
        )

    def _damage_player(
        self, player: Player, amount: float, now: float, source: str
    ) -> bool:
        if now < player.invulnerable_until:
            return False
        player.health = max(0.0, player.health - amount)
        player.healing_blocked_until = now + MEDICAL_DAMAGE_COOLDOWN
        self._add_event(
            "damage",
            f"{player.name} recibió {amount:g} de daño por {source}.",
        )
        if player.health <= 0.0:
            self._respawn_player(player, now)
        return True

    def consume_chicken(
        self, player_id: int, now: float | None = None
    ) -> tuple[bool, str]:
        now = time.monotonic() if now is None else now
        with self.lock:
            player = self.players.get(player_id)
            if not player:
                return False, "Jugador inexistente."
            if self.game_status != "playing":
                return False, "La campaña ya terminó."
            if player.chicken_portions <= 0:
                return False, "No llevas una porción de pollo a la brasa."
            player.chicken_portions -= 1
            contaminated = player.chicken_contaminated
            if player.chicken_portions <= 0:
                player.chicken_contaminated = False
            if contaminated:
                survived = player.health > 15.0
                self._damage_player(player, 15.0, now, "el menú con mosca")
                if survived:
                    player.fatigue = min(MAX_FATIGUE, player.fatigue + 25.0)
                    self._unlock_achievement(player, "menu_con_mosca")
                text = f"{player.name} comió el menú con mosca. Mala idea."
            else:
                player.health = min(MAX_HEALTH, player.health + CHICKEN_HEAL)
                player.fatigue = max(
                    0.0, player.fatigue - CHICKEN_FATIGUE_RECOVERY
                )
                player.chicken_boost_until = now + CHICKEN_BOOST_DURATION
                text = (
                    f"{player.name} comió pollo a la brasa: "
                    "recuperó energía y velocidad."
                )
            self._add_event("chicken", text)
            return True, text

    def _try_pick_up_chicken(
        self, player: Player, now: float
    ) -> tuple[bool, str] | None:
        if not self._near_facility(player, "COMEDOR"):
            return None
        if player.chicken_portions > 0:
            return None
        if now < player.next_chicken_pickup_at:
            remaining = player.next_chicken_pickup_at - now
            return (
                False,
                f"Debes esperar {remaining:.1f}s para recoger otro pollo.",
            )
        if self.chicken_stock <= 0:
            return False, "El pollo se está cocinando. Vuelve en unos segundos."
        self.chicken_stock -= 1
        portions = {"double": 2, "triple": 3}.get(self.food_event, 1)
        player.chicken_portions = portions
        player.chicken_contaminated = self.food_event == "fly"
        player.next_chicken_pickup_at = now + CHICKEN_PICKUP_COOLDOWN
        if self.food_event == "double":
            self._unlock_achievement(player, "doble_uni")
            text = f"¡DOBLEEE! {player.name} recibió 2 porciones."
        elif self.food_event == "triple":
            self._unlock_achievement(player, "triple_uni")
            text = f"¡TRIPLEEE! {player.name} recibió 3 porciones."
        elif self.food_event == "fly":
            text = f"{player.name} recogió un sospechoso menú con mosca."
        else:
            text = f"{player.name} recogió pollo a la brasa en el Comedor."
        self._add_event("chicken", text)
        return True, text

    def _safe_zone_centers(self) -> list[tuple[float, float]]:
        centers = []
        for name in ("COMEDOR", "CENTRO MEDICO"):
            facility = self._facility_by_name(name)
            centers.append(
                (
                    (facility.col + 0.5) * TILE_SIZE,
                    (facility.row + 0.5) * TILE_SIZE,
                )
            )
        entrance = self._router_by_name("ENTRADA")
        centers.append(
            ((entrance.col + 0.5) * TILE_SIZE, (entrance.row + 0.5) * TILE_SIZE)
        )
        return centers

    def _is_safe_bomb_tile(self, row: int, col: int) -> bool:
        if MAPA_UNI[row][col] != 0:
            return False
        center = ((col + 0.5) * TILE_SIZE, (row + 0.5) * TILE_SIZE)
        safe_radius = SAFE_ZONE_RADIUS_TILES * TILE_SIZE
        return all(
            math.hypot(center[0] - safe_x, center[1] - safe_y) > safe_radius
            for safe_x, safe_y in self._safe_zone_centers()
        )

    def _spawn_bomb(self, now: float) -> Bomb | None:
        candidates = [
            (row, col)
            for row, tiles in enumerate(MAPA_UNI)
            for col, _ in enumerate(tiles)
            if self._is_safe_bomb_tile(row, col)
            and all(bomb.row != row or bomb.col != col for bomb in self.bombs.values())
        ]
        if not candidates:
            return None
        row, col = self.rng.choice(candidates)
        bomb = Bomb(self.next_bomb_id, row, col, now + BOMB_FUSE)
        self.next_bomb_id += 1
        self.bombs[bomb.bomb_id] = bomb
        self._add_event("bomb", "¡Una bomba de lag apareció en el campus!")
        return bomb

    def _update_bombs(self, now: float) -> None:
        for bomb in list(self.bombs.values()):
            if bomb.exploded_at is None and now >= bomb.explode_at:
                bomb.exploded_at = now
                bomb_x = (bomb.col + 0.5) * TILE_SIZE
                bomb_y = (bomb.row + 0.5) * TILE_SIZE
                for player in self.players.values():
                    player_x, player_y = self._player_center(player)
                    if math.hypot(player_x - bomb_x, player_y - bomb_y) <= BOMB_RADIUS:
                        self._damage_player(player, BOMB_DAMAGE, now, "una bomba de lag")
            elif (
                bomb.exploded_at is not None
                and now - bomb.exploded_at >= BOMB_EXPLOSION_DISPLAY
            ):
                del self.bombs[bomb.bomb_id]

        active = sum(bomb.exploded_at is None for bomb in self.bombs.values())
        if now >= self.next_bomb_at and active < BOMB_MAX_ACTIVE:
            self._spawn_bomb(now)
            self.next_bomb_at = now + self.rng.uniform(
                BOMB_MIN_INTERVAL, BOMB_MAX_INTERVAL
            )

    def _spawn_powerup(self, now: float) -> PowerUp | None:
        occupied = {(p.row, p.col) for p in self.powerups.values()}
        candidates = [
            (row, col)
            for row, tiles in enumerate(MAPA_UNI)
            for col, tile in enumerate(tiles)
            if tile == 0 and (row, col) not in occupied
        ]
        if not candidates:
            return None
        row, col = self.rng.choice(candidates)
        powerup = PowerUp(
            self.next_powerup_id,
            row,
            col,
            self.rng.choice(POWERUP_KINDS),
            now + POWERUP_LIFETIME,
        )
        self.next_powerup_id += 1
        self.powerups[powerup.powerup_id] = powerup
        return powerup

    def _collect_powerup(self, player: Player, powerup: PowerUp, now: float) -> None:
        if powerup.kind == "shield":
            player.invulnerable_until = max(
                player.invulnerable_until, now + SHIELD_DURATION
            )
            text = (
                f"{player.name} recogió un Escudo Firewall: "
                "inmune al daño por un momento."
            )
        elif powerup.kind == "instant_repair":
            player.instant_repairs += 1
            text = (
                f"{player.name} consiguió un Parche Express: "
                "su próxima reparación será automática."
            )
        else:  # freeze
            self.lag_freeze_until = max(
                self.lag_freeze_until, now + LAG_FREEZE_DURATION
            )
            text = (
                f"{player.name} activó un Respaldo de Red: "
                "el Ciclo del Lag se congela para todos."
            )
        self._add_event("powerup", text)

    def _update_powerups(self, now: float) -> None:
        for powerup in list(self.powerups.values()):
            if now >= powerup.expires_at:
                del self.powerups[powerup.powerup_id]

        for powerup in list(self.powerups.values()):
            powerup_x = (powerup.col + 0.5) * TILE_SIZE
            powerup_y = (powerup.row + 0.5) * TILE_SIZE
            for player in self.players.values():
                center_x, center_y = self._player_center(player)
                if (
                    math.hypot(center_x - powerup_x, center_y - powerup_y)
                    <= POWERUP_PICKUP_DISTANCE
                ):
                    self._collect_powerup(player, powerup, now)
                    self.powerups.pop(powerup.powerup_id, None)
                    break

        if now >= self.next_powerup_at and len(self.powerups) < POWERUP_MAX_ACTIVE:
            self._spawn_powerup(now)
            self.next_powerup_at = now + self.rng.uniform(
                POWERUP_MIN_INTERVAL, POWERUP_MAX_INTERVAL
            )

    def _update_chicken_stock(self, now: float) -> None:
        while (
            self.chicken_stock < CHICKEN_MAX_STOCK
            and now >= self.next_chicken_restock_at
        ):
            self.chicken_stock += 1
            self.next_chicken_restock_at += CHICKEN_RESTOCK_INTERVAL
        if self.chicken_stock >= CHICKEN_MAX_STOCK:
            self.next_chicken_restock_at = now + CHICKEN_RESTOCK_INTERVAL

    def _update_medical_healing(self, player: Player, dt: float, now: float) -> None:
        if (
            player.health < MAX_HEALTH
            and now >= player.healing_blocked_until
            and self._near_facility(player, "CENTRO MEDICO")
        ):
            previous_health = player.health
            player.health = min(
                MAX_HEALTH, player.health + MEDICAL_HEAL_PER_SECOND * min(dt, 0.1)
            )
            if previous_health < MAX_HEALTH and player.health >= MAX_HEALTH:
                self._unlock_achievement(player, "paciente_modelo")

    def _reset_router(self, router: Router) -> None:
        router.repaired = False
        router.repaired_by = None
        router.rotation = self.rng.uniform(0.0, 360.0)

    def _begin_mission(self, index: int, now: float) -> None:
        self.mission_index = index
        self.mission_started_at = now
        self.mission_deadline = now + MISSION_DURATIONS[index]
        self.mission_repaired.clear()
        self.route_progress = 0
        self.hold_started_at = None

        if index == 1:
            self.critical_route = self.rng.sample(
                [router.name for router in self.routers.values()],
                CRITICAL_ROUTE_LENGTH,
            )
            for name in self.critical_route:
                self._reset_router(self._router_by_name(name))
        elif index == 3:
            for router in self.routers.values():
                self._reset_router(router)

        mission = MISSIONS[index]
        self._add_event(
            "mission",
            f"Misión {index + 1}: {mission['title']}.",
        )

    def _complete_mission(self, now: float) -> None:
        completed = MISSIONS[self.mission_index]
        self._add_event("mission", f"¡{completed['title']} completada!")
        if self.mission_index == len(MISSIONS) - 1:
            self.game_status = "victory"
            self.result_message = (
                "Eduroam ha sido estabilizado en todo el campus de la UNI."
            )
            self.mission_deadline = None
            self._add_event("victory", self.result_message)
            return
        self._begin_mission(self.mission_index + 1, now)

    def _coverage_zones_active(self) -> bool:
        active_zones: set[str] = set()
        for router in self.routers.values():
            if not router.repaired:
                continue
            if router.row <= 7:
                active_zones.add("superior")
            elif router.row <= 15:
                active_zones.add("central")
            else:
                active_zones.add("inferior")
        return len(active_zones) == 3

    def _register_repair(self, router: Router, now: float) -> None:
        if self.game_status != "playing":
            return

        if self.mission_index == 0:
            self.mission_repaired.add(router.router_id)
            if len(self.mission_repaired) >= int(MISSIONS[0]["goal"]):
                self._complete_mission(now)
        elif self.mission_index == 1:
            expected = self.critical_route[self.route_progress]
            if router.name == expected:
                self.route_progress += 1
                if self.route_progress >= len(self.critical_route):
                    self._complete_mission(now)

    def _update_timed_mission(self, now: float) -> None:
        if self.mission_index == 2:
            condition_met = self._coverage_zones_active()
            required = COVERAGE_HOLD_TIME
        elif self.mission_index == 3:
            condition_met = (
                sum(router.repaired for router in self.routers.values())
                >= MAX_REPAIRED_ROUTERS
            )
            required = BLACKOUT_HOLD_TIME
        else:
            return

        if not condition_met:
            self.hold_started_at = None
            return
        if self.hold_started_at is None:
            self.hold_started_at = now
        if now - self.hold_started_at >= required:
            self._complete_mission(now)

    def restart_campaign(self, now: float | None = None) -> tuple[bool, str]:
        now = time.monotonic() if now is None else now
        with self.lock:
            if self.game_status == "playing":
                return False, "La campaña todavía está en curso."

            self.game_status = "playing"
            self.result_message = ""
            for index, player in enumerate(self.players.values()):
                self._place_player_at_spawn(player, index)
                player.repairs = 0
                player.effect = None
                player.effect_until = 0.0
                player.health = MAX_HEALTH
                player.fatigue = 0.0
                player.chicken_portions = 0
                player.chicken_contaminated = False
                player.next_chicken_pickup_at = 0.0
                player.chicken_boost_until = 0.0
                player.invulnerable_until = 0.0
                player.healing_blocked_until = 0.0
                player.instant_repairs = 0
                player.repaired_locations.clear()
                player.achievements.clear()
                for key in player.inputs:
                    player.inputs[key] = False
            for router in self.routers.values():
                self._reset_router(router)
            self.bombs.clear()
            self.powerups.clear()
            self.next_powerup_at = now + self.rng.uniform(
                POWERUP_MIN_INTERVAL, POWERUP_MAX_INTERVAL
            )
            self.lag_freeze_until = 0.0
            self.chicken_stock = CHICKEN_MAX_STOCK
            self.next_chicken_restock_at = now + CHICKEN_RESTOCK_INTERVAL
            self.next_bomb_at = now + self.rng.uniform(
                BOMB_MIN_INTERVAL, BOMB_MAX_INTERVAL
            )
            self.food_event = "normal"
            self.food_event_until = 0.0
            self.next_food_event_at = now + self.rng.uniform(
                FOOD_EVENT_MIN_INTERVAL, FOOD_EVENT_MAX_INTERVAL
            )
            self.food_event_sequence = 0
            self.side_quest = dict(self.rng.choice(SIDE_QUESTS))
            self.side_quest_status = "available"
            self.side_quest_owner_id = None
            self.side_quest_progress = 0
            self.side_quest_deadline = None
            self.next_karma_at = now + KARMA_INTERVAL
            self.events.clear()
            self._begin_mission(0, now)
            text = "La campaña de Eduroam se reinició."
            self._add_event("restart", text)
            return True, text

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
        multiplier = self._speed_multiplier(player, now)
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
            if self.game_status != "playing":
                return
            for player in self.players.values():
                self._move_player(player, dt, now)
                self._update_medical_healing(player, dt, now)
            self._update_chicken_stock(now)
            self._update_food_event(now)
            self._update_bombs(now)
            self._update_powerups(now)
            self._update_side_quest(now)
            if (
                self.mission_started_at is not None
                and self.mission_deadline is not None
                and now >= self.mission_deadline
            ):
                self.game_status = "defeat"
                self.result_message = (
                    f"Se agotó el tiempo en: "
                    f"{MISSIONS[self.mission_index]['title']}."
                )
                self._add_event("defeat", self.result_message)
                return
            self._update_timed_mission(now)
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

    def interact(
        self, player_id: int, now: float | None = None
    ) -> tuple[bool, str]:
        now = time.monotonic() if now is None else now
        with self.lock:
            if self.game_status != "playing":
                return False, "La campaña terminó. Reinícienla para volver a jugar."
            player = self.players.get(player_id)
            if not player:
                return False, "Jugador inexistente."

            professor_result = self._accept_side_quest(player, now)
            if professor_result is not None:
                return professor_result

            chicken_result = self._try_pick_up_chicken(player, now)

            center_x, center_y = self._player_center(player)
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
                if chicken_result is not None:
                    return chicken_result
                return False, "No hay un router caído suficientemente cerca."

            router = min(
                nearby,
                key=lambda item: math.hypot(
                    center_x - (item.col + 0.5) * TILE_SIZE,
                    center_y - (item.row + 0.5) * TILE_SIZE,
                ),
            )
            used_instant_repair = False
            if not REPAIR_MIN_ANGLE <= router.rotation <= REPAIR_MAX_ANGLE:
                if player.instant_repairs > 0:
                    player.instant_repairs -= 1
                    used_instant_repair = True
                else:
                    if chicken_result is not None and chicken_result[0]:
                        return chicken_result
                    self._damage_player(
                        player, FAILED_REPAIR_DAMAGE, now, "un cortocircuito del router"
                    )
                    return (
                        False,
                        f"{router.name}: mala sincronización "
                        f"({router.rotation:.0f}°).",
                    )

            repaired = [item for item in self.routers.values() if item.repaired]
            if len(repaired) >= MAX_REPAIRED_ROUTERS and now >= self.lag_freeze_until:
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
            player.repaired_locations.add(router.name)
            player.fatigue = min(MAX_FATIGUE, player.fatigue + REPAIR_FATIGUE)
            self._unlock_achievement(player, "primera_vuelta")
            if len(player.repaired_locations) >= 8:
                self._unlock_achievement(player, "tour_uni")
            if router.name == "BIBLIOTECA":
                self._unlock_achievement(player, "raton_biblioteca")
            if router.name == "ESTADIO UNI" and player.fatigue >= 60.0:
                self._unlock_achievement(player, "estadio_agotado")
            if (
                self.side_quest_status == "active"
                and self.side_quest_owner_id == player.player_id
                and self.side_quest.get("kind") == "repairs"
            ):
                self.side_quest_progress += 1
                if self.side_quest_progress >= int(self.side_quest["goal"]):
                    self._complete_side_quest(player)
            text = f"{player.name} reparó el router de {router.name}."
            if used_instant_repair:
                text += " (Parche Express)"
            if chicken_result is not None and chicken_result[0]:
                text += " También recogió pollo a la brasa."
            self._add_event("repair", text)
            self._register_repair(router, now)
            return True, text

    def _mission_snapshot(self, now: float) -> dict[str, Any]:
        mission = MISSIONS[self.mission_index]
        target_router: str | None = None
        if self.mission_index == 0:
            progress: float = len(self.mission_repaired)
        elif self.mission_index == 1:
            progress = self.route_progress
            if self.route_progress < len(self.critical_route):
                target_router = self._router_by_name(
                    self.critical_route[self.route_progress]
                ).router_id
        else:
            progress = (
                max(0.0, now - self.hold_started_at)
                if self.hold_started_at is not None
                else 0.0
            )

        return {
            "id": mission["id"],
            "number": self.mission_index + 1,
            "total": len(MISSIONS),
            "title": mission["title"],
            "description": (
                "Ruta: " + " → ".join(self.critical_route)
                if self.mission_index == 1
                else mission["description"]
            ),
            "progress": round(min(progress, float(mission["goal"])), 1),
            "goal": mission["goal"],
            "time_remaining": round(
                max(0.0, (self.mission_deadline or now) - now), 1
            ),
            "target_router": target_router,
            "route": list(self.critical_route) if self.mission_index == 1 else [],
        }

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
                        "health": round(player.health, 1),
                        "max_health": MAX_HEALTH,
                        "fatigue": round(player.fatigue, 1),
                        "has_chicken": player.chicken_portions > 0,
                        "chicken_portions": player.chicken_portions,
                        "chicken_contaminated": player.chicken_contaminated,
                        "chicken_pickup_cooldown": round(
                            max(0.0, player.next_chicken_pickup_at - now), 1
                        ),
                        "speed_multiplier": round(
                            self._speed_multiplier(player, now), 2
                        ),
                        "chicken_boost_remaining": round(
                            max(0.0, player.chicken_boost_until - now), 1
                        ),
                        "invulnerable_remaining": round(
                            max(0.0, player.invulnerable_until - now), 1
                        ),
                        "instant_repairs": player.instant_repairs,
                        "achievements": [
                            {
                                "id": achievement_id,
                                "title": ACHIEVEMENTS[achievement_id][0],
                                "description": ACHIEVEMENTS[achievement_id][1],
                            }
                            for achievement_id in sorted(player.achievements)
                        ],
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
                "facilities": {
                    facility_id: {
                        "id": facility.facility_id,
                        "row": facility.row,
                        "col": facility.col,
                        "name": facility.name,
                        "type": facility.facility_type,
                        "active": (
                            self.chicken_stock > 0
                            if facility.facility_type == "food"
                            else True
                        ),
                    }
                    for facility_id, facility in self.facilities.items()
                },
                "events": list(self.events),
                "bombs": {
                    str(bomb_id): {
                        "id": bomb.bomb_id,
                        "row": bomb.row,
                        "col": bomb.col,
                        "time_remaining": round(max(0.0, bomb.explode_at - now), 2),
                        "exploded": bomb.exploded_at is not None,
                    }
                    for bomb_id, bomb in self.bombs.items()
                },
                "powerups": {
                    str(powerup_id): {
                        "id": powerup.powerup_id,
                        "row": powerup.row,
                        "col": powerup.col,
                        "kind": powerup.kind,
                        "time_remaining": round(
                            max(0.0, powerup.expires_at - now), 1
                        ),
                    }
                    for powerup_id, powerup in self.powerups.items()
                },
                "lag_freeze_remaining": round(
                    max(0.0, self.lag_freeze_until - now), 1
                ),
                "chicken_stock": self.chicken_stock,
                "chicken_max_stock": CHICKEN_MAX_STOCK,
                "chicken_restock_in": round(
                    max(0.0, self.next_chicken_restock_at - now)
                    if self.chicken_stock < CHICKEN_MAX_STOCK
                    else 0.0,
                    1,
                ),
                "food_event": {
                    "type": self.food_event,
                    "sequence": self.food_event_sequence,
                    "time_remaining": round(
                        max(0.0, self.food_event_until - now), 1
                    ),
                },
                "achievement_total": len(ACHIEVEMENTS),
                "professor": {
                    "name": "PROF. MONTALVO",
                    "row": PROFESSOR_ROW,
                    "col": PROFESSOR_COL,
                },
                "side_quest": {
                    "id": self.side_quest["id"],
                    "title": self.side_quest["title"],
                    "description": self.side_quest["description"],
                    "status": self.side_quest_status,
                    "owner_id": self.side_quest_owner_id,
                    "progress": self.side_quest_progress,
                    "goal": self.side_quest["goal"],
                    "time_remaining": round(
                        max(0.0, (self.side_quest_deadline or now) - now), 1
                    ),
                    "target": (
                        self.side_quest.get("route", [])[self.side_quest_progress]
                        if self.side_quest_status == "active"
                        and self.side_quest.get("kind") == "route"
                        and self.side_quest_progress
                        < len(self.side_quest.get("route", []))
                        else None
                    ),
                },
                "karma_in": round(max(0.0, self.next_karma_at - now), 1),
                "max_repaired": MAX_REPAIRED_ROUTERS,
                "game_status": self.game_status,
                "mission": self._mission_snapshot(now),
                "result_message": self.result_message,
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
                elif message_type == "consume_chicken":
                    success, text = self.game.consume_chicken(player.player_id)
                    interaction_result = {"success": success, "message": text}
                elif message_type == "restart":
                    success, text = self.game.restart_campaign()
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
