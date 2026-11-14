const MISSING = "TRAILMEND_API is not set; the web app has no API to call.";

export function apiBaseUrl(): string {
  const raw = process.env.TRAILMEND_API;
  if (raw === undefined || raw.trim() === "") {
    throw new Error(MISSING);
  }
  return raw.trim().replace(/\/+$/, "");
}
