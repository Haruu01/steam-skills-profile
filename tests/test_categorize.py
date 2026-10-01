import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.categorize import (  # noqa: E402
    build_tag_index,
    categorize_games,
    load_tag_mapping,
    match_categories,
)


class TestMatchCategories(unittest.TestCase):
    def setUp(self):
        self.mapping = load_tag_mapping()

    def test_exact_tag_matches(self):
        self.assertEqual(match_categories(["FPS"], self.mapping), ["FPS"])
        self.assertEqual(match_categories(["Shooter"], self.mapping), ["FPS"])

    def test_case_insensitive(self):
        self.assertEqual(match_categories(["shooter"], self.mapping), ["FPS"])

    def test_multiple_categories_in_mapping_order(self):
        matched = match_categories(
            ["Vehicular Combat", "Tanks", "Simulation"], self.mapping
        )
        self.assertIn("Tanks", matched)
        self.assertIn("Driving", matched)
        self.assertIn("Simulation", matched)

    def test_unknown_tag_yields_no_categories(self):
        self.assertEqual(match_categories(["Totally Unknown Tag"], self.mapping), [])

    def test_tag_index_has_no_empty_entries(self):
        index = build_tag_index(self.mapping)
        self.assertIn("fps", index)
        self.assertTrue(all(index.values()))


class TestCategorizeGames(unittest.TestCase):
    def setUp(self):
        self.mapping = load_tag_mapping()

    def test_unknown_tags_fall_back_to_other(self):
        games = [{"appid": 1, "name": "Mystery", "hours": 10.0}]
        result = categorize_games(games, lambda appid: ["no-such-tag"], self.mapping)
        self.assertEqual(result[0]["categories"], ["Other"])

    def test_appid_zero_is_skipped(self):
        games = [{"appid": 0, "name": "Steam Client", "hours": 1.0}]
        result = categorize_games(games, lambda appid: [], self.mapping)
        self.assertEqual(result, [])

    def test_attaches_tags_and_categories(self):
        games = [{"appid": 730, "name": "Counter-Strike 2", "hours": 500.0}]
        result = categorize_games(games, lambda appid: ["FPS", "Shooter"], self.mapping)
        self.assertEqual(result[0]["tags"], ["FPS", "Shooter"])
        self.assertEqual(result[0]["categories"], ["FPS"])

    def test_original_game_objects_are_not_mutated(self):
        game = {"appid": 730, "name": "CS2", "hours": 1.0}
        categorize_games([game], lambda appid: ["FPS"], self.mapping)
        self.assertNotIn("categories", game)


if __name__ == "__main__":
    unittest.main()
