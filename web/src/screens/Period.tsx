import { useState } from "react";

import { copy } from "../copy";
import { defaultPeriod, type Flow } from "../flow";
import { monthKey } from "../selection";
import type { Period as PeriodName, Selection } from "../types";
import { Card } from "../ui";

const PERIODS: PeriodName[] = ["Q1", "H1", "M9", "Y"];
const MONTH_NAMES = [
  "січень", "лютий", "березень", "квітень", "травень", "червень",
  "липень", "серпень", "вересень", "жовтень", "листопад", "грудень",
];

interface Props {
  flow: Flow;
  onSelect: (selection: Selection) => void;
  onBack: () => void;
}

export function PeriodScreen({ flow, onSelect, onBack }: Props) {
  const [tab, setTab] = useState<"period" | "months">(
    flow.selection?.kind === "months" ? "months" : "period",
  );
  const [period, setPeriod] = useState<PeriodName>(
    flow.selection?.kind === "period" ? flow.selection.period : defaultPeriod(flow.year, new Date()),
  );
  const [months, setMonths] = useState<string[]>(
    flow.selection?.kind === "months" ? flow.selection.months : [],
  );

  const toggleMonth = (key: string) =>
    setMonths((current) => (current.includes(key) ? current.filter((m) => m !== key) : [...current, key]));

  const ready = tab === "period" || months.length > 0;
  const submit = () =>
    onSelect(
      tab === "period"
        ? { year: flow.year, kind: "period", period }
        : { year: flow.year, kind: "months", months: [...months].sort() },
    );

  return (
    <Card title={`${copy.period.title} (${flow.year})`}>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "period"} onClick={() => setTab("period")}>
          {copy.period.tabPeriod}
        </button>
        <button type="button" role="tab" aria-selected={tab === "months"} onClick={() => setTab("months")}>
          {copy.period.tabMonths}
        </button>
      </div>
      {tab === "period" ? (
        <>
          <p className="muted">{copy.period.periodHint}</p>
          {PERIODS.map((p) => (
            <label key={p} className={`option ${period === p ? "selected" : ""}`} style={{ marginBottom: 8 }}>
              <input type="radio" name="period" checked={period === p} onChange={() => setPeriod(p)} />
              <span>
                <strong>{copy.period.labels[p].name}</strong>
                <br />
                <span className="muted">{copy.period.labels[p].detail}</span>
              </span>
            </label>
          ))}
        </>
      ) : (
        <>
          <p className="muted">{copy.period.monthsHint}</p>
          <div className="grid">
            {MONTH_NAMES.map((name, i) => {
              const key = monthKey(flow.year, i + 1);
              return (
                <label key={key} className={`option ${months.includes(key) ? "selected" : ""}`}>
                  <input type="checkbox" checked={months.includes(key)} onChange={() => toggleMonth(key)} />
                  {name}
                </label>
              );
            })}
          </div>
          {months.length === 0 ? <div className="notice warn">{copy.period.pickMonths}</div> : null}
        </>
      )}
      <div className="actions">
        <button type="button" onClick={onBack}>
          {copy.back}
        </button>
        <button type="button" className="primary" disabled={!ready} onClick={submit}>
          {copy.next}
        </button>
      </div>
    </Card>
  );
}
