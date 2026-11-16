import Link from "next/link";
import type { ReplayExample, ReplayRound } from "@/lib/api";

const DASH = "—";

export function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-mono text-[11px] tracking-[0.18em] text-mend uppercase">
      {children}
    </p>
  );
}

export type Repair = {
  round: number;
  quarantine: ReplayExample;
  reweight: ReplayExample | null;
};

export function pickRepair(rounds: ReplayRound[] | null): Repair | null {
  const found: Repair[] = [];
  for (const round of rounds ?? []) {
    for (const quarantine of round.examples) {
      if (
        quarantine.kind !== "quarantine" ||
        quarantine.edge.truth !== "planted_wrong" ||
        quarantine.edge.true_dst_name === undefined
      ) {
        continue;
      }
      const reweight =
        round.examples.find(
          (e) =>
            e.kind === "reweight" &&
            e.edge.src === quarantine.edge.src &&
            e.edge.dst === quarantine.edge.dst &&
            e.edge.rel_type === quarantine.edge.rel_type,
        ) ?? null;
      found.push({ round: round.round, quarantine, reweight });
    }
  }
  return found.find((repair) => repair.reweight !== null) ?? found[0] ?? null;
}

function Hop({
  src,
  rel,
  dst,
  tone,
}: {
  src: string;
  rel: string;
  dst: string;
  tone: "bad" | "mend";
}) {
  return (
    <div className="font-mono text-sm">
      <p className="truncate text-ink">{src}</p>
      <p
        className={`my-1.5 text-[10px] tracking-wider ${tone === "bad" ? "text-bad" : "text-mend"}`}
      >
        ──{rel}──›
      </p>
      <p
        className={`truncate ${tone === "bad" ? "text-bad line-through decoration-bad/60" : "text-mend"}`}
      >
        {dst}
      </p>
    </div>
  );
}

export function RepairCard({
  repair,
  runId,
  seed,
  heldOut,
}: {
  repair: Repair | null;
  runId: string | null;
  seed: number;
  heldOut: number | null;
}) {
  if (repair === null) {
    return (
      <div className="rounded-2xl border border-white/10 bg-stone-950/80 p-6 font-mono text-sm text-stone-500">
        {DASH}
      </div>
    );
  }
  const edge = repair.quarantine.edge;
  const before = repair.reweight?.before.cost ?? repair.quarantine.before.cost;
  return (
    <div className="rounded-2xl border border-white/10 bg-stone-950/80 p-5 backdrop-blur-sm sm:p-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-bad/30 bg-bad/[0.04] p-4">
          <p className="font-mono text-[10px] tracking-wider text-bad uppercase">
            Walked · planted fault
          </p>
          <div className="mt-3">
            <Hop
              src={edge.src_name}
              rel={edge.rel_type}
              dst={edge.dst_name}
              tone="bad"
            />
          </div>
          <p className="mt-3 font-mono text-xs text-stone-400">
            cost {before.toFixed(2)}
            {repair.reweight && (
              <>
                <span className="text-stone-600"> › </span>
                {repair.reweight.after.cost.toFixed(2)}
              </>
            )}
            <span className="text-stone-600"> › </span>
            <span className="text-bad">cut</span>
          </p>
        </div>
        <div className="rounded-xl border border-mend/30 bg-mend/[0.04] p-4">
          <p className="font-mono text-[10px] tracking-wider text-mend uppercase">
            The truth · from the generator
          </p>
          <div className="mt-3">
            <Hop
              src={edge.src_name}
              rel={edge.rel_type}
              dst={edge.true_dst_name ?? DASH}
              tone="mend"
            />
          </div>
          <p className="mt-3 font-mono text-xs text-stone-400">
            the wrong link can no longer be searched
          </p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] tracking-wider text-stone-400 uppercase">
        <span className="rounded-full border border-bad/40 px-2 py-0.5 text-bad">
          Quarantined
        </span>
        <span>round {repair.round}</span>
        <span className="text-stone-600">·</span>
        <span className="normal-case">{repair.quarantine.receipt_id}</span>
      </div>
      <p className="mt-3 text-xs text-stone-500">
        A real receipt from run {runId ?? DASH}, company graph seed {seed}
        {heldOut !== null ? `, ${heldOut} held-out questions` : ""}. Nobody told
        it this link was wrong; its own training answers did.
      </p>
    </div>
  );
}

