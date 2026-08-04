#!/usr/bin/env python3
"""Inline a deck's stylesheets and images into self-contained HTML.

Reads an authored slide file (which links deck.css and references chart PNGs by
relative path) and writes two self-contained documents next to ``tmp/``:

  <name>.preview.html   deck.css + preview.css, used for rendering and review
  <name>.pptx.html      deck.css only, consumed by Factory's PowerPoint renderer

The pptx renderer strips scripts, remote resources and non-``data:`` URLs, so
this script resolves those ahead of time and fails loudly when it cannot.

Usage:
    python3 build_deck.py tmp/deck/slides.html [--out-dir tmp] [--name deck]

Standard library only.
"""

from __future__ import annotations

import argparse
import base64
import mimetypes
import re
import sys
from pathlib import Path

SKILL_ASSETS = Path(__file__).resolve().parent.parent / "assets"
PREVIEW_CSS = SKILL_ASSETS / "preview.css"

RASTER_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}

LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
IMG_SRC_RE = re.compile(r"""(<img\b[^>]*?\bsrc\s*=\s*)(["'])([^"']+)\2""", re.IGNORECASE)
SCRIPT_RE = re.compile(r"<script\b.*?</script\s*>", re.IGNORECASE | re.DOTALL)
ON_ATTR_RE = re.compile(r"""\son[a-z]+\s*=\s*(["']).*?\1""", re.IGNORECASE | re.DOTALL)
CSS_URL_RE = re.compile(r"""url\(\s*(["']?)([^"')]+)\1\s*\)""", re.IGNORECASE)
SLIDE_RE = re.compile(r"""<section\b[^>]*\bclass\s*=\s*["'][^"']*\bslide\b""", re.IGNORECASE)
HEAD_CLOSE_RE = re.compile(r"</head\s*>", re.IGNORECASE)


class BuildError(Exception):
    pass


def _is_remote(url: str) -> bool:
    low = url.strip().lower()
    return low.startswith(("http://", "https://", "//", "data:"))


def _data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime not in RASTER_TYPES:
        raise BuildError(
            f"{path}: PowerPoint accepts only png/jpeg/gif/webp images, got {mime or 'unknown'}. "
            "Re-export the chart as PNG."
        )
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def _inline_css_urls(css: str, css_dir: Path) -> str:
    """Embed local url(...) references inside a stylesheet."""

    def repl(m: re.Match[str]) -> str:
        url = m.group(2)
        if _is_remote(url):
            return "none" if not url.lower().startswith("data:") else m.group(0)
        target = (css_dir / url).resolve()
        if not target.is_file():
            raise BuildError(f"{css_dir}: stylesheet references missing file {url}")
        return f"url({_data_uri(target)})"

    return CSS_URL_RE.sub(repl, css)


def _collect_stylesheets(html: str, base: Path) -> tuple[str, str]:
    """Replace local <link rel=stylesheet> tags with a single inlined <style>."""
    collected: list[str] = []

    def repl(m: re.Match[str]) -> str:
        tag = m.group(0)
        if "stylesheet" not in tag.lower():
            return tag
        href_m = HREF_RE.search(tag)
        if not href_m:
            return ""
        href = href_m.group(1)
        if _is_remote(href):
            raise BuildError(
                f"remote stylesheet {href!r} is not allowed; the PowerPoint renderer strips it. "
                "Use deck.css plus a local <style> override block."
            )
        target = (base / href).resolve()
        if not target.is_file():
            raise BuildError(f"stylesheet not found: {href} (resolved to {target})")
        collected.append(_inline_css_urls(target.read_text(encoding="utf-8"), target.parent))
        return ""

    stripped = LINK_RE.sub(repl, html)
    return stripped, "\n".join(collected)


