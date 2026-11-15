import { Failed, Hops, Panel } from "@/components/Shell";
import { fetchEvidence, fetchReceipts } from "@/lib/api";
import { NOT_MEASURED } from "@/lib/curve";

export const dynamic = "force-dynamic";

type QuarantineRow = {
  seed: number;
  arm: string;
  planted_wrong_edges: number;
  quarantined: number;
  quarantined_that_were_planted: number;
  precision: number | null;
  recall_on_planted_wrong_edges: number | null;
  false_quarantine_rate: number | null;
  gaps_filled: number;
  spurious_ingests: number;
};

function share(value: number | null | undefined): string {
  return typeof value === "number" ? value.toFixed(2) : NOT_MEASURED;
}

export default async function MendPage() {
  const [receipts, quarantine] = await Promise.all([fetchReceipts(30), fetchEvidence("quarantine")]);
  const rows =
    quarantine.ok && quarantine.value.available && quarantine.value.payload
      ? (quarantine.value.payload.rows as QuarantineRow[]).filter((row) => row.arm === "full")
      : [];
  const kinds = receipts.ok
    ? receipts.value.reduce<Record<string, number>>((tally, receipt) => {
        tally[receipt.kind] = (tally[receipt.kind] ?? 0) + 1;
        return tally;
      }, {})
    : {};

  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">The link that kept being wrong</h1>
      <p className="mt-2 text-stone-400">
        The generated graph has planted faults: links pointing at the wrong target, links withheld entirely,
        duplicated services, two people merged into one. Blame accumulates on an edge across rounds. When an edge is
        blamed enough times, with a high enough share of its last judgements and almost no confirmations, it is
        quarantined: moved to a <span className="font-mono">Q_</span> type that the search can never traverse.
      </p>

      <Panel title="How often quarantine was right">
        {quarantine.ok ? (
          rows.length === 0 ? (
            <p className="text-sm text-stone-400">
              Not measured yet. This fills in from evidence/quarantine.json once a run has been scored against the
              planted faults.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs text-stone-400 uppercase">
                  <tr>
                    <th className="py-2 pr-4">seed</th>
                    <th className="py-2 pr-4">planted</th>
                    <th className="py-2 pr-4">quarantined</th>
                    <th className="py-2 pr-4">precision</th>
                    <th className="py-2 pr-4">recall</th>
                    <th className="py-2 pr-4">false rate</th>
                    <th className="py-2 pr-4">gaps filled</th>
                    <th className="py-2">spurious</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {rows.map((row) => (
                    <tr key={row.seed} className="border-t border-stone-800">
                      <td className="py-2 pr-4">{row.seed}</td>
                      <td className="py-2 pr-4">{row.planted_wrong_edges}</td>
                      <td className="py-2 pr-4">{row.quarantined}</td>
                      <td className="py-2 pr-4">{share(row.precision)}</td>
                      <td className="py-2 pr-4">{share(row.recall_on_planted_wrong_edges)}</td>
                      <td className="py-2 pr-4">{share(row.false_quarantine_rate)}</td>
                      <td className="py-2 pr-4">{row.gaps_filled}</td>
                      <td className="py-2">{row.spurious_ingests}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <Failed code={quarantine.error.code} message={quarantine.error.message} />
        )}
        <p className="mt-3 text-xs text-stone-500">
          Precision counts quarantined edges that a planted fault introduced. The false-quarantine rate counts
          quarantined edges that are in the truth graph. An ingest is spurious if the edge it added is not in the
          truth graph.
        </p>
      </Panel>

      <Panel title="What the live demo graph has done">
        {receipts.ok ? (
          <>
            <p className="text-sm text-stone-300">
              {receipts.value.length === 0
                ? "No receipts yet on the live demo graph."
                : Object.entries(kinds)
                    .map(([kind, count]) => `${count} ${kind}`)
                    .join(", ")}
            </p>
            <ul className="mt-3 flex flex-col gap-2">
              {receipts.value.slice(0, 12).map((receipt) => (
                <li key={receipt.receipt_id} className="rounded border border-stone-800 p-2">
                  <p className="font-mono text-xs break-all text-stone-400">
                    {receipt.receipt_id} · {receipt.kind} · round {receipt.round}
                  </p>
                  {receipt.edge && <div className="mt-1"><Hops hops={[receipt.edge]} /></div>}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <Failed code={receipts.error.code} message={receipts.error.message} />
        )}
        <p className="mt-3 text-xs text-stone-500">
          Every change writes its receipt before the graph is touched, so a receipt can describe a change that was
          then rolled back, but never a change that was made without one. Rolling back needs the admin token and
          writes its own receipt.
        </p>
      </Panel>
    </main>
  );
}
