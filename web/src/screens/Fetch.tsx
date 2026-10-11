import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import { copy } from "../copy";
import { scopeOf, type Flow } from "../flow";
import type { Job } from "../types";
import { Card, ErrorBox } from "../ui";

const POLL_MS = 1000;

interface Props {
  flow: Flow;
  jobId: string | null; // a job this screen already owns (after a reload): attach, never start a second
  onJob: (id: string) => void;
  onDone: () => void;
  onBack: () => void;
}

export function Fetch({ flow, jobId, onJob, onDone, onBack }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<unknown>(null);
  const started = useRef(false);

  useEffect(() => {
    const scope = scopeOf(flow);
    if (scope === null || started.current) return;
    started.current = true;
    if (jobId !== null) {
      // The server forgot the job (restarted): go back and let the user plan again; nothing is lost.
      api.job(jobId).then(setJob).catch(onBack);
      return;
    }
    api
      .startFetch(scope)
      .then((newJob) => {
        onJob(newJob.id);
        setJob(newJob);
      })
      .catch(setError);
  }, [flow]);

  useEffect(() => {
    if (job === null || job.state !== "running") return;
    const timer = window.setInterval(() => {
      api.job(job.id).then(setJob).catch(setError);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [job]);

  const percent = job && job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;
  const finished = job !== null && job.state !== "running";

  return (
    <Card title={copy.fetch.title}>
      <ErrorBox error={error} />
      {job === null && error === null ? <p>{copy.loading}</p> : null}
      {job !== null ? (
        <>
          <div className="progress" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
            <div style={{ width: `${percent}%` }} />
          </div>
          <p>
            {copy.fetch.progress(job.done, job.total)}
            {job.month && job.state === "running" ? ` · ${copy.fetch.month(job.month)}` : null}
          </p>
          {job.state === "cancelled" ? <div className="notice warn">{copy.fetch.cancelled}</div> : null}
          {job.state === "done" ? <p>{copy.fetch.done}</p> : null}
          {job.error ? <div className="notice error pre" role="alert">{job.error.message}</div> : null}
          <p className="muted">{copy.fetch.resumable}</p>
        </>
      ) : null}
      <div className="actions">
        {job?.state === "running" ? (
          <button type="button" onClick={() => api.cancelJob(job.id).then(setJob).catch(setError)}>
            {copy.fetch.cancel}
          </button>
        ) : (
          <button type="button" onClick={onBack}>
            {copy.back}
          </button>
        )}
        {finished && job.state !== "failed" ? (
          <button type="button" className="primary" onClick={onDone}>
            {copy.fetch.continue}
          </button>
        ) : null}
      </div>
    </Card>
  );
}
