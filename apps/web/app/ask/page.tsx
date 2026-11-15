import { Failed, Panel } from "@/components/Shell";
import { fetchExamples } from "@/lib/api";
import { AskForm } from "./AskForm";

export const dynamic = "force-dynamic";

export default async function AskPage() {
  const examples = await fetchExamples();
  const listed = examples.ok ? examples.value : [];

  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">Ask, then judge</h1>
      <p className="mt-2 text-stone-400">
        The answer is the cheapest path HydraDB can find from the entity named in the question to a node of the
        expected kind. Judging it moves the cost of the edges on that path and writes a receipt for each change.
      </p>

      <Panel title="Ask">
        <AskForm examples={listed} />
      </Panel>

      <Panel title="Questions this graph can answer">
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
          These are drawn from the training split, so nothing here reveals a held-out question. Judging on this page
          changes the live demo graph; it never touches a measured run.
        </p>
      </Panel>
    </main>
  );
}
