#!/usr/bin/env node
/**
 * Token guard — SPEC-045.
 *
 * A component rule that names a colour cannot be theme-correct: the second
 * theme is a redefinition of ~30 semantic aliases, and a literal hex is
 * invisible to it. The same goes for a raw font size, which is how the type
 * scale drifted to nine ad-hoc values with no top end.
 *
 * So the design rule is a lint rather than a review convention: raw colours and
 * raw font sizes live in `styles/tokens.css` and nowhere else. Modelled on the
 * existing `generate-types.cjs --check` drift gate, and wired into
 * `make frontend-check` beside it.
 *
 * Exits non-zero with the offending file, line and value.
 */

const fs = require("node:fs");
const path = require("node:path");

const SRC = path.join(__dirname, "..", "src");
const TOKENS_FILE = path.join(SRC, "styles", "tokens.css");

// Extensions worth scanning: CSS carries the styling, TSX can carry inline
// styles, and both have been a home for stray colours in this codebase.
const EXTENSIONS = new Set([".css", ".ts", ".tsx"]);

// `#` followed by 3, 4, 6 or 8 hex digits, not part of a longer word.
const HEX = /#[0-9a-fA-F]{3,8}\b/g;
// A raw font size in rem/px/em, as a CSS declaration or a JSX style value.
const RAW_FONT_SIZE = /font-?[Ss]ize"?\s*[:=]\s*"?\s*[0-9.]+(rem|px|em)\b/g;

/** Files legitimately allowed to hold raw values, with the reason. */
const ALLOWED = new Map([
  [TOKENS_FILE, "the token layer is where raw values are defined"],
]);

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      // Generated types are derived from the JSON schemas, not hand-written.
      if (entry.name === "generated") continue;
      walk(full, out);
    } else if (EXTENSIONS.has(path.extname(entry.name))) {
      out.push(full);
    }
  }
  return out;
}

function violationsIn(file) {
  if (ALLOWED.has(file)) return [];
  const found = [];
  const lines = fs.readFileSync(file, "utf8").split("\n");
  lines.forEach((line, i) => {
    // A hex inside a comment is documentation, not a style declaration.
    const code = line.replace(/\/\*.*?\*\//g, "").replace(/\/\/.*$/, "");
    for (const match of code.match(HEX) ?? []) {
      found.push({ line: i + 1, value: match, kind: "raw colour" });
    }
    for (const match of code.match(RAW_FONT_SIZE) ?? []) {
      found.push({ line: i + 1, value: match.trim(), kind: "raw font size" });
    }
  });
  return found;
}

function main() {
  if (!fs.existsSync(TOKENS_FILE)) {
    console.error(`check-tokens: no token layer at ${path.relative(SRC, TOKENS_FILE)}`);
    process.exit(1);
  }

  const failures = [];
  for (const file of walk(SRC)) {
    for (const v of violationsIn(file)) {
      failures.push(`  ${path.relative(process.cwd(), file)}:${v.line}  ${v.kind}: ${v.value}`);
    }
  }

  if (failures.length > 0) {
    console.error(
      `check-tokens: ${failures.length} raw value(s) outside the token layer.\n` +
        "Colours and font sizes belong in src/styles/tokens.css as semantic\n" +
        "aliases; a literal here is invisible to the second theme.\n",
    );
    console.error(failures.join("\n"));
    process.exit(1);
  }

  console.log("check-tokens: clean — no raw colours or font sizes outside tokens.css");
}

main();
