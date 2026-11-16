import { Failed, Panel } from "@/components/Shell";
import { fetchExamples } from "@/lib/api";
import { AskForm } from "./AskForm";

export const dynamic = "force-dynamic";

export default async function AskPage() {
  const examples = await fetchExamples();
  const listed = examples.ok ? examples.value : [];

  return (
    <main>
      <p className="font-mono text-xs tracking-wider text-mend uppercase">
        Try it
      </p>
      <h1 className="mt-3 text-4xl tracking-tight text-ink sm:text-5xl">
        Ask the graph. Tell it when it&apos;s wrong.
      </h1>
      <p className="mt-4 text-stone-400">
        The answer is the cheapest path HydraDB can find from the entity named
        in the question to a node of the expected kind. Judging it moves the
        cost of the edges on that path and writes a receipt for each change.
      </p>

      <div className="mt-8 border-t border-white/10 pt-8">
        <section className="rounded-2xl border border-white/10 bg-stone-950/70 p-5 backdrop-blur-sm sm:p-6">
          <AskForm examples={listed} />
        </section>
      </div>

      <Panel title="About these questions">
        {examples.ok ? (
          <ul className="flex flex-col gap-2 text-sm">
            {listed.map((one) => (
              <li key={one.question} className="break-all">
                <span className="font-mono text-stone-200">{one.question}</span>
                <span className="text-stone-500">
                  {" "}
                  — {one.template}, {one.hops} hop{one.hops === 1 ? "" : "s"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Failed code={examples.error.code} message={examples.error.message} />
        )}
        <p className="mt-4 text-xs text-stone-500">
          These are drawn from the training split, so nothing here reveals a
          held-out question.
        </p>
        <p className="mt-2 text-xs text-stone-500">
          Anyone can judge here, and judging writes to{" "}
          <span className="text-stone-300">one shared live demo graph</span>{" "}
          that this site keeps for exactly that. It never touches the evaluation
          evidence: every number on the curve and on the evidence page comes
          from recorded runs against a separate graph, written before this page
          was served, each file carrying its own sha256. An admin can reset the
          demo graph to its loaded state, and the reset writes a receipt of its
          own.
        </p>
      </Panel>
    </main>
  );
}
