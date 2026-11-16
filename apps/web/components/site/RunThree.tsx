import Link from "next/link";
import { fetchEvidence } from "@/lib/api";
import { REPO_URL } from "@/lib/site";

export async function RunThree() {
  const file = await fetchEvidence("summary_v3");
  const row = file.ok && file.value.available
    ? file.value.payload?.rows?.[0] as { verdicts?: Record<string, unknown> } | undefined
    : undefined;
  const verdicts = row?.verdicts;
  const available = verdicts && ["R1", "R2", "R3"].every((key) => typeof verdicts[key] === "string");
  return (
    <p className="mx-auto max-w-6xl px-6 py-8 text-sm text-stone-400">
      <Link className="underline" href={`${REPO_URL}/blob/master/evidence/hypotheses_v3.json`}>Run 3</Link>
      {available
        ? ` (generated Northwind v2): R1 ${String(verdicts.R1)}, R2 ${String(verdicts.R2)}, R3 ${String(verdicts.R3)}. MetaQA: not_run.`
        : ": —"}
    </p>
  );
}
