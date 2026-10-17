import type { Conflict, Editable, KeyDate } from "./api";

export const toEditable = (p: Editable): Editable => ({
  name: p.name,
  sector: p.sector,
  country: p.country,
  stage: p.stage,
  key_dates: p.key_dates.map((d) => ({ label: d.label, date: d.date })),
});

export const sameEditable = (a: Editable, b: Editable) => JSON.stringify(toEditable(a)) === JSON.stringify(toEditable(b));

export const hasDuplicateLabels = (dates: KeyDate[]) => new Set(dates.map((d) => d.label)).size !== dates.length;

export const humanize = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

/** "name" -> "Name", "key_dates:Tender launch" -> "Key date: Tender launch". */
export function describeKey(key: string): string {
  if (key === "key_dates") return "Key dates (whole list)";
  if (key.startsWith("key_dates:")) return `Key date: ${key.slice("key_dates:".length)}`;
  return humanize(key);
}

export function describeValue(value: unknown): string {
  if (value === null || value === undefined) return "(none)";
  if (Array.isArray(value)) return value.map((d: KeyDate) => `${d.label}: ${d.date}`).join("; ") || "(empty)";
  return String(value);
}

/**
 * Turn the person's decisions into the next request. `proposed` already holds their non-conflicting edits plus the
 * other writer's value on every conflicting field; choosing "mine" puts the person's own value back.
 */
export function applyChoices(proposed: Editable, conflicts: Conflict[], choices: Record<string, "mine" | "theirs">): Editable {
  const out = toEditable(proposed);
  for (const c of conflicts) {
    if (choices[c.key] !== "mine") continue;
    if (c.kind === "scalar") {
      (out as Record<string, unknown>)[c.field] = c.mine;
    } else if (c.kind === "key_dates_list") {
      out.key_dates = (c.mine as KeyDate[]).map((d) => ({ ...d }));
    } else {
      const index = out.key_dates.findIndex((d) => d.label === c.label);
      if (c.mine === null) {
        if (index >= 0) out.key_dates.splice(index, 1);
      } else if (index >= 0) {
        out.key_dates[index].date = c.mine as string;
      } else {
        out.key_dates.push({ label: c.label as string, date: c.mine as string });
      }
    }
  }
  return out;
}
