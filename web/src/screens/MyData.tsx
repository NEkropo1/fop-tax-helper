import { useEffect, useState } from "react";

import { api } from "../api";
import { copy } from "../copy";
import { formatBytes } from "../format";
import type { DataInfo } from "../types";
import { Card, ErrorBox } from "../ui";

type Pending = { kind: "year"; year: number } | { kind: "all" } | null;

export function MyData({ onClose }: { onClose: () => void }) {
  const [info, setInfo] = useState<DataInfo | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState<Pending>(null);

  const reload = () => api.data().then(setInfo).catch(setError);
  useEffect(() => {
    void reload();
  }, []);

  const confirmDelete = () => {
    if (pending === null) return;
    const done = pending.kind === "all" ? api.deleteAll() : api.deleteYear(pending.year);
    done
      .then(() => {
        setPending(null);
        return reload();
      })
      .catch(setError);
  };

  return (
    <Card title={copy.data.title}>
      <ErrorBox error={error} />
      {info === null && error === null ? <p>{copy.loading}</p> : null}
      {info !== null ? (
        <>
          <p className="muted">
            {copy.data.folder}: <code>{info.folder}</code>
            <br />
            {copy.data.key}: {info.key_storage ?? "—"}
          </p>
          {info.years.length === 0 ? <p>{copy.data.empty}</p> : null}
          {info.years.map((y) => (
            <div className="row" key={y.year}>
              <div className="grow">
                <strong>{y.year}</strong> · {formatBytes(y.bytes)}
              </div>
              <button type="button" className="danger" onClick={() => setPending({ kind: "year", year: y.year })}>
                {copy.data.deleteYear(y.year)}
              </button>
            </div>
          ))}
          {info.years.length > 1 ? (
            <div className="actions">
              <button type="button" className="danger" onClick={() => setPending({ kind: "all" })}>
                {copy.data.deleteAll}
              </button>
            </div>
          ) : null}
          {pending !== null ? (
            <div className="notice warn" role="alertdialog">
              <p className="pre">
                {pending.kind === "all"
                  ? copy.data.confirmAll(info.folder)
                  : copy.data.confirmYear(pending.year, info.folder)}
              </p>
              <div className="actions">
                <button type="button" className="danger" onClick={confirmDelete}>
                  {copy.data.confirm}
                </button>
                <button type="button" onClick={() => setPending(null)}>
                  {copy.data.cancel}
                </button>
              </div>
            </div>
          ) : null}
        </>
      ) : null}
      <div className="actions">
        <button type="button" onClick={onClose}>
          {copy.back}
        </button>
      </div>
    </Card>
  );
}
