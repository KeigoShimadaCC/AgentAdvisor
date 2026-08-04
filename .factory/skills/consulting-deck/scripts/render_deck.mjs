#!/usr/bin/env node
/**
 * Render a built deck and report layout defects.
 *
 * Usage:
 *   node render_deck.mjs tmp/deck.preview.html [--out tmp/deck-render] [--no-pdf]
 *
 * Writes per-slide PNGs at 2x, a print-fidelity PDF, and report.json listing
 * every overflow, out-of-bounds element, clipped label and underfull slide.
 * Reuses the Chromium already installed for frontend/'s Playwright suite.
 *
 * Exit code is 1 when the report is non-empty, so it can gate a build.
 */

import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { mkdir, writeFile, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";

const SCRIPT_DIR = path.dirname(new URL(import.meta.url).pathname);
const REPO_ROOT = path.resolve(SCRIPT_DIR, "../../../..");

const SLIDE_W = 960;
const SLIDE_H = 540;
const UNDERFULL_RATIO = 0.45;
const MIN_FONT_PX = 9;

async function loadChromium() {
  const SPECS = ["playwright", "@playwright/test", "playwright-core"];
  // Playwright's entry points are CommonJS, so a dynamic import may expose the
  // named exports only under `default`.
  const pick = (mod) => mod?.chromium ?? mod?.default?.chromium;

  for (const spec of SPECS) {
    try {
      const chromium = pick(await import(spec));
      if (chromium) return chromium;
    } catch {
      /* try next */
    }
  }
  const anchor = path.join(REPO_ROOT, "frontend", "package.json");
  if (existsSync(anchor)) {
    const require = createRequire(pathToFileURL(anchor));
    for (const spec of SPECS) {
      try {
        const chromium = pick(await import(pathToFileURL(require.resolve(spec)).href));
        if (chromium) return chromium;
      } catch {
        /* try next */
      }
    }
  }
  throw new Error(
    "Playwright not found. Install it in frontend/ (npm install) or run: npm i -D playwright",
  );
}

function parseArgs(argv) {
  const args = { src: null, out: null, pdf: true };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--out") args.out = argv[++i];
    else if (a === "--no-pdf") args.pdf = false;
    else if (!args.src) args.src = a;
  }
  if (!args.src) throw new Error("usage: node render_deck.mjs <deck.preview.html> [--out DIR]");
  return args;
}

