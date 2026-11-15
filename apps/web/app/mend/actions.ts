"use server";

import { rollbackReceipt, type ApiError, type Rollback } from "@/lib/api";
import { revalidatePath } from "next/cache";

export type RollbackState = {
  undone?: Rollback;
  error?: ApiError;
};

export async function runRollback(_state: RollbackState | undefined, form: FormData): Promise<RollbackState> {
  const receiptId = String(form.get("receipt_id") ?? "").trim();
  if (receiptId === "") {
    return { error: { code: "invalid_request", message: "No receipt was named." } };
  }
  const done = await rollbackReceipt(receiptId);
  if (!done.ok) {
    return { error: done.error };
  }
  revalidatePath("/mend");
  return { undone: done.value };
}
