import { useEffect, useState } from "react";

import { cardsChanged, selectionExists } from "../accounts";
import { api } from "../api";
import { copy } from "../copy";
import { rulesFallbackYear, type Flow } from "../flow";
import { YEAR_MAX, YEAR_MIN } from "../limits";
import type { Account } from "../types";
import { Card, ErrorBox, RulesFallbackNotice } from "../ui";

interface Props {
  flow: Flow;
  years: number[];
  onYear: (year: number) => void;
  onHandles: (handles: string[]) => void;
  onNext: () => void;
}

export function Cards({ flow, years, onYear, onHandles, onNext }: Props) {
  const fallbackYear = rulesFallbackYear(years, flow.year);
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [resetNote, setResetNote] = useState(false);
  const [yearDraft, setYearDraft] = useState(String(flow.year));

  const load = (refresh: boolean) => {
    setError(null);
    api
      .accounts(flow.year, refresh)
      .then((next) => {
        // The selection is dropped only when the bank's cards really changed (or vanished).
        const changed = refresh && accounts !== null && cardsChanged(accounts, next);
        if (changed || !selectionExists(flow.handles, next)) {
          if (flow.handles.length > 0) setResetNote(true);
          onHandles([]);
        } else if (refresh) {
          setResetNote(false);
        }
        setAccounts(next);
      })
      .catch(setError);
  };
  // The card list does not depend on the year: loaded once per visit, never again on a year change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => load(false), []);

  const toggle = (handle: string) =>
    onHandles(
      flow.handles.includes(handle)
        ? flow.handles.filter((h) => h !== handle)
        : [...flow.handles, handle],
    );

  return (
    <Card title={copy.cards.title}>
      <p className="muted">{copy.cards.hint}</p>
      <label className={fallbackYear === null ? "" : "year-warn"}>
        {copy.cards.year}{" "}
        <input
          type="number"
          className="year"
          list="rules-years"
          min={YEAR_MIN}
          max={YEAR_MAX}
          step={1}
          value={yearDraft}
          onChange={(e) => {
            setYearDraft(e.target.value);
            const year = Number(e.target.value);
            if (Number.isInteger(year) && year >= YEAR_MIN && year <= YEAR_MAX) onYear(year);
          }}
          onBlur={() => setYearDraft(String(flow.year))}
        />
        <datalist id="rules-years">
          {years.map((y) => (
            <option key={y} value={y} />
          ))}
        </datalist>
      </label>
      {fallbackYear === null ? null : <RulesFallbackNotice year={flow.year} usedYear={fallbackYear} />}
      <ErrorBox error={error} />
      {resetNote ? <div className="notice warn">{copy.cards.selectionReset}</div> : null}
      {accounts === null && error === null ? <p>{copy.loading}</p> : null}
      {accounts?.map((a) => (
        <label
          key={a.handle}
          className={`option ${flow.handles.includes(a.handle) ? "selected" : ""}`}
          style={{ marginTop: 8 }}
        >
          <input
            type="checkbox"
            checked={flow.handles.includes(a.handle)}
            disabled={!a.selectable}
            onChange={() => toggle(a.handle)}
          />
          <span>
            <strong>{a.type ?? "—"}</strong> · {a.currency} · {a.masked_pans.length > 0 ? a.masked_pans.join(", ") : copy.cards.noCard}
            {a.selectable ? null : <span className="muted"> ({copy.cards.unsupported})</span>}
          </span>
        </label>
      ))}
      <p className="muted">{copy.cards.firstFetchNote}</p>
      {flow.handles.length === 0 && accounts !== null ? (
        <div className="notice warn">{copy.cards.none}</div>
      ) : null}
      <div className="actions">
        <button type="button" onClick={() => load(true)}>
          {copy.cards.refresh}
        </button>
        <button type="button" className="primary" disabled={flow.handles.length === 0} onClick={onNext}>
          {copy.next}
        </button>
      </div>
    </Card>
  );
}