export function Fraction({
  value,
  of,
  tone,
  label,
  note,
}: {
  value: string;
  of: string;
  tone: "bad" | "mend" | "ink";
  label: string;
  note: string;
}) {
  const colour =
    tone === "bad" ? "text-bad" : tone === "mend" ? "text-mend" : "text-ink";
  return (
    <div className="rounded-2xl border border-white/10 bg-stone-950/70 p-6 backdrop-blur-sm">
      <p className={`font-mono text-5xl tabular-nums sm:text-6xl ${colour}`}>
        {value}
        <span className="text-2xl text-stone-600 sm:text-3xl">/{of}</span>
      </p>
      <p className="mt-5 font-mono text-[11px] tracking-wider text-stone-300 uppercase">
        {label}
      </p>
      <p className="mt-2 text-sm text-stone-400">{note}</p>
    </div>
  );
}

const STEPS: { title: string; body: string }[] = [
  {
    title: "Ask",
    body: "A question becomes a weighted shortest-path search inside HydraDB (algo.SSpaths on the cost property). The cheapest path is the answer, with every hop and its cost shown.",
  },
  {
    title: "Judge",
    body: "Only training questions are judged right or wrong. Held-out questions never reach the Mend, so the score below is earned on questions it never saw.",
  },
  {
    title: "Mend",
    body: "Links on right paths get cheaper, links on wrong paths dearer. A link that keeps misleading is moved to a Q_ type search cannot walk; confirmed paths become shortcuts; unreachable questions read withheld documents.",
  },
  {
    title: "Receipt",
    body: "Every change is written as a receipt before it touches the graph, with the cost before and after and the questions that caused it. Any one of them rolls back.",
  },
];

export function Steps() {
  return (
    <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {STEPS.map((step, index) => (
        <li
          key={step.title}
          className="rounded-2xl border border-white/10 bg-stone-950/70 p-6 backdrop-blur-sm"
        >
          <p className="font-mono text-[11px] tracking-wider text-stone-500 uppercase">
            Step {index + 1}
          </p>
          <h3 className="mt-3 text-xl text-ink">{step.title}</h3>
          <p className="mt-3 text-sm leading-relaxed text-stone-400">
            {step.body}
          </p>
        </li>
      ))}
    </ol>
  );
}

export function Figure({
  value,
  label,
  note,
}: {
  value: string;
  label: string;
  note: string;
}) {
  return (
    <div className="border-t border-white/10 pt-5">
      <p className="font-mono text-4xl text-ink tabular-nums sm:text-5xl">
        {value}
      </p>
      <p className="mt-3 font-mono text-[11px] tracking-wider text-stone-300 uppercase">
        {label}
      </p>
      <p className="mt-2 text-sm text-stone-400">{note}</p>
    </div>
  );
}

export function AskCta() {
  return (
    <div className="rounded-2xl border border-white/10 bg-stone-950/70 p-6 backdrop-blur-sm sm:p-10">
      <h2 className="max-w-2xl text-3xl leading-tight text-ink sm:text-5xl">
        Ask it something, then tell it it was wrong.
      </h2>
      <p className="mt-4 max-w-2xl text-stone-400">
        Every answer comes back with the path it walked, what each hop cost, and
        — once you judge it — the receipts for every link that moved. Never
        prose alone.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          href="/ask"
          className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-night hover:opacity-85"
        >
          Ask TrailMend →
        </Link>
        <Link
          href="/truth"
          className="rounded-full border border-white/15 px-5 py-3 text-sm text-ink hover:bg-white/5"
        >
          See every planted fault
        </Link>
      </div>
    </div>
  );
}
