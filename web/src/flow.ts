import type { Period, Scope, Selection } from "./types";

/** What the user has chosen so far; the same object drives every screen after the first two. */
export interface Flow {
  year: number;
  handles: string[];
  selection: Selection | null;
  withHistory: boolean;
}

export function initialFlow(year: number): Flow {
  return { year, handles: [], selection: null, withHistory: false };
}

/** The rules year used instead of `year` when it has no rules file (the latest one); else null. */
export function rulesFallbackYear(years: readonly number[], year: number): number | null {
  if (years.length === 0 || years.includes(year)) return null;
  return Math.max(...years);
}

/**
 * The period most likely wanted for `year`: the latest one already over as of `today`. A past year
 * means the full year; before the first quarter ends (or for a future year) it is the first period.
 */
export function defaultPeriod(year: number, today: Date): Period {
  const thisYear = today.getFullYear();
  if (year < thisYear) return "Y";
  if (year > thisYear) return "Q1";
  const month = today.getMonth(); // 0-based
  if (month >= 9) return "M9";
  if (month >= 6) return "H1";
  return "Q1";
}

export function scopeOf(flow: Flow): Scope | null {
  if (flow.selection === null || flow.handles.length === 0) return null;
  return { selection: flow.selection, handles: flow.handles, with_history: flow.withHistory };
}
