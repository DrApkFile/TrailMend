import "server-only";
import { apiBaseUrl } from "./env";

export type ApiError = { code: string; message: string };

export type Fetched<T> = { ok: true; value: T } | { ok: false; error: ApiError };

export type Readiness = { graph_writable: boolean };

function errorFrom(status: number, body: unknown): ApiError {
  if (typeof body === "object" && body !== null && "error" in body) {
    const inner = (body as { error: unknown }).error;
    if (typeof inner === "object" && inner !== null && "code" in inner) {
      const shape = inner as { code: unknown; message?: unknown };
      return {
        code: String(shape.code),
        message: typeof shape.message === "string" ? shape.message : `HTTP ${status}`,
      };
    }
  }
  return { code: `http_${status}`, message: `The API answered HTTP ${status}.` };
}

async function getJson(path: string): Promise<Fetched<unknown>> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, { cache: "no-store" });
  } catch (cause) {
    return {
      ok: false,
      error: { code: "api_unreachable", message: cause instanceof Error ? cause.message : "fetch failed" },
    };
  }
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
  if (typeof body !== "object" || body === null || typeof (body as Readiness).graph_writable !== "boolean") {
    return { ok: false, error: { code: "unreadable_response", message: "/v1/ready did not return graph_writable." } };
  }
  return { ok: true, value: { graph_writable: (body as Readiness).graph_writable } };
}
