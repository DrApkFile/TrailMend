import { Failed, Panel } from "@/components/Shell";
import { fetchCurve, fetchEvidence } from "@/lib/api";
import { NOT_MEASURED } from "@/lib/curve";

export const dynamic = "force-dynamic";

const FILES = ["round_zero", "plain_store", "mechanisms", "non_regression", "quarantine", "hypotheses", "run_manifest"];

export default async function EvidencePage() {
  const [curve, ...files] = await Promise.all([fetchCurve(), ...FILES.map((name) => fetchEvidence(name))]);

  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">Evidence</h1>
      <p className="mt-2 text-stone-400">
        Every file here is written by code, never by hand, and carries the design it was measured under. The sha256
        is of the file as served. A file that has not been produced says so.
      </p>

      <Panel title="curve.jsonl">
        {curve.ok ? (
          <dl className="text-sm">
            <div className="flex justify-between border-b border-stone-800 py-2">
              <dt className="text-stone-400">rows</dt>
              <dd className="font-mono">{curve.value.available ? curve.value.rows.length : NOT_MEASURED}</dd>
            </div>
            <div className="flex flex-col gap-1 border-b border-stone-800 py-2 sm:flex-row sm:justify-between">
              <dt className="text-stone-400">sha256</dt>
              <dd className="font-mono text-xs break-all">{curve.value.sha256 ?? NOT_MEASURED}</dd>
            </div>
          </dl>
        ) : (
          <Failed code={curve.error.code} message={curve.error.message} />
        )}
      </Panel>

      {files.map((file, index) => (
        <Panel key={FILES[index]} title={`${FILES[index]}.json`}>
          {!file.ok ? (
            <Failed code={file.error.code} message={file.error.message} />
          ) : !file.value.available ? (
            <p className="text-sm text-stone-400">Not produced yet.</p>
          ) : (
            <div className="text-sm">
              <p className="text-stone-300">{file.value.payload?.claim}</p>
              <p className="mt-2 text-xs text-stone-400">{file.value.payload?.design}</p>
              <dl className="mt-3">
                <div className="flex justify-between border-t border-stone-800 py-2">
                  <dt className="text-stone-400">rows</dt>
                  <dd className="font-mono">{file.value.payload?.rows.length ?? NOT_MEASURED}</dd>
                </div>
                <div className="flex justify-between border-t border-stone-800 py-2">
                  <dt className="text-stone-400">measured at</dt>
                  <dd className="font-mono text-xs">{file.value.payload?.measured_at ?? NOT_MEASURED}</dd>
                </div>
                <div className="flex flex-col gap-1 border-t border-stone-800 py-2 sm:flex-row sm:justify-between">
                  <dt className="text-stone-400">sha256</dt>
                  <dd className="font-mono text-xs break-all">{file.value.sha256 ?? NOT_MEASURED}</dd>
                </div>
              </dl>
            </div>
          )}
        </Panel>
      ))}
    </main>
  );
}
