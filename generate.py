#!/usr/bin/env python
"""CLI entry point for the steam-profile skill.

Examples:
    python generate.py --steamid 7656119XXXXXXXXXX
    python generate.py --fixture tests/fixtures/owned_games.json --out output/test.png
    python generate.py --steamid 7656119XXXXXXXXXX --aggregation primary --scale log
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_ROOT))

from scripts.build_profile import build_profile, write_profile_json  # noqa: E402
from scripts.config import ensure_dirs, get_api_key, load_config  # noqa: E402
from scripts.generate_chart import (  # noqa: E402
    load_template,
    save_infographic,
    save_radar_svg,
)
from scripts.steam_fetch import (  # noqa: E402
    InvalidSteamId,
    NoGames,
    PrivateProfile,
    SteamError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Generate a Steam gaming profile infographic.",
    )
    parser.add_argument("--steamid", default="", help="SteamID64, profile URL, or vanity name.")
    parser.add_argument("--fixture", default="", help="Use a local fixture instead of the Steam API.")
    parser.add_argument(
        "--out",
        default=str(SKILL_ROOT / "output" / "steam_profile.png"),
        help="Output PNG path.",
    )
    parser.add_argument("--json-out", default="", help="Profile JSON path (defaults next to --out).")
    parser.add_argument("--mode", default="", help="Profile mode label, e.g. lifetime.")
    parser.add_argument("--aggregation", choices=["weighted", "full", "primary"], default="")
    parser.add_argument("--scale", choices=["linear", "sqrt", "log"], default="")
    parser.add_argument("--metadata-source", choices=["steamspy", "store"], default="")
    parser.add_argument("--top", type=int, default=0, help="Number of top games to show.")
    parser.add_argument("--categories", type=int, default=0, help="Max categories on the chart.")
    parser.add_argument("--no-other", action="store_true", help="Do not fold small categories into Other.")
    parser.add_argument("--template", default="", help="Path to a template JSON.")
    parser.add_argument("--title", default="", help="Override the chart title.")
    parser.add_argument("--subtitle", default="", help="Override the chart subtitle.")
    parser.add_argument("--api-key", default="", help="Steam Web API key (else STEAM_API_KEY).")
    parser.add_argument("--offline", action="store_true", help="Only use cached data; no network.")
    parser.add_argument("--radar-svg", default="", help="Optional path to also export the radar as SVG.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    ensure_dirs()

    mode = args.mode or config["default_mode"]
    aggregation = args.aggregation or config["aggregation"]
    scale = args.scale or config["scale"]
    metadata_source = args.metadata_source or config["metadata_source"]
    top = args.top or int(config["top_games"])
    max_categories = args.categories or int(config["max_categories"])
    include_other = config["include_other"] and not args.no_other

    steam_id = args.steamid or config["steam_id"]
    if not args.fixture and not steam_id:
        parser.error("Provide --steamid, set STEAM_ID, or pass --fixture.")

    try:
        profile = build_profile(
            steam_id=steam_id,
            mode=mode,
            top_games=top,
            max_categories=max_categories,
            aggregation=aggregation,
            scale=scale,
            include_other=include_other,
            api_key=get_api_key(args.api_key),
            metadata_source=metadata_source,
            offline=args.offline,
            fixture=args.fixture or None,
            cache_ttl_hours=float(config["cache_ttl_hours"]),
        )
    except PrivateProfile:
        print(
            "Your Steam game details appear to be private. "
            "Please make the relevant game details visible.",
            file=sys.stderr,
        )
        return 2
    except InvalidSteamId as exc:
        print(f"I couldn't find that Steam profile. {exc}", file=sys.stderr)
        return 2
    except NoGames:
        print("No playable games were found for this Steam profile.", file=sys.stderr)
        return 2
    except SteamError as exc:
        print(f"Steam data couldn't be retrieved right now. {exc}", file=sys.stderr)
        return 3

    out_png = Path(args.out)
    if not out_png.is_absolute():
        out_png = Path.cwd() / out_png
    json_path = Path(args.json_out) if args.json_out else out_png.with_suffix(".json")
    if not json_path.is_absolute():
        json_path = Path.cwd() / json_path

    write_profile_json(profile, json_path)

    template = load_template(args.template or None)
    if args.title:
        template["title"] = args.title
    if args.subtitle:
        template["subtitle"] = args.subtitle
    template["top_games"] = top

    save_infographic(profile, out_png, template)
    if args.radar_svg:
        save_radar_svg(
            list(profile["categories"].keys()),
            [float(v) for v in profile["categories"].values()],
            args.radar_svg,
            color=template["accent"],
        )

    print(f"Profile JSON: {json_path}")
    print(f"Image:        {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
