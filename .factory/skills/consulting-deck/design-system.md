# Design system

Read this before authoring the first slide. Everything below is already
implemented in `assets/deck.css`. Compose these classes; do not invent layout
with ad-hoc inline styles, and do not edit `deck.css`.

## Slide grammar

The rules that separate a consulting deck from a corporate one.

**Action titles.** The title is the finding, written as a full sentence that a
reader could quote. "Revenue growth is concentrated in two accounts, leaving the
plan exposed" is a title. "Revenue analysis" is a label, and labels make a deck
unreadable without a presenter. Read your titles top to bottom: they should form
the argument on their own.

**Answer first.** Slide 2 states the recommendation. Support follows. Never
build to a conclusion at the end; the reader will not get there.

**One message, one exhibit.** If a slide needs two charts to make its point, it
is two slides or the wrong chart.

**So what, not what.** Every exhibit is followed by its consequence, either in
the right-hand `.rail` or in a `.takeaway` band. Data with no interpretation is
an appendix item.

**MECE.** Columns, cards and buckets must not overlap, and together must cover
the space. Three cards labelled "Cost", "Risk" and "Financial impact" fail this.

**Sources always.** Every slide with a number carries a `<p class="src">` giving
the source and the date, plus any limitation the reader would need. This is not
decoration; it is what makes the deck auditable.

**Restraint.** One accent colour. No shadows, no gradients, no icon sets, no
stock photography, no more than two type sizes per zone.

## Frame and type scale

The frame is 960 x 540 px with 44 px side padding, so the content column is
872 px wide. Default reading-deck scale: action title 28 px, body 15 px, small
text 12.5 px, source 9.5 px. Add `class="deck--present"` on `<body>` for a stage
deck (title 36, body 20).

Serif (Georgia) is used only for action titles, big numerals and KPI values.
Everything else is Arial/Helvetica. Both are web-safe, which the PowerPoint
export requires.

## Slide skeleton

```html
<section class="slide">
  <div class="hd">
    <p class="kicker">Section name</p>
    <h1 class="action-title">The claim this slide proves</h1>
  </div>
  <div class="bd">
    <!-- one layout container from the list below -->
  </div>
  <div class="ft">
    <p class="src">Source: …</p>
    <span class="pg">4</span>
  </div>
</section>
```

`.hd` and `.ft` are fixed height; `.bd` absorbs the rest. Use `.ft--bare` when
the body already ends in a `.takeaway` band, so you do not stack two rules.

## Layout containers

Put exactly one of these directly inside `.bd`.

| Class | Shape | Use for |
| --- | --- | --- |
| `.cols-2` | two equal columns | before/after, option A vs B |
| `.cols-3` | three equal columns | three reasons, three workstreams |
| `.cols-4` | four equal columns | four short cards, never four paragraphs |
| `.split` | content + 252 px rail | any chart that needs commentary |
| `.split--narrow` | content + 190 px rail | wide tables with a short note |
| `.split--left` | 190 px rail + content | when the label column reads first |
| `.exhibit` | single centred figure | full-bleed chart, no commentary |
| `.matrix` | 2 x 2 grid | positioning, prioritisation |
| `.steps` | horizontal step flow | process, phasing, timeline |
| `.kpis` | metric band | 3 to 5 headline numbers |

## Components

**Cards.** `.card` (tinted, accent top rule), `.card--plain`, `.card--warm`,
`.card--pos`, `.card--neg`. Structure: optional `<span class="num">1</span>`,
then `<h3>`, then one or two short lines.

**KPI band.** `.kpis` wrapping `.kpi` blocks, each holding
`<span class="kpi__val">` (add `--pos` / `--neg`) and `<span class="kpi__lab">`.
Keep labels to three words.

**Table.** `<table class="tbl">`. First column is auto-bolded as the row label.
Add `class="n"` to numeric cells for right alignment and tabular figures. Add
`class="hl"` to the row that carries the recommendation.

**Commentary rail.** `.rail` containing `<h4>` sub-labels and short `<p>`
paragraphs. This is where "what it shows" and "why it matters" live.

**Takeaway.** `.takeaway` with a bolded lead-in, e.g.
`<b>So what.</b> …`. One per slide at most. `.callout` is the warmer variant for
a caveat or a risk.

**Tags.** `.tag`, `.tag--pos`, `.tag--neg`, `.tag--warn`, `.tag--flat` for
status, confidence level, or verdict chips inside tables and cards.

**Harvey balls.** `<span class="hb hb-3"></span>`, levels `hb-0` through `hb-4`.
The standard way to score options against criteria in a table. Always add a
legend line in the source area explaining the scale.

**Exhibit.** `.exhibit` wrapping `<p class="exhibit__cap">Exhibit 1 · units</p>`
and an `<img>`. The caption states what is plotted and in what unit; the
interpretation belongs in the rail or takeaway.

## Slide variants

| Class | Purpose |
| --- | --- |
| `.slide--title` | Dark cover. Kicker, 44 px title, `.meta` line for audience and date. |
| `.slide--section` | Tinted divider. `<div class="rule"></div>`, kicker, title. |
| `.slide--exec` | Executive summary. Use the `.answer` block for the recommendation. |
| `.slide--dark` | Inverted content slide, for a single emphatic point. |
| `.slide--appendix` | Denser type for evidence tables and method notes. |

## Retheming

Override custom properties in the deck-local `<style>` block, never in
`deck.css`:

```html
<style>
  :root {
    --accent: #7a4b8f;
    --accent-soft: #ece2f2;
  }
</style>
```

`--accent`, `--ink`, `--tint`, `--warm`, `--pos`, `--neg`, `--serif`, `--sans`
and the `--t-*` type sizes are all safe to override. Keep contrast high; the
deck must stay legible when printed in greyscale.

## Failure modes the renderer will catch, and what to do

| Report entry | Severity | Fix |
| --- | --- | --- |
| `vertical-overflow` | error | Cut copy. A slide that overflows is a slide with two messages. |
| `horizontal-overflow` | error | Usually a table with too many columns or an unbroken string. |
| `outside-frame` | error | An absolutely positioned or negatively margined element; remove it. |
| `clipped-text` | error | A grid cell too narrow for its label. Shorten the label or widen the column. |
| `type-too-small` | advice | You overrode a font size. Use the scale instead. |
| `underfull` | advice | Children fill under 45% of the content area. Fine for a short appendix table, not for an argument slide. |

Layout containers placed directly in `.bd` stretch to fill the frame, so cards
and exhibits reach the footer instead of leaving a dead band. Tables keep their
natural row heights; a trailing `.takeaway` or `.callout` is pinned to the
bottom so the slack reads as spacing.

A clean report means the geometry is valid. It says nothing about whether the
deck looks good, which is why the workflow requires you to read the PNGs.
