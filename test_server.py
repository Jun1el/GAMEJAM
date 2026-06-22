import random
import unittest

from server import (
    KARMA_DURATION,
    MAX_REPAIRED_ROUTERS,
    PLAYER_SIZE,
    REPAIR_MAX_ANGLE,
    TILE_SIZE,
    GameState,
)


class GameStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.game = GameState(random.Random(7))

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
        self.repair(second, "COMEDOR", now=2.0)

        self.assertEqual(len(self.game.mission_repaired), 2)
        self.assertEqual(self.game.mission_index, 0)

        self.repair(first, "FIC", now=3.0)

        self.assertEqual(self.game.mission_index, 1)

    def test_critical_route_only_advances_in_order(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        self.game._begin_mission(1, now=0.0)

        self.repair(player, "FIEE", now=1.0)
        self.assertEqual(self.game.route_progress, 0)

        for index, name in enumerate(
            ("ENTRADA", "CTIC", "BIBLIOTECA", "FIGMM"), start=2
        ):
            self.repair(player, name, now=float(index))

        self.assertEqual(self.game.mission_index, 2)

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

        self.game.update(0.1, now=90.0)

        self.assertEqual(self.game.game_status, "defeat")

    def test_restart_resets_campaign_players_and_routers(self) -> None:
        player = self.game.add_player("Ada")
        assert player is not None
        player.repairs = 8
        player.effect = "ping"
        next(iter(self.game.routers.values())).repaired = True
        self.game.game_status = "victory"

        success, _ = self.game.restart_campaign(now=500.0)

        self.assertTrue(success)
        self.assertEqual(self.game.game_status, "playing")
        self.assertEqual(self.game.mission_index, 0)
        self.assertEqual(player.repairs, 0)
        self.assertIsNone(player.effect)
        self.assertFalse(any(router.repaired for router in self.game.routers.values()))

    def test_snapshot_exposes_campaign_contract(self) -> None:
        self.game._begin_mission(1, now=20.0)

        state = self.game.snapshot(now=25.0)

        self.assertEqual(state["game_status"], "playing")
        self.assertEqual(state["mission"]["id"], "critical_route")
        self.assertEqual(state["mission"]["time_remaining"], 145.0)
        self.assertIsNotNone(state["mission"]["target_router"])
        self.assertIn("result_message", state)


if __name__ == "__main__":
    unittest.main()
