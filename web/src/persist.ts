/**
 * Wizard position kept in sessionStorage (same lifetime as the launch token): a reload resumes the
 * last step instead of starting over. Everything read back is untrusted: any doubt means "start over".
 */
import type { Flow } from "./flow";
import { YEAR_MAX, YEAR_MIN } from "./limits";
import type { Period, Selection } from "./types";
import type { Step } from "./ui";

export const STATE_KEY = "mono-it-tax-ui";
export const STATE_VERSION = 1;

const STEPS: readonly Step[] = ["cards", "period", "confirm", "fetch", "mark", "result", "data"];
const PERIODS = ["Q1", "H1", "M9", "Y"];
const MONTH_KEY = /^\d{4}-(0[1-9]|1[0-2])$/;

export interface Saved {
  step: Step;
  flow: Flow;
  jobId: string | null; // the running/finished fetch job of the Fetch step, if any
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseSelection(value: unknown, year: number): Selection | null {
  if (value === null) return null;
  if (!isRecord(value) || value.year !== year) return null;
  if (value.kind === "period" && typeof value.period === "string" && PERIODS.includes(value.period)) {
    return { year, kind: "period", period: value.period as Period };
  }
  if (
    value.kind === "months" &&
    Array.isArray(value.months) &&
    value.months.length > 0 &&
    value.months.every((m) => typeof m === "string" && MONTH_KEY.test(m) && m.startsWith(`${year}-`))
  ) {
    return { year, kind: "months", months: value.months as string[] };
  }
  return null;
}

export function decodeSaved(raw: string | null): Saved | null {
  if (raw === null) return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(data) || data.v !== STATE_VERSION || !isRecord(data.flow)) return null;
  const { flow } = data;
  const year = flow.year;
  if (typeof year !== "number" || !Number.isInteger(year) || year < YEAR_MIN || year > YEAR_MAX) return null;
  if (!Array.isArray(flow.handles) || !flow.handles.every((h) => typeof h === "string")) return null;
  const selection = parseSelection(flow.selection, year);
  if (flow.selection !== null && selection === null) return null;
  if (typeof data.step !== "string" || !STEPS.includes(data.step as Step)) return null;
  const jobId = typeof data.jobId === "string" ? data.jobId : null;
  return {
    step: data.step as Step,
    flow: { year, handles: flow.handles as string[], selection, withHistory: flow.withHistory === true },
    jobId,
  };
}

export function encodeSaved(saved: Saved): string {
  return JSON.stringify({ v: STATE_VERSION, ...saved });
}

/**
 * The step a resumed or history-navigated user may land on. Never a step whose inputs are missing,
 * and never the Fetch step without a known job (opening it would start bank requests by itself).
 */
export function safeStep(step: Step, flow: Flow, jobId: string | null): Step {
  if (flow.handles.length === 0) return "cards";
  if (step === "data" || step === "cards") return "cards";
  if (step === "period") return "period";
  if (flow.selection === null) return "period";
  if (step === "fetch") return jobId === null ? "confirm" : "fetch";
  return step;
}

// sessionStorage can be missing or throw (private mode, blocked site data): the app works without it.
export function loadSaved(): Saved | null {
  try {
    return decodeSaved(window.sessionStorage.getItem(STATE_KEY));
  } catch {
    return null;
  }
}

export function storeSaved(saved: Saved): void {
  try {
    window.sessionStorage.setItem(STATE_KEY, encodeSaved(saved));
  } catch {
    // not persisted: a reload simply starts over
  }
}

export function clearSaved(): void {
  try {
    window.sessionStorage.removeItem(STATE_KEY);
  } catch {
    // nothing to clear
  }
}
