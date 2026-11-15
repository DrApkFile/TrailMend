import { Curve } from "@/components/Curve";
import { Failed, Panel } from "@/components/Shell";
import {
  fetchCurve,
  fetchCurveV2,
  fetchEvidence,
  fetchReadiness,
} from "@/lib/api";
import type { CurveRow } from "@/lib/api";
import {
  NOT_MEASURED,
  delta,
  meanByRound,
  percent,
  seedsOf,
} from "@/lib/curve";

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

type Verdict = { id: string; claim: string; verdict: string };

function verdictsOf(
  file: Awaited<ReturnType<typeof fetchEvidence>>,
): Verdict[] {
  return file.ok && file.value.available && file.value.payload
    ? (file.value.payload.rows as Verdict[])
    : [];
}

function Summary({ rows, arm }: { rows: CurveRow[]; arm: string }) {
  const points = meanByRound(rows, arm);
  const moved = delta(rows, arm);
  return (
    <dl className="mt-4">
      <Row
        label="seeds in the run"
        value={rows.length ? seedsOf(rows).join(", ") : NOT_MEASURED}
      />
      <Row
        label={`${arm}, round 0`}
        value={points.length ? percent(points[0]?.accuracy) : NOT_MEASURED}
      />
      <Row
        label={`${arm}, last round`}
        value={points.length ? percent(points.at(-1)?.accuracy) : NOT_MEASURED}
      />
      <Row
        label="change over the run"
        value={
          typeof moved === "number"
            ? `${moved >= 0 ? "+" : ""}${(moved * 100).toFixed(1)} points`
            : NOT_MEASURED
        }
      />
      <Row label="run id" value={rows.at(0)?.run_id ?? NOT_MEASURED} />
      <Row label="data version" value={rows.at(0)?.data_version ?? "v1"} />
    </dl>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 border-b border-stone-800 py-2 sm:flex-row sm:items-baseline sm:justify-between">
      <dt className="text-sm text-stone-400">{label}</dt>
      <dd className="font-mono text-sm break-all text-stone-100">{value}</dd>
    </div>
  );
}

