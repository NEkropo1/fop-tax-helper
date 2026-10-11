import { useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api";
import { copy } from "../copy";
import { formatDate, formatMoney, formatPercent } from "../format";
import { scopeOf, type Flow } from "../flow";
import type { Declaration, Estimate, PreviousRows, Rules } from "../types";
import { DeclarationText, SourcesSection } from "../DeclarationText";
import { Card, ErrorBox, RulesFallbackNotice } from "../ui";

type Help = "ask" | "choose" | "typing" | "running" | "shown" | "declined";

const MONEY = /^\d+(\.\d{1,2})?$/;
const EMPTY_ROWS: PreviousRows = { income: "", row_07: "0", row_12: "", row_23: "" };
const ROW_KEYS = ["income", "row_07", "row_12", "row_23"] as const;

interface Props {
  flow: Flow;
  rules: Rules | null;
  fallbackYear: number | null; // the rules year in use when flow.year has no rules file
  onNeedHistory: () => void;
  onBack: () => void;
  onStartOver: () => void;
}

function EstimateView({ estimate }: { estimate: Estimate }) {
  const common: [string, string][] = [
    [copy.result.income, estimate.income],
    [copy.result.levy, estimate.military_levy],
    [copy.result.esv, estimate.esv],
  ];
  return (
    <>
      <h3 className="section-label">{copy.result.estimateLabel}</h3>
      <p className="doc-lead">{copy.result.info}</p>
      <dl className="estimate">
        {common.map(([label, value]) => (
          <div key={label} className="estimate-row">
            <dt>{label}</dt>
            <dd className="amount">{formatMoney(value)} грн</dd>
          </div>
        ))}
      </dl>
      {estimate.by_rate.map((item) => (
        <div key={item.rate}>
          <h4 className="rate-label">{copy.result.byRate(formatPercent(item.rate))}</h4>
          <dl className="estimate">
            <div className="estimate-row">
              <dt>{copy.result.singleTax}</dt>
              <dd className="amount">{formatMoney(item.single_tax)} грн</dd>
            </div>
            <div className="estimate-row total">
              <dt>{copy.result.total}</dt>
              <dd className="amount">{formatMoney(item.total)} грн</dd>
            </div>
          </dl>
        </div>
      ))}
      <p className="notice caution">{copy.result.verify}</p>
    </>
  );
}

function DeclarationView({ declaration, rules }: { declaration: Declaration; rules: Rules | null }) {
  return (
    <>
      {declaration.preliminary ? <div className="notice warn">{copy.result.preliminary}</div> : null}
      <DeclarationText text={declaration.text} newDeclarationUrl={rules?.new_declaration ?? null} />
      <h3 className="section-label">{copy.result.paymentsLabel}</h3>
      <table className="fields">
        <tbody>
          <tr>
            <td>{copy.result.dueDeclaration}</td>
            <td>{formatDate(declaration.declaration_due)}</td>
          </tr>
          {declaration.payments.map((p) => (
            <tr key={p.tax}>
              <td>{copy.result.taxLabels[p.tax] ?? p.tax}</td>
              <td className="amount">
                {Number(p.amount) === 0 ? copy.result.nothingToPay : `${formatMoney(p.amount)} грн`} ·{" "}
                {formatDate(p.due)} · {p.budget_code}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {rules ? (
        <div className="actions">
          <a href={rules.cabinet} target="_blank" rel="noreferrer">
            {copy.result.openCabinet}
          </a>
          <a href={rules.tax_account} target="_blank" rel="noreferrer">
            {copy.result.openTaxAccount}
          </a>
        </div>
      ) : null}
      <SourcesSection text={declaration.text} />
    </>
  );
}

export function Result({ flow, rules, fallbackYear, onNeedHistory, onBack, onStartOver }: Props) {
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [declaration, setDeclaration] = useState<Declaration | null>(null);
  const [help, setHelp] = useState<Help>("ask");
  const [error, setError] = useState<unknown>(null);
  const [previousText, setPreviousText] = useState("");
  const [rows, setRows] = useState<PreviousRows>(EMPTY_ROWS);
  const started = useRef(false);

  const selection = flow.selection;
  const period = selection?.kind === "period" ? selection.period : null;
  const first = period === "Q1";

  const runDeclaration = (previous: PreviousRows | null) => {
    if (period === null) return;
    setHelp("running");
    setError(null);
    api
      .declaration(flow.year, period, flow.handles, previous)
      .then((d) => {
        setDeclaration(d);
        setHelp("shown");
      })
      .catch((e: unknown) => {
        setError(e);
        setHelp(previous === null && !first && !flow.withHistory ? "choose" : "typing");
      });
  };

  useEffect(() => {
    const scope = scopeOf(flow);
    if (scope === null || started.current) return;
    started.current = true;
    api.info(scope).then(setEstimate).catch(setError);
    if (first || flow.withHistory) runDeclaration(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow]);

  const startTyping = () => {
    if (period === null) return;
    setHelp("typing");
    api.previousRequest(flow.year, period).then((r) => setPreviousText(r.text)).catch(setError);
  };

  const rowsValid = ROW_KEYS.every((k) => MONEY.test(rows[k].trim()));
  const needsHistory = error instanceof ApiError && error.body.code === "months_not_reviewed";

  return (
    <Card title={copy.result.title}>
      {fallbackYear === null ? null : <RulesFallbackNotice year={flow.year} usedYear={fallbackYear} />}
      {estimate ? <EstimateView estimate={estimate} /> : error === null ? <p>{copy.loading}</p> : null}
      <ErrorBox error={error} />
      {needsHistory && !flow.withHistory && !first ? (
        <div className="actions">
          <button type="button" onClick={onNeedHistory}>
            {copy.result.needHistory}
          </button>
        </div>
      ) : null}

      {period !== null && !first && help === "ask" && estimate ? (
        <>
          <h3>{copy.result.helpQuestion}</h3>
          <div className="actions">
            <button type="button" className="primary" onClick={() => setHelp("choose")}>
              {copy.result.helpYes}
            </button>
            <button type="button" onClick={() => setHelp("declined")}>
              {copy.result.helpNo}
            </button>
          </div>
        </>
      ) : null}

      {help === "choose" ? (
        <>
          <h3>{copy.result.pathTitle}</h3>
          <label className="option" style={{ marginBottom: 8 }}>
            <input type="radio" name="path" onChange={startTyping} />
            <span>
              <strong>{copy.result.pathA}</strong>
              <br />
              <span className="muted">{copy.result.pathAHint}</span>
            </span>
          </label>
          <label className="option">
            <input type="radio" name="path" onChange={onNeedHistory} />
            <span>
              <strong>{copy.result.pathB}</strong>
              <br />
              <span className="muted">{copy.result.pathBHint}</span>
            </span>
          </label>
        </>
      ) : null}

      {help === "typing" ? (
        <>
          <p className="pre">{previousText}</p>
          {ROW_KEYS.map((key) => (
            <p key={key}>
              <label>
                {copy.result.rows[key]}{" "}
                <input
                  type="text"
                  inputMode="decimal"
                  placeholder="0.00"
                  value={rows[key]}
                  onChange={(e) => setRows({ ...rows, [key]: e.target.value })}
                />
              </label>
            </p>
          ))}
          <div className="actions">
            <button type="button" className="primary" disabled={!rowsValid} onClick={() => runDeclaration(rows)}>
              {copy.result.calculate}
            </button>
          </div>
        </>
      ) : null}

      {help === "running" ? <p>{copy.loading}</p> : null}
      {declaration !== null && help === "shown" ? <DeclarationView declaration={declaration} rules={rules} /> : null}

      <div className="actions">
        <button type="button" onClick={onBack}>
          {copy.back}
        </button>
        <button type="button" onClick={onStartOver}>
          {copy.startOver}
        </button>
      </div>
    </Card>
  );
}