/** Runs in the page. Collects geometry defects the eye would otherwise have to catch. */
function auditSlides({ minFont, underfullRatio }) {
  const label = (el) => {
    const cls = (el.getAttribute("class") || "").trim().split(/\s+/).filter(Boolean).slice(0, 2);
    const text = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 48);
    return `${el.tagName.toLowerCase()}${cls.map((c) => "." + c).join("")}${text ? ` "${text}"` : ""}`;
  };

  const slides = [...document.querySelectorAll("section.slide")];
  return slides.map((slide, i) => {
    const issues = [];
    const sr = slide.getBoundingClientRect();

    if (slide.scrollHeight > slide.clientHeight + 1) {
      issues.push({
        type: "vertical-overflow",
        severity: "error",
        overflowPx: Math.round(slide.scrollHeight - slide.clientHeight),
        hint: "content taller than the frame; cut copy, drop a bullet, or move detail to the appendix",
      });
    }
    if (slide.scrollWidth > slide.clientWidth + 1) {
      issues.push({
        type: "horizontal-overflow",
        severity: "error",
        overflowPx: Math.round(slide.scrollWidth - slide.clientWidth),
        hint: "something is wider than the frame; check a table, an image, or a long unbroken string",
      });
    }

    for (const el of slide.querySelectorAll("*")) {
      const r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;

      const out = {
        top: sr.top - r.top,
        bottom: r.bottom - sr.bottom,
        left: sr.left - r.left,
        right: r.right - sr.right,
      };
      const worst = Object.entries(out).filter(([, v]) => v > 0.5);
      if (worst.length) {
        issues.push({
          type: "outside-frame",
          severity: "error",
          element: label(el),
          edges: Object.fromEntries(worst.map(([k, v]) => [k, Math.round(v)])),
        });
      }

      const ecs = getComputedStyle(el);
      const clipped =
        (ecs.overflow !== "visible" || ecs.overflowX !== "visible") &&
        (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) &&
        el !== slide;
      if (clipped && el.childElementCount === 0) {
        issues.push({ type: "clipped-text", severity: "error", element: label(el) });
      }

      const fs = parseFloat(ecs.fontSize);
      if (fs && fs < minFont && (el.textContent || "").trim()) {
        issues.push({
          type: "type-too-small",
          severity: "advice",
          element: label(el),
          fontSizePx: +fs.toFixed(1),
        });
      }
    }

    // Fill is measured inside .bd only. Measuring against the frame is
    // meaningless because .ft is pinned to the bottom of every slide.
    const body = slide.querySelector(":scope > .bd");
    const isDivider =
      slide.classList.contains("slide--title") || slide.classList.contains("slide--section");
    if (body && !isDivider) {
      // Sum the children rather than measuring to the last one's bottom edge:
      // a band pinned with margin-top:auto would otherwise mask an empty slide.
      const br = body.getBoundingClientRect();
      let filled = 0;
      for (const el of body.children) {
        const r = el.getBoundingClientRect();
        if (r.height >= 1) filled += r.height;
      }
      const used = br.height > 0 ? filled / br.height : 1;
      if (used < underfullRatio) {
        issues.push({
          type: "underfull",
          severity: "advice",
          fillRatio: +used.toFixed(2),
          hint: "most of the content area is empty; merge with a neighbour or add the supporting exhibit",
        });
      }
    }

    return { slide: i + 1, issues };
  });
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const src = path.resolve(args.src);
  if (!existsSync(src)) throw new Error(`not found: ${src}`);

  const base = path.basename(src).replace(/\.preview\.html$/, "").replace(/\.html$/, "");
  const outDir = path.resolve(args.out ?? path.join(path.dirname(src), `${base}-render`));
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });

  const chromium = await loadChromium();
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: SLIDE_W, height: SLIDE_H },
    deviceScaleFactor: 2,
  });

  await page.goto(pathToFileURL(src).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts?.ready);

  const slides = await page.locator("section.slide").all();
  if (slides.length === 0) throw new Error('no <section class="slide"> elements found');

  for (let i = 0; i < slides.length; i += 1) {
    const n = String(i + 1).padStart(2, "0");
    await slides[i].screenshot({ path: path.join(outDir, `slide-${n}.png`) });
  }

  const audit = await page.evaluate(auditSlides, {
    minFont: MIN_FONT_PX,
    underfullRatio: UNDERFULL_RATIO,
  });
  const findings = audit.filter((s) => s.issues.length > 0);

  let pdfPath = null;
  if (args.pdf) {
    pdfPath = path.join(path.dirname(src), `${base}.pdf`);
    await page.pdf({
      path: pdfPath,
      width: `${SLIDE_W / 96}in`,
      height: `${SLIDE_H / 96}in`,
      printBackground: true,
      pageRanges: `1-${slides.length}`,
    });
  }

  await browser.close();

  const errors = findings.reduce(
    (n, s) => n + s.issues.filter((i) => i.severity === "error").length,
    0,
  );
  const advice = findings.reduce(
    (n, s) => n + s.issues.filter((i) => i.severity !== "error").length,
    0,
  );

  const report = { source: src, slides: slides.length, errors, advice, findings };
  await writeFile(path.join(outDir, "report.json"), JSON.stringify(report, null, 2) + "\n");

  console.log(`slides rendered: ${slides.length} -> ${outDir}/slide-NN.png`);
  if (pdfPath) console.log(`pdf: ${pdfPath}`);

  if (findings.length === 0) {
    console.log("layout report: clean");
  } else {
    console.log(`layout report: ${errors} error(s), ${advice} advisory`);
    for (const { slide, issues } of findings) {
      for (const issue of issues) {
        const detail = Object.entries(issue)
          .filter(([k]) => !["type", "hint", "severity"].includes(k))
          .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`)
          .join(" ");
        console.log(`  slide ${slide}: [${issue.severity}] ${issue.type} ${detail}`);
        if (issue.hint) console.log(`      ${issue.hint}`);
      }
    }
  }

  console.log("Now READ the slide PNGs. Geometry is checked; visual quality is not.");
  return errors > 0 ? 1 : 0;
}

main().then(
  (code) => process.exit(code),
  (err) => {
    console.error(`error: ${err.message}`);
    process.exit(2);
  },
);
