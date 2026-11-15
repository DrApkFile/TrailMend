import { NOT_MEASURED } from "@/lib/curve";

export type ManifestPayload = {
  run_id?: string;
  code_commit?: string;
  hydradb?: { image?: string; digest?: string };
  config?: { path?: string; sha256?: string };
  seeds?: Record<string, unknown>;
  evidence_sha256?: Record<string, string>;
};

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 border-t border-stone-800 py-2 sm:flex-row sm:justify-between">
      <dt className="text-stone-400">{label}</dt>
      <dd className="font-mono text-xs break-all">{value}</dd>
    </div>
  );
}

export function Manifest({ payload }: { payload: ManifestPayload | undefined }) {
  const seeds = Object.keys(payload?.seeds ?? {})
    .sort((a, b) => Number(a) - Number(b))
    .join(", ");
  const hashed = Object.keys(payload?.evidence_sha256 ?? {}).length;
  return (
    <div className="text-sm">
      <p className="text-stone-300">
        What produced every number on this site: the commit, the HydraDB that answered, the frozen config and the
        sha256 of each evidence file.
      </p>
      <dl className="mt-3">
        <Line label="run id" value={payload?.run_id ?? NOT_MEASURED} />
        <Line label="code commit" value={payload?.code_commit ?? NOT_MEASURED} />
        <Line
          label="HydraDB"
          value={
            payload?.hydradb?.image
              ? `${payload.hydradb.image}@${payload.hydradb.digest ?? NOT_MEASURED}`
              : NOT_MEASURED
          }
        />
        <Line label="config" value={`${payload?.config?.path ?? NOT_MEASURED} sha256 ${payload?.config?.sha256 ?? NOT_MEASURED}`} />
        <Line label="seeds" value={seeds || NOT_MEASURED} />
        <Line label="evidence files hashed" value={hashed ? String(hashed) : NOT_MEASURED} />
      </dl>
    </div>
  );
}
