import type { Account } from "./types";

/** Everything about an account the user can see: when it differs, the cards "changed". */
function describe(account: Account): string {
  return [account.handle, account.type, account.currency, account.masked_pans.join(","), account.selectable].join("|");
}

/** True when a refresh brought new, removed or altered cards (order does not matter). */
export function cardsChanged(previous: readonly Account[], next: readonly Account[]): boolean {
  const key = (list: readonly Account[]) => list.map(describe).sort().join("\n");
  return key(previous) !== key(next);
}

/** A saved selection survives only while every selected account still exists. */
export function selectionExists(handles: readonly string[], accounts: readonly Account[]): boolean {
  const known = new Set(accounts.map((a) => a.handle));
  return handles.every((h) => known.has(h));
}
