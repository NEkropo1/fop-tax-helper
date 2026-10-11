// Mirrors src/mono_it_tax/api/schemas.py. Account ids never reach the browser: only handles.

export type Period = "Q1" | "H1" | "M9" | "Y";

export type Selection =
  | { year: number; kind: "period"; period: Period }
  | { year: number; kind: "months"; months: string[] };

export interface Scope {
  selection: Selection;
  handles: string[];
  with_history: boolean;
}

export interface ErrorBody {
  code: string;
  message: string;
  params: Record<string, string>;
}

export interface Account {
  handle: string;
  type: string | null;
  currency: string;
  masked_pans: string[];
  selectable: boolean;
}

export interface Plan {
  requests: number;
  eta_seconds: number;
  tasks: { handle: string; month: string }[];
}

export type JobState = "running" | "done" | "cancelled" | "failed";

export interface Job {
  id: string;
  state: JobState;
  done: number;
  total: number;
  month: string | null;
  error: ErrorBody | null;
}

export interface Payment {
  id: string;
  handle: string;
  month: string;
  time: string;
  amount: string;
  currency: string; // the account currency: `amount` is in it
  operation_currency: string | null; // original operation currency (differs on a conversion)
  description: string | null;
  comment: string | null;
  counter_name: string | null;
  counter_edrpou: string | null;
  counter_iban: string | null;
  mcc: number | null;
  original_mcc: number | null;
  operation_amount: string | null;
  commission_rate: string | null;
  cashback_amount: string | null;
  balance: string | null;
  hold: boolean | null;
  extra: Record<string, unknown>;
  possible_internal_transfer: boolean;
  marked: boolean;
  amount_override: string | null;
}

export type MonthStateName = "not_fetched" | "partial" | "fetched" | "reviewed";

export interface MonthState {
  handle: string;
  month: string;
  state: MonthStateName;
  payments: number;
  marked: number;
}

export interface Payments {
  payments: Payment[];
  months: MonthState[];
}

export interface RateEstimate {
  rate: string; // fraction, e.g. "0.05"
  single_tax: string;
  total: string;
}

export interface Estimate {
  income: string;
  military_levy: string;
  esv: string;
  by_rate: RateEstimate[];
  months: number;
  text: string;
}

export interface Declaration {
  text: string;
  preliminary: boolean;
  declaration_due: string;
  payments: { tax: string; amount: string; due: string; budget_code: string }[];
  rows: Record<string, string>;
}

export interface PreviousRows {
  income: string;
  row_07: string;
  row_12: string;
  row_23: string;
}

export interface Rules {
  year: number;
  version: string;
  updated_on: string;
  disclaimer: string;
  cabinet: string;
  tax_account: string;
  new_declaration: string;
  declaration_video: string;
  channels: { name: string; url: string }[];
  linkedin: string;
}

export interface Meta {
  ready: boolean;
  error: ErrorBody | null;
  version: string;
  store_key: string | null;
  years: number[];
  current_year: number | null;
  rules: Rules | null;
}

export interface DataInfo {
  folder: string;
  years: { year: number; bytes: number }[];
  key_storage: string | null;
}
