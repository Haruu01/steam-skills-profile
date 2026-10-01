"""Render the Steam gaming profile infographic (radar + top games)."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from . import config  # noqa: E402
from .categorize import load_category_config  # noqa: E402

DEFAULT_TEMPLATE: Dict[str, Any] = {
    "title": "YOU ARE WHAT YOU PLAY",
    "subtitle": "Your Steam Gaming Profile",
    "width": 1600,
    "height": 1600,
    "top_games": 5,
    "categories": 8,
    "background_top": "#0B1020",
    "background_bottom": "#141B36",
    "accent": "#4FC3F7",
    "text": "#F5F7FF",
    "muted": "#9AA4C7",
}


def load_template(path: Optional[str] = None) -> Dict[str, Any]:
    template = dict(DEFAULT_TEMPLATE)
    template_path = Path(path) if path else config.TEMPLATES_DIR / "classic.json"
    if template_path.exists():
        try:
            loaded = json.loads(template_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                template.update(loaded)
        except (json.JSONDecodeError, OSError):
            pass
    return template


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _default_font_path() -> Optional[str]:
    bundled = config.FONTS_DIR / "Inter-Regular.ttf"
    if bundled.exists():
        return str(bundled)
    try:
        from matplotlib import font_manager

        return font_manager.findfont("DejaVu Sans")
    except Exception:  # noqa: BLE001
        return None


def _bold_font_path() -> Optional[str]:
    bundled = config.FONTS_DIR / "Inter-Bold.ttf"
    if bundled.exists():
        return str(bundled)
    try:
        from matplotlib import font_manager

        return font_manager.findfont("DejaVu Sans:bold")
    except Exception:  # noqa: BLE001
        return _default_font_path()


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = _bold_font_path() if bold else _default_font_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)  # type: ignore[call-arg]
    except TypeError:
        return ImageFont.load_default()


def render_radar(
    labels: List[str],
    values: List[float],
    size: int = 820,
    color: str = "#4FC3F7",
    fill_alpha: float = 0.30,
) -> Optional[Image.Image]:
    """Render a transparent radar chart. Returns None when fewer than 3 axes."""
    if len(labels) < 3:
        return None

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    closed_angles = angles + angles[:1]
    closed_values = list(values) + list(values[:1])

    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    ax = fig.add_subplot(111, polar=True)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, color="#F5F7FF", fontsize=13)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels([])

    ax.spines["polar"].set_visible(False)
    ax.grid(color="#8A93B8", alpha=0.30, linewidth=0.8)

    rgb = tuple(c / 255 for c in _hex_to_rgb(color))
    ax.plot(closed_angles, closed_values, color=rgb, linewidth=2.4)
    ax.fill(closed_angles, closed_values, color=rgb, alpha=fill_alpha)
    ax.scatter(angles, values, color=rgb, s=26, zorder=5)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    buffer.seek(0)
    return Image.open(buffer).convert("RGBA")


def render_bars(
    labels: List[str],
    values: List[float],
    width: int = 900,
    height: int = 620,
    color: str = "#4FC3F7",
) -> Image.Image:
    """Bar-chart fallback used when there are fewer than 3 categories."""
    fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
    fig.patch.set_alpha(0.0)
    ax.set_facecolor("none")
    rgb = tuple(c / 255 for c in _hex_to_rgb(color))
    ax.barh(labels[::-1], values[::-1], color=rgb, alpha=0.85)
    ax.tick_params(colors="#F5F7FF", labelsize=13)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="x", color="#8A93B8", alpha=0.25)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", transparent=True, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    buffer.seek(0)
    return Image.open(buffer).convert("RGBA")


def _vertical_gradient(width: int, height: int, top: str, bottom: str) -> Image.Image:
    top_rgb, bottom_rgb = _hex_to_rgb(top), _hex_to_rgb(bottom)
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(
            int(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * t) for i in range(3)
        )
        draw.line([(0, y), (width, y)], fill=color)
    return image.convert("RGBA")


def _truncate(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    if font.getlength(text) <= max_width:
        return text
    ellipsis = "\u2026"
    while text and font.getlength(text + ellipsis) > max_width:
        text = text[:-1]
    return text + ellipsis


def render_infographic(profile: Dict[str, Any], template: Optional[Dict[str, Any]] = None) -> Image.Image:
    template = template or load_template()
    width = int(template["width"])
    height = int(template["height"])
    text_color = template["text"]
    muted = template["muted"]
    accent = template["accent"]

    canvas = _vertical_gradient(
        width, height, template["background_top"], template["background_bottom"]
    )
    draw = ImageDraw.Draw(canvas)

    title_font = _load_font(66, bold=True)
    subtitle_font = _load_font(30)
    section_font = _load_font(34, bold=True)
    row_font = _load_font(30)
    rank_font = _load_font(30, bold=True)

    draw.text((width / 2, 96), str(template["title"]).upper(), font=title_font, fill=text_color, anchor="mm")
    draw.text((width / 2, 164), str(template["subtitle"]), font=subtitle_font, fill=muted, anchor="mm")

    categories = profile.get("categories", {})
    labels = list(categories.keys())
    values = [float(v) for v in categories.values()]

    chart_top = 220
    chart_bottom = 1050
    chart_height = chart_bottom - chart_top
    chart_size = min(width - 240, chart_height, 820)

    if len(labels) >= 3:
        chart = render_radar(labels, values, size=chart_size, color=accent)
    else:
        chart = render_bars(labels, values, width=int(chart_size * 1.2), height=chart_height - 60, color=accent)

    if chart is not None:
        chart = chart.resize(
            (
                int(chart.width * min(1.0, (chart_height) / chart.height)),
                int(chart.height * min(1.0, (chart_height) / chart.height)),
            ),
            Image.LANCZOS,
        )
        canvas.alpha_composite(chart, ((width - chart.width) // 2, chart_top))

    top_games = profile.get("top_games", [])[: int(template.get("top_games", 5))]
    section_y = 1090
    draw.text((width / 2, section_y), "YOUR TOP GAMES", font=section_font, fill=text_color, anchor="mm")

    row_y = section_y + 70
    row_step = 62
    left = 260
    right = width - 260
    for index, game in enumerate(top_games, start=1):
        y = row_y + (index - 1) * row_step
        if y > height - 40:
            break
        draw.text((left, y), f"{index:02d}", font=rank_font, fill=accent, anchor="lm")
        name = _truncate(str(game.get("name", "Unknown")), row_font, right - left - 180)
        draw.text((left + 70, y), name, font=row_font, fill=text_color, anchor="lm")
        hours = game.get("hours", 0)
        draw.text((right, y), f"{hours:g}h", font=row_font, fill=muted, anchor="rm")

    footer = f"{profile.get('stats', {}).get('game_count', 0)} games  \u00b7  {profile.get('stats', {}).get('total_hours', 0):g}h total"
    draw.text((width / 2, height - 46), footer, font=subtitle_font, fill=muted, anchor="mm")

    return canvas


def save_radar_svg(
    labels: List[str], values: List[float], path: str | Path, color: str = "#4FC3F7"
) -> Optional[Path]:
    if len(labels) < 3:
        return None
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    closed_angles = angles + angles[:1]
    closed_values = list(values) + list(values[:1])
    fig = plt.figure(figsize=(8, 8), dpi=100)
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 100)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels)
    rgb = tuple(c / 255 for c in _hex_to_rgb(color))
    ax.plot(closed_angles, closed_values, color=rgb, linewidth=2.4)
    ax.fill(closed_angles, closed_values, color=rgb, alpha=0.3)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig)
    return out


def save_infographic(
    profile: Dict[str, Any],
    out_path: str | Path,
    template: Optional[Dict[str, Any]] = None,
) -> Path:
    image = render_infographic(profile, template)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(out, format="PNG")
    return out