export default async function Home() {
  const [readiness, curve, curveV2, hypotheses, hypothesesV2, captured] =
    await Promise.all([
      fetchReadiness(),
      fetchCurve(),
      fetchCurveV2(),
      fetchEvidence("hypotheses"),
      fetchEvidence("hypotheses_v2"),
      fetchEvidence("captured_share_v2"),
    ]);
  const rows = curve.ok && curve.value.available ? curve.value.rows : [];
  const rowsV2 =
    curveV2.ok && curveV2.value.available ? curveV2.value.rows : [];
  const verdicts = verdictsOf(hypotheses);
  const verdictsV2 = verdictsOf(hypothesesV2);
  const shares =
    captured.ok && captured.value.available && captured.value.payload
      ? (captured.value.payload.rows as {
          seed: number;
          captured_share: number;
          reachable_points: number;
        }[])
      : [];
  const current = rowsV2.length > 0;

  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">
        A graph that answers &ldquo;who do I page?&rdquo; and repairs the links
        that got it wrong
      </h1>
      <p className="mt-3 text-stone-400">
        Every answer is a weighted path search inside HydraDB. Every judgement
        moves the cost of the edges on that path, quarantines links that keep
        being blamed, compresses paths that keep being confirmed, and fetches
        documents for questions nothing could reach. Every change writes a
        receipt first and can be rolled back.
      </p>
      <p className="mt-3 text-sm text-stone-500">
        Every number here comes from a run on record. A dash means it has not
        been measured. The evaluation data is generated and labelled as
        generated wherever it appears.
      </p>

      <Panel
        title={
          current
            ? "Held-out accuracy by round, run 2"
            : "Held-out accuracy by round"
        }
      >
        {curveV2.ok || curve.ok ? (
          <Curve
            rows={current ? rowsV2 : rows}
            arms={current ? RUN2_ARMS : RUN1_ARMS}
            band={current ? "full_v2" : "full"}
          />
        ) : (
          <Failed
            code={curveV2.ok ? "no_curve" : curveV2.error.code}
            message="No curve has been recorded."
          />
        )}
        {current ? (
          <Summary rows={rowsV2} arm="full_v2" />
        ) : (
          <Summary rows={rows} arm="full" />
        )}
        {current && shares.length > 0 && (
          <p className="mt-3 text-xs text-stone-400">
            Of the damage this arm&apos;s mechanisms could repair at all,
            measured by an oracle on the same data, it captured{" "}
            <span className="font-mono">
              {shares
                .map((one) => `${(one.captured_share * 100).toFixed(0)}%`)
                .join(", ")}
            </span>{" "}
            per seed, out of{" "}
            <span className="font-mono">
              {shares.map((one) => one.reachable_points.toFixed(1)).join(", ")}
            </span>{" "}
            reachable points. Run 1 captured 4% and nothing on this page said
            so.
          </p>
        )}
      </Panel>

      {current && (
        <Panel title="Run 1, which failed, is still here">
          <p className="text-sm text-stone-300">
            The first run&apos;s headline hypothesis failed: the full Mend ended
            round 5 at 84.2% against 83.9% at round 0, inside the spread between
            seeds. It is published as FAIL, not withdrawn or re-scored, and it
            is drawn here beside run 2. The two runs use different generated
            data — run 1&apos;s faults mostly had no recoverable truth in the
            corpus and every edge cost the same at round 0 — so only comparisons
            inside a run are claims.
          </p>
          <div className="mt-4">
            <Curve rows={rows} arms={RUN1_ARMS} band="full" />
          </div>
          <Summary rows={rows} arm="full" />
          <p className="mt-3 text-xs text-stone-400">
            Why it failed, measured on the train split only and before anything
            was changed:{" "}
            <a
              className="underline"
              href="https://github.com/DrApkFile/TrailMend/blob/main/docs/RUN1_DIAGNOSIS.md"
            >
              docs/RUN1_DIAGNOSIS.md
            </a>
            . What run 2 changed in response, fixed before it ran:{" "}
            <a
              className="underline"
              href="https://github.com/DrApkFile/TrailMend/blob/main/docs/PRD.md"
            >
              PRD §3.2
            </a>
            .
          </p>
        </Panel>
      )}

      <Panel title="Judge it yourself in 60 seconds">
        <ol className="flex flex-col gap-3 text-sm text-stone-300">
          <li>
            <span className="text-stone-500">1.</span> Open{" "}
            <a className="underline" href="/ask">
              Ask
            </a>{" "}
            and run one of the listed questions. You see the path the graph
            walked and the cost of every hop.
          </li>
          <li>
            <span className="text-stone-500">2.</span> Press{" "}
            <span className="font-mono">wrong</span>. The answer is blamed, the
            edges on that path get more expensive, and you are handed receipt
            ids.
          </li>
          <li>
            <span className="text-stone-500">3.</span> Ask again. If another
            route is now cheaper, the answer changes. Nothing else about the
            graph moved.
          </li>
          <li>
            <span className="text-stone-500">4.</span> Open{" "}
            <a className="underline" href="/mend">
              the bad link
            </a>{" "}
            to watch blame build up on one planted wrong edge until it is
            quarantined, then roll it back.
          </li>
          <li>
            <span className="text-stone-500">5.</span> Every figure on{" "}
            <a className="underline" href="/evidence">
              Evidence
            </a>{" "}
            links to the file that produced it and its sha256.
          </li>
        </ol>
      </Panel>

      <Panel title="Preregistered hypotheses">
        {verdictsV2.length === 0 && verdicts.length === 0 ? (
          <p className="text-sm text-stone-400">
            Not decided yet. The hypotheses are fixed in the PRD before a run
            and published here with their verdicts, including the ones that
            fail.
          </p>
        ) : (
          <>
            {verdictsV2.length > 0 && (
              <>
                <p className="text-xs tracking-wide text-stone-500 uppercase">
                  Run 2, preregistered in PRD §3.2
                </p>
                <dl className="mb-4">
                  {verdictsV2.map((one) => (
                    <Row
                      key={one.id}
                      label={`${one.id} ${one.claim}`}
                      value={one.verdict}
                    />
                  ))}
                </dl>
              </>
            )}
            {verdicts.length > 0 && (
              <>
                <p className="text-xs tracking-wide text-stone-500 uppercase">
                  Run 1, decided and published as it came out
                </p>
                <dl>
                  {verdicts.map((one) => (
                    <Row
                      key={one.id}
                      label={`${one.id} ${one.claim}`}
                      value={one.verdict}
                    />
                  ))}
                </dl>
              </>
            )}
          </>
        )}
      </Panel>

      <Panel title="Graph readiness">
        <dl>
          <Row
            label="graph_writable"
            value={
              readiness.ok
                ? String(readiness.value.graph_writable)
                : NOT_MEASURED
            }
          />
          <Row label="source" value="GET /v1/ready, server-side" />
        </dl>
        {!readiness.ok && (
          <Failed
            code={readiness.error.code}
            message={readiness.error.message}
          />
        )}
      </Panel>
    </main>
  );
}
