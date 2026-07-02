import type { ValidationReport } from "../api/types";
import { Badge } from "./ui";

const RULE_NAMES: Record<string, string> = {
  unknown_blocks: "Known blocks only",
  block_count: "Block count",
  grid_size: "Grid size",
  pcu_limit: "PCU limit",
  weapon_count: "Weapon count",
  block_whitelist: "Block whitelist",
  block_blacklist: "Block blacklist",
};

function fmt(v: any): string {
  if (Array.isArray(v)) return v.length ? v.join(", ") : "—";
  if (v && typeof v === "object")
    return Object.entries(v)
      .filter(([, val]) => val !== null && val !== undefined)
      .map(([k, val]) => `${k}: ${val}`)
      .join(", ") || "—";
  return v === null || v === undefined ? "—" : String(v);
}

export function ValidationReportView({ report }: { report: ValidationReport }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {report.passed ? (
          <Badge tone="good">All checks passed</Badge>
        ) : (
          <Badge tone="bad">Validation failed</Badge>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 text-sm">
        {report.stats && (
          <>
            <Stat label="Blocks" value={report.stats.block_count} />
            <Stat label="PCU" value={report.stats.pcu} />
            <Stat label="Weapons" value={report.stats.weapon_count} />
            <Stat label="Grid" value={(report.stats.grid_sizes || []).join(", ")} />
          </>
        )}
      </div>

      <ul className="divide-y divide-border rounded-xl border border-border overflow-hidden">
        {report.results.map((r, i) => (
          <li key={i} className="flex items-start gap-3 p-3">
            <span className={r.passed ? "text-good" : "text-bad"}>
              {r.passed ? "✓" : "✗"}
            </span>
            <div className="flex-1">
              <div className="font-medium text-sm">{RULE_NAMES[r.rule] ?? r.rule}</div>
              {!r.passed && (
                <div className="text-xs text-muted mt-0.5">
                  measured <b>{fmt(r.measured)}</b>, allowed <b>{fmt(r.allowed)}</b>
                  {r.detail ? ` — ${r.detail}` : ""}
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl bg-cream px-3 py-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="font-semibold">{value ?? "—"}</div>
    </div>
  );
}
