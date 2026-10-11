import { describe, expect, it } from "vitest";

import { formatDate, formatDuration, formatMoney, formatPercent } from "./format";
import { bulkIds, monthKey, rangeIds } from "./selection";
import { rulesFallbackYear } from "./flow";
import { decodeSaved, encodeSaved, safeStep, STATE_VERSION } from "./persist";
import { linkify, parseDeclaration, splitFormCode, splitValue } from "./declaration_parse";

describe("formatPercent", () => {
  it("shows the rules-file fractions as plain percents", () => {
    expect(formatPercent("0.03")).toBe("3%");
    expect(formatPercent("0.05")).toBe("5%");
    expect(formatPercent("0.15")).toBe("15%");
    expect(formatPercent("0.075")).toBe("7.5%");
  });
});

describe("bulkIds", () => {
  const payments = [
    { id: "a", month: "2026-07", marked: false },
    { id: "b", month: "2026-07", marked: true },
    { id: "c", month: "2026-08", marked: false },
    { id: "d", month: "2026-09", marked: false },
  ];
  const locked = new Set(["2026-09"]);
  it("marks every unmarked payment of unlocked months", () => {
    expect(bulkIds(payments, locked, null, true)).toEqual(["a", "c"]);
  });
  it("limits the change to one month", () => {
    expect(bulkIds(payments, locked, "2026-07", true)).toEqual(["a"]);
    expect(bulkIds(payments, locked, "2026-07", false)).toEqual(["b"]);
  });
  it("never touches a confirmed month, even when asked for it", () => {
    expect(bulkIds(payments, locked, "2026-09", true)).toEqual([]);
  });
});

describe("rangeIds", () => {
  const ids = ["a", "b", "c", "d", "e"];
  it("toggles a single payment without shift", () => {
    expect(rangeIds(ids, "a", "d", false)).toEqual(["d"]);
  });
  it("selects the range between anchor and click, in either direction", () => {
    expect(rangeIds(ids, "b", "d", true)).toEqual(["b", "c", "d"]);
    expect(rangeIds(ids, "d", "b", true)).toEqual(["b", "c", "d"]);
  });
  it("falls back to the clicked payment without an anchor or for unknown ids", () => {
    expect(rangeIds(ids, null, "c", true)).toEqual(["c"]);
    expect(rangeIds(ids, "zzz", "c", true)).toEqual(["c"]);
  });
});

describe("format", () => {
  it("groups thousands and keeps two decimals", () => {
    expect(formatMoney("120000.40")).toBe("120 000.40");
    expect(formatMoney("5")).toBe("5.00");
    expect(formatMoney("1234.5")).toBe("1 234.50");
    expect(formatMoney("-1000")).toBe("-1 000.00");
  });
  it("rounds waiting time up and never shows zero for a real wait", () => {
    expect(formatDuration(0)).toBe("0 хв");
    expect(formatDuration(10)).toBe("≈ 1 хв");
    expect(formatDuration(360)).toBe("≈ 6 хв");
  });
  it("formats dates and month keys", () => {
    expect(formatDate("2026-11-09")).toBe("09.11.2026");
    expect(monthKey(2026, 7)).toBe("2026-07");
  });
});

describe("declaration text parsing", () => {
  const text = [
    "Створіть декларацію F0103309.",
    "",
    "1. Перший крок.",
    "5. Кабінет заповнить:",
    "   - 08 (усього доходу) = 120 000.40",
    "   Якщо цифри відрізняються — НЕ подавайте.",
    "",
    "Нотатка.",
    "",
    "Платежі (рахунки):",
    "   - ЄСВ: 1 грн",
    "",
    "Відео: https://v.test/watch",
    "Канал (https://c.test/@x/). Кінець.",
  ].join("\n");

  it("splits header, steps, bullets, warning, notes and footer", () => {
    const parsed = parseDeclaration(text);
    expect(parsed.header).toBe("Створіть декларацію F0103309.");
    expect(parsed.steps).toHaveLength(2);
    expect(parsed.steps[1]?.bullets).toEqual(["08 (усього доходу) = 120 000.40"]);
    expect(parsed.steps[1]?.warning).toBe("Якщо цифри відрізняються — НЕ подавайте.");
    expect(parsed.notes).toEqual(["Нотатка."]);
    expect(parsed.footer).toHaveLength(2);
  });

  it("separates the value and keeps closing brackets out of links", () => {
    expect(splitValue("08 (усього доходу) = 120 000.40")).toEqual({ label: "08 (усього доходу)", value: "120 000.40" });
    expect(splitValue("без значення")).toEqual({ label: "без значення", value: null });
    const links = linkify("Канал (https://c.test/@x/). Кінець.").filter((p) => p.kind === "link");
    expect(links).toEqual([{ kind: "link", value: "https://c.test/@x/" }]);
  });
});

