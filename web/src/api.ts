import type {
  Account,
  DataInfo,
  Declaration,
  ErrorBody,
  Estimate,
  Job,
  Meta,
  MonthState,
  Payments,
  Period,
  Plan,
  PreviousRows,
  Scope,
} from "./types";

const TOKEN_KEY = "mono-it-tax-token";
const TOKEN_HEADER = "X-App-Token";

/** The launch token arrives in the URL fragment; keep it for reloads and remove it from the URL. */
export function readToken(): string | null {
  const fromHash = new URLSearchParams(window.location.hash.slice(1)).get("token");
  if (fromHash) {
    sessionStorage.setItem(TOKEN_KEY, fromHash);
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  return sessionStorage.getItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorBody,
  ) {
    super(body.message);
  }
}

const GENERIC: ErrorBody = {
  code: "internal",
  message: "Не вдалося зв'язатися із застосунком. Перевірте, що він запущений, і повторіть.",
  params: {},
};

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = readToken();
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: {
        ...(token ? { [TOKEN_HEADER]: token } : {}),
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, GENERIC);
  }
  if (!response.ok) {
    let parsed: ErrorBody = GENERIC;
    try {
      const json = (await response.json()) as Partial<ErrorBody>;
      if (typeof json.code === "string" && typeof json.message === "string") {
        parsed = { code: json.code, message: json.message, params: json.params ?? {} };
      }
    } catch {
      /* not JSON: keep the generic message */
    }
    throw new ApiError(response.status, parsed);
  }
  return (await response.json()) as T;
}

export const api = {
  meta: (year?: number) => call<Meta>("GET", year ? `/api/meta?year=${year}` : "/api/meta"),
  accounts: (year: number, refresh = false) =>
    call<Account[]>("GET", `/api/accounts?year=${year}&refresh=${refresh}`),
  plan: (scope: Scope) => call<Plan>("POST", "/api/plan", scope),
  startFetch: (scope: Scope) => call<Job>("POST", "/api/fetch", scope),
  job: (id: string) => call<Job>("GET", `/api/jobs/${id}`),
  cancelJob: (id: string) => call<Job>("POST", `/api/jobs/${id}/cancel`),
  payments: (scope: Scope) => call<Payments>("POST", "/api/payments", scope),
  mark: (year: number, paymentIds: string[], marked: boolean) =>
    call<{ changed: number }>("POST", "/api/marks", { year, payment_ids: paymentIds, marked }),
  setAmount: (year: number, paymentId: string, amount: string | null) =>
    call<{ amount: string | null }>("POST", "/api/marks/amount", {
      year,
      payment_id: paymentId,
      amount,
    }),
  cancelReview: (year: number, handles: string[], months: string[]) =>
    call<MonthState[]>("POST", "/api/review/cancel", { year, handles, months }),
  review: (year: number, handles: string[], months: string[]) =>
    call<MonthState[]>("POST", "/api/review", { year, handles, months }),
  info: (scope: Scope) => call<Estimate>("POST", "/api/report/info", scope),
  previousRequest: (year: number, period: Period) =>
    call<{ text: string }>("GET", `/api/declaration/previous-request?year=${year}&period=${period}`),
  declaration: (year: number, period: Period, handles: string[], previous: PreviousRows | null) =>
    call<Declaration>("POST", "/api/report/declaration", { year, period, handles, previous }),
  data: () => call<DataInfo>("GET", "/api/data"),
  deleteYear: (year: number) => call<unknown>("DELETE", `/api/data/${year}?confirm=true`),
  deleteAll: () => call<unknown>("DELETE", "/api/data?confirm=true"),
};
