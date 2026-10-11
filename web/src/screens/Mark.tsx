import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../api";
import { copy } from "../copy";
import { formatMoney } from "../format";
import { scopeOf, type Flow } from "../flow";
import { bulkIds, rangeIds } from "../selection";
import type { MonthState, Payment, Payments } from "../types";
import { Card, ErrorBox } from "../ui";

interface Props {
  flow: Flow;
  onNext: () => void;
  onBack: () => void;
}

function PaymentRow({
  payment,
  locked,
  onClick,
  onAmount,
}: {
  payment: Payment;
  locked: boolean;
  onClick: (id: string, shift: boolean) => void;
  onAmount: (id: string, amount: string | null) => void;
}) {
  const [draft, setDraft] = useState(payment.amount_override ?? "");
  const known = [
    ["Опис", payment.description],
    ["Коментар", payment.comment],
    ["Контрагент", payment.counter_name],
    ["ЄДРПОУ", payment.counter_edrpou],
    ["IBAN контрагента", payment.counter_iban],
    ["MCC", payment.mcc],
    ["Початковий MCC", payment.original_mcc],
    ["Валюта операції", payment.operation_currency],
    ["Сума операції", payment.operation_amount],
    ["Комісія", payment.commission_rate],
    ["Кешбек", payment.cashback_amount],
    ["Залишок після", payment.balance],
    ["Не остаточна (hold)", payment.hold],
  ] as const;
  const extra = Object.entries(payment.extra);
  // The bank converted the money: `amount` is already in the account currency, no NBU rate applies.
  const converted =
    payment.operation_currency !== null &&
    payment.operation_currency !== payment.currency &&
    payment.operation_amount !== null;

  return (
    <div className="row">
      <input
        type="checkbox"
        checked={payment.marked}
        disabled={locked}
        aria-label={`Позначити платіж ${payment.time}`}
        onChange={() => undefined}
        onClick={(e) => onClick(payment.id, e.shiftKey)}
      />
      <div className="grow">
        <div>
          <span className="amount">
            <strong>
              +{formatMoney(payment.amount)} {payment.currency}
            </strong>
          </span>{" "}
          <span className="muted">{payment.time.slice(0, 16).replace("T", " ")}</span>{" "}
          {converted ? (
            <span className="badge" title={copy.mark.convertedHint}>
              {copy.mark.converted(payment.operation_amount ?? "", payment.operation_currency ?? "")}
            </span>
          ) : null}{" "}
          {payment.possible_internal_transfer ? (
            <span className="badge warn" title={copy.mark.transferHint}>
              {copy.mark.transfer}
            </span>
          ) : null}
        </div>
        <div className="muted">
          {[payment.counter_name, payment.description, payment.comment].filter(Boolean).join(" · ")}
        </div>
        {payment.marked ? (
          <label className="muted">
            {copy.mark.amount}{" "}
            <input
              type="text"
              inputMode="decimal"
              size={12}
              value={draft}
              disabled={locked}
              placeholder={formatMoney(payment.amount)}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={() => onAmount(payment.id, draft.trim() === "" ? null : draft.trim())}
            />{" "}
            {payment.currency}
            <span> — {copy.mark.amountHint}</span>
          </label>
        ) : null}
        <details>
          <summary className="muted">{copy.mark.details}</summary>
          <table className="fields">
            <tbody>
              {known
                .filter(([, v]) => v !== null && v !== "")
                .map(([label, value]) => (
                  <tr key={label}>
                    <td>{label}</td>
                    <td>{String(value)}</td>
                  </tr>
                ))}
              {extra.map(([key, value]) => (
                <tr key={key}>
                  <td>{key}</td>
                  <td>{String(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      </div>
    </div>
  );
}

export function Mark({ flow, onNext, onBack }: Props) {
  const [data, setData] = useState<Payments | null>(null);
  const [error, setError] = useState<unknown>(null);
  const anchor = useRef<string | null>(null);

  const reload = useCallback(() => {
    const scope = scopeOf(flow);
    if (scope === null) return Promise.resolve();
    return api.payments(scope).then(setData).catch(setError);
  }, [flow]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const ordered = useMemo(() => data?.payments.map((p) => p.id) ?? [], [data]);

  const click = (id: string, shift: boolean) => {
    if (data === null) return;
    const target = !(data.payments.find((p) => p.id === id)?.marked ?? false);
    const ids = rangeIds(ordered, anchor.current, id, shift);
    anchor.current = id;
    setError(null);
    api
      .mark(flow.year, ids, target)
      .then(reload)
      .catch(setError);
  };

  const setAmount = (id: string, amount: string | null) =>
    api
      .setAmount(flow.year, id, amount)
      .then(reload)
      .catch((e: unknown) => {
        setError(e);
        void reload();
      });

  const review = (months: string[]) =>
    api
      .review(flow.year, flow.handles, months)
      .then(reload)
      .catch(setError);

  const reopen = (months: string[]) =>
    api
      .cancelReview(flow.year, flow.handles, months)
      .then(reload)
      .catch(setError);

  const months = useMemo(() => {
    const byMonth = new Map<string, MonthState[]>();
    for (const state of data?.months ?? []) {
      byMonth.set(state.month, [...(byMonth.get(state.month) ?? []), state]);
    }
    return [...byMonth.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [data]);

  const allReviewed = months.length > 0 && months.every(([, s]) => s.every((x) => x.state === "reviewed"));
  const pending = months.filter(([, s]) => s.some((x) => x.state !== "reviewed")).map(([m]) => m);

  const lockedMonths = useMemo(
    () =>
      new Set(
        months.filter(([, s]) => s.every((x) => x.state === "reviewed")).map(([month]) => month),
      ),
    [months],
  );

  const markBulk = (month: string | null, marked: boolean) => {
    const ids = bulkIds(data?.payments ?? [], lockedMonths, month, marked);
    if (ids.length === 0) return;
    setError(null);
    api.mark(flow.year, ids, marked).then(reload).catch(setError);
  };

  return (
    <Card title={copy.mark.title}>
      <p className="muted">{copy.mark.hint}</p>
      {data !== null && !allReviewed ? (
        <div className="actions bulk">
          <button type="button" onClick={() => markBulk(null, true)}>
            {copy.mark.markAll}
          </button>
          <button type="button" onClick={() => markBulk(null, false)}>
            {copy.mark.unmarkAll}
          </button>
        </div>
      ) : null}
      <ErrorBox error={error} />
      {data === null && error === null ? <p>{copy.loading}</p> : null}
      {months.map(([month, states]) => {
        const listed = data?.payments.filter((p) => p.month === month) ?? [];
        const total = states.reduce((n, s) => n + s.payments, 0);
        const marked = states.reduce((n, s) => n + s.marked, 0);
        const done = states.every((s) => s.state === "reviewed");
        return (
          <section key={month} aria-label={month} className={`month ${done ? "done" : ""}`}>
            <div className="month-head">
              <h3>
                {month}{" "}
                <span className="muted">{copy.mark.marked(marked, total)}</span>{" "}
                {done ? <span className="badge ok">{copy.mark.reviewed}</span> : null}
              </h3>
              {done ? (
                <span className="muted">{copy.mark.locked}</span>
              ) : (
                <span className="actions">
                  <button type="button" onClick={() => markBulk(month, true)}>
                    {copy.mark.markMonth}
                  </button>
                  <button type="button" onClick={() => markBulk(month, false)}>
                    {copy.mark.unmarkMonth}
                  </button>
                </span>
              )}
            </div>
            {listed.length === 0 ? <p className="muted">{copy.mark.emptyMonth}</p> : null}
            {listed.map((p) => (
              <PaymentRow key={p.id} payment={p} locked={done} onClick={click} onAmount={setAmount} />
            ))}
            <div className="actions month-foot">
              {done ? (
                <button type="button" onClick={() => void reopen([month])}>
                  {copy.mark.reopenMonth(month)}
                </button>
              ) : (
                <button type="button" className="confirm" onClick={() => void review([month])}>
                  {copy.mark.confirmMonth(month)}
                </button>
              )}
            </div>
          </section>
        );
      })}
      {!allReviewed && data !== null ? <div className="notice warn">{copy.mark.needReview}</div> : null}
      <div className="actions">
        <button type="button" onClick={onBack}>
          {copy.back}
        </button>
        {!allReviewed && pending.length > 0 ? (
          <button type="button" onClick={() => void review(pending)}>
            {copy.mark.confirmAll}
          </button>
        ) : null}
        {allReviewed ? (
          <button type="button" onClick={() => void reopen(months.map(([m]) => m))}>
            {copy.mark.reopenAll}
          </button>
        ) : null}
        <button type="button" className="primary" disabled={!allReviewed} onClick={onNext}>
          {copy.mark.next}
        </button>
      </div>
    </Card>
  );
}
