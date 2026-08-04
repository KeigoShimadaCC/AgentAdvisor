# Charts

Every number on a slide comes from executed code. Write a script, run it, embed
the PNG it produced. Do not hand-author SVG, do not have the model compute
figures in prose, and do not retype numbers from an artifact into HTML when a
script could read them.

## Setup

`chart_style.py` provides the theme and the exhibit builders. matplotlib is not
a project dependency, so run chart scripts through `uv`:

```bash
uv run --with matplotlib python tmp/deck/charts.py
```

Script skeleton, written to `tmp/deck/charts.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, ".factory/skills/consulting-deck/scripts")
from chart_style import use_deck_style, save, scenario_bars, tornado, ACCENT

use_deck_style()
OUT = Path("tmp/deck/charts")

fig, ax = scenario_bars(
    ["Base case", "Upside", "Downside"],
    [0.52, 0.28, 0.20],
    focus="Base case",
    slot="split",
)
save(fig, OUT / "scenarios.png")
```

Verify the builders render on this machine before writing a deck script:

```bash
uv run --with matplotlib python .factory/skills/consulting-deck/scripts/chart_style.py
```

## Sizing

Pass the `slot` that matches the layout container the chart sits in. This makes
chart type render at the same size as slide type instead of being scaled by the
browser, which is the usual reason AI-built decks have illegible axis labels.

| Slot | Inches | Use inside |
| --- | --- | --- |
| `full` | 9.08 x 3.10 | `.exhibit` with a `.takeaway` below |
| `full-tall` | 9.08 x 3.75 | `.exhibit` alone |
| `split` | 6.23 x 3.10 | `.split` beside a `.rail`, with a takeaway |
| `split-tall` | 6.23 x 3.75 | `.split` beside a `.rail` |
| `half` | 4.44 x 2.90 | one column of `.cols-2` |
| `third` | 2.90 x 2.30 | one column of `.cols-3` |

## Builders

| Function | Exhibit | Use for |
| --- | --- | --- |
| `scenario_bars(labels, probabilities, focus=)` | ranked horizontal % bars | outcome probabilities by scenario |
| `ranked_bar(labels, values, focus=)` | ranked horizontal bars | comparing alternatives on one measure |
| `tornado(drivers, low, high, base=)` | sensitivity tornado | which assumption moves the answer most |
| `waterfall(labels, deltas, start=)` | bridge | decomposing a total into contributions |
| `fan(x, median, bands)` | median plus uncertainty bands | projections over time |

Each returns `(fig, ax)` so you can adjust before `save(fig, path)`. Build
anything else with `figure(slot)` plus `clean(ax)` and `label_bars(...)`.

## Conventions

**Label directly, drop the axis.** If every bar carries its value, the value
axis is redundant. `label_bars` plus `clean(ax, yaxis=False)` does this.

**One thing in colour.** Use `highlight(labels, focus)` so the recommended
option or the base case is `ACCENT` and everything else is grey. A chart where
every series is a different colour has no point of view.

**No title inside the chart.** The action title on the slide is the title. The
chart gets only `.exhibit__cap` stating what is plotted and its unit.

**Sort by value, not alphabetically**, unless the category has a natural order
such as time or a rating scale.

**Zero baseline on bars.** Truncated bar axes misrepresent differences. Line
charts may be truncated if the caption says so.

**Transparent background.** The theme saves with no background so charts sit on
white or tinted slides equally well. Do not set `facecolor`.

**Show uncertainty when it exists.** For anything projected or estimated, plot
the range, not just the point. `fan` and `tornado` exist for this. A single
confident line where the underlying number is a wide distribution is the most
common way a deck misleads.

## Tables versus charts

Use a table when the reader needs exact values, when the categories are more
than about eight, or when comparing options across several criteria (with
harvey balls). Use a chart when the shape of the data is the message. Do not
render a table as an image; use `<table class="tbl">` so the text stays crisp
and editable in the PowerPoint export.
