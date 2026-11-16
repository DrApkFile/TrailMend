import { Changes, toChangeRows } from "@/components/Changes";
import { Latency, type LatencyRow } from "@/components/Latency";
import { Manifest, type ManifestPayload } from "@/components/Manifest";
import { Failed, Panel } from "@/components/Shell";
import { fetchCurve, fetchCurveV2, fetchEvidence } from "@/lib/api";
import { NOT_MEASURED } from "@/lib/curve";

export const dynamic = "force-dynamic";

const RUN2_FILES = [
  "mechanisms_v2",
  "paired_v2",
  "captured_share_v2",
  "oracle_v2",
  "changes_v2",
  "non_regression_v2",
  "quarantine_v2",
  "hypotheses_v2",
  "plain_store_v2",
  "fault_recoverability_v2",
  "run_manifest_v2",
];
const RUN1_FILES = [
  "round_zero",
  "plain_store",
  "mechanisms",
  "changes",
  "non_regression",
  "quarantine",
  "hypotheses",
  "anatomy",
  "oracle",
  "fault_recoverability",
  "run_manifest",
];
const SHARED_FILES = [
  "load",
  "latency",
  "benchmark",
  "paired_v2_unweighted",
  "replication_v2_clean",
  "hypotheses_metaqa",
  "paired_metaqa",
  "captured_share_metaqa",
  "oracle_metaqa",
  "non_regression_metaqa",
  "plain_store_metaqa",
];
const FILES = [...RUN2_FILES, ...RUN1_FILES, ...SHARED_FILES];

