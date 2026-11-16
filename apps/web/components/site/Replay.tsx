"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { ReplayExample, ReplayRound } from "@/lib/api";

const DASH = "—";
const STEP_MS = 1800;
const COUNT_MS = 750;

function subscribeMotion(change: () => void): () => void {
  const query = window.matchMedia("(prefers-reduced-motion: reduce)");
  query.addEventListener("change", change);
  return () => query.removeEventListener("change", change);
}

function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeMotion,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}

function signed(value: number, sign: string): string {
  return value === 0 ? "0" : `${sign}${value}`;
}

function pct(correct: number, n: number): string {
  return n > 0 ? ((correct / n) * 100).toFixed(1) : DASH;
}

function useCounted(target: number | null, animate: boolean): number | null {
  const [shown, setShown] = useState<number | null>(target);
  const from = useRef<number | null>(target);
  useEffect(() => {
    const start = from.current;
    if (target === null || !animate || start === null) {
      from.current = target;
      return;
    }
    const began = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - began) / COUNT_MS);
      const eased = 1 - (1 - t) ** 3;
      setShown(start + (target - start) * eased);
      if (t < 1) {
        frame = requestAnimationFrame(tick);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      from.current = target;
    };
  }, [target, animate]);
  return animate ? (shown ?? target) : target;
}

function mended(example: ReplayExample): boolean | null {
  const rose = example.after.cost > example.before.cost;
  const fell = example.after.cost < example.before.cost;
  if (example.edge.truth === "planted_wrong") {
    return example.kind === "quarantine" || rose;
  }
  if (example.edge.truth === "true") {
    return example.kind === "gapfill" || fell;
  }
  return null;
}

const KIND_LABEL: Record<string, string> = {
  reweight: "reweight",
  quarantine: "quarantine",
  gapfill: "gap-fill",
  promote: "shortcut",
};

const TRUTH_LABEL: Record<string, string> = {
  planted_wrong: "planted fault",
  true: "true link",
  shortcut: "learned shortcut",
  not_in_truth: "not in the truth",
};

function cost(value: number, status: string): string {
  if (status === "absent") {
    return "absent";
  }
  if (status === "quarantined") {
    return "cut";
  }
  return value.toFixed(2);
}

function Card({ example, index }: { example: ReplayExample; index: number }) {
  const verdict = mended(example);
  const link =
    verdict === true
      ? "replay-link replay-link-mend"
      : verdict === false
        ? "replay-link bg-bad"
        : "replay-link bg-stone-500";
  return (
    <li
      className="replay-card rounded-xl border border-white/10 bg-stone-950/80 p-4"
      style={{ animationDelay: `${index * 110}ms` }}
    >
      <div className="flex items-center justify-between gap-3 font-mono text-[10px] tracking-wider uppercase">
        <span
          className={
            example.kind === "quarantine" ? "text-bad" : "text-stone-400"
          }
        >
          {KIND_LABEL[example.kind] ?? example.kind}
        </span>
        <span className="text-stone-500">
          {TRUTH_LABEL[example.edge.truth] ?? example.edge.truth}
        </span>
      </div>
      <p
        className="mt-3 truncate text-sm text-ink"
        title={example.edge.src_name}
      >
        {example.edge.src_name}
      </p>
      <div className="my-2 flex items-center gap-2">
        <span
          className={`${link} h-0.5 flex-1 rounded-full`}
          style={{ animationDelay: `${index * 110 + 350}ms` }}
        />
        <span className="font-mono text-[10px] text-stone-500">
          {example.edge.rel_type}
        </span>
      </div>
      <p className="truncate text-sm text-ink" title={example.edge.dst_name}>
        {example.edge.dst_name}
      </p>
      <p className="mt-3 font-mono text-xs text-stone-400">
        cost {cost(example.before.cost, example.before.status)}
        <span className="text-stone-600"> › </span>
        <span className={verdict === true ? "text-mend" : "text-ink"}>
          {cost(example.after.cost, example.after.status)}
        </span>
      </p>
      <p className="mt-1 truncate font-mono text-[10px] text-stone-600">
        {example.receipt_id}
      </p>
    </li>
  );
}

function Spark({ rounds, at }: { rounds: ReplayRound[]; at: number }) {
  const w = 320;
  const h = 96;
  const values = rounds.flatMap((r) => [
    r.full_v2.correct / r.full_v2.n,
    r.frozen.correct / r.frozen.n,
  ]);
  const lo = Math.min(...values) - 0.02;
  const hi = Math.max(...values) + 0.02;
  const x = (i: number) =>
    rounds.length > 1 ? (i / (rounds.length - 1)) * w : 0;
  const y = (v: number) => h - ((v - lo) / (hi - lo)) * h;
  const line = (pick: (r: ReplayRound) => number, upto: number) =>
    rounds
      .slice(0, upto + 1)
      .map(
        (r, i) =>
          `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(pick(r)).toFixed(1)}`,
      )
      .join(" ");
  const mend = (r: ReplayRound) => r.full_v2.correct / r.full_v2.n;
  const frozen = (r: ReplayRound) => r.frozen.correct / r.frozen.n;
  const current = rounds[at];
  return (
    <svg
      viewBox={`-6 -6 ${w + 12} ${h + 12}`}
      className="h-24 w-full"
      role="img"
      aria-label="Held-out accuracy by round: the mended graph against the frozen one"
    >
      <path
        d={line(frozen, rounds.length - 1)}
        fill="none"
        stroke="#ff5a47"
        strokeWidth="1.5"
        strokeDasharray="4 4"
        opacity="0.8"
      />
      <path d={line(mend, at)} fill="none" stroke="#6ee7b7" strokeWidth="2" />
      {current && (
        <circle cx={x(at)} cy={y(mend(current))} r="4" fill="#6ee7b7" />
      )}
    </svg>
  );
}

