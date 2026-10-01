import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.aggregate import aggregate  # noqa: E402

CATEGORY_ORDER = ["FPS", "Military", "Tanks", "Simulation", "Racing", "Driving"]


def game(name, hours, categories):
    return {"name": name, "hours": hours, "categories": categories}


class TestModes(unittest.TestCase):
    def setUp(self):
        self.games = [
            game("War Thunder", 800.0, ["Military", "Tanks", "Simulation", "Driving"]),
            game("Counter-Strike 2", 500.0, ["FPS"]),
        ]

    def test_weighted_sums_to_total(self):
        result = aggregate(self.games, mode="weighted", category_order=CATEGORY_ORDER)
        self.assertAlmostEqual(sum(result["category_hours"].values()), 1300.0, places=1)
        self.assertAlmostEqual(result["category_hours"]["FPS"], 500.0, places=1)
        self.assertAlmostEqual(result["category_hours"]["Military"], 200.0, places=1)

    def test_full_attribution_overlaps(self):
        result = aggregate(self.games, mode="full", category_order=CATEGORY_ORDER)
        self.assertAlmostEqual(result["category_hours"]["Military"], 800.0, places=1)
        self.assertAlmostEqual(result["category_hours"]["FPS"], 500.0, places=1)

    def test_primary_uses_category_order(self):
        result = aggregate(self.games, mode="primary", category_order=CATEGORY_ORDER)
        self.assertEqual(result["category_hours"].get("FPS"), 500.0)
        self.assertEqual(result["category_hours"].get("Military"), 800.0)
        self.assertNotIn("Tanks", result["category_hours"])


class TestNormalization(unittest.TestCase):
    def setUp(self):
        self.games = [
            game("A", 1000.0, ["Military"]),
            game("B", 250.0, ["FPS"]),
            game("C", 0.0, ["Music"]),
        ]

    def test_linear_scale(self):
        result = aggregate(self.games, scale="linear", category_order=CATEGORY_ORDER)
        self.assertEqual(result["categories"]["Military"], 100.0)
        self.assertEqual(result["categories"]["FPS"], 25.0)

    def test_sqrt_scale_raises_small_values(self):
        result = aggregate(self.games, scale="sqrt", category_order=CATEGORY_ORDER)
        self.assertEqual(result["categories"]["Military"], 100.0)
        self.assertEqual(result["categories"]["FPS"], 50.0)

    def test_log_scale(self):
        result = aggregate(self.games, scale="log", category_order=CATEGORY_ORDER)
        self.assertEqual(result["categories"]["Military"], 100.0)
        self.assertLess(result["categories"]["FPS"], 100.0)
        self.assertGreater(result["categories"]["FPS"], 0.0)


class TestSelection(unittest.TestCase):
    def test_top_n_folds_remainder_into_other(self):
        games = [
            game("a", 5.0, ["FPS"]),
            game("b", 4.0, ["Military"]),
            game("c", 3.0, ["Tanks"]),
            game("d", 2.0, ["Simulation"]),
            game("e", 1.0, ["Music"]),
        ]
        result = aggregate(
            games,
            mode="full",
            max_categories=3,
            include_other=True,
            category_order=CATEGORY_ORDER,
        )
        self.assertIn("Other", result["category_hours"])
        self.assertAlmostEqual(result["category_hours"]["Other"], 3.0, places=1)
        self.assertEqual(len(result["categories"]), 4)

    def test_include_other_can_be_disabled(self):
        games = [game("a", 5.0, ["FPS"]), game("b", 1.0, ["Music"])]
        result = aggregate(
            games,
            mode="full",
            max_categories=1,
            include_other=False,
            category_order=CATEGORY_ORDER,
        )
        self.assertNotIn("Other", result["category_hours"])

    def test_zero_value_categories_are_dropped(self):
        result = aggregate(
            [game("a", 5.0, ["FPS"])], mode="full", category_order=CATEGORY_ORDER
        )
        self.assertEqual(list(result["categories"].keys()), ["FPS"])


class TestTopGames(unittest.TestCase):
    def test_top_games_sorted_descending(self):
        games = [game("low", 1.0, ["FPS"]), game("high", 90.0, ["FPS"])]
        result = aggregate(games, top_games=2, category_order=CATEGORY_ORDER)
        self.assertEqual([g["name"] for g in result["top_games"]], ["high", "low"])

    def test_empty_library(self):
        result = aggregate([], category_order=CATEGORY_ORDER)
        self.assertEqual(result["categories"], {})
        self.assertEqual(result["top_games"], [])
        self.assertEqual(result["total_hours"], 0.0)


if __name__ == "__main__":
    unittest.main()