export default async function EvidencePage() {
  const [curve, curveV2, ...files] = await Promise.all([
    fetchCurve(),
    fetchCurveV2(),
    ...FILES.map((name) => fetchEvidence(name)),
  ]);
  const changes = files[FILES.indexOf("changes")];
  const benchmark = files[FILES.indexOf("benchmark")];
  const comparability =
    benchmark?.ok && benchmark.value.available
      ? (
          (benchmark.value.payload?.rows ?? []) as {
            key?: string;
            text?: string;
          }[]
        ).find((row) => row.key === "comparability")?.text
      : undefined;
  const latency = files[FILES.indexOf("latency")];
  const latencyRows =
    latency?.ok && latency.value.available
      ? ((latency.value.payload?.rows ?? []) as LatencyRow[])
      : [];
  const changeRows =
    changes?.ok && changes.value.available
      ? toChangeRows(changes.value.payload?.rows ?? [])
      : [];

  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">Evidence</h1>
      <p className="mt-2 text-stone-400">
        Every file here is written by code, never by hand, and carries the
        design it was measured under. The sha256 is of the file as served. A
        file that has not been produced says so. Files ending{" "}
        <span className="font-mono">_v2</span> are run 2; MetaQA and the
        unweighted extension are named separately. Run 1 failed and is kept
        exactly as it was published.
      </p>
      <p className="mt-3 text-sm text-stone-300">
        {comparability ?? NOT_MEASURED}
      </p>

      <Panel title="curve_v2.jsonl">
        {curveV2.ok ? (
          <dl className="text-sm">
            <div className="flex justify-between border-b border-stone-800 py-2">
              <dt className="text-stone-400">rows</dt>
              <dd className="font-mono">
                {curveV2.value.available
                  ? curveV2.value.rows.length
                  : NOT_MEASURED}
              </dd>
            </div>
            <div className="flex flex-col gap-1 border-b border-stone-800 py-2 sm:flex-row sm:justify-between">
              <dt className="text-stone-400">sha256</dt>
              <dd className="font-mono text-xs break-all">
                {curveV2.value.sha256 ?? NOT_MEASURED}
              </dd>
            </div>
          </dl>
        ) : (
          <Failed code={curveV2.error.code} message={curveV2.error.message} />
        )}
      </Panel>

      <Panel title="curve.jsonl">
        {curve.ok ? (
          <dl className="text-sm">
            <div className="flex justify-between border-b border-stone-800 py-2">
              <dt className="text-stone-400">rows</dt>
              <dd className="font-mono">
                {curve.value.available ? curve.value.rows.length : NOT_MEASURED}
              </dd>
            </div>
            <div className="flex flex-col gap-1 border-b border-stone-800 py-2 sm:flex-row sm:justify-between">
              <dt className="text-stone-400">sha256</dt>
              <dd className="font-mono text-xs break-all">
                {curve.value.sha256 ?? NOT_MEASURED}
              </dd>
            </div>
          </dl>
        ) : (
          <Failed code={curve.error.code} message={curve.error.message} />
        )}
      </Panel>

      <Panel title="The controls, side by side">
        <p className="text-sm text-stone-300">
          Changes each arm applied, per seed and round:{" "}
          <span className="font-mono">rw</span> reweights,{" "}
          <span className="font-mono">qu</span> quarantines, and promotions,
          retirements and ingests where there were any. Hover a cell for what
          the Mend planned that round. A random control applies exactly as many
          changes as the Mend planned in that same round of that same arm, of
          the one mechanism it controls — that equality is checked before any of
          these files is written, and a mismatch stops the analysis.
        </p>
        <p className="mt-2 text-xs text-stone-400">
          The counts differ between arms because every arm resets the graph and
          evolves on its own, so round 2 of full plans from full&apos;s graph
          and round 2 of random_reweight plans from its own.
        </p>
        <div className="mt-4">
          {changeRows.length === 0 ? (
            <p className="text-sm text-stone-400">Not produced yet.</p>
          ) : (
            <Changes rows={changeRows} />
          )}
        </div>
      </Panel>

      <Panel title="What it costs to answer">
        <p className="text-sm text-stone-300">
          Concurrent clients asking the product question mix over HTTP against
          this deployment, then the same load again while a Mend round writes to
          the same graph. The tail is connection setup, not the graph: the first
          request on a fresh connection to the edge costs about six seconds and
          later ones on it about half a second.
        </p>
        <div className="mt-4">
          {latencyRows.length === 0 ? (
            <p className="text-sm text-stone-400">Not produced yet.</p>
          ) : (
            <Latency rows={latencyRows} />
          )}
        </div>
        {latencyRows[1]?.writer && (
          <p className="mt-3 text-xs text-stone-400">
            The writer in the second pass took{" "}
            <span className="font-mono">{latencyRows[1].writer.seconds}s</span>{" "}
            to apply{" "}
            <span className="font-mono">{latencyRows[1].writer.reweights}</span>{" "}
            reweights and{" "}
            <span className="font-mono">
              {latencyRows[1].writer.quarantines}
            </span>{" "}
            quarantines under{" "}
            <span className="font-mono">{latencyRows[1].writer.receipts}</span>{" "}
            receipts.
          </p>
        )}
      </Panel>

      {files.map((file, index) => (
        <Panel key={FILES[index]} title={`${FILES[index]}.json`}>
          {!file.ok ? (
            <Failed code={file.error.code} message={file.error.message} />
          ) : !file.value.available ? (
            <p className="text-sm text-stone-400">Not produced yet.</p>
          ) : FILES[index] === "run_manifest" ? (
            <Manifest
              payload={file.value.payload as ManifestPayload | undefined}
            />
          ) : (
            <div className="text-sm">
              <p className="text-stone-300">{file.value.payload?.claim}</p>
              <p className="mt-2 text-xs text-stone-400">
                {file.value.payload?.design}
              </p>
              <dl className="mt-3">
                <div className="flex justify-between border-t border-stone-800 py-2">
                  <dt className="text-stone-400">rows</dt>
                  <dd className="font-mono">
                    {file.value.payload?.rows?.length ?? NOT_MEASURED}
                  </dd>
                </div>
                <div className="flex justify-between border-t border-stone-800 py-2">
                  <dt className="text-stone-400">measured at</dt>
                  <dd className="font-mono text-xs">
                    {file.value.payload?.measured_at ?? NOT_MEASURED}
                  </dd>
                </div>
                <div className="flex flex-col gap-1 border-t border-stone-800 py-2 sm:flex-row sm:justify-between">
                  <dt className="text-stone-400">sha256</dt>
                  <dd className="font-mono text-xs break-all">
                    {file.value.sha256 ?? NOT_MEASURED}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </Panel>
      ))}
    </main>
  );
}
