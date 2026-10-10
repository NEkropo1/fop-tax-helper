/** "1234.5" -> "1 234.50" (the backend sends decimal strings; never parse them as floats for math). */
export function formatMoney(value: string): string {
  const [whole = "0", fraction = ""] = value.split(".");
  const negative = whole.startsWith("-");
  const digits = negative ? whole.slice(1) : whole;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${negative ? "-" : ""}${grouped}.${(fraction + "00").slice(0, 2)}`;
}

/** Seconds -> "≈ 3 хв" (rounded up; never "0 хв" for a non-zero wait). */
export function formatDuration(seconds: number): string {
  if (seconds <= 0) return "0 хв";
  return `≈ ${Math.max(1, Math.ceil(seconds / 60))} хв`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

export function formatDate(iso: string): string {
  const [year, month, day] = iso.split("-");
  return `${day}.${month}.${year}`;
}
