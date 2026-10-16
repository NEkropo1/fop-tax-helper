import { useState } from "react";

import { copy } from "./copy";
import { copyableAmount, isErrorLine, linkify, parseDeclaration, splitFormCode, splitValue } from "./declaration_parse";

function Linkified({ line }: { line: string }) {
  return (
    <>
      {linkify(line).map((piece, i) =>
        piece.kind === "link" ? (
          <a key={i} href={piece.value} target="_blank" rel="noreferrer">
            {piece.value}
          </a>
        ) : (
          <span key={i}>{piece.value}</span>
        ),
      )}
    </>
  );
}

function CopyButton({ value }: { value: string }) {
  const [done, setDone] = useState(false);
  const onClick = () => {
    void navigator.clipboard.writeText(value).then(() => {
      setDone(true);
      window.setTimeout(() => setDone(false), 2000);
    });
  };
  return (
    <button type="button" className="copy-button" onClick={onClick}>
      {done ? copy.result.copied : copy.result.copyAmount}
    </button>
  );
}

function Bullet({ line }: { line: string }) {
  if (isErrorLine(line)) return <li className="row-error">{line}</li>;
  const { label, value } = splitValue(line);
  return (
    <li>
      <span>{label}</span>
      {value !== null ? <span className="row-value">{value}</span> : null}
    </li>
  );
}

interface Props {
  text: string;
  newDeclarationUrl: string | null;
  income: string; // the income row exactly as the API sends it, e.g. "161550.72"
}

export function DeclarationText({ text, newDeclarationUrl, income }: Props) {
  const parsed = parseDeclaration(text);
  const header = splitFormCode(parsed.header);
  return (
    <div className="declaration">
      <section className="doc-section">
        <h3 className="section-label">{copy.result.stepsLabel}</h3>
        <p className="doc-lead">
          {header === null ? (
            parsed.header
          ) : (
            <>
              {header.before}
              <mark className="form-code">{header.code}</mark>
              {header.after}
            </>
          )}
        </p>
        {newDeclarationUrl !== null ? (
          <p className="doc-link">
            <span className="muted">{copy.result.createHere}</span>{" "}
            <a href={newDeclarationUrl} target="_blank" rel="noreferrer">
              {newDeclarationUrl.replace(/^https?:\/\//, "")}
            </a>
          </p>
        ) : null}
        <ol className="doc-steps">
          {parsed.steps.map((step, i) => (
            <li key={i}>
              <p>{step.text}</p>
              {copyableAmount(step.text, income) !== null ? <CopyButton value={income} /> : null}
              {step.bullets.length > 0 ? (
                <ul className="doc-rows">
                  {step.bullets.map((b, j) => (
                    <Bullet key={j} line={b} />
                  ))}
                </ul>
              ) : null}
              {step.warning !== null ? <p className="notice caution">{step.warning}</p> : null}
            </li>
          ))}
        </ol>
      </section>

      {parsed.notes.length > 0 ? (
        <section className="doc-section">
          <h3 className="section-label">{copy.result.notesLabel}</h3>
          {parsed.notes.map((note, i) => (
            <p key={i} className="doc-note">
              {note}
            </p>
          ))}
        </section>
      ) : null}
    </div>
  );
}

export function SourcesSection({ text }: { text: string }) {
  const { footer } = parseDeclaration(text);
  if (footer.length === 0) return null;
  return (
    <section className="doc-section sources">
      <h3 className="section-label">{copy.result.sourcesLabel}</h3>
      <ul>
        {footer.map((line, i) => (
          <li key={i}>
            <Linkified line={line} />
          </li>
        ))}
      </ul>
    </section>
  );
}
