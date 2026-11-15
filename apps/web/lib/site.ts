export const REPO_URL = "https://github.com/DrApkFile/TrailMend";

export const NAV: { href: string; label: string }[] = [
  { href: "/ask", label: "Ask" },
  { href: "/truth", label: "Truth" },
  { href: "/evidence", label: "Evidence" },
  { href: "/pricing", label: "Pricing" },
];

export function demoUrl(): string {
  const raw = process.env.TRAILMEND_DEMO_URL;
  return raw === undefined || raw.trim() === ""
    ? `${REPO_URL}#demo`
    : raw.trim();
}
