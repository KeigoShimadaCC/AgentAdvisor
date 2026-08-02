#!/usr/bin/env node
/**
 * Generate TypeScript type files from JSON Schemas.
 *
 * Reads every `schemas/*.schema.json` and emits a corresponding
 * `frontend/src/generated/<name>.ts` file using json-schema-to-typescript.
 *
 * With --check: exits non-zero if any generated file would change (CI guard).
 */

const fs = require("fs");
const path = require("path");
const { compileFromFile } = require("json-schema-to-typescript");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const SCHEMAS_DIR = path.join(REPO_ROOT, "schemas");
const OUTPUT_DIR = path.join(__dirname, "..", "src", "generated");

const CHECK_MODE = process.argv.includes("--check");

async function main() {
  // Ensure output directory exists.
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });

  const schemaFiles = fs
    .readdirSync(SCHEMAS_DIR)
    .filter((f) => f.endsWith(".schema.json"))
    .sort();

  if (schemaFiles.length === 0) {
    console.error("No schema files found in " + SCHEMAS_DIR);
    process.exit(1);
  }

  let changed = 0;
  let unchanged = 0;

  for (const schemaFile of schemaFiles) {
    const baseName = schemaFile.replace(/\.schema\.json$/, "");
    const schemaPath = path.join(SCHEMAS_DIR, schemaFile);
    const outputPath = path.join(OUTPUT_DIR, baseName + ".ts");

    const tsCode = await compileFromFile(schemaPath, {
      bannerComment: `/* Generated from ${schemaFile}. Do not edit manually. */`,
      style: {
        singleQuote: true,
        semi: true,
      },
    });

    if (CHECK_MODE) {
      const existing = fs.existsSync(outputPath)
        ? fs.readFileSync(outputPath, "utf-8")
        : null;
      if (existing !== tsCode) {
        console.error(`Generated type would change: ${baseName}.ts`);
        changed++;
      } else {
        unchanged++;
      }
    } else {
      fs.writeFileSync(outputPath, tsCode);
      unchanged++;
    }
  }

  if (CHECK_MODE && changed > 0) {
    console.error(`${changed} generated type(s) are out of date. Run 'make frontend-types'.`);
    process.exit(1);
  }

  console.log(`Processed ${schemaFiles.length} schema(s): ${unchanged} ok, ${changed} changed.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