describe("splitFormCode", () => {
  it("splits the form code out of the header", () => {
    expect(splitFormCode("Створіть декларацію F0103309: період")).toEqual({
      before: "Створіть декларацію ",
      code: "F0103309",
      after: ": період",
    });
  });
  it("returns null when there is no form code", () => {
    expect(splitFormCode("без коду")).toBeNull();
  });
});

describe("saved wizard state", () => {
  const flow = {
    year: 2026,
    handles: ["h1"],
    selection: { year: 2026, kind: "period", period: "Q1" } as const,
    withHistory: false,
  };
  const raw = (over: object = {}) =>
    JSON.stringify({ v: STATE_VERSION, step: "mark", flow, jobId: null, ...over });

  it("round-trips", () => {
    const saved = { step: "mark", flow, jobId: "j1" } as const;
    expect(decodeSaved(encodeSaved(saved))).toEqual(saved);
  });
  it("treats anything doubtful as no saved state", () => {
    expect(decodeSaved(null)).toBeNull();
    expect(decodeSaved("{not json")).toBeNull();
    expect(decodeSaved(raw({ v: STATE_VERSION + 1 }))).toBeNull();
    expect(decodeSaved(raw({ step: "nowhere" }))).toBeNull();
    expect(decodeSaved(raw({ flow: { ...flow, year: 1 } }))).toBeNull();
    expect(decodeSaved(raw({ flow: { ...flow, handles: [1] } }))).toBeNull();
    expect(decodeSaved(raw({ flow: { ...flow, selection: { year: 2025, kind: "period", period: "Q1" } } }))).toBeNull();
    expect(decodeSaved(raw({ flow: { ...flow, selection: { year: 2026, kind: "months", months: ["2025-01"] } } }))).toBeNull();
    expect(decodeSaved(raw({ flow: { ...flow, selection: { year: 2026, kind: "period", period: "Z" } } }))).toBeNull();
  });
  it("accepts a months selection of the same year", () => {
    const selection = { year: 2026, kind: "months", months: ["2026-02", "2026-03"] };
    expect(decodeSaved(raw({ flow: { ...flow, selection } }))?.flow.selection).toEqual(selection);
  });
});

describe("rulesFallbackYear", () => {
  it("is null when the year has rules, or there are none to fall back on", () => {
    expect(rulesFallbackYear([2025, 2026], 2025)).toBeNull();
    expect(rulesFallbackYear([], 2025)).toBeNull();
  });
  it("is the latest rules year otherwise", () => {
    expect(rulesFallbackYear([2026], 2025)).toBe(2026);
    expect(rulesFallbackYear([2024, 2026], 2030)).toBe(2026);
  });
});

describe("safeStep", () => {
  const base = { year: 2026, handles: ["h"], selection: null, withHistory: false };
  const chosen = { ...base, selection: { year: 2026, kind: "period", period: "Q1" } as const };
  it("needs accounts before anything else", () => {
    expect(safeStep("mark", { ...chosen, handles: [] }, null)).toBe("cards");
  });
  it("needs a period before the later steps", () => {
    expect(safeStep("result", base, null)).toBe("period");
    expect(safeStep("period", base, null)).toBe("period");
  });
  it("never reopens Fetch without a job, and never resumes the data screen", () => {
    expect(safeStep("fetch", chosen, null)).toBe("confirm");
    expect(safeStep("fetch", chosen, "j1")).toBe("fetch");
    expect(safeStep("data", chosen, null)).toBe("cards");
  });
  it("keeps a reachable step", () => {
    expect(safeStep("mark", chosen, null)).toBe("mark");
  });
});
