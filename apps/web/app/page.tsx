import { fetchReadiness } from "@/lib/api";

export const dynamic = "force-dynamic";

const NOT_MEASURED = "—";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 border-b border-stone-800 py-3 sm:flex-row sm:items-baseline sm:justify-between">
      <dt className="text-sm text-stone-400">{label}</dt>
      <dd className="font-mono text-sm break-all text-stone-100">{value}</dd>
    </div>
  );
}

export default async function Home() {
  const readiness = await fetchReadiness();
  const writable = readiness.ok ? String(readiness.value.graph_writable) : NOT_MEASURED;

  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">TrailMend</h1>
      <p className="mt-2 text-stone-400">
        The graph that repairs its own relationships. Every number on this site is produced by a run on record; a
        dash means it has not been measured yet.
      </p>

      <section className="mt-8 rounded-lg border border-stone-800 bg-stone-900/40 p-4">
        <h2 className="text-sm font-semibold tracking-wide text-stone-300 uppercase">Graph readiness</h2>
        <dl className="mt-2">
          <Row label="graph_writable" value={writable} />
          <Row label="source" value="GET /v1/ready, server-side" />
        </dl>
        {!readiness.ok && (
          <p className="mt-4 rounded border border-amber-900/60 bg-amber-950/40 p-3 text-sm text-amber-200">
            The API did not report readiness: <span className="font-mono">{readiness.error.code}</span> —{" "}
            {readiness.error.message}
          </p>
        )}
      </section>

      <p className="mt-8 text-xs text-stone-500">
        Evaluation data is generated, and labelled generated everywhere it appears.
      </p>
    </main>
  );
}
