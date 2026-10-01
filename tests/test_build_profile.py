import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_profile import build_profile, load_fixture  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
OWNED_GAMES = FIXTURES / "owned_games.json"
EXPECTED = FIXTURES / "expected_profile.json"


class TestFixturePipeline(unittest.TestCase):
    def test_matches_expected_profile(self):
        profile = build_profile(fixture=str(OWNED_GAMES), top_games=5)
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))

        profile["profile"].pop("generated_at", None)
        expected["profile"].pop("generated_at", None)
        self.assertEqual(profile, expected)

    def test_weighted_hours_equal_total(self):
        profile = build_profile(fixture=str(OWNED_GAMES))
        self.assertAlmostEqual(
            sum(profile["category_hours"].values()),
            profile["stats"]["total_hours"],
            places=1,
        )

    def test_load_fixture_accepts_raw_steam_payload(self):
        import tempfile

        payload = {
            "response": {
                "games": [
                    {"appid": 1, "name": "A", "playtime_forever": 120},
                    {"appid": 2, "name": "B", "playtime_forever": 60},
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            games, tags = load_fixture(path)
        self.assertEqual([g["hours"] for g in games], [2.0, 1.0])
        self.assertEqual(tags, {})


if __name__ == "__main__":
    unittest.main()
