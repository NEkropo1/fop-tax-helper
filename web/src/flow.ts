import type { Scope, Selection } from "./types";

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

export function scopeOf(flow: Flow): Scope | null {
  if (flow.selection === null || flow.handles.length === 0) return null;
  return { selection: flow.selection, handles: flow.handles, with_history: flow.withHistory };
}
