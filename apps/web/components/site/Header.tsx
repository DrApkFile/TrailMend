import Link from "next/link";
import { REPO_URL, demoUrl } from "@/lib/site";
import { NavLinks } from "./NavLinks";

function Logo() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 22 22"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M4 5.5 L11 11"
        stroke="#f4f1ea"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <path
        d="M11 11 L17.5 5"
        stroke="#ff5a47"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeDasharray="1.5 2.6"
      />
      <path
        d="M11 11 L13 18"
        stroke="#6ee7b7"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <circle cx="4" cy="5.5" r="2.1" fill="#f4f1ea" />
      <circle cx="11" cy="11" r="2.4" fill="#f4f1ea" />
      <circle cx="17.5" cy="5" r="1.7" fill="#ff5a47" />
      <circle cx="13" cy="18" r="2.1" fill="#6ee7b7" />
    </svg>
  );
}

function GitHubMark() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 .2a8 8 0 0 0-2.53 15.59c.4.07.55-.17.55-.38v-1.33c-2.23.48-2.7-1.07-2.7-1.07-.36-.93-.89-1.17-.89-1.17-.73-.5.05-.49.05-.49.8.06 1.23.83 1.23.83.72 1.22 1.88.87 2.33.66.07-.52.28-.87.5-1.07-1.77-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.03 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.28.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.2c0 .21.15.46.55.38A8 8 0 0 0 8 .2Z" />
    </svg>
  );
}

const PILL =
  "pointer-events-auto flex items-center rounded-full border border-white/10 bg-black/55 backdrop-blur-md";

export function Header() {
  return (
    <header className="pointer-events-none fixed inset-x-0 top-0 z-40 flex items-start justify-between gap-2 p-2.5 sm:p-5">
      <nav
        aria-label="Main"
        className={`${PILL} gap-0.5 py-1 pr-1.5 pl-1 sm:gap-1 sm:pr-3`}
      >
        <Link
          href="/"
          aria-label="TrailMend, home"
          className="flex items-center gap-2 rounded-full px-2 py-1.5 text-sm font-medium text-ink"
        >
          <Logo />
          <span className="hidden sm:inline">TrailMend</span>
        </Link>
        <NavLinks />
      </nav>
      <div className={`${PILL} gap-1 p-1`}>
        <a
          href={REPO_URL}
          aria-label="TrailMend on GitHub"
          className="flex items-center gap-2 rounded-full px-2.5 py-2 text-sm text-stone-300 transition-colors hover:text-ink sm:px-3 sm:py-1.5"
        >
          <GitHubMark />
          <span className="hidden sm:inline">GitHub</span>
        </a>
        <a
          href={demoUrl()}
          className="rounded-full bg-ink px-3 py-1.5 text-[13px] font-medium whitespace-nowrap text-night transition-opacity hover:opacity-85 sm:text-sm"
        >
          <span className="sm:hidden">Demo</span>
          <span className="hidden sm:inline">Watch the demo</span>
        </a>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-white/10 px-4 py-10 text-sm text-stone-500 sm:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-baseline sm:justify-between">
        <p>
          TrailMend. Built on HydraDB for the HydraDB hackathon, Track 1. The
          company graphs are generated; MetaQA is public data.
        </p>
        <p className="flex gap-4">
          <Link href="/mend" className="hover:text-ink">
            Receipts
          </Link>
          <a href={REPO_URL} className="hover:text-ink">
            Source
          </a>
        </p>
      </div>
    </footer>
  );
}
