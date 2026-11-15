import Link from "next/link";
import { Curve } from "@/components/Curve";
import { Failed } from "@/components/Shell";
import {
  ReceiptFlight,
  type FlightCard,
} from "@/components/site/ReceiptFlight";
import { TrailCanvas } from "@/components/site/TrailCanvas";
import {
  fetchCurve,
  fetchCurveMetaqa,
  fetchCurveV2,
  fetchEvidence,
  fetchReadiness,
  type BenchmarkSentence,
  type CurveRow,
  type EvidenceFile,
  type Fetched,
} from "@/lib/api";
import {
  NOT_MEASURED,
  delta,
  meanByRound,
  percent,
  seedsOf,
} from "@/lib/curve";
import { REPO_URL } from "@/lib/site";

export const dynamic = "force-dynamic";

const RUN1_ARMS = [
  "full",
  "frozen",
  "plain_store",
  "random_reweight",
  "random_quarantine",
];
const RUN2_ARMS = [
  "full_v2",
  "frozen",
  "plain_store",
  "random_reweight",
  "random_quarantine",
];
const METAQA_ARMS = ["full_v2", "frozen", "plain_store", "random_reweight"];
const BENCHMARK_TEMPLATE =
  "I tested TrailMend on — generated company graphs (— nodes, — planted faults each) and on MetaQA, a public movie " +
  "knowledge graph (— triples, — held-out questions). After — rounds of learning from its own answers, held-out " +
  "accuracy went from —% to —%. It captured —% of the gain that perfect repairs would give. Random reweighting " +
  "with the same number of changes ends at —%. The same loop on a plain store ends at —%, and with unweighted " +
  "search —. Wrong answers changed by —%, and — of — questions that were right stayed right.";

type Verdict = { id: string; claim: string; verdict: string };

function rowsOf<T>(file: Fetched<EvidenceFile>): T[] {
  return file.ok && file.value.available && file.value.payload?.rows
    ? (file.value.payload.rows as T[])
    : [];
}

function total(
  rows: CurveRow[],
  arm: string,
  field: keyof CurveRow | "receipts",
): string {
  const picked = rows.filter((row) => row.arm === arm);
  if (picked.length === 0) {
    return NOT_MEASURED;
  }
  const sum = picked.reduce((running, row) => {
    const value = (row as unknown as Record<string, unknown>)[field];
    return running + (typeof value === "number" ? value : 0);
  }, 0);
  return sum.toLocaleString("en-US");
}

function Stat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="border-t border-white/10 pt-3">
      <dt className="text-xs text-stone-500">{label}</dt>
      <dd className="mt-1 font-mono text-2xl text-ink sm:text-3xl">{value}</dd>
      {note && <p className="mt-1 text-xs text-stone-500">{note}</p>}
    </div>
  );
}

function RunStats({
  rows,
  arm,
  metric,
}: {
  rows: CurveRow[];
  arm: string;
  metric: string;
}) {
  const points = meanByRound(rows, arm);
  const moved = delta(rows, arm);
  return (
    <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
      <Stat
        label={`${metric}, round 0`}
        value={points.length ? percent(points[0]?.accuracy) : NOT_MEASURED}
      />
      <Stat
        label={`${metric}, round ${points.length ? (points.at(-1)?.round ?? "") : "N"}`}
        value={points.length ? percent(points.at(-1)?.accuracy) : NOT_MEASURED}
      />
      <Stat
        label="change"
        value={
          typeof moved === "number"
            ? `${moved >= 0 ? "+" : ""}${(moved * 100).toFixed(1)} pts`
            : NOT_MEASURED
        }
      />
      <Stat
        label="seeds"
        value={rows.length ? seedsOf(rows).join(" · ") : NOT_MEASURED}
        note={rows.at(0)?.run_id ? `run ${rows.at(0)?.run_id}` : undefined}
      />
    </dl>
  );
}

