"use client";

import { useEffect, useRef } from "react";

export type FlightCard = { kind: string; value: string; note: string };

const START = [0.06, 0.24, 0.42, 0.6];
const SPAN = 0.26;

function ease(value: number): number {
  const t = Math.min(1, Math.max(0, value));
  return t * t * (3 - 2 * t);
}

export function ReceiptFlight({
  cards,
  lead,
  joins,
  tail,
}: {
  cards: FlightCard[];
  lead: string;
  joins: string[];
  tail: string;
}) {
  const wrap = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = wrap.current;
    if (
      root === null ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }
    const flying = Array.from(
      root.querySelectorAll<HTMLElement>("[data-card]"),
    );
    const slots = Array.from(root.querySelectorAll<HTMLElement>("[data-slot]"));
    let offsets: { dx: number; dy: number }[] = [];
    let frame = 0;

    function measure(): void {
      flying.forEach((card) => {
        card.style.transform = "none";
      });
      offsets = flying.map((card, index) => {
        const from = card.getBoundingClientRect();
        const to = (slots[index] ?? card).getBoundingClientRect();
        return {
          dx: to.left + to.width / 2 - (from.left + from.width / 2),
          dy: to.top + to.height / 2 - (from.top + from.height / 2),
        };
      });
    }

    function paint(): void {
      frame = 0;
      const box = root!.getBoundingClientRect();
      const travel = box.height - window.innerHeight;
      const progress =
        travel > 0 ? Math.min(1, Math.max(0, -box.top / travel)) : 1;
      flying.forEach((card, index) => {
        const moved = ease((progress - (START[index] ?? 0.6)) / SPAN);
        const offset = offsets[index] ?? { dx: 0, dy: 0 };
        card.style.transform = `translate(${offset.dx * moved}px, ${offset.dy * moved}px) scale(${1 - 0.7 * moved})`;
        card.style.opacity = String(1 - moved ** 4);
        const slot = slots[index];
        if (slot !== undefined) {
          slot.style.opacity = String(0.12 + 0.88 * moved ** 3);
        }
      });
    }

    function onScroll(): void {
      if (frame === 0) {
        frame = requestAnimationFrame(paint);
      }
    }
    function onResize(): void {
      measure();
      paint();
    }

    root.dataset.live = "true";
    measure();
    paint();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      delete root.dataset.live;
    };
  }, []);

  return (
    <div ref={wrap} className="flight relative">
      <div className="flight-stick flex flex-col justify-center gap-8 px-4 py-16 sm:px-8 lg:flex-row lg:items-center lg:gap-16">
        <ol className="relative mx-auto flex w-full max-w-sm flex-col gap-2.5 border-l border-white/15 pl-5 sm:gap-4 lg:mx-0 lg:w-80 lg:shrink-0">
          {cards.map((card) => (
            <li key={card.kind} className="relative">
              <span className="absolute top-1/2 -left-[1.6rem] h-2 w-2 -translate-y-1/2 rounded-full bg-stone-500" />
              <div
                data-card
                className="flex items-baseline justify-between gap-4 rounded-xl border border-white/10 bg-stone-900 px-4 py-2.5 will-change-transform sm:py-3.5"
              >
                <div className="min-w-0">
                  <p className="font-mono text-[11px] tracking-wider text-stone-500 uppercase">
                    {card.kind}
                  </p>
                  <p className="truncate text-xs text-stone-400">{card.note}</p>
                </div>
                <p className="font-mono text-xl text-ink sm:text-2xl">
                  {card.value}
                </p>
              </div>
            </li>
          ))}
        </ol>
        <p className="mx-auto max-w-2xl font-display text-[clamp(1.75rem,5.2vw,3.6rem)] leading-[1.08] text-stone-400 lg:mx-0">
          {lead}{" "}
          {cards.map((card, index) => (
            <span key={card.kind}>
              <span
                data-slot
                className="font-mono text-[0.72em] whitespace-nowrap text-ink"
              >
                {card.value}
              </span>{" "}
              {joins[index] ?? ""}{" "}
            </span>
          ))}
          <span className="text-ink">{tail}</span>
        </p>
      </div>
    </div>
  );
}