def _inline_images(html: str, base: Path) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        prefix, quote, src = m.group(1), m.group(2), m.group(3)
        if src.lower().startswith("data:"):
            return m.group(0)
        if _is_remote(src):
            raise BuildError(
                f"remote image {src!r} is not allowed; download it into the deck folder first."
            )
        target = (base / src).resolve()
        if not target.is_file():
            raise BuildError(
                f"image not found: {src} (resolved to {target}). "
                "Generate the chart before building the deck."
            )
        count += 1
        return f"{prefix}{quote}{_data_uri(target)}{quote}"

    return IMG_SRC_RE.sub(repl, html), count


def _insert_style(html: str, css: str) -> str:
    block = f"<style>\n{css}\n</style>\n"
    if HEAD_CLOSE_RE.search(html):
        return HEAD_CLOSE_RE.sub(block + "</head>", html, count=1)
    return block + html


def _lint(html: str) -> list[str]:
    """Cheap structural warnings. Visual defects are caught by render_deck.mjs."""
    warnings: list[str] = []
    sections = re.findall(
        r"<section\b[^>]*\bclass\s*=\s*[\"']([^\"']*)[\"'][^>]*>(.*?)</section\s*>",
        html,
        re.IGNORECASE | re.DOTALL,
    )
    n = 0
    for classes, inner in sections:
        if "slide" not in classes.split():
            continue
        n += 1
        variant = classes
        if "slide--title" in variant or "slide--section" in variant:
            continue
        if 'class="src"' not in inner and "class='src'" not in inner:
            warnings.append(f'slide {n}: no source line (<p class="src">)')
        title_m = re.search(
            r"<h1\b[^>]*class\s*=\s*[\"'][^\"']*action-title[^\"']*[\"'][^>]*>(.*?)</h1>",
            inner,
            re.IGNORECASE | re.DOTALL,
        )
        if not title_m:
            warnings.append(f"slide {n}: no action title")
        else:
            text = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            # Appendix slides conventionally use labels, not assertions.
            if "slide--appendix" not in variant and len(text.split()) < 4:
                warnings.append(
                    f'slide {n}: title "{text}" reads as a label; make it a full-sentence claim'
                )
    if n == 0:
        warnings.append('no <section class="slide"> found; the deck would render empty')
    return warnings


def build(src: Path, out_dir: Path, name: str) -> tuple[Path, Path]:
    if not src.is_file():
        raise BuildError(f"slide source not found: {src}")
    base = src.parent
    html = src.read_text(encoding="utf-8")

    html = SCRIPT_RE.sub("", html)
    html = ON_ATTR_RE.sub("", html)
    html, deck_css = _collect_stylesheets(html, base)
    html, n_images = _inline_images(html, base)

    if not deck_css.strip():
        raise BuildError(
            "no local stylesheet was linked. Link deck.css from slides.html, e.g. "
            '<link rel="stylesheet" href="../../.factory/skills/consulting-deck/assets/deck.css">'
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = out_dir / f"{name}.pptx.html"
    preview_path = out_dir / f"{name}.preview.html"

    pptx_path.write_text(_insert_style(html, deck_css), encoding="utf-8")
    preview_css = deck_css + "\n" + PREVIEW_CSS.read_text(encoding="utf-8")
    preview_path.write_text(_insert_style(html, preview_css), encoding="utf-8")

    n_slides = len(SLIDE_RE.findall(html))
    print(f"slides: {n_slides}   images embedded: {n_images}")
    print(f"powerpoint -> {pptx_path}")
    print(f"preview    -> {preview_path}")

    for w in _lint(html):
        print(f"warning: {w}")
    return pptx_path, preview_path


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=Path, help="authored slides HTML")
    ap.add_argument(
        "--out-dir", type=Path, default=None, help="output directory (default: tmp/ beside source)"
    )
    ap.add_argument("--name", default=None, help="output basename (default: parent folder name)")
    args = ap.parse_args(argv)

    src = args.source.resolve()
    name = args.name or (src.parent.name if src.parent.name != "tmp" else src.stem)
    out_dir = (args.out_dir or src.parent.parent).resolve()

    try:
        build(src, out_dir, name)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