function Verdicts({ title, verdicts }: { title: string; verdicts: Verdict[] }) {
  if (verdicts.length === 0) {
    return null;
  }
  return (
    <div>
      <h3 className="font-mono text-xs tracking-wider text-stone-500 uppercase">
        {title}
      </h3>
      <ul className="mt-3 flex flex-col">
        {verdicts.map((one) => (
          <li
            key={one.id}
            className="flex items-baseline justify-between gap-4 border-t border-white/10 py-2.5 text-sm"
          >
            <span className="text-stone-300">
              <span className="font-mono text-stone-500">{one.id}</span>{" "}
              {one.claim}
            </span>
            <span
              className={`font-mono text-xs ${one.verdict === "PASS" ? "text-mend" : "text-bad"}`}
            >
              {one.verdict}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-xs tracking-wider text-stone-500 uppercase">
      {children}
    </p>
  );
}

export default async function Home() {
  const [
    readiness,
    curve,
    curveV2,
    curveMetaqa,
    hypotheses,
    hypothesesV2,
    hypothesesMetaqa,
    benchmark,
  ] = await Promise.all([
    fetchReadiness(),
    fetchCurve(),
    fetchCurveV2(),
    fetchCurveMetaqa(),
    fetchEvidence("hypotheses"),
    fetchEvidence("hypotheses_v2"),
    fetchEvidence("hypotheses_metaqa"),
    fetchEvidence("benchmark"),
  ]);
  const rows = curve.ok && curve.value.available ? curve.value.rows : [];
  const rowsV2 =
    curveV2.ok && curveV2.value.available ? curveV2.value.rows : [];
  const rowsMetaqa =
    curveMetaqa.ok && curveMetaqa.value.available ? curveMetaqa.value.rows : [];
  const sentences = rowsOf<BenchmarkSentence>(benchmark);
  const rounds = rowsV2.length
    ? Math.max(...rowsV2.map((row) => row.round))
    : null;
  const cards: FlightCard[] = [
    {
      kind: "reweight",
      value: total(rowsV2, "full_v2", "applied_reweights"),
      note: "a link repriced by an answer",
    },
    {
      kind: "quarantine",
      value: total(rowsV2, "full_v2", "applied_quarantines"),
      note: "a link search may no longer walk",
    },
    {
      kind: "promote",
      value: total(rowsV2, "full_v2", "promoted"),
      note: "a confirmed path made one hop",
    },
    {
      kind: "gap-fill",
      value: total(rowsV2, "full_v2", "ingested"),
      note: "a withheld link read from a document",
    },
  ];

  return (
    <main>
      <div className="loader" aria-hidden="true">
        <p className="loader-line font-display text-2xl text-ink sm:text-3xl">
          Following the trail&hellip;
        </p>
      </div>

      <section className="relative flex min-h-svh flex-col justify-end overflow-hidden">
        <TrailCanvas />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-night via-night/70 to-transparent" />
        <div className="relative flex flex-col gap-8 px-4 pb-8 sm:px-8 sm:pb-10 lg:flex-row lg:items-end lg:justify-between">
          <h1 className="rise font-display text-[clamp(3.5rem,13.5vw,11.5rem)] leading-[0.86] tracking-tight text-ink">
            Every answer
            <br />
            <span className="italic">leaves a trail.</span>
          </h1>
          <div className="rise-late max-w-sm lg:pb-4">
            <p className="text-base text-stone-300 sm:text-lg">
              TrailMend answers by searching weighted paths in HydraDB, then
              learns from the verdict: the links an answer walked get repriced,
              the ones that keep being wrong are cut, and every change keeps a
              receipt.
            </p>
            <Link
              href="/ask"
              className="mt-5 inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-medium text-night transition-opacity hover:opacity-85"
            >
              Try it yourself
              <svg
                width="14"
                height="14"
                viewBox="0 0 14 14"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M2 7h10M8 3l4 4-4 4"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pt-24 sm:px-8 sm:pt-32">
        <Eyebrow>The accuracy curve</Eyebrow>
        <h2 className="mt-3 max-w-3xl font-display text-4xl leading-tight sm:text-6xl">
          Held-out questions, round by round.
        </h2>
        <p className="mt-4 max-w-2xl text-stone-400">
          The Mend only ever sees training questions. These are the ones it
          never saw, on the same graph, after each round. Every figure on this
          page is read from a recorded run through the API; a dash means it has
          not been measured.
        </p>
        <div className="mt-10 grid gap-10 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 sm:p-6">
            <h3 className="text-sm text-stone-300">
              Generated company graphs, run 2
            </h3>
            <div className="mt-4">
              {curveV2.ok ? (
                <Curve rows={rowsV2} arms={RUN2_ARMS} band="full_v2" />
              ) : (
                <Failed
                  code={curveV2.error.code}
                  message={curveV2.error.message}
                />
              )}
            </div>
            <RunStats rows={rowsV2} arm="full_v2" metric="accuracy" />
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 sm:p-6">
            <h3 className="text-sm text-stone-300">
              MetaQA, public movie knowledge graph, half the triples withheld
            </h3>
            <div className="mt-4">
              {curveMetaqa.ok ? (
                <Curve rows={rowsMetaqa} arms={METAQA_ARMS} band="full_v2" />
              ) : (
                <Failed
                  code={curveMetaqa.error.code}
                  message={curveMetaqa.error.message}
                />
              )}
            </div>
            <RunStats rows={rowsMetaqa} arm="full_v2" metric="Hits@1" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-4 pt-24 sm:px-8 sm:pt-32">
        <Eyebrow>The benchmark, in one paragraph</Eyebrow>
        <p className="mt-5 font-display text-[clamp(1.5rem,3.6vw,2.4rem)] leading-snug text-stone-200">
          {sentences.length > 0
            ? sentences.map((sentence) => sentence.text).join(" ")
            : BENCHMARK_TEMPLATE}
        </p>
        <p className="mt-5 text-sm text-stone-500">
          {sentences.length > 0
            ? "Written by the report generator from the evidence files, not typed. Where a claim did not hold, the sentence says what happened instead."
            : "The paragraph is generated from the evidence files; the API has not served it yet, so no number is shown."}{" "}
          <Link href="/evidence" className="underline hover:text-ink">
            Every file and its sha256
          </Link>
          .
        </p>
      </section>

      <section className="pt-16 sm:pt-24">
        <div className="mx-auto max-w-6xl px-4 sm:px-8">
          <Eyebrow>
            What {rounds ?? NOT_MEASURED} rounds left behind, run 2, all seeds
          </Eyebrow>
        </div>
        <ReceiptFlight
          cards={cards}
          lead="The graph did not get bigger by guessing. It wrote down"
          joins={["repricings,", "quarantines,", "shortcuts and", "ingests."]}
          tail={`${total(rowsV2, "full_v2", "receipts")} receipts, and any one of them can be rolled back.`}
        />
      </section>

      <section className="mx-auto grid max-w-6xl gap-12 px-4 pb-8 sm:px-8 lg:grid-cols-2">
        <div>
          <Eyebrow>Decided before the runs</Eyebrow>
          <h2 className="mt-3 font-display text-4xl leading-tight sm:text-5xl">
            Hypotheses, pass or fail.
          </h2>
          <div className="mt-8 flex flex-col gap-8">
            <Verdicts
              title="Run 2, company graphs (PRD §3.2)"
              verdicts={rowsOf<Verdict>(hypothesesV2)}
            />
            <Verdicts
              title="MetaQA (PRD §3.3)"
              verdicts={rowsOf<Verdict>(hypothesesMetaqa)}
            />
            <Verdicts
              title="Run 1, published as it came out"
              verdicts={rowsOf<Verdict>(hypotheses)}
            />
          </div>
        </div>
        <div className="flex flex-col gap-10">
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4 sm:p-6">
            <Eyebrow>Run 1 failed and is still here</Eyebrow>
            <p className="mt-3 text-sm text-stone-300">
              The first run&apos;s headline hypothesis failed: the full Mend
              went from {percent(meanByRound(rows, "full")[0]?.accuracy)} to{" "}
              {percent(meanByRound(rows, "full").at(-1)?.accuracy)}, inside the
              spread between seeds. It is published as FAIL, not withdrawn or
              re-scored. The two runs use different generated data, so only
              comparisons inside a run are claims.
            </p>
            <div className="mt-4">
              <Curve rows={rows} arms={RUN1_ARMS} band="full" />
            </div>
            <p className="mt-3 text-xs text-stone-500">
              Why it failed:{" "}
              <a
                className="underline hover:text-ink"
                href={`${REPO_URL}/blob/master/docs/RUN1_DIAGNOSIS.md`}
              >
                docs/RUN1_DIAGNOSIS.md
              </a>
              . What changed in response, fixed before run 2:{" "}
              <a
                className="underline hover:text-ink"
                href={`${REPO_URL}/blob/master/docs/PRD.md`}
              >
                PRD §3.2
              </a>
              .
            </p>
          </div>
          <div id="walkthrough">
            <Eyebrow>Judge it yourself in 60 seconds</Eyebrow>
            <ol className="mt-4 flex flex-col gap-3 text-sm text-stone-300">
              <li>
                <span className="font-mono text-stone-500">1</span> Open{" "}
                <Link className="underline hover:text-ink" href="/ask">
                  Ask
                </Link>{" "}
                and run a listed question. You see the path the graph walked and
                what every hop cost.
              </li>
              <li>
                <span className="font-mono text-stone-500">2</span> Press{" "}
                <span className="font-mono">wrong</span>. The links on that path
                get more expensive and you are handed receipt ids.
              </li>
              <li>
                <span className="font-mono text-stone-500">3</span> Ask again.
                When the true link becomes the cheaper one, the answer changes.
              </li>
              <li>
                <span className="font-mono text-stone-500">4</span> Open{" "}
                <Link className="underline hover:text-ink" href="/truth">
                  Truth
                </Link>{" "}
                to see that planted fault move from still wrong to corrected,
                then roll it back.
              </li>
            </ol>
            <p className="mt-6 font-mono text-xs text-stone-500">
              graph_writable{" "}
              {readiness.ok
                ? String(readiness.value.graph_writable)
                : NOT_MEASURED}{" "}
              · GET /v1/ready
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
