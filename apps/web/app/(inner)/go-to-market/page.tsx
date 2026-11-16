import Link from "next/link";
import { Panel } from "@/components/Shell";

export const metadata = { title: "TrailMend — go to market" };

const BUYERS: { who: string; why: string }[] = [
  {
    who: "Platform and SRE leads",
    why: "They own the on-call rota and the service catalogue, and they are the ones paged when an alert goes to a team that no longer owns the service.",
  },
  {
    who: "On-call engineers and incident commanders",
    why: "They ask “who owns this, who do I page” at 3 a.m. and pay for every wrong answer in minutes of a live incident.",
  },
  {
    who: "IT and service-desk owners",
    why: "Routing a ticket is the same question on a different graph: which team, which queue, which person, today.",
  },
  {
    who: "Security and compliance teams",
    why: "“Who owns this asset” has to be right during an audit or a breach, and every change to the answer has to be explainable afterwards.",
  },
];

const REASONS: { title: string; body: string }[] = [
  {
    title: "Fewer pages to the wrong human",
    body: "A misrouted page is the most expensive kind of wrong answer: the incident clock keeps running while someone finds the right owner. TrailMend fixes the link that sent it there.",
  },
  {
    title: "The catalogue maintains itself from use",
    body: "No quarterly audit, no one remembering to edit the wiki. Every judged answer reprices the links it walked, so the map gets more correct the more it is used.",
  },
  {
    title: "Every change is auditable and reversible",
    body: "Each repair is a receipt written before it touches the graph: what changed, by how much, and which answers caused it. Any one of them rolls back.",
  },
  {
    title: "No model guessing at the answer",
    body: "Answers are path searches inside HydraDB, and no LLM writes to the graph or scores an answer. Owners can trust it in the places where a hallucination is unacceptable.",
  },
];

export default function GoToMarketPage() {
  return (
    <main>
      <p className="font-mono text-[11px] tracking-[0.18em] text-mend uppercase">
        Go to market
      </p>
      <h1 className="mt-3 text-3xl tracking-tight text-ink sm:text-4xl">
        Who wants this, and why they would pay for it.
      </h1>
      <p className="mt-3 max-w-2xl text-stone-300">
        Your service catalogue is quietly wrong. TrailMend finds out from its
        own answers and fixes it, with a receipt for every change.
      </p>

      <Panel title="The problem">
        <p className="text-sm text-stone-300">
          Every company past a few dozen services keeps a map of who owns what:
          a service catalogue, an on-call rota, a Backstage entry or a wiki. It
          is wrong in ways nobody notices until an incident. A service points at
          a team that no longer owns it, a rota entry is stale, two entries
          describe the same person. The page goes to the wrong human and the
          incident runs long. The map is edited by hand, so it decays between
          audits, and nothing uses the one signal that is always available:
          whether the answer it just gave was right.
        </p>
      </Panel>

      <Panel title="Who wants it">
        <ul className="flex flex-col">
          {BUYERS.map((buyer) => (
            <li
              key={buyer.who}
              className="grid gap-1 border-t border-white/10 py-3 first:border-t-0 first:pt-0 sm:grid-cols-[14rem_1fr] sm:gap-6"
            >
              <span className="text-sm text-ink">{buyer.who}</span>
              <span className="text-sm text-stone-400">{buyer.why}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-stone-300">
          The first buyer is the platform or SRE lead: one person owns the
          problem, feels it every week, and can say yes.
        </p>
      </Panel>

      <Panel title="Why they would pay for it">
        <div className="grid gap-4 sm:grid-cols-2">
          {REASONS.map((reason) => (
            <div
              key={reason.title}
              className="rounded-xl border border-white/10 p-4"
            >
              <h3 className="text-sm text-ink">{reason.title}</h3>
              <p className="mt-2 text-sm text-stone-400">{reason.body}</p>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="The pitch">
        <ol className="flex flex-col gap-3 text-sm text-stone-300">
          <li>
            <span className="font-mono text-stone-500">1</span> Connect the
            catalogue, the rota and the incident write-ups you already have.
            TrailMend loads them into a HydraDB graph.
          </li>
          <li>
            <span className="font-mono text-stone-500">2</span> It answers
            &ldquo;who owns this / who do I page&rdquo; with the path it walked,
            so every answer can be checked.
          </li>
          <li>
            <span className="font-mono text-stone-500">3</span> Judgements come
            from work that already happens: who actually resolved the incident,
            who reassigned the ticket. Each one repairs the graph and leaves a
            receipt.
          </li>
          <li>
            <span className="font-mono text-stone-500">4</span> Success is one
            number agreed up front: the share of ownership questions answered
            correctly on a held-out set the team writes, before and after. That
            is the same test every result on this site is measured with.
          </li>
        </ol>
      </Panel>

      <Panel title="Why HydraDB">
        <p className="text-sm text-stone-300">
          The repair only works because the answer is a weighted path search
          inside the graph database itself. HydraDB runs that search on the cost
          of each link, so changing a cost changes the answer, and moving a link
          to a quarantine type takes it out of every future search.
        </p>
      </Panel>

      <Panel title="What it is not">
        <p className="text-sm text-stone-300">
          It is not an incident-response tool and it does not replace the
          catalogue as the place humans edit. It sits beside it and keeps it
          honest. The numbers on this site come from generated company graphs
          and the public MetaQA dataset, labelled as such; no customer data has
          been measured.{" "}
          <Link href="/evidence" className="underline hover:text-ink">
            Every result and its source file
          </Link>
          .
        </p>
      </Panel>
    </main>
  );
}
