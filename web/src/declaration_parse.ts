// Splits the declaration help text (built by the API, see copy/declaration_uk.py) into the parts the
// screen lays out. Pure: the text stays the single source of truth, this only recognises its shape.

export interface TextStep {
  text: string;
  bullets: string[];
  warning: string | null;
}

export interface ParsedDeclaration {
  header: string;
  steps: TextStep[];
  notes: string[];
  footer: string[];
}

export type Piece = { kind: "text"; value: string } | { kind: "link"; value: string };

const BLOCK_SEPARATOR = "\n\n";
const STEP_START = /^\d+\.\s+/;
const BULLET_START = /^\s+-\s+/;
const CONTINUATION_START = /^\s+\S/;
const PAYMENTS_BLOCK_PREFIX = "Платежі"; // shown as a table next to the text, so skipped here
const URL_PATTERN = /https?:\/\/[^\s)]+/g;
const TRAILING_PUNCTUATION = /[.,;:]+$/;
const VALUE_SEPARATOR = " = ";
const FORM_CODE = /\bF\d{7}\b/;

export function parseDeclaration(text: string): ParsedDeclaration {
  const [header = "", stepBlock = "", ...rest] = text.split(BLOCK_SEPARATOR).map((b) => b.trim());
  const footerBlock = rest.length > 0 ? (rest[rest.length - 1] ?? "") : "";
  const notes = rest.slice(0, -1).filter((b) => b !== "" && !b.startsWith(PAYMENTS_BLOCK_PREFIX));

  const steps: TextStep[] = [];
  for (const line of stepBlock.split("\n")) {
    const current = steps[steps.length - 1];
    if (STEP_START.test(line)) {
      steps.push({ text: line.replace(STEP_START, ""), bullets: [], warning: null });
    } else if (current !== undefined && BULLET_START.test(line)) {
      current.bullets.push(line.replace(BULLET_START, ""));
    } else if (current !== undefined && CONTINUATION_START.test(line)) {
      current.warning = line.trim();
    }
  }
  return {
    header,
    steps,
    notes,
    footer: footerBlock.split("\n").filter((l) => l !== ""),
  };
}

// "08 (усього доходу) = 120 000.40" -> label + value; a line without " = " is all label.
export function splitValue(line: string): { label: string; value: string | null } {
  const at = line.lastIndexOf(VALUE_SEPARATOR);
  if (at < 0) return { label: line, value: null };
  return { label: line.slice(0, at), value: line.slice(at + VALUE_SEPARATOR.length) };
}

// Turns every http(s) URL in a line into a link piece; closing brackets and sentence dots stay text.
export function linkify(line: string): Piece[] {
  const pieces: Piece[] = [];
  let last = 0;
  for (const match of line.matchAll(URL_PATTERN)) {
    const url = match[0].replace(TRAILING_PUNCTUATION, "");
    const start = match.index;
    if (start > last) pieces.push({ kind: "text", value: line.slice(last, start) });
    pieces.push({ kind: "link", value: url });
    last = start + url.length;
  }
  if (last < line.length) pieces.push({ kind: "text", value: line.slice(last) });
  return pieces;
}

export function splitFormCode(line: string): { before: string; code: string; after: string } | null {
  const match = FORM_CODE.exec(line);
  if (match === null) return null;
  const start = match.index;
  return {
    before: line.slice(0, start),
    code: match[0],
    after: line.slice(start + match[0].length),
  };
}
