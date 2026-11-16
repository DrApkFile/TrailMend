"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV } from "@/lib/site";

export function NavLinks() {
  const path = usePathname();
  return (
    <>
      {NAV.map((page) => {
        const active = path === page.href || path.startsWith(`${page.href}/`);
        return (
          <Link
            key={page.href}
            href={page.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-full px-1.5 py-1.5 text-[13px] transition-colors sm:px-3 sm:text-sm ${
              active ? "bg-white/10 text-ink" : "text-stone-400 hover:text-ink"
            }`}
          >
            {page.label}
          </Link>
        );
      })}
    </>
  );
}
