import { useEffect, useState } from "react";

import { api } from "../api";
import { copy } from "../copy";
import { formatDuration } from "../format";
import { scopeOf, type Flow } from "../flow";
import type { Plan } from "../types";
import { Card, ErrorBox } from "../ui";

interface Props {
  flow: Flow;
  folder: string | null;
  onGo: () => void;
  onSkip: () => void;
  onBack: () => void;
}

export function Confirm({ flow, folder, onGo, onSkip, onBack }: Props) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const scope = scopeOf(flow);
    if (scope === null) return;
    api.plan(scope).then(setPlan).catch(setError);
  }, [flow]);

  return (
    <Card title={copy.confirm.title}>
      <ErrorBox error={error} />
      {plan === null && error === null ? <p>{copy.loading}</p> : null}
      {plan !== null && plan.requests === 0 ? <p>{copy.confirm.nothing}</p> : null}
      {plan !== null && plan.requests > 0 ? (
        <>
          <p>{copy.confirm.requests(plan.requests, formatDuration(plan.eta_seconds))}</p>
          <p className="muted">{copy.confirm.stored(folder ?? "data/store")}</p>
        </>
      ) : null}
      <div className="actions">
        <button type="button" onClick={onBack}>
          {copy.confirm.cancel}
        </button>
        {plan !== null && plan.requests > 0 ? (
          <button type="button" className="primary" onClick={onGo}>
            {copy.confirm.go}
          </button>
        ) : null}
        {plan !== null && plan.requests === 0 ? (
          <button type="button" className="primary" onClick={onSkip}>
            {copy.confirm.toMarking}
          </button>
        ) : null}
      </div>
    </Card>
  );
}
