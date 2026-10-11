import type { ReactNode } from "react";

import { ApiError } from "./api";
import { copy } from "./copy";
import { formatDate } from "./format";
import type { Meta } from "./types";

export type Step = "cards" | "period" | "confirm" | "fetch" | "mark" | "result" | "data";

const FLOW: Step[] = ["cards", "period", "confirm", "fetch", "mark", "result"];

/** Finished steps are links back; Fetch is not one, since opening it would start bank requests. */
export function Steps({ current, onGo }: { current: Step; onGo: (step: Step) => void }) {
  const index = FLOW.indexOf(current);
  return (
    <ol className="steps" aria-label="Кроки">
      {FLOW.map((step, i) => (
        <li
          key={step}
          className={i === index ? "current" : i < index ? "done" : ""}
          aria-current={i === index ? "step" : undefined}
        >
          {i < index && step !== "fetch" ? (
            <button type="button" className="step-link" onClick={() => onGo(step)}>
              {i + 1}. {copy.steps[step as keyof typeof copy.steps]}
            </button>
          ) : (
            <>
              {i + 1}. {copy.steps[step as keyof typeof copy.steps]}
            </>
          )}
        </li>
      ))}
    </ol>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  if (error === null || error === undefined) return null;
  const message = error instanceof ApiError ? error.body.message : copy.noToken;
  return (
    <div className="notice error pre" role="alert">
      {message}
    </div>
  );
}

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="card">
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
  );
}

export function Footer({ meta }: { meta: Meta | null }) {
  const rules = meta?.rules ?? null;
  return (
    <footer className="foot">
      <div>
        {meta ? copy.footer.version(meta.version) : null}
        {rules ? ` · ${copy.footer.rules(formatDate(rules.updated_on), rules.year)}` : null}
      </div>
      {rules ? (
        <div>
          {rules.channels.map((c) => (
            <span key={c.url}>
              {copy.footer.channel}: <a href={c.url} target="_blank" rel="noreferrer">{c.name}</a>{" "}
            </span>
          ))}
          · {copy.footer.author}:{" "}
          <a href={rules.linkedin} target="_blank" rel="noreferrer">LinkedIn</a>
        </div>
      ) : null}
      <div>{copy.footer.notAdvice}</div>
    </footer>
  );
}
