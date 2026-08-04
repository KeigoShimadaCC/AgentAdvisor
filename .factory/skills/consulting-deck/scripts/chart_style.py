#!/usr/bin/env python3
"""Matplotlib theme and exhibit builders matched to deck.css.

Charts are exported as PNG because the PowerPoint renderer only accepts
png/jpeg/gif/webp data URIs. Figures are sized to the slide slots so type in the
chart matches type on the slide instead of being scaled up or down by the
browser.

Run with matplotlib available, e.g.:
    uv run --with matplotlib python tmp/deck/charts.py

Import from a deck script:
    import sys; sys.path.insert(0, ".factory/skills/consulting-deck/scripts")
    from chart_style import use_deck_style, figure, save, INK, ACCENT, MUTED
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

# Mirrors the custom properties in assets/deck.css.
INK = "#10202E"
INK_SOFT = "#33475B"
MUTED = "#6B7C8C"
RULE = "#D8DEE4"
TINT = "#F2F5F7"
ACCENT = "#1B6B8F"
ACCENT_SOFT = "#DBE9F0"
WARM = "#C2703A"
POS = "#2E7D5B"
NEG = "#A63B27"

#: Neutral series colours. Highlight one series with ACCENT and leave the rest grey.
SERIES = ["#1B6B8F", "#7FA8BC", "#B9C6CF", "#C2703A", "#2E7D5B", "#8794A0"]

#: Figure sizes in inches for the standard content slots, at 96 css px per inch.
SLOTS: dict[str, tuple[float, float]] = {
    "full": (9.08, 3.10),  # full content width, header + takeaway present
    "full-tall": (9.08, 3.75),  # full width, no takeaway band
    "split": (6.23, 3.10),  # beside a 252px commentary rail
    "split-tall": (6.23, 3.75),
    "half": (4.44, 2.90),
    "third": (2.90, 2.30),
}

DPI = 200


def use_deck_style() -> None:
    """Apply the deck theme globally. Call once before building figures."""
    plt.rcParams.update(
        {
            "figure.facecolor": "none",
            "axes.facecolor": "none",
            "savefig.facecolor": "none",
            "savefig.transparent": True,
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 10.5,
            "text.color": INK_SOFT,
            "axes.edgecolor": RULE,
            "axes.labelcolor": MUTED,
            "axes.labelsize": 9.5,
            "axes.titlesize": 11,
            "axes.titlecolor": INK,
            "axes.titlelocation": "left",
            "axes.titlepad": 8,
            "axes.linewidth": 0.9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": RULE,
            "grid.linewidth": 0.7,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "xtick.major.size": 3,
            "ytick.major.size": 0,
            "legend.frameon": False,
            "legend.fontsize": 9.5,
            "lines.linewidth": 2.0,
            "lines.solid_capstyle": "round",
            "patch.linewidth": 0,
        }
    )


def figure(slot: str = "full", **kwargs):
    """Create a figure sized for a slide slot. Returns ``(fig, ax)``."""
    if slot not in SLOTS:
        raise ValueError(f"unknown slot {slot!r}; choose from {sorted(SLOTS)}")
    w, h = SLOTS[slot]
    fig, ax = plt.subplots(figsize=(w, h), dpi=DPI, **kwargs)
    return fig, ax


def save(fig: Figure, path: str | Path) -> Path:
    """Write a transparent PNG and close the figure."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=DPI, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)
    return out


def clean(ax, *, xgrid: bool = False, ygrid: bool = True, yaxis: bool = True) -> None:
    """Strip chartjunk. Turn ``yaxis`` off when bars carry direct value labels."""
    ax.grid(axis="y", visible=ygrid)
    ax.grid(axis="x", visible=xgrid)
    ax.spines["left"].set_visible(False)
    if not yaxis:
        ax.set_yticks([])
        ax.set_ylabel("")


def label_bars(
    ax, bars, values: Sequence[float], fmt: str = "{:.0f}", *, horizontal: bool = False
) -> None:
    """Write the value at the end of each bar so the axis can be dropped."""
    for bar, v in zip(bars, values, strict=False):
        if horizontal:
            ax.annotate(
                fmt.format(v),
                (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                xytext=(5, 0),
                textcoords="offset points",
                va="center",
                ha="left",
                fontsize=9.5,
                color=INK,
                fontweight="bold",
            )
        else:
            ax.annotate(
                fmt.format(v),
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9.5,
                color=INK,
                fontweight="bold",
            )


def highlight(labels: Iterable[str], focus: str | Sequence[str]) -> list[str]:
    """Colour list putting ACCENT on the focus label(s) and grey on the rest."""
    focus_set = {focus} if isinstance(focus, str) else set(focus)
    return [ACCENT if lab in focus_set else "#B9C6CF" for lab in labels]


# --------------------------------------------------------------------------
# Exhibit builders for decision decks
# --------------------------------------------------------------------------


def scenario_bars(
    labels: Sequence[str],
    probabilities: Sequence[float],
    *,
    focus: str | None = None,
    slot: str = "split",
    unit: str = "",
):
    """Horizontal probability bars, highest at the top, labelled as percentages.

    ``probabilities`` are fractions in 0..1.
    """
    fig, ax = figure(slot)
    order = sorted(range(len(labels)), key=lambda i: probabilities[i])
    labs = [labels[i] for i in order]
    vals = [probabilities[i] for i in order]
    colors = highlight(labs, focus) if focus else [ACCENT] * len(labs)
    bars = ax.barh(labs, vals, color=colors, height=0.62)
    label_bars(ax, bars, [v * 100 for v in vals], "{:.0f}%", horizontal=True)
    ax.set_xlim(0, max(vals) * 1.22)
    ax.set_xticks([])
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelcolor=INK)
    ax.set_xlabel(unit)
    return fig, ax


