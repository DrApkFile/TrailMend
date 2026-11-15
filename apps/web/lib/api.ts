import "server-only";
import { adminToken, apiBaseUrl } from "./env";

export type ApiError = { code: string; message: string };

export type Fetched<T> =
  { ok: true; value: T } | { ok: false; error: ApiError };

export type Readiness = { graph_writable: boolean };

function errorFrom(status: number, body: unknown): ApiError {
  if (typeof body === "object" && body !== null && "error" in body) {
    const inner = (body as { error: unknown }).error;
    if (typeof inner === "object" && inner !== null && "code" in inner) {
      const shape = inner as { code: unknown; message?: unknown };
      return {
        code: String(shape.code),
        message:
          typeof shape.message === "string" ? shape.message : `HTTP ${status}`,
      };
    }
  }
  return {
    code: `http_${status}`,
    message: `The API answered HTTP ${status}.`,
  };
}

async function once(url: string): Promise<Response | Error> {
  try {
    return await fetch(url, { cache: "no-store" });
  } catch (cause) {
    return cause instanceof Error ? cause : new Error("fetch failed");
  }
}

async function getJson(path: string): Promise<Fetched<unknown>> {
  const url = `${apiBaseUrl()}${path}`;
  let attempt = await once(url);
  if (attempt instanceof Error) {
    attempt = await once(url);
  }
  if (attempt instanceof Error) {
    return {
      ok: false,
      error: { code: "api_unreachable", message: attempt.message },
    };
  }
  const response: Response = attempt;
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    return { ok: false, error: errorFrom(response.status, body) };
  }
  return { ok: true, value: body };
}

export async function fetchReadiness(): Promise<Fetched<Readiness>> {
  const result = await getJson("/v1/ready");
  if (!result.ok) {
    return result;
  }
  const body = result.value;
  if (
    typeof body !== "object" ||
    body === null ||
    typeof (body as Readiness).graph_writable !== "boolean"
  ) {
    return {
      ok: false,
      error: {
        code: "unreadable_response",
        message: "/v1/ready did not return graph_writable.",
      },
    };
  }
  return {
    ok: true,
    value: { graph_writable: (body as Readiness).graph_writable },
  };
}

export type Hop = {
  src: number;
  src_name: string;
  rel_type: string;
  dst: number;
  dst_name: string;
  cost: number;
};

export type Answer = {
  question: string;
  seed_entity_id: number;
  seed_entity_name: string;
  matched_how: string;
  answer_ids: number[];
  answer_names: string[];
  cost: number;
  paths: Hop[][];
  template: string | null;
};

export type Example = { question: string; template: string; hops: number };

export type Score = {
  n: number;
  correct: number;
  accuracy: number;
  set_f1: number;
  unreachable: number;
  refused: number;
  wrong: number;
};

export type CurveRow = {
  dataset: string;
  seed: number;
  arm: string;
  round: number;
  run_id: string;
  held_out: Score;
  train: Score | null;
  promoted?: number;
  retired?: number;
  gaps?: number;
  ingested?: number;
  applied_reweights?: number;
  applied_quarantines?: number;
  data_version?: string;
  gapfill_reached?: number;
  gapfill_ingested?: number;
  rules?: { update: string; gapfill: string };
};

export type Curve = { rows: CurveRow[]; available: boolean; sha256?: string };

export type EvidenceFile = {
  name: string;
  available: boolean;
  sha256?: string;
  payload?: {
    claim?: string;
    design?: string;
    measured_at?: string;
    rows?: unknown[];
  };
};

export type Receipt = {
  receipt_id: string;
  run_id: string;
  round: number;
  sequence: number;
  kind: string;
  edge: Hop | null;
  digest: string;
};

export type Neighbour = {
  rel_type: string;
  other_id: number;
  other_name: string;
  direction: string;
  cost: number;
  status: string;
};

export type Neighbourhood = {
  entity_id: number;
  name: string;
  label: string;
  neighbours: Neighbour[];
};

export type Judgement = {
  question: string;
  verdict: string;
  confirmed: number[];
  blamed: number[];
  receipts: string[];
  changed_anything: boolean;
};

async function postJson(
  path: string,
  body: unknown,
  headers: Record<string, string> = {},
): Promise<Fetched<unknown>> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json", ...headers },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch (cause) {
    return {
      ok: false,
      error: {
        code: "api_unreachable",
        message: cause instanceof Error ? cause.message : "fetch failed",
      },
    };
  }
  let parsed: unknown = null;
  try {
    parsed = await response.json();
  } catch {
    parsed = null;
  }
  if (!response.ok) {
    return { ok: false, error: errorFrom(response.status, parsed) };
  }
  return { ok: true, value: parsed };
}

function shaped<T>(
  result: Fetched<unknown>,
  guard: (body: unknown) => boolean,
  what: string,
): Fetched<T> {
  if (!result.ok) {
    return result;
  }
  if (!guard(result.value)) {
    return {
      ok: false,
      error: {
        code: "unreadable_response",
        message: `${what} did not return what we expect.`,
      },
    };
  }
  return { ok: true, value: result.value as T };
}

const isObject = (body: unknown): body is Record<string, unknown> =>
  typeof body === "object" && body !== null;

export async function fetchCurve(): Promise<Fetched<Curve>> {
  return shaped<Curve>(
    await getJson("/v1/evidence/curve"),
    (body) =>
      isObject(body) &&
      Array.isArray(body.rows) &&
      typeof body.available === "boolean",
    "/v1/evidence/curve",
  );
}

