import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  ROLE_VOICES,
  PROVENANCE_VOICES,
  SOURCE_VOICES,
  roleVoice,
  voiceFor,
  provenanceVoice,
  sourceVoice,
} from "./voices";

/**
 * Exhaustiveness is checked against the Python source, not against a copy of it
 * (SPEC-049).
 *
 * A hand-maintained list of "the roles we know about" drifts silently, and the
 * failure mode is the one the terminology guard exists to prevent: a new enum
 * value renders at the reader as `assumption_analyst`. Reading the enum out of
 * `orchestrator/artifacts/common.py` means adding a role there fails this test
 * until someone decides what that role's voice is.
 */
const REPO = resolve(__dirname, "../../..");

function pythonEnumValues(file: string, enumName: string): string[] {
  const source = readFileSync(resolve(REPO, file), "utf8");
  const start = source.indexOf(`class ${enumName}(StrEnum):`);
  expect(start, `${enumName} not found in ${file}`).toBeGreaterThan(-1);
  // The class body ends at the next top-level `class` or the end of file.
  const rest = source.slice(start + 1);
  const end = rest.search(/\nclass /);
  const body = end === -1 ? rest : rest.slice(0, end);
  return [...body.matchAll(/^\s+[A-Z_0-9]+ = "([a-z_0-9]+)"$/gm)].map((m) => m[1]);
}

function pythonConstants(file: string, prefix: string): string[] {
  const source = readFileSync(resolve(REPO, file), "utf8");
  const pattern = new RegExp(`^${prefix}[A-Z_]+ = "([a-z_]+)"$`, "gm");
  return [...source.matchAll(pattern)].map((m) => m[1]);
}

describe("every role has a voice", () => {
  const roles = pythonEnumValues("orchestrator/artifacts/common.py", "TaskRole");

  it("finds the roles to check, so an empty match cannot pass silently", () => {
    expect(roles.length).toBeGreaterThanOrEqual(15);
    expect(roles).toContain("assumption_analyst");
  });

  it.each(roles)("%s", (role) => {
    expect(ROLE_VOICES[role], `TaskRole.${role} has no voice in copy/voices.ts`).toBeDefined();
    expect(ROLE_VOICES[role].label).not.toBe("");
    expect(ROLE_VOICES[role].blurb, `${role}'s voice has no blurb`).not.toBe("");
  });

  it("names no role by its enum value", () => {
    for (const [role, voice] of Object.entries(ROLE_VOICES)) {
      expect(voice.label, `${role} renders as its own enum value`).not.toBe(role);
    }
  });

  it("covers the synthetic actors the audit stream emits, which are not TaskRole members", () => {
    // `director_framing` and `director_b` are how the dual-track design shows up
    // on the wire; `independent_reviewer` is phase 8's third model family.
    for (const actor of ["director_framing", "director_b", "independent_reviewer", "orchestrator"]) {
      expect(ROLE_VOICES[actor], `${actor} has no voice`).toBeDefined();
    }
  });

  it("degrades to something readable rather than throwing on an unknown role", () => {
    expect(voiceFor("some_new_role")).toBe("some new role");
    expect(voiceFor(null)).toBe("The system");
    expect(roleVoice(undefined).label).toBe("The system");
  });
});

describe("every provenance has a voice", () => {
  const provenances = pythonConstants("orchestrator/service/caseview.py", "PROVENANCE_");

  it("finds the provenances to check", () => {
    expect(provenances.length).toBeGreaterThanOrEqual(6);
    expect(provenances).toContain("sourced_fact");
  });

  it.each(provenances)("%s", (provenance) => {
    expect(
      PROVENANCE_VOICES[provenance],
      `provenance "${provenance}" has no voice in copy/voices.ts`,
    ).toBeDefined();
    expect(PROVENANCE_VOICES[provenance].blurb).not.toBe("");
  });

  it("says 'unattributed' rather than rendering a raw value it does not know", () => {
    // The raw enum is exactly what must never reach the reader, so an unknown
    // provenance degrades to a statement instead of passing the value through.
    expect(provenanceVoice("something_new").label).toBe("Unattributed");
    expect(provenanceVoice(null).label).toBe("Unattributed");
  });

  it("distinguishes what the north star requires it to distinguish", () => {
    const labels = new Set(Object.values(PROVENANCE_VOICES).map((v) => v.label));
    expect(labels.size).toBe(Object.keys(PROVENANCE_VOICES).length);
  });
});

describe("every source type has a voice", () => {
  const sourceTypes = pythonEnumValues("orchestrator/artifacts/common.py", "SourceType");

  it("finds the source types to check", () => {
    expect(sourceTypes).toContain("user_document");
  });

  it.each(sourceTypes)("%s", (sourceType) => {
    expect(
      SOURCE_VOICES[sourceType],
      `SourceType.${sourceType} has no voice in copy/voices.ts`,
    ).toBeDefined();
  });

  it("renders a user document as the user's own voice, not as a research finding", () => {
    const voice = sourceVoice("user_document");
    expect(voice.label).toMatch(/your/i);
    // The property that makes it dangerous is that it can never corroborate,
    // and that has to be in the copy rather than in a comment.
    expect(voice.blurb).toMatch(/corroborate/i);
  });
});
