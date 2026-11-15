import Link from "next/link";

const PAGES: { href: string; label: string }[] = [
  { href: "/", label: "The curve" },
  { href: "/ask", label: "Ask" },
  { href: "/mend", label: "The bad link" },
  { href: "/evidence", label: "Evidence" },
  { href: "/pricing", label: "Pricing" },
];

export function Nav() {
  return (
    <nav className="mb-8 flex flex-wrap gap-x-4 gap-y-2 border-b border-stone-800 pb-4 text-sm">
      {PAGES.map((page) => (
        <Link key={page.href} href={page.href} className="text-stone-400 hover:text-stone-100">
          {page.label}
        </Link>
      ))}
    </nav>
  );
}

export function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-6 rounded-lg border border-stone-800 bg-stone-900/40 p-4">
      <h2 className="text-sm font-semibold tracking-wide text-stone-300 uppercase">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function Failed({ code, message }: { code: string; message: string }) {
  return (
    <p className="rounded border border-amber-900/60 bg-amber-950/40 p-3 text-sm text-amber-200">
      Not shown, because the API did not answer: <span className="font-mono">{code}</span> — {message}
    </p>
  );
}

export function Hops({ hops }: { hops: { src_name: string; rel_type: string; dst_name: string; cost: number }[] }) {
  return (
    <ol className="flex flex-col gap-1 font-mono text-xs text-stone-200">
      {hops.map((hop, index) => (
        <li key={`${hop.src_name}-${hop.rel_type}-${hop.dst_name}-${index}`} className="break-all">
          <span className="text-stone-100">{hop.src_name}</span>
          <span className="text-stone-500"> —{hop.rel_type}→ </span>
          <span className="text-stone-100">{hop.dst_name}</span>
          <span className="text-stone-500"> cost {hop.cost.toFixed(3)}</span>
        </li>
      ))}
    </ol>
  );
}
