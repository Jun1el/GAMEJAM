import random
import unittest

from server import (
    BOMB_DAMAGE,
    BOMB_RADIUS,
    CHICKEN_FATIGUE_RECOVERY,
    CHICKEN_HEAL,
    CHICKEN_PICKUP_COOLDOWN,
    FAILED_REPAIR_DAMAGE,
    KARMA_DURATION,
    MAPA_UNI,
    MAX_FATIGUE,
    MAX_HEALTH,
    MAX_REPAIRED_ROUTERS,
    MEDICAL_HEAL_PER_SECOND,
    PLAYER_SIZE,
    REPAIR_FATIGUE,
    REPAIR_MAX_ANGLE,
    SHIELD_DURATION,
    TILE_SIZE,
    Bomb,
    GameState,
    PowerUp,
)


class GameStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game = GameState(random.Random(7))
        self.game.start_game()

    def repair(
        self, player, router_name: str, now: float = 10.0
    ) -> tuple[bool, str]:
        router = self.game._router_by_name(router_name)
        router.repaired = False
        router.rotation = REPAIR_MAX_ANGLE / 2
        player.x = router.col * TILE_SIZE - PLAYER_SIZE
        player.y = router.row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2
        return self.game.interact(player.player_id, now=now)

    def test_accepts_only_four_players(self) -> None:
        players = [self.game.add_player(f"P{i}") for i in range(5)]
        self.assertTrue(all(player is not None for player in players[:4]))
        self.assertIsNone(players[4])

    def test_wall_collision_is_authoritative(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        player.x = 23 * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2
        player.y = 2 * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2
        original_x = player.x
        self.game.set_inputs(player.player_id, {"right": True})

        self.game.update(0.1, now=1.0)

        self.assertEqual(player.x, original_x)

    def test_repairs_router_inside_angle_window(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        router = next(iter(self.game.routers.values()))
        router.rotation = REPAIR_MAX_ANGLE / 2
        player.x = router.col * TILE_SIZE - PLAYER_SIZE
        player.y = router.row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2

        success, _ = self.game.interact(player.player_id)

        self.assertTrue(success)
        self.assertTrue(router.repaired)
        self.assertEqual(player.repairs, 1)
        self.assertEqual(player.fatigue, REPAIR_FATIGUE)

    def test_rejects_repair_just_outside_larger_window(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        router = next(iter(self.game.routers.values()))
        router.rotation = REPAIR_MAX_ANGLE + 0.1
        player.x = router.col * TILE_SIZE - PLAYER_SIZE
        player.y = router.row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2

        success, _ = self.game.interact(player.player_id)

        self.assertFalse(success)
        self.assertFalse(router.repaired)
        self.assertEqual(player.health, MAX_HEALTH - FAILED_REPAIR_DAMAGE)

    def test_map_is_expanded_without_duplicating_routers(self) -> None:
        self.assertEqual((len(MAPA_UNI), len(MAPA_UNI[0])), (22, 62))
        self.assertEqual(len(self.game.routers), 16)
        self.assertEqual(len(self.game.facilities), 2)
        self.assertNotIn(
            "COMEDOR", {router.name for router in self.game.routers.values()}
        )
        self.assertNotIn(
            "CENTRO MEDICO", {router.name for router in self.game.routers.values()}
        )

    def test_fatigue_reduces_speed_to_half_at_maximum(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        player.fatigue = MAX_FATIGUE

        self.assertEqual(self.game._speed_multiplier(player, now=10.0), 0.5)

    def test_comedor_stock_is_shared_and_chicken_can_be_consumed(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        comedor = self.game._facility_by_name("COMEDOR")
        player.x = comedor.col * TILE_SIZE - PLAYER_SIZE
        player.y = comedor.row * TILE_SIZE
        player.health = 50.0
        player.fatigue = 80.0

        success, _ = self.game.interact(player.player_id, now=10.0)

        self.assertTrue(success)
        self.assertEqual(player.chicken_portions, 1)
        self.assertEqual(self.game.chicken_stock, 2)
        self.assertEqual(player.repairs, 0)
        self.assertEqual(
            sum(router.repaired for router in self.game.routers.values()), 0
        )

        success, _ = self.game.consume_chicken(player.player_id, now=11.0)

        self.assertTrue(success)
        self.assertEqual(player.chicken_portions, 0)
        self.assertEqual(player.health, 50.0 + CHICKEN_HEAL)
        self.assertEqual(player.fatigue, 80.0 - CHICKEN_FATIGUE_RECOVERY)
        self.assertGreater(player.chicken_boost_until, 11.0)
        self.assertEqual(
            player.next_chicken_pickup_at, 10.0 + CHICKEN_PICKUP_COOLDOWN
        )

        success, message = self.game.interact(player.player_id, now=12.0)

        self.assertFalse(success)
        self.assertIn("13.0s", message)
        self.assertEqual(player.chicken_portions, 0)
        self.assertEqual(self.game.chicken_stock, 2)

        success, _ = self.game.interact(player.player_id, now=25.0)

        self.assertTrue(success)
        self.assertEqual(player.chicken_portions, 1)
        self.assertEqual(self.game.chicken_stock, 1)

    def test_medical_center_heals_gradually(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        medical = self.game._facility_by_name("CENTRO MEDICO")
        player.x = medical.col * TILE_SIZE - PLAYER_SIZE
        player.y = medical.row * TILE_SIZE
        player.health = 50.0
        player.healing_blocked_until = 0.0

        self.game.update(0.1, now=10.0)

        self.assertAlmostEqual(
            player.health, 50.0 + MEDICAL_HEAL_PER_SECOND * 0.1
        )

    def test_double_and_triple_events_grant_extra_portions(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        comedor = self.game._facility_by_name("COMEDOR")
        player.x = comedor.col * TILE_SIZE - PLAYER_SIZE
        player.y = comedor.row * TILE_SIZE

        self.game.food_event = "double"
        success, _ = self.game.interact(player.player_id, now=10.0)

        self.assertTrue(success)
        self.assertEqual(player.chicken_portions, 2)
        self.assertIn("doble_uni", player.achievements)

        player.chicken_portions = 0
        player.next_chicken_pickup_at = 0.0
        self.game.food_event = "triple"
        success, _ = self.game.interact(player.player_id, now=20.0)

        self.assertTrue(success)
        self.assertEqual(player.chicken_portions, 3)
        self.assertIn("triple_uni", player.achievements)

    def test_fly_menu_damages_player_and_unlocks_achievement(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        comedor = self.game._facility_by_name("COMEDOR")
        player.x = comedor.col * TILE_SIZE - PLAYER_SIZE
        player.y = comedor.row * TILE_SIZE
        self.game.food_event = "fly"

        self.game.interact(player.player_id, now=10.0)
        success, _ = self.game.consume_chicken(player.player_id, now=11.0)

        self.assertTrue(success)
        self.assertEqual(player.health, MAX_HEALTH - 15.0)
        self.assertEqual(player.fatigue, 25.0)
        self.assertIn("menu_con_mosca", player.achievements)

    def test_professor_assigns_and_completes_repair_side_quest(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        self.game.side_quest = {
            "id": "control_sorpresa",
            "title": "Control sorpresa",
            "description": "Repara 2 routers.",
            "goal": 2,
            "kind": "repairs",
        }
        self.game.side_quest_status = "available"
        player.x = 9 * TILE_SIZE
        player.y = 11 * TILE_SIZE

        success, _ = self.game.interact(player.player_id, now=10.0)

        self.assertTrue(success)
        self.assertEqual(self.game.side_quest_status, "active")
        self.repair(player, "FIEE", now=11.0)
        self.repair(player, "FIC", now=12.0)

        self.assertEqual(self.game.side_quest_status, "completed")
        self.assertIn("alumno_montalvo", player.achievements)

    def test_repair_achievements_track_unique_faculties(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        names = [router.name for router in self.game.routers.values()][:8]

        for index, name in enumerate(names, start=1):
            self.repair(player, name, now=float(index))

        self.assertIn("primera_vuelta", player.achievements)
        self.assertIn("tour_uni", player.achievements)

    def test_faculty_specific_achievements(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None

        self.repair(player, "BIBLIOTECA", now=1.0)
        player.fatigue = 50.0
        self.repair(player, "ESTADIO UNI", now=2.0)

        self.assertIn("raton_biblioteca", player.achievements)
        self.assertIn("estadio_agotado", player.achievements)

    def _explode_bomb_on(self, player, now: float = 10.0) -> None:
        """Detona una bomba sobre la casilla del jugador indicado."""
        center_x = player.x + PLAYER_SIZE / 2
        center_y = player.y + PLAYER_SIZE / 2
        row = int(center_y // TILE_SIZE)
        col = int(center_x // TILE_SIZE)
        bomb_id = len(self.game.bombs) + 1
        self.game.bombs[bomb_id] = Bomb(bomb_id, row, col, explode_at=now)
        self.game.next_bomb_at = 999.0

    def test_one_player_down_keeps_campaign_alive(self) -> None:
        ada = self.game.add_player("Ada")
        ben = self.game.add_player("Ben")
        assert ada is not None and ben is not None
        ada.health = BOMB_DAMAGE
        # Aleja a Ben para que la explosión no lo alcance.
        ben.x = ada.x + BOMB_RADIUS * 3
        self._explode_bomb_on(ada)

        self.game.update(0.1, now=10.0)

        self.assertEqual(ada.health, 0.0)
        self.assertFalse(ada.alive)
        self.assertTrue(ben.alive)
        # La derrota es compartida: con un compañero en pie la campaña sigue.
        self.assertEqual(self.game.game_status, "playing")
        self.assertTrue(
            any(
                event["kind"] == "eliminated" and "Ada" in event["text"]
                for event in self.game.events
            )
        )

    def test_defeat_only_when_all_players_eliminated(self) -> None:
        ada = self.game.add_player("Ada")
        ben = self.game.add_player("Ben")
        assert ada is not None and ben is not None

        # Ben cae primero: la campaña cooperativa continúa.
        ben.health = BOMB_DAMAGE
        ada.x = ben.x + BOMB_RADIUS * 3
        self._explode_bomb_on(ben)
        self.game.update(0.1, now=10.0)
        self.assertFalse(ben.alive)
        self.assertTrue(ada.alive)
        self.assertEqual(self.game.game_status, "playing")

        # Ada también queda fuera: ahora sí es derrota compartida.
        ada.health = BOMB_DAMAGE
        self._explode_bomb_on(ada)
        self.game.update(0.1, now=11.0)
        self.assertFalse(ada.alive)
        self.assertEqual(self.game.game_status, "defeat")
        self.assertTrue(
            any(event["kind"] == "defeat" for event in self.game.events)
        )

    def test_eliminated_player_ignores_inputs_and_actions(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        player.alive = False

        self.game.set_inputs(player.player_id, {"right": True})
        self.assertFalse(player.inputs["right"])

        success, _ = self.game.interact(player.player_id, now=5.0)
        self.assertFalse(success)
        player.chicken_portions = 1
        success, _ = self.game.consume_chicken(player.player_id, now=5.0)
        self.assertFalse(success)

    def test_bombs_spawn_only_on_walkable_tiles_outside_safe_zones(self) -> None:
        bomb = self.game._spawn_bomb(now=10.0)

        assert bomb is not None
        self.assertEqual(MAPA_UNI[bomb.row][bomb.col], 0)
        self.assertTrue(self.game._is_safe_bomb_tile(bomb.row, bomb.col))

    def test_zero_sum_cycle_breaks_one_at_capacity(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        routers = list(self.game.routers.values())
        for router in routers[:MAX_REPAIRED_ROUTERS]:
            router.repaired = True
        target = routers[MAX_REPAIRED_ROUTERS]
        target.rotation = 5.0
        player.x = target.col * TILE_SIZE - PLAYER_SIZE
        player.y = target.row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2

        success, _ = self.game.interact(player.player_id)

        self.assertTrue(success)
        self.assertEqual(
            sum(router.repaired for router in routers),
            MAX_REPAIRED_ROUTERS,
        )

    def _place_on_powerup(self, player, powerup: PowerUp) -> None:
        player.x = (powerup.col + 0.5) * TILE_SIZE - PLAYER_SIZE / 2
        player.y = (powerup.row + 0.5) * TILE_SIZE - PLAYER_SIZE / 2

    def test_powerups_spawn_only_on_floor_tiles(self) -> None:
        powerup = self.game._spawn_powerup(now=10.0)

        assert powerup is not None
        self.assertEqual(MAPA_UNI[powerup.row][powerup.col], 0)
        self.assertIn(powerup.kind, ("shield", "instant_repair", "freeze"))

    def test_powerup_collected_on_contact_and_despawns(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        floor_row, floor_col = next(
            (row, col)
            for row, tiles in enumerate(MAPA_UNI)
            for col, tile in enumerate(tiles)
            if tile == 0
        )
        shield = PowerUp(99, floor_row, floor_col, "shield", expires_at=100.0)
        self.game.powerups[shield.powerup_id] = shield
        self._place_on_powerup(player, shield)
        self.game.next_powerup_at = 999.0

        self.game.update(0.1, now=10.0)

        self.assertNotIn(shield.powerup_id, self.game.powerups)
        self.assertEqual(player.invulnerable_until, 10.0 + SHIELD_DURATION)

    def test_instant_repair_charge_fixes_router_outside_window(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        player.instant_repairs = 1
        router = next(iter(self.game.routers.values()))
        router.rotation = REPAIR_MAX_ANGLE + 30.0  # fuera de la ventana
        player.x = router.col * TILE_SIZE - PLAYER_SIZE
        player.y = router.row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2

        success, _ = self.game.interact(player.player_id, now=10.0)

        self.assertTrue(success)
        self.assertTrue(router.repaired)
        self.assertEqual(player.instant_repairs, 0)
        self.assertEqual(player.health, MAX_HEALTH)  # no recibió daño

    def test_lag_freeze_prevents_router_knockdown(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        self.game.lag_freeze_until = 100.0
        routers = list(self.game.routers.values())
        for router in routers[:MAX_REPAIRED_ROUTERS]:
            router.repaired = True
        target = routers[MAX_REPAIRED_ROUTERS]
        target.rotation = 5.0
        player.x = target.col * TILE_SIZE - PLAYER_SIZE
        player.y = target.row * TILE_SIZE + (TILE_SIZE - PLAYER_SIZE) / 2

        success, _ = self.game.interact(player.player_id, now=10.0)

        self.assertTrue(success)
        self.assertEqual(
            sum(router.repaired for router in routers),
            MAX_REPAIRED_ROUTERS + 1,
        )

    def test_karma_assigns_distinct_effects(self) -> None:
        first = self.game.add_player("Primero")
        second = self.game.add_player("Segundo")
        assert first is not None and second is not None
        first.repairs = 10
        second.repairs = 1

        self.game._apply_karma(now=100.0)

        self.assertEqual(first.effect, "ping")
        self.assertEqual(second.effect, "fiber")
        self.assertEqual(first.effect_until, 100.0 + KARMA_DURATION)

    def test_diagnosis_progress_is_shared_between_players(self) -> None:
        first = self.game.add_player("Ada")
        second = self.game.add_player("Linus")
        assert first is not None and second is not None
        self.game._begin_mission(0, now=0.0)

        self.repair(first, "FIEE", now=1.0)
        self.repair(second, "BIBLIOTECA", now=2.0)

        self.assertEqual(len(self.game.mission_repaired), 2)
        self.assertEqual(self.game.mission_index, 0)

        self.repair(first, "FIC", now=3.0)

        self.assertEqual(self.game.mission_index, 1)

    def test_critical_route_only_advances_in_order(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        self.game._begin_mission(1, now=0.0)
        route = list(self.game.critical_route)

        self.repair(player, "FIEE", now=1.0)
        if route[0] != "FIEE":
            self.assertEqual(self.game.route_progress, 0)
        else:
            self.game.route_progress = 0
            self.game._reset_router(self.game._router_by_name("FIEE"))

        for index, name in enumerate(route, start=2):
            self.repair(player, name, now=float(index))

        self.assertEqual(self.game.mission_index, 2)

    def test_critical_route_has_four_unique_random_routers(self) -> None:
        self.game._begin_mission(1, now=0.0)
        first_route = list(self.game.critical_route)
        self.game._begin_mission(1, now=1.0)
        second_route = list(self.game.critical_route)

        self.assertEqual(len(first_route), 4)
        self.assertEqual(len(set(first_route)), 4)
        self.assertEqual(len(second_route), 4)
        self.assertNotEqual(first_route, second_route)
        self.assertNotIn("COMEDOR", first_route + second_route)
        self.assertNotIn("CENTRO MEDICO", first_route + second_route)

    def test_coverage_requires_three_zones_for_fifteen_seconds(self) -> None:
        self.game._begin_mission(2, now=100.0)
        for name in ("FIGMM", "CTIC", "ENTRADA"):
            self.game._router_by_name(name).repaired = True

        self.game.update(0.1, now=101.0)
        self.game.update(0.1, now=115.9)
        self.assertEqual(self.game.mission_index, 2)

        self.game.update(0.1, now=116.0)
        self.assertEqual(self.game.mission_index, 3)
        self.assertFalse(any(router.repaired for router in self.game.routers.values()))

    def test_blackout_hold_completes_campaign(self) -> None:
        self.game._begin_mission(3, now=200.0)
        for router in list(self.game.routers.values())[:MAX_REPAIRED_ROUTERS]:
            router.repaired = True

        self.game.update(0.1, now=201.0)
        self.game.update(0.1, now=211.0)

        self.assertEqual(self.game.game_status, "victory")
        self.assertTrue(self.game.result_message)

    def test_mission_timeout_causes_defeat(self) -> None:
        self.game._begin_mission(0, now=0.0)

        self.game.update(0.1, now=120.0)

        self.assertEqual(self.game.game_status, "defeat")

    def test_restart_resets_campaign_players_and_routers(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        player.repairs = 8
        player.effect = "ping"
        player.health = 20
        player.fatigue = 90
        player.chicken_portions = 1
        player.next_chicken_pickup_at = 999.0
        next(iter(self.game.routers.values())).repaired = True
        self.game.game_status = "victory"

        success, _ = self.game.restart_campaign(now=500.0)

        self.assertTrue(success)
        self.assertEqual(self.game.game_status, "playing")
        self.assertEqual(self.game.mission_index, 0)
        self.assertEqual(player.repairs, 0)
        self.assertIsNone(player.effect)
        self.assertEqual(player.health, MAX_HEALTH)
        self.assertEqual(player.fatigue, 0)
        self.assertEqual(player.chicken_portions, 0)
        self.assertEqual(player.next_chicken_pickup_at, 0.0)
        self.assertFalse(any(router.repaired for router in self.game.routers.values()))

    def test_snapshot_exposes_campaign_contract(self) -> None:
        self.game._begin_mission(1, now=20.0)

        state = self.game.snapshot(now=25.0)

        self.assertEqual(state["game_status"], "playing")
        self.assertEqual(state["mission"]["id"], "critical_route")
        self.assertEqual(state["mission"]["time_remaining"], 175.0)
        self.assertIsNotNone(state["mission"]["target_router"])
        self.assertEqual(state["mission"]["route"], self.game.critical_route)
        self.assertIn(" → ".join(self.game.critical_route), state["mission"]["description"])
        self.assertIn("result_message", state)
        self.assertIn("bombs", state)
        self.assertIn("chicken_stock", state)
        self.assertIn("facilities", state)
        player = self.game.add_player("Cooldown")
        assert player is not None
        player.next_chicken_pickup_at = 40.0
        state = self.game.snapshot(now=25.0)
        self.assertEqual(
            state["players"][str(player.player_id)]["chicken_pickup_cooldown"],
            15.0,
        )



    def test_rain_event_creates_puddles(self) -> None:
        # Start rain manually
        self.game.weather = "rain"
        self.game.weather_until = 20.0
        self.game.next_puddle_at = 10.0
        
        # Spawn puddle
        self.game._update_weather_and_puddles(now=10.0)
        self.assertTrue(len(self.game.puddles) > 0)
        self.assertEqual(self.game.next_puddle_at, 10.0 + 1.5) # PUDDLE_SPAWN_INTERVAL

    def test_player_slips_on_puddle_losing_chicken_and_getting_stunned(self) -> None:
        player = self.game.add_player("PuddleSlipping")
        assert player is not None
        player.chicken_portions = 2
        
        # Make player move
        player.inputs["right"] = True
        
        self.game.weather = "rain"
        self.game.weather_until = 20.0
        self.game.next_puddle_at = 10.0
        self.game._spawn_puddle(now=10.0)
        
        # Force a puddle under the player
        puddle = next(iter(self.game.puddles.values()))
        player.x = (puddle.col + 0.5) * 32 # TILE_SIZE
        player.y = (puddle.row + 0.5) * 32
        
        # Update
        self.game._update_weather_and_puddles(now=10.5)
        
        self.assertEqual(player.chicken_portions, 0)
        self.assertEqual(player.stun_until, 10.5 + 2.0) # STUN_DURATION
        
        # Ensure stun blocks movement
        original_x = player.x
        self.game._move_player(player, 0.1, 11.0)
        self.assertEqual(player.x, original_x) # shouldn't move



    def test_dog_wakes_up_when_player_moves_nearby_without_sneak(self) -> None:
        self.game.dogs.clear()
        
        dog = __import__("server").Dog(1, 100.0, 100.0, "sleeping", home_x=100.0, home_y=100.0)
        self.game.dogs[1] = dog
        
        player = self.game.add_player("Test")
        assert player is not None
        player.x, player.y = 110.0, 110.0
        
        # Player is moving without sneak
        player.inputs["right"] = True
        player.inputs["sneak"] = False
        
        self.game._update_dogs(0.1, 10.0)
        
        self.assertEqual(dog.state, "chasing")
        self.assertEqual(dog.target_id, player.player_id)
        
    def test_dog_ignores_sneaking_player(self) -> None:
        self.game.dogs.clear()
        
        dog = __import__("server").Dog(1, 100.0, 100.0, "sleeping", home_x=100.0, home_y=100.0)
        self.game.dogs[1] = dog
        
        player = self.game.add_player("Test")
        assert player is not None
        player.x, player.y = 110.0, 110.0
        
        # Player is sneaking
        player.inputs["right"] = True
        player.inputs["sneak"] = True
        
        self.game._update_dogs(0.1, 10.0)
        
        self.assertEqual(dog.state, "sleeping")
        self.assertIsNone(dog.target_id)
        
    def test_dog_steals_chicken_and_returns_to_sleep(self) -> None:
        self.game.dogs.clear()
        
        dog = __import__("server").Dog(1, 100.0, 100.0, "chasing", home_x=100.0, home_y=100.0)
        self.game.dogs[1] = dog
        
        player = self.game.add_player("Test")
        assert player is not None
        dog.target_id = player.player_id
        
        # Player is right on the dog
        player.x, player.y = 100.0, 100.0
        player.chicken_portions = 2
        
        self.game._update_dogs(0.1, 10.0)
        
        self.assertEqual(player.chicken_portions, 0)
        self.assertEqual(dog.state, "returning")
        self.assertIsNone(dog.target_id)
        
    def test_panic_speed_boost_applied(self) -> None:
        player = self.game.add_player("Test")
        assert player is not None
        
        # Normal speed
        player.x, player.y = 1510.0, 166.0
        player.inputs["right"] = True
        x1 = player.x
        self.game._move_player(player, 0.01, 10.0)
        speed_normal = (player.x - x1) / 0.01
        
        # Sneak speed
        player.x, player.y = 1510.0, 166.0
        player.inputs["sneak"] = True
        x2 = player.x
        self.game._move_player(player, 0.01, 11.0)
        speed_sneak = (player.x - x2) / 0.01
        self.assertTrue(speed_sneak < speed_normal)
        
        # Panic speed
        player.x, player.y = 1510.0, 166.0
        player.inputs["sneak"] = False
        player.panic_until = 20.0
        x3 = player.x
        self.game._move_player(player, 0.01, 12.0)
        speed_panic = (player.x - x3) / 0.01
        self.assertTrue(speed_panic > speed_normal)



    def test_dog_bites_player_without_chicken(self) -> None:
        self.game.dogs.clear()
        
        dog = __import__("server").Dog(1, 100.0, 100.0, "chasing", home_x=100.0, home_y=100.0)
        self.game.dogs[1] = dog
        
        player = self.game.add_player("Test")
        assert player is not None
        dog.target_id = player.player_id
        
        player.x, player.y = 100.0, 100.0
        player.chicken_portions = 0
        player.health = 100.0
        
        self.game._update_dogs(0.1, 10.0)
        
        self.assertEqual(player.health, 85.0)
        self.assertEqual(dog.state, "returning")
        self.assertIsNone(dog.target_id)

    def test_dog_bite_at_zero_health_eliminates_player(self) -> None:
        self.game.dogs.clear()

        dog = __import__("server").Dog(1, 100.0, 100.0, "chasing", home_x=100.0, home_y=100.0)
        self.game.dogs[1] = dog

        player = self.game.add_player("Test")
        assert player is not None
        dog.target_id = player.player_id

        player.x, player.y = 100.0, 100.0
        player.chicken_portions = 0
        player.health = 15.0

        self.game._update_dogs(0.1, 10.0)

        self.assertEqual(player.health, 0.0)
        self.assertFalse(player.alive)
        self.assertEqual(self.game.game_status, "defeat")
        
    def test_dog_stops_chasing_after_3_seconds(self) -> None:
        self.game.dogs.clear()
        
        dog = __import__("server").Dog(1, 100.0, 100.0, "chasing", home_x=100.0, home_y=100.0)
        dog.chase_until = 12.0
        self.game.dogs[1] = dog
        
        player = self.game.add_player("Test")
        assert player is not None
        dog.target_id = player.player_id
        
        # Player is far away
        player.x, player.y = 500.0, 500.0
        
        # Time is before 12.0 -> continues chasing
        self.game._update_dogs(0.1, 11.0)
        self.assertEqual(dog.state, "chasing")
        
        # Time is after 12.0 -> gives up
        self.game._update_dogs(0.1, 12.5)
        self.assertEqual(dog.state, "returning")


if __name__ == "__main__":
    unittest.main()