function Counter({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-t border-white/10 pt-2">
      <dt className="font-mono text-[10px] tracking-wider text-stone-500 uppercase">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-lg text-ink">{value}</dd>
    </div>
  );
}

export function Replay({
  rounds,
  runId,
  seed,
}: {
  rounds: ReplayRound[] | null;
  runId: string | null;
  seed: number;
}) {
  const last = rounds && rounds.length ? rounds.length - 1 : 0;
  const still = useReducedMotion();
  const [chosen, setChosen] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const at = chosen ?? (still ? last : 0);
  const motion = !still;

  useEffect(() => {
    if (!playing) {
      return;
    }
    const timer = window.setTimeout(() => {
      const next = Math.min(last, at + 1);
      setChosen(next);
      if (next >= last) {
        setPlaying(false);
      }
    }, STEP_MS);
    return () => window.clearTimeout(timer);
  }, [playing, at, last]);

  const round = rounds?.[at] ?? null;
  const counted = useCounted(
    round ? (round.full_v2.correct / round.full_v2.n) * 100 : null,
    motion,
  );

  function toggle(): void {
    if (playing) {
      setPlaying(false);
      return;
    }
    if (at >= last) {
      setChosen(0);
    }
    setPlaying(true);
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-stone-950/70 p-5 backdrop-blur-sm sm:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-[11px] tracking-wider text-mend uppercase">
            Watch it learn
          </p>
          <h2 className="mt-2 text-2xl text-ink sm:text-3xl">
            Replayed round by round from the receipts.
          </h2>
          <p className="mt-2 text-sm text-stone-400">
            Run 2, company graph seed {seed},{" "}
            {rounds ? (rounds[0]?.full_v2.n ?? DASH) : DASH} held-out questions.
            Nothing here is computed live: it is read from the recorded tapes
            {runId ? ` of run ${runId}` : ""}.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggle}
            disabled={!rounds}
            className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-night transition-opacity hover:opacity-85 disabled:opacity-40"
          >
            {playing ? "Pause" : at >= last && at > 0 ? "Replay" : "Play"}
          </button>
        </div>
      </div>

      <div className="mt-6 flex items-center gap-4">
        <label
          htmlFor="replay-round"
          className="font-mono text-xs text-stone-500"
        >
          round {rounds ? at : DASH}
        </label>
        <input
          id="replay-round"
          type="range"
          min={0}
          max={last}
          step={1}
          value={at}
          disabled={!rounds}
          onChange={(event) => {
            setPlaying(false);
            setChosen(Number(event.target.value));
          }}
          className="flex-1 accent-[#6ee7b7]"
        />
        <span className="font-mono text-xs text-stone-500">
          {rounds ? last : DASH}
        </span>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_1.6fr]">
        <div>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="font-mono text-[11px] tracking-wider text-stone-500 uppercase">
                Mended graph
              </p>
              <p className="mt-3 font-mono text-5xl text-mend tabular-nums sm:text-6xl">
                {counted === null ? DASH : counted.toFixed(1)}
                <span className="text-2xl text-stone-600">%</span>
              </p>
              <p className="mt-2 font-mono text-xs text-stone-400">
                {round ? `${round.full_v2.correct}/${round.full_v2.n}` : DASH}
              </p>
            </div>
            <div>
              <p className="font-mono text-[11px] tracking-wider text-stone-500 uppercase">
                Frozen graph
              </p>
              <p className="mt-3 font-mono text-5xl text-bad tabular-nums sm:text-6xl">
                {round ? pct(round.frozen.correct, round.frozen.n) : DASH}
                <span className="text-2xl text-stone-600">%</span>
              </p>
              <p className="mt-2 font-mono text-xs text-stone-400">
                {round ? `${round.frozen.correct}/${round.frozen.n}` : DASH}
              </p>
            </div>
          </div>
          <div className="mt-6">
            {rounds ? (
              <Spark rounds={rounds} at={at} />
            ) : (
              <p className="font-mono text-xs text-stone-500">{DASH}</p>
            )}
          </div>
          <dl className="mt-6 grid grid-cols-3 gap-x-4 gap-y-3">
            <Counter
              label="reweights"
              value={round ? round.reweights.toLocaleString("en-US") : DASH}
            />
            <Counter
              label="quarantines"
              value={round ? String(round.quarantines) : DASH}
            />
            <Counter
              label="gap-fills"
              value={round ? String(round.gapfills) : DASH}
            />
            <Counter
              label="shortcuts"
              value={round ? String(round.promotions) : DASH}
            />
            <Counter
              label="questions fixed"
              value={round ? signed(round.full_v2.fixed, "+") : DASH}
            />
            <Counter
              label="questions broken"
              value={round ? signed(round.full_v2.broke, "−") : DASH}
            />
          </dl>
        </div>
        <div>
          <p className="font-mono text-[11px] tracking-wider text-stone-500 uppercase">
            {round && round.examples.length
              ? `Receipts written in round ${at}, up to six`
              : round
                ? "Round 0 is the graph as ingested: no receipts yet"
                : DASH}
          </p>
          <ul
            key={at}
            className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
          >
            {round?.examples.map((example, index) => (
              <Card key={example.receipt_id} example={example} index={index} />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
