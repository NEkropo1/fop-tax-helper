import { useCallback, useEffect, useState } from "react";

import { api, readToken } from "./api";
import { copy } from "./copy";
import { initialFlow, type Flow } from "./flow";
import { clearSaved, loadSaved, safeStep, storeSaved } from "./persist";
import { Cards } from "./screens/Cards";
import { Confirm } from "./screens/Confirm";
import { Fetch } from "./screens/Fetch";
import { Mark } from "./screens/Mark";
import { MyData } from "./screens/MyData";
import { PeriodScreen } from "./screens/Period";
import { Result } from "./screens/Result";
import type { Meta, Selection } from "./types";
import { Card, ErrorBox, Footer, Steps, type Step } from "./ui";

export function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [step, setStep] = useState<Step>("cards"); // set directly only by history/resume: see go()
  const [flow, setFlow] = useState<Flow | null>(null);
  const [folder, setFolder] = useState<string | null>(null);
  const [returnTo, setReturnTo] = useState<Step>("cards");
  const [jobId, setJobId] = useState<string | null>(null);

  /** The saved position, kept only while its accounts still exist (the list is cached: no bank call). */
  const resume = useCallback(async () => {
    const saved = loadSaved();
    if (saved === null) return null;
    if (saved.flow.handles.length === 0) return saved;
    try {
      const known = new Set((await api.accounts(saved.flow.year)).map((a) => a.handle));
      const handles = saved.flow.handles.filter((h) => known.has(h));
      return handles.length === saved.flow.handles.length ? saved : null;
    } catch {
      return null;
    }
  }, []);

  const loadMeta = useCallback(() => {
    setError(null);
    api
      .meta()
      .then(async (m) => {
        const saved = m.ready ? await resume() : null;
        setMeta(m);
        setFlow((current) => {
          if (current !== null) return current;
          if (saved !== null) return saved.flow;
          return initialFlow(m.current_year ?? m.years.at(-1) ?? new Date().getFullYear());
        });
        if (saved !== null) {
          setJobId(saved.jobId);
          setStep(safeStep(saved.step, saved.flow, saved.jobId));
        }
        // The page's first history entry is the step we start on, so "back" never lands on nothing.
        window.history.replaceState({ step: saved ? safeStep(saved.step, saved.flow, saved.jobId) : "cards" }, "");
      })
      .catch(setError);
  }, [resume]);

  useEffect(() => {
    if (readToken() === null) {
      setError(new Error(copy.noToken));
      return;
    }
    loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    if (meta?.ready) api.data().then((d) => setFolder(d.folder)).catch(() => undefined);
  }, [meta]);

  /** A step change is a history entry, so the browser's back/forward arrows walk the wizard. */
  const go = (next: Step) => {
    setStep(next);
    window.history.pushState({ step: next }, "");
  };

  useEffect(() => {
    const onPop = (event: PopStateEvent) => {
      const target = (event.state as { step?: Step } | null)?.step;
      if (flow !== null && target !== undefined) setStep(safeStep(target, flow, jobId));
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [flow, jobId]);

  useEffect(() => {
    if (meta?.ready && flow !== null) storeSaved({ step, flow, jobId });
  }, [meta, step, flow, jobId]);

  const patch = (changes: Partial<Flow>) => setFlow((f) => (f ? { ...f, ...changes } : f));
  const reset = () => {
    clearSaved();
    setJobId(null);
    setFlow(initialFlow(flow?.year ?? new Date().getFullYear()));
    go("cards");
  };

  const openData = () => {
    setReturnTo(step === "data" ? "cards" : step);
    go("data");
  };

  let body;
  if (meta === null || flow === null) {
    body = (
      <Card>
        <ErrorBox error={error} />
        {error === null ? <p>{copy.loading}</p> : null}
      </Card>
    );
  } else if (!meta.ready) {
    body = (
      <Card title={copy.blockedTitle}>
        <div className="notice error pre" role="alert">
          {meta.error?.message}
        </div>
        <div className="actions">
          <button type="button" className="primary" onClick={loadMeta}>
            {copy.retry}
          </button>
        </div>
      </Card>
    );
  } else if (step === "data") {
    body = <MyData onClose={() => go(returnTo)} />;
  } else if (step === "cards") {
    body = (
      <Cards
        flow={flow}
        years={meta.years}
        onYear={(year) => patch({ year, handles: [], selection: null })}
        onHandles={(handles) => patch({ handles })}
        onNext={() => go("period")}
      />
    );
  } else if (step === "period") {
    body = (
      <PeriodScreen
        flow={flow}
        onBack={() => go("cards")}
        onSelect={(selection: Selection) => {
          patch({ selection, withHistory: false });
          go("confirm");
        }}
      />
    );
  } else if (step === "confirm") {
    body = (
      <Confirm
        flow={flow}
        folder={folder}
        onBack={() => go(flow.withHistory ? "result" : "period")}
        onGo={() => {
          setJobId(null); // a fresh start, not the job of an earlier visit
          go("fetch");
        }}
        onSkip={() => go("mark")}
      />
    );
  } else if (step === "fetch") {
    body = (
      <Fetch
        flow={flow}
        jobId={jobId}
        onJob={setJobId}
        onBack={() => {
          setJobId(null);
          go("confirm");
        }}
        onDone={() => {
          setJobId(null);
          go("mark");
        }}
      />
    );
  } else if (step === "mark") {
    body = <Mark flow={flow} onBack={() => go("confirm")} onNext={() => go("result")} />;
  } else {
    body = (
      <Result
        key={`${flow.withHistory}`}
        flow={flow}
        rules={meta.rules}
        onBack={() => go("mark")}
        onStartOver={reset}
        onNeedHistory={() => {
          patch({ withHistory: true });
          go("confirm");
        }}
      />
    );
  }

  return (
    <div className="shell">
      <header className="top">
        <h1>{copy.appTitle}</h1>
        {meta?.ready ? (
          <div className="actions">
            <button type="button" onClick={reset} title={copy.restartHint}>
              {copy.startOver}
            </button>
            <button type="button" onClick={openData}>
              {copy.myData}
            </button>
          </div>
        ) : null}
      </header>
      {meta?.ready && step !== "data" ? <Steps current={step} onGo={go} /> : null}
      {body}
      <Footer meta={meta} />
    </div>
  );
}