def tornado(
    drivers: Sequence[str],
    low: Sequence[float],
    high: Sequence[float],
    *,
    base: float = 0.0,
    slot: str = "full",
    unit: str = "",
):
    """Sensitivity tornado, widest swing at the top."""
    fig, ax = figure(slot)
    spans = [abs(h - lo) for lo, h in zip(low, high, strict=True)]
    order = sorted(range(len(drivers)), key=lambda i: spans[i])
    y = range(len(order))
    for k, i in enumerate(order):
        lo, hi = min(low[i], high[i]), max(low[i], high[i])
        ax.barh(k, lo - base, left=base, color="#B9C6CF", height=0.6)
        ax.barh(k, hi - base, left=base, color=ACCENT, height=0.6)
    ax.set_yticks(list(y))
    ax.set_yticklabels([drivers[i] for i in order])
    ax.axvline(base, color=INK, linewidth=1.1)
    ax.tick_params(axis="y", length=0, labelcolor=INK)
    ax.set_xlabel(unit)
    clean(ax, xgrid=True, ygrid=False)
    ax.spines["bottom"].set_visible(False)
    return fig, ax


def waterfall(
    labels: Sequence[str],
    deltas: Sequence[float],
    *,
    start: float = 0.0,
    slot: str = "full",
    unit: str = "",
    fmt: str = "{:+,.0f}",
):
    """Bridge chart from a starting value through signed contributions to a total."""
    fig, ax = figure(slot)
    running = start
    for i, d in enumerate(deltas):
        color = POS if d >= 0 else NEG
        bottom = running if d >= 0 else running + d
        ax.bar(i, abs(d), bottom=bottom, color=color, width=0.62)
        ax.annotate(
            fmt.format(d),
            (i, max(running, running + d)),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color=INK,
        )
        running += d
    ax.bar(len(labels), running - start, bottom=start, color=ACCENT, width=0.62)
    ax.annotate(
        f"{running:,.0f}",
        (len(labels), running),
        xytext=(0, 4),
        textcoords="offset points",
        ha="center",
        fontsize=9.5,
        color=INK,
        fontweight="bold",
    )
    ax.set_xticks(range(len(labels) + 1))
    ax.set_xticklabels([*labels, "Total"], rotation=0)
    ax.set_ylabel(unit)
    clean(ax)
    return fig, ax


def ranked_bar(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    focus: str | None = None,
    slot: str = "split",
    unit: str = "",
    fmt: str = "{:,.0f}",
):
    """Ranked horizontal bars. The default exhibit for comparing alternatives."""
    fig, ax = figure(slot)
    order = sorted(range(len(labels)), key=lambda i: values[i])
    labs = [labels[i] for i in order]
    vals = [values[i] for i in order]
    colors = highlight(labs, focus) if focus else [ACCENT] * len(labs)
    bars = ax.barh(labs, vals, color=colors, height=0.62)
    label_bars(ax, bars, vals, fmt, horizontal=True)
    ax.set_xlim(0, max(vals) * 1.2)
    ax.set_xticks([])
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0, labelcolor=INK)
    ax.set_xlabel(unit)
    return fig, ax


def fan(
    x: Sequence[float],
    median: Sequence[float],
    bands: Sequence[tuple[Sequence[float], Sequence[float], str]],
    *,
    slot: str = "full",
    unit: str = "",
):
    """Median line with shaded uncertainty bands.

    ``bands`` is a sequence of ``(low, high, label)`` from widest to narrowest.
    """
    fig, ax = figure(slot)
    for k, (lo, hi, label) in enumerate(bands):
        ax.fill_between(x, lo, hi, color=ACCENT, alpha=0.14 + 0.12 * k, linewidth=0, label=label)
    ax.plot(x, median, color=ACCENT, linewidth=2.2, label="Median")
    ax.set_ylabel(unit)
    clean(ax)
    ax.legend(loc="upper left", ncol=len(bands) + 1, fontsize=9)
    return fig, ax


if __name__ == "__main__":
    # Smoke test: writes one of each exhibit to ./chart-style-check/.
    use_deck_style()
    out = Path("chart-style-check")
    save(
        scenario_bars(
            ["Base case", "Upside", "Downside", "Severe downside"],
            [0.45, 0.25, 0.22, 0.08],
            focus="Base case",
        )[0],
        out / "scenarios.png",
    )
    save(
        tornado(
            ["Discount rate", "Terminal growth", "Margin", "Volume"],
            [-18, -9, -14, -5],
            [21, 12, 8, 6],
            unit="change in NPV (%)",
        )[0],
        out / "tornado.png",
    )
    save(
        waterfall(["Revenue", "COGS", "Opex", "Tax"], [120, -48, -31, -9], unit="USD m")[0],
        out / "waterfall.png",
    )
    save(
        ranked_bar(
            ["Acquire", "Partner", "Build", "Do nothing"],
            [82, 64, 51, 30],
            focus="Acquire",
            unit="weighted score",
        )[0],
        out / "ranked.png",
    )
    print(f"wrote sample exhibits to {out.resolve()}")