export async function fetchCurveV2(): Promise<Fetched<Curve>> {
  return shaped<Curve>(
    await getJson("/v1/evidence/curve-v2"),
    (body) =>
      isObject(body) &&
      Array.isArray(body.rows) &&
      typeof body.available === "boolean",
    "/v1/evidence/curve-v2",
  );
}

export async function fetchEvidence(
  name: string,
): Promise<Fetched<EvidenceFile>> {
  return shaped<EvidenceFile>(
    await getJson(`/v1/evidence/${name}`),
    (body) => isObject(body) && typeof body.available === "boolean",
    `/v1/evidence/${name}`,
  );
}

export async function fetchExamples(): Promise<Fetched<Example[]>> {
  return shaped<Example[]>(
    await getJson("/v1/examples"),
    Array.isArray,
    "/v1/examples",
  );
}

export async function fetchReceipts(limit = 20): Promise<Fetched<Receipt[]>> {
  return shaped<Receipt[]>(
    await getJson(`/v1/receipts?limit=${limit}`),
    Array.isArray,
    "/v1/receipts",
  );
}

export async function fetchNeighbourhood(
  id: number,
): Promise<Fetched<Neighbourhood>> {
  return shaped<Neighbourhood>(
    await getJson(`/v1/graph/neighbourhood/${id}`),
    (body) => isObject(body) && Array.isArray(body.neighbours),
    "/v1/graph/neighbourhood",
  );
}

export async function askQuestion(question: string): Promise<Fetched<Answer>> {
  return shaped<Answer>(
    await postJson("/v1/ask", { question }),
    (body) =>
      isObject(body) &&
      Array.isArray(body.answer_ids) &&
      Array.isArray(body.paths),
    "/v1/ask",
  );
}

export type Rollback = {
  receipt_id: string;
  undone_by: string;
  kind: string;
  changed_anything: boolean;
};

export async function rollbackReceipt(
  receiptId: string,
): Promise<Fetched<Rollback>> {
  const token = adminToken();
  if (token === null) {
    return {
      ok: false,
      error: {
        code: "admin_token_missing",
        message:
          "Rolling back writes to the graph, so it needs TRAILMEND_ADMIN_TOKEN set on the server.",
      },
    };
  }
  return shaped<Rollback>(
    await postJson(
      `/v1/rollback/${encodeURIComponent(receiptId)}`,
      {},
      { "x-admin-token": token },
    ),
    (body) => isObject(body) && typeof body.undone_by === "string",
    "/v1/rollback",
  );
}

export async function judgeAnswer(
  question: string,
  verdict: string,
  correctAnswerIds: number[] = [],
): Promise<Fetched<Judgement>> {
  const token = adminToken();
  if (token === null) {
    return {
      ok: false,
      error: {
        code: "admin_token_missing",
        message:
          "Judging writes to the graph, so it needs TRAILMEND_ADMIN_TOKEN set on the server.",
      },
    };
  }
  return shaped<Judgement>(
    await postJson(
      "/v1/judge",
      { question, verdict, correct_answer_ids: correctAnswerIds },
      { "x-admin-token": token },
    ),
    (body) => isObject(body) && Array.isArray(body.receipts),
    "/v1/judge",
  );
}

export type TruthEdge = { hop: Hop; status: string };

export type TruthFault = {
  fault_id: string;
  kind: string;
  status: string;
  repairable_by: string;
  planted: TruthEdge | null;
  truth: TruthEdge | null;
  other_edges: number;
  receipts: Receipt[];
};

export type Truth = {
  dataset: string;
  seed: number;
  data_version: string;
  counts: Record<string, number>;
  receipts_recorded: number;
  faults: TruthFault[];
};

export async function fetchTruth(): Promise<Fetched<Truth>> {
  return shaped<Truth>(
    await getJson("/v1/truth"),
    (body) =>
      isObject(body) && Array.isArray(body.faults) && isObject(body.counts),
    "/v1/truth",
  );
}

type MetaqaScore = {
  n: number;
  hits: number;
  hits_at_1: number;
  exact_set: number;
  wrong: number;
  wrong_rate: number;
  unreachable: number;
  refused: number;
};

export async function fetchCurveMetaqa(): Promise<Fetched<Curve>> {
  const fetched = await shaped<{
    rows: (Omit<CurveRow, "held_out"> & { held_out: MetaqaScore })[];
    available: boolean;
    sha256?: string;
  }>(
    await getJson("/v1/evidence/curve-metaqa"),
    (body) =>
      isObject(body) &&
      Array.isArray(body.rows) &&
      typeof body.available === "boolean",
    "/v1/evidence/curve-metaqa",
  );
  if (!fetched.ok) {
    return fetched;
  }
  return {
    ok: true,
    value: {
      available: fetched.value.available,
      sha256: fetched.value.sha256,
      rows: fetched.value.rows.map((row) => ({
        ...row,
        train: null,
        held_out: {
          n: row.held_out.n,
          correct: row.held_out.hits,
          accuracy: row.held_out.hits_at_1,
          set_f1: row.held_out.exact_set,
          unreachable: row.held_out.unreachable,
          refused: row.held_out.refused,
          wrong: row.held_out.wrong,
        },
      })),
    },
  };
}

export type BenchmarkSentence = {
  key: string;
  text: string;
  sources: string[];
};
