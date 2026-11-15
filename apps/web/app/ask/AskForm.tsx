"use client";

import { useActionState } from "react";
import { runAsk, type AskState } from "./actions";

const EMPTY: AskState = { question: "" };

export function AskForm({ examples }: { examples: { question: string; template: string; hops: number }[] }) {
  const [state, action, pending] = useActionState(runAsk, EMPTY);

  return (
    <div className="flex flex-col gap-4">
      <form action={action} className="flex flex-col gap-3">
        <label className="text-sm text-stone-400" htmlFor="question">
          Question
        </label>
        <input
          id="question"
          name="question"
          defaultValue={state.question}
          placeholder={examples[0]?.question ?? "Who do I page for …?"}
          className="w-full rounded border border-stone-700 bg-stone-950 px-3 py-2 font-mono text-sm text-stone-100"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={pending}
            className="rounded bg-stone-100 px-3 py-1.5 text-sm font-medium text-stone-900 disabled:opacity-50"
          >
            {pending ? "asking…" : "Ask"}
          </button>
          <button
            type="submit"
            name="verdict"
            value="correct"
            disabled={pending || !state.answer}
            className="rounded border border-emerald-700 px-3 py-1.5 text-sm text-emerald-300 disabled:opacity-40"
          >
            correct
          </button>
          <button
            type="submit"
            name="verdict"
            value="wrong"
            disabled={pending || !state.answer}
            className="rounded border border-rose-800 px-3 py-1.5 text-sm text-rose-300 disabled:opacity-40"
          >
            wrong
          </button>
        </div>
      </form>

      {state.error && (
        <p className="rounded border border-amber-900/60 bg-amber-950/40 p-3 text-sm text-amber-200">
          <span className="font-mono">{state.error.code}</span> — {state.error.message}
        </p>
      )}

      {state.judgement && (
        <div className="rounded border border-stone-800 bg-stone-900/40 p-3 text-sm">
          <p className="text-stone-300">
            Judged <span className="font-mono">{state.judgement.verdict}</span>. Changed anything:{" "}
            <span className="font-mono">{String(state.judgement.changed_anything)}</span>.
          </p>
          <p className="mt-2 font-mono text-xs break-all text-stone-400">
            {state.judgement.receipts.length > 0
              ? state.judgement.receipts.join(" ")
              : "no receipts: nothing needed changing"}
          </p>
        </div>
      )}

      {state.answer && (
        <div className="rounded border border-stone-800 bg-stone-900/40 p-3">
          <p className="text-sm text-stone-300">
            <span className="text-stone-500">answer </span>
            <span className="font-mono text-stone-100">{state.answer.answer_names.join(", ")}</span>
            <span className="text-stone-500"> at cost {state.answer.cost.toFixed(3)}, seeded on </span>
            <span className="font-mono">{state.answer.seed_entity_name}</span>
            <span className="text-stone-500"> ({state.answer.matched_how})</span>
          </p>
          <div className="mt-3 flex flex-col gap-3">
            {state.answer.paths.map((path, index) => (
              <ol key={index} className="flex flex-col gap-1 font-mono text-xs text-stone-200">
                {path.map((hop, hopIndex) => (
                  <li key={`${hop.src}-${hop.rel_type}-${hop.dst}-${hopIndex}`} className="break-all">
                    <span>{hop.src_name}</span>
                    <span className="text-stone-500"> —{hop.rel_type}→ </span>
                    <span>{hop.dst_name}</span>
                    <span className="text-stone-500"> cost {hop.cost.toFixed(3)}</span>
                  </li>
                ))}
              </ol>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
