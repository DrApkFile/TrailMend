from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

WIDTH = 760
HEIGHT = 420
PAD_LEFT = 64
PAD_RIGHT = 190
PAD_TOP = 28
PAD_BOTTOM = 48
COLOURS: tuple[str, ...] = (
    "#2563eb",
    "#dc2626",
    "#059669",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#be185d",
    "#4b5563",
    "#65a30d",
)


@dataclass(frozen=True, slots=True)
class Series:
    name: str
    points: tuple[tuple[int, float], ...]


def _x(round_index: int, rounds: int) -> float:
    span = WIDTH - PAD_LEFT - PAD_RIGHT
    return PAD_LEFT + (span * round_index / rounds if rounds else 0)


def _y(value: float, low: float, high: float) -> float:
    span = HEIGHT - PAD_TOP - PAD_BOTTOM
    reach = high - low or 1.0
    return HEIGHT - PAD_BOTTOM - span * (value - low) / reach


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(series: Sequence[Series], title: str, low: float = 0.0, high: float = 1.0) -> str:
    rounds = max((point[0] for one in series for point in one.points), default=0)
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" '
        f'height="{HEIGHT}" font-family="ui-sans-serif, system-ui, sans-serif" font-size="12">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        f'<text x="{PAD_LEFT}" y="18" font-size="13" fill="#111827">{_escape(title)}</text>',
    ]
    for step in range(6):
        value = low + (high - low) * step / 5
        y = _y(value, low, high)
        parts.append(f'<line x1="{PAD_LEFT}" y1="{y:.1f}" x2="{WIDTH - PAD_RIGHT}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{PAD_LEFT - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#6b7280">{value:.2f}</text>')
    for round_index in range(rounds + 1):
        x = _x(round_index, rounds)
        parts.append(
            f'<text x="{x:.1f}" y="{HEIGHT - PAD_BOTTOM + 18:.1f}" text-anchor="middle" fill="#6b7280">'
            f"{round_index}</text>"
        )
    parts.append(
        f'<text x="{(PAD_LEFT + WIDTH - PAD_RIGHT) / 2:.1f}" y="{HEIGHT - 12}" text-anchor="middle" '
        f'fill="#6b7280">round</text>'
    )
    for index, one in enumerate(series):
        colour = COLOURS[index % len(COLOURS)]
        points = " ".join(
            f"{_x(round_index, rounds):.1f},{_y(value, low, high):.1f}" for round_index, value in one.points
        )
        parts.append(f'<polyline fill="none" stroke="{colour}" stroke-width="2" points="{points}"/>')
        for round_index, value in one.points:
            parts.append(
                f'<circle cx="{_x(round_index, rounds):.1f}" cy="{_y(value, low, high):.1f}" r="2.5" fill="{colour}"/>'
            )
        legend_y = PAD_TOP + 14 + index * 18
        parts.append(
            f'<line x1="{WIDTH - PAD_RIGHT + 16}" y1="{legend_y - 4}" x2="{WIDTH - PAD_RIGHT + 40}" '
            f'y2="{legend_y - 4}" stroke="{colour}" stroke-width="2"/>'
        )
        parts.append(f'<text x="{WIDTH - PAD_RIGHT + 46}" y="{legend_y}" fill="#374151">{_escape(one.name)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def mean_by_round(rows: Sequence[Mapping[str, object]], arm: str) -> tuple[tuple[int, float], ...]:
    totals: dict[int, list[float]] = {}
    for row in rows:
        if row.get("arm") != arm:
            continue
        held_out = row.get("held_out")
        if not isinstance(held_out, dict):
            continue
        accuracy = cast("dict[str, object]", held_out).get("accuracy")
        if not isinstance(accuracy, int | float):
            continue
        totals.setdefault(int(str(row["round"])), []).append(float(accuracy))
    return tuple((round_index, sum(values) / len(values)) for round_index, values in sorted(totals.items()))
