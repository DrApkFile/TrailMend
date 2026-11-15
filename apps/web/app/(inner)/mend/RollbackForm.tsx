"use client";

import { useActionState } from "react";
import { runRollback, type RollbackState } from "./actions";

const EMPTY: RollbackState = {};

export function RollbackForm({ receiptId, kind }: { receiptId: string; kind: string }) {
  const [state, action, pending] = useActionState(runRollback, EMPTY);
  const undoable = kind !== "reset";

  return (
    <form action={action} className="mt-2 flex flex-col gap-2">
      <input type="hidden" name="receipt_id" value={receiptId} />
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="submit"
          disabled={pending || !undoable}
          className="rounded border border-stone-700 px-2 py-1 text-xs text-stone-300 disabled:opacity-40"
        >
          {pending ? "rolling back…" : "roll this back"}
        </button>
        {!undoable && <span className="text-xs text-stone-600">a reset has no inverse</span>}
      </div>
      {state.error && (
        <p className="text-xs break-all text-amber-300">
          <span className="font-mono">{state.error.code}</span> — {state.error.message}
        </p>
      )}
      {state.undone && (
        <p className="font-mono text-xs break-all text-emerald-300">
          undone by {state.undone.undone_by}, changed anything {String(state.undone.changed_anything)}
        </p>
      )}
    </form>
  );
}
