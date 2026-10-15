import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import session  # noqa: E402
from scripts.steam_fetch import (  # noqa: E402
    SteamClient,
    _repair_mojibake,
    is_non_game,
)


class FakeCache:
    def __init__(self, value):
        self.value = value
        self.set_values = {}

    def get(self, key):
        return self.value

    def set(self, key, value, ttl_seconds=None):
        self.set_values[key] = value


class TestRepairMojibake(unittest.TestCase):
    def test_fixes_double_encoded_trademark(self):
        mojibake = "Battlefield" + "\u00e2\u201e\u00a2" + " 6"
        self.assertEqual(_repair_mojibake(mojibake), "Battlefield\u2122 6")

    def test_fixes_double_encoded_registered(self):
        mojibake = "Overwatch" + "\u00c2\u00ae"
        self.assertEqual(_repair_mojibake(mojibake), "Overwatch\u00ae")

    def test_clean_text_unchanged(self):
        self.assertEqual(_repair_mojibake("Counter-Strike 2"), "Counter-Strike 2")

    def test_empty_and_none(self):
        self.assertEqual(_repair_mojibake(""), "")
        self.assertIsNone(_repair_mojibake(None))


class TestIsNonGame(unittest.TestCase):
    def test_software(self):
        self.assertTrue(is_non_game("OBS Studio"))
        self.assertTrue(is_non_game("Action! - Gameplay Recording and Streaming"))
        self.assertTrue(is_non_game("Discord Bot Maker"))
        self.assertTrue(is_non_game("EmoteLab"))

    def test_pre_release_builds(self):
        self.assertTrue(is_non_game("BattleBit Remastered Playtest"))
        self.assertTrue(is_non_game("Delta Force Alpha Test"))
        self.assertTrue(is_non_game("Mecha BREAK Beta"))

    def test_real_games(self):
        self.assertFalse(is_non_game("Counter-Strike 2"))
        self.assertFalse(is_non_game("War Thunder"))
        self.assertFalse(is_non_game("Half-Life 2"))
        self.assertFalse(is_non_game("Euro Truck Simulator 2"))


class TestFetchLibraryFiltering(unittest.TestCase):
    def test_filters_and_repairs(self):
        raw = [
            {
                "appid": 1,
                "name": "Battlefield" + "\u00e2\u201e\u00a2" + " 6",
                "playtime_forever": 6184,
            },
            {"appid": 2, "name": "OBS Studio", "playtime_forever": 1000},
            {"appid": 3, "name": "Counter-Strike 2", "playtime_forever": 0},
            {"appid": 4, "name": "Some Game Playtest", "playtime_forever": 500},
        ]
        client = SteamClient(api_key="test", cache=FakeCache(raw))
        games = client.fetch_library("76561198203279320")

        self.assertEqual([g["appid"] for g in games], [1])
        self.assertEqual(games[0]["name"], "Battlefield\u2122 6")
        self.assertEqual(games[0]["hours"], round(6184 / 60.0, 1))


class TestSessionSecretProduction(unittest.TestCase):
    def test_raises_in_production_without_secret(self):
        with mock.patch.dict(
            os.environ, {"ENV": "production", "SESSION_SECRET": ""}, clear=False
        ):
            with self.assertRaises(RuntimeError):
                session._secret()

    def test_uses_dev_secret_outside_production(self):
        with mock.patch.dict(
            os.environ, {"ENV": "", "SESSION_SECRET": ""}, clear=False
        ):
            self.assertEqual(session._secret(), session.DEV_SECRET.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
