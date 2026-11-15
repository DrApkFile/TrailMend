import { Failed, Panel } from "@/components/Shell";
import { fetchTruth, type TruthEdge, type TruthFault } from "@/lib/api";
import { RollbackForm } from "../mend/RollbackForm";

export const dynamic = "force-dynamic";

const STATUS: Record<string, { label: string; tone: string }> = {
  still_wrong: {
    label: "still wrong",
    tone: "border-red-900/70 bg-red-950/40 text-red-200",
  },
  quarantined: {
    label: "quarantined",
    tone: "border-amber-900/70 bg-amber-950/40 text-amber-200",
  },
  corrected: {
    label: "corrected",
    tone: "border-emerald-900/70 bg-emerald-950/40 text-emerald-200",
  },
  restored_by_gapfill: {
    label: "restored by gap-fill",
    tone: "border-sky-900/70 bg-sky-950/40 text-sky-200",
  },
};
const ORDER = [
  "still_wrong",
  "quarantined",
  "corrected",
  "restored_by_gapfill",
];
const KIND: Record<string, string> = {
  contradicted: "stale link, true link also in the graph",
  recoverable: "wrong link, true link in an un-ingested document",
  destroyed: "wrong link, true link in no document",
  missing_edge: "link withheld from the graph",
  alias_duplicate: "one service entered twice",
  conflation: "two people merged into one",
};

function statusOf(key: string): { label: string; tone: string } {
  return (
    STATUS[key] ?? {
      label: key.replaceAll("_", " "),
      tone: "border-stone-700 text-stone-300",
    }
  );
}

function Edge({ edge, role }: { edge: TruthEdge | null; role: string }) {
  if (edge === null) {
    return null;
  }
  const gone = edge.status === "absent";
  return (
    <p className="font-mono text-xs break-words text-stone-300">
      <span className="text-stone-500">{role} </span>
      <span className={gone ? "text-stone-500" : "text-stone-100"}>
        {edge.hop.src_name}
      </span>
      <span className="text-stone-500"> —{edge.hop.rel_type}→ </span>
      <span className={gone ? "text-stone-500" : "text-stone-100"}>
        {edge.hop.dst_name}
      </span>
      <span className="text-stone-500">
        {" "}
        {gone
          ? "not in the graph"
          : `${edge.status}, cost ${edge.hop.cost.toFixed(3)}`}
      </span>
    </p>
  );
}

function Fault({ fault }: { fault: TruthFault }) {
  const status = statusOf(fault.status);
  return (
    <li className="rounded-lg border border-stone-800 bg-stone-900/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded-full border px-2 py-0.5 text-xs ${status.tone}`}
        >
          {status.label}
        </span>
        <span className="text-xs text-stone-400">
          {KIND[fault.kind] ?? fault.kind}
        </span>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        <Edge edge={fault.planted} role="planted" />
        <Edge edge={fault.truth} role="true" />
        {fault.other_edges > 0 && (
          <p className="text-xs text-stone-500">
            and {fault.other_edges} more edges moved by the same fault
          </p>
        )}
      </div>
      <p className="mt-2 text-xs text-stone-500">
        Can be repaired by {fault.repairable_by}.
      </p>
      {fault.receipts.length > 0 && (
        <ul className="mt-2 flex flex-col gap-2 border-t border-stone-800 pt-2">
          {fault.receipts.map((receipt) => (
            <li key={receipt.receipt_id}>
              <p className="font-mono text-xs break-all text-stone-300">
                {receipt.kind} · {receipt.receipt_id}
              </p>
              <RollbackForm
                receiptId={receipt.receipt_id}
                kind={receipt.kind}
              />
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export default async function TruthPage() {
  const truth = await fetchTruth();
  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">
        What is actually wrong with this graph
      </h1>
      <p className="mt-2 text-stone-400">
        The demo graph is generated, and every fault in it was planted on
        purpose and written down. This page reads each one back from HydraDB as
        it is right now: whether the wrong link is still the one the search
        walks, whether it was quarantined, whether the true link has become the
        cheaper one, or whether gap-fill put a withheld link back. Judge an
        answer on Ask and the fault behind it changes here.
      </p>
      {!truth.ok && (
        <div className="mt-6">
          <Failed code={truth.error.code} message={truth.error.message} />
        </div>
      )}
      {truth.ok && (
        <>
          <Panel
            title={`Seed ${truth.value.seed}, data ${truth.value.data_version}, generated`}
          >
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {ORDER.map((key) => (
                <div key={key}>
                  <dt className="text-xs text-stone-500">
                    {statusOf(key).label}
                  </dt>
                  <dd className="font-mono text-xl text-stone-100">
                    {truth.value.counts[key] ?? 0}
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-xs text-stone-500">
              {truth.value.faults.length} planted faults. The status comes from
              the graph. The receipts come from the live journal, which holds{" "}
              {truth.value.receipts_recorded} entries and starts empty after
              each deploy, so a fault can have changed before the oldest receipt
              listed here.
            </p>
          </Panel>
          {ORDER.map((key) => {
            const faults = truth.value.faults.filter(
              (fault) => fault.status === key,
            );
            if (faults.length === 0) {
              return null;
            }
            return (
              <section key={key} className="mt-6">
                <h2 className="text-sm font-semibold tracking-wide text-stone-300 uppercase">
                  {statusOf(key).label} · {faults.length}
                </h2>
                <ul className="mt-3 flex flex-col gap-3">
                  {faults.map((fault) => (
                    <Fault key={fault.fault_id} fault={fault} />
                  ))}
                </ul>
              </section>
            );
          })}
        </>
      )}
    </main>
  );
}
