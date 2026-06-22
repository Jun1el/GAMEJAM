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


if __name__ == "__main__":
    unittest.main()
