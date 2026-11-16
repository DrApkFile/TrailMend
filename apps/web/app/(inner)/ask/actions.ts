"use server";

import {
  askQuestion,
  judgeAnswer,
  type Answer,
  type ApiError,
  type Judgement,
} from "@/lib/api";

export type AskState = {
  question: string;
  answer?: Answer;
  judgement?: Judgement;
  error?: ApiError;
};

export async function runAsk(
  _state: AskState | undefined,
  form: FormData,
): Promise<AskState> {
  const question = String(form.get("question") ?? "").trim();
  const verdict = String(form.get("verdict") ?? "");
  if (question.length < 3) {
    return {
      question,
      error: { code: "invalid_request", message: "Type a question first." },
    };
  }
  if (verdict === "") {
    const answer = await askQuestion(question);
    return answer.ok
      ? { question, answer: answer.value }
      : { question, error: answer.error };
  }
  const judged = await judgeAnswer(question, verdict);
  if (!judged.ok) {
    return { question, error: judged.error };
  }
  const again = await askQuestion(question);
  return {
    question,
    judgement: judged.value,
    answer: again.ok ? again.value : undefined,
    error: again.ok ? undefined : again.error,
  };
}
