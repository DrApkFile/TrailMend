import { NOT_MEASURED } from "@/lib/curve";

export type LatencyRow = {
  label: string;
  clients: number;
  requests: number;
  qps: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
  p99_ms: number | null;
  ok: number;
  errors_by_code: Record<string, number>;
  writer?: { seconds: number; code: string; reweights?: number; quarantines?: number; receipts?: number };
};

function ms(value: number | null | undefined): string {
  return typeof value === "number" ? `${value.toFixed(0)} ms` : NOT_MEASURED;
}

function errors(row: LatencyRow): string {
  const entries = Object.entries(row.errors_by_code ?? {});
  return entries.length === 0 ? "none" : entries.map(([code, count]) => `${count} ${code}`).join(", ");
}

export function Latency({ rows }: { rows: LatencyRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-stone-400 uppercase">
          <tr>
            <th className="py-2 pr-4">pass</th>
            <th className="py-2 pr-4">clients</th>
            <th className="py-2 pr-4">requests</th>
            <th className="py-2 pr-4">qps</th>
            <th className="py-2 pr-4">p50</th>
            <th className="py-2 pr-4">p95</th>
            <th className="py-2 pr-4">p99</th>
            <th className="py-2 pr-4">answered</th>
            <th className="py-2">errors</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-t border-stone-800">
              <td className="py-2 pr-4">{row.label}</td>
              <td className="py-2 pr-4 font-mono">{row.clients}</td>
              <td className="py-2 pr-4 font-mono">{row.requests}</td>
              <td className="py-2 pr-4 font-mono">{row.qps ?? NOT_MEASURED}</td>
              <td className="py-2 pr-4 font-mono">{ms(row.p50_ms)}</td>
              <td className="py-2 pr-4 font-mono">{ms(row.p95_ms)}</td>
              <td className="py-2 pr-4 font-mono">{ms(row.p99_ms)}</td>
              <td className="py-2 pr-4 font-mono">{row.ok}</td>
              <td className="py-2 font-mono">{errors(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
