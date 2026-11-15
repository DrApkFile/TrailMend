type CountField =
  | "planned_reweights"
  | "planned_quarantines"
  | "applied_reweights"
  | "applied_quarantines"
  | "promoted"
  | "retired"
  | "ingested";

type Counts = Partial<Record<CountField, number>>;
type ChangeRow = { seed: number; round: number; arms: Record<string, Counts> };

function isCounts(value: unknown): value is Counts {
  return typeof value === "object" && value !== null;
}

export function toChangeRows(rows: unknown[]): ChangeRow[] {
  const out: ChangeRow[] = [];
  for (const row of rows) {
    if (typeof row !== "object" || row === null) {
      continue;
    }
    const shape = row as { seed?: unknown; round?: unknown; arms?: unknown };
    if (typeof shape.seed !== "number" || typeof shape.round !== "number") {
      continue;
    }
    if (typeof shape.arms !== "object" || shape.arms === null) {
      continue;
    }
    const arms: Record<string, Counts> = {};
    for (const [arm, counts] of Object.entries(
      shape.arms as Record<string, unknown>,
    )) {
      if (isCounts(counts)) {
        arms[arm] = counts;
      }
    }
    out.push({ seed: shape.seed, round: shape.round, arms });
  }
  return out.sort((a, b) => a.seed - b.seed || a.round - b.round);
}

function armNames(rows: ChangeRow[]): string[] {
  const seen = new Set<string>();
  for (const row of rows) {
    for (const arm of Object.keys(row.arms)) {
      seen.add(arm);
    }
  }
  const ordered = [
    "full_v2",
    "full",
    "full_v1_rule",
    "gapfill_wide_only",
    "reweight_only",
    "random_reweight",
    "quarantine_only",
    "random_quarantine",
  ];
  const first = ordered.filter((arm) => seen.has(arm));
  const rest = [...seen].filter((arm) => !first.includes(arm)).sort();
  return [...first, ...rest];
}

function cell(counts: Counts | undefined): string {
  if (counts === undefined) {
    return "—";
  }
  const parts = [
    `${counts.applied_reweights ?? 0} rw`,
    `${counts.applied_quarantines ?? 0} qu`,
  ];
  for (const [field, label] of [
    ["promoted", "pr"],
    ["retired", "re"],
    ["ingested", "in"],
  ] as const) {
    const value = counts[field] ?? 0;
    if (value > 0) {
      parts.push(`${value} ${label}`);
    }
  }
  return parts.join(" · ");
}

function planned(counts: Counts | undefined): string {
  if (counts === undefined) {
    return "—";
  }
  return `${counts.planned_reweights ?? 0} rw / ${counts.planned_quarantines ?? 0} qu`;
}

export function Changes({ rows }: { rows: ChangeRow[] }) {
  const arms = armNames(rows);
  const seeds = [...new Set(rows.map((row) => row.seed))];

  return (
    <div className="flex flex-col gap-6">
      {seeds.map((seed) => (
        <div key={seed}>
          <h3 className="mb-2 text-sm text-stone-400">seed {seed}</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-stone-400">
                <tr>
                  <th className="py-1 pr-3 font-normal">round</th>
                  {arms.map((arm) => (
                    <th
                      key={arm}
                      className="py-1 pr-3 font-normal whitespace-nowrap"
                    >
                      {arm}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {rows
                  .filter((row) => row.seed === seed)
                  .map((row) => (
                    <tr key={row.round} className="border-t border-stone-800">
                      <td className="py-1 pr-3">{row.round}</td>
                      {arms.map((arm) => (
                        <td
                          key={arm}
                          className="py-1 pr-3 whitespace-nowrap"
                          title={`planned ${planned(row.arms[arm])}`}
                        >
                          {cell(row.arms[arm])}
                        </td>
                      ))}
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
