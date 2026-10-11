/**
 * Marking with a mouse: a click toggles one payment, shift+click applies the same state to the whole
 * range between the last clicked payment and this one (in the order shown on screen).
 */
export function rangeIds(
  orderedIds: readonly string[],
  anchorId: string | null,
  clickedId: string,
  shift: boolean,
): string[] {
  if (!shift || anchorId === null) return [clickedId];
  const from = orderedIds.indexOf(anchorId);
  const to = orderedIds.indexOf(clickedId);
  if (from < 0 || to < 0) return [clickedId];
  const [low, high] = from <= to ? [from, to] : [to, from];
  return orderedIds.slice(low, high + 1);
}

/** Months of one year as "YYYY-MM" strings (the API format). */
export function monthKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

/**
 * Payments that "mark all" / "unmark all" must change: in one month (or every month when `month` is
 * null), skipping confirmed (locked) months and payments already in the wanted state.
 */
export function bulkIds(
  payments: readonly { id: string; month: string; marked: boolean }[],
  lockedMonths: ReadonlySet<string>,
  month: string | null,
  marked: boolean,
): string[] {
  return payments
    .filter((p) => (month === null || p.month === month) && !lockedMonths.has(p.month))
    .filter((p) => p.marked !== marked)
    .map((p) => p.id);
}
