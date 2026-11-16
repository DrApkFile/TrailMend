"use client";

import { useActionState, useState } from "react";
import { runAsk, type AskState } from "./actions";

const EMPTY: AskState = { question: "" };

export function AskForm({
  examples,
}: {
  examples: { question: string; template: string; hops: number }[];
}) {
  const [state, action, pending] = useActionState(runAsk, EMPTY);
  const [draft, setDraft] = useState(state.question);
  const step = "font-mono text-[11px] tracking-wider text-stone-500 uppercase";

  return (
    <div className="flex flex-col gap-4">
      <form action={action} className="flex flex-col gap-4">
        <p className={step}>1. Pick a question</p>
        <div className="flex flex-wrap gap-2">
          {examples.map((one) => (
            <button
              key={one.question}
              type="button"
              onClick={() => setDraft(one.question)}
              className={`rounded-full border px-3 py-1.5 text-left text-xs transition-colors ${
                draft === one.question
                  ? "border-mend/60 bg-mend/10 text-mend"
                  : "border-white/10 text-stone-400 hover:border-white/25 hover:text-ink"
              }`}
            >
              {one.question}
            </button>
          ))}
        </div>
        <label className={`${step} mt-2`} htmlFor="question">
          2. Ask it, or type your own
        </label>
        <input
          id="question"
          name="question"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={examples[0]?.question ?? "Who do I page for …?"}
          className="w-full rounded-xl border border-white/10 bg-night px-4 py-3 font-mono text-sm text-ink"
        />
        <p className={`${step} mt-2`}>
          3. Judge the answer — wrong makes the links it walked more expensive
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="submit"
            disabled={pending}
            className="rounded-full bg-ink px-5 py-2 text-sm font-medium text-night disabled:opacity-50"
          >
            {pending ? "asking…" : "Ask"}
          </button>
          <button
            type="submit"
            name="verdict"
            value="correct"
            disabled={pending || !state.answer}
            className="rounded-full border border-emerald-700 px-4 py-2 text-sm text-emerald-300 disabled:opacity-40"
          >
            correct
          </button>
          <button
            type="submit"
            name="verdict"
            value="wrong"
            disabled={pending || !state.answer}
            className="rounded-full border border-rose-800 px-4 py-2 text-sm text-rose-300 disabled:opacity-40"
          >
            wrong
          </button>
        </div>
      </form>

      {state.error && (
        <p className="rounded border border-amber-900/60 bg-amber-950/40 p-3 text-sm text-amber-200">
          <span className="font-mono">{state.error.code}</span> —{" "}
          {state.error.message}
        </p>
      )}

      {state.judgement && (
        <div className="rounded-xl border border-white/10 bg-night/60 p-4 text-sm">
          <p className="text-stone-300">
            Judged <span className="font-mono">{state.judgement.verdict}</span>.
            Changed anything:{" "}
            <span className="font-mono">
              {String(state.judgement.changed_anything)}
            </span>
            .
          </p>
          <p className="mt-2 font-mono text-xs break-all text-stone-400">
            {state.judgement.receipts.length > 0
              ? state.judgement.receipts.join(" ")
              : "no receipts: nothing needed changing"}
          </p>
        </div>
      )}

      {state.answer && (
        <div className="rounded-xl border border-white/10 bg-night/60 p-4">
          <p className="text-sm text-stone-300">
            <span className="text-stone-500">answer </span>
            <span className="font-mono text-stone-100">
              {state.answer.answer_names.join(", ")}
            </span>
            <span className="text-stone-500">
              {" "}
              at cost {state.answer.cost.toFixed(3)}, seeded on{" "}
            </span>
            <span className="font-mono">{state.answer.seed_entity_name}</span>
            <span className="text-stone-500">
              {" "}
              ({state.answer.matched_how})
            </span>
          </p>
          <div className="mt-3 flex flex-col gap-3">
            {state.answer.paths.map((path, index) => (
              <ol
                key={index}
                className="flex flex-col gap-1 font-mono text-xs text-stone-200"
              >
                {path.map((hop, hopIndex) => (
                  <li
                    key={`${hop.src}-${hop.rel_type}-${hop.dst}-${hopIndex}`}
                    className="break-all"
                  >
                    <span>{hop.src_name}</span>
                    <span className="text-stone-500"> —{hop.rel_type}→ </span>
                    <span>{hop.dst_name}</span>
                    <span className="text-stone-500">
                      {" "}
                      cost {hop.cost.toFixed(3)}
                    </span>
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
