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
  const [step, setStep] = useState<Step>("cards");
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

  useEffect(() => {
    if (meta?.ready && flow !== null) storeSaved({ step, flow, jobId });
  }, [meta, step, flow, jobId]);

  const patch = (changes: Partial<Flow>) => setFlow((f) => (f ? { ...f, ...changes } : f));
  const reset = () => {
    clearSaved();
    setJobId(null);
    setFlow(initialFlow(flow?.year ?? new Date().getFullYear()));
    setStep("cards");
  };

  const openData = () => {
    setReturnTo(step === "data" ? "cards" : step);
    setStep("data");
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
    body = <MyData onClose={() => setStep(returnTo)} />;
  } else if (step === "cards") {
    body = (
      <Cards
        flow={flow}
        years={meta.years}
        onYear={(year) => patch({ year, handles: [], selection: null })}
        onHandles={(handles) => patch({ handles })}
        onNext={() => setStep("period")}
      />
    );
  } else if (step === "period") {
    body = (
      <PeriodScreen
        flow={flow}
        onBack={() => setStep("cards")}
        onSelect={(selection: Selection) => {
          patch({ selection, withHistory: false });
          setStep("confirm");
        }}
      />
    );
  } else if (step === "confirm") {
    body = (
      <Confirm
        flow={flow}
        folder={folder}
        onBack={() => setStep(flow.withHistory ? "result" : "period")}
        onGo={() => setStep("fetch")}
        onSkip={() => setStep("mark")}
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
          setStep("confirm");
        }}
        onDone={() => {
          setJobId(null);
          setStep("mark");
        }}
      />
    );
  } else if (step === "mark") {
    body = <Mark flow={flow} onBack={() => setStep("confirm")} onNext={() => setStep("result")} />;
  } else {
    body = (
      <Result
        key={`${flow.withHistory}`}
        flow={flow}
        rules={meta.rules}
        onBack={() => setStep("mark")}
        onStartOver={reset}
        onNeedHistory={() => {
          patch({ withHistory: true });
          setStep("confirm");
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
      {meta?.ready && step !== "data" ? <Steps current={step} /> : null}
      {body}
      <Footer meta={meta} />
    </div>
  );
}
