export type Point = {
  x: number;
  y: number;
  px: number;
  py: number;
  pinned: boolean;
  size: number;
};
export type Link = { a: number; b: number; rest: number };
export type MendPhase = "held" | "flagged" | "free" | "forming" | "mended";

export type Trail = {
  points: Point[];
  links: Link[];
  bridgeEnd: number;
  targets: [number, number];
  attached: 0 | 1;
  bridgeLink: Link | null;
  phase: MendPhase;
  clock: number;
};

const SPACING = 0.125;
const GRAVITY = 1.15;
const DAMPING = 0.985;
const ITERATIONS = 10;
const PUSH_RADIUS = 0.34;
const PUSH_FORCE = 0.02;

export const PHASE_SECONDS: Record<MendPhase, number> = {
  held: 3.2,
  flagged: 1.3,
  free: 1.5,
  forming: 0.9,
  mended: 2.6,
};
const ORDER: MendPhase[] = ["held", "flagged", "free", "forming", "mended"];

function strand(
  points: Point[],
  links: Link[],
  x: number,
  top: number,
  count: number,
): number[] {
  const made: number[] = [];
  for (let index = 0; index < count; index += 1) {
    const y = top - index * SPACING;
    points.push({
      x,
      y,
      px: x,
      py: y,
      pinned: index === 0,
      size: index === 0 ? 0 : index % 4 === 2 ? 1.5 : 1,
    });
    made.push(points.length - 1);
    if (index > 0) {
      links.push({ a: points.length - 2, b: points.length - 1, rest: SPACING });
    }
  }
  return made;
}

function twig(
  points: Point[],
  links: Link[],
  from: number,
  dx: number,
  count: number,
): number {
  let previous = from;
  for (let index = 1; index <= count; index += 1) {
    const base = points[from] as Point;
    const x = base.x + dx * index * SPACING * 0.9;
    const y = base.y - index * SPACING * 0.5;
    points.push({ x, y, px: x, py: y, pinned: false, size: 0.8 });
    links.push({ a: previous, b: points.length - 1, rest: SPACING * 0.95 });
    previous = points.length - 1;
  }
  return previous;
}

export function buildTrail(aspect: number): Trail {
  const points: Point[] = [];
  const links: Link[] = [];
  const narrow = aspect < 0.8;
  const top = 1.08;
  const left = strand(
    points,
    links,
    (narrow ? -0.62 : 0.08) * aspect,
    top,
    narrow ? 9 : 10,
  );
  const middle = strand(
    points,
    links,
    (narrow ? 0.0 : 0.45) * aspect,
    top,
    narrow ? 12 : 13,
  );
  const right = strand(
    points,
    links,
    (narrow ? 0.64 : 0.8) * aspect,
    top,
    narrow ? 8 : 9,
  );
  twig(points, links, middle[3] as number, -1, 2);
  twig(points, links, left[4] as number, -1, 2);
  twig(points, links, right[3] as number, 1, 2);
  twig(points, links, middle[9] as number, 1, 2);
  const bridgeEnd = twig(points, links, middle[6] as number, -1, 3);
  const targets: [number, number] = [left[6] as number, right[5] as number];
  const bridgeLink: Link = { a: bridgeEnd, b: targets[0], rest: SPACING };
  links.push(bridgeLink);
  return {
    points,
    links,
    bridgeEnd,
    targets,
    attached: 0,
    bridgeLink,
    phase: "held",
    clock: 0,
  };
}

function advancePhase(trail: Trail): void {
  const next = ORDER[
    (ORDER.indexOf(trail.phase) + 1) % ORDER.length
  ] as MendPhase;
  trail.phase = next;
  trail.clock = 0;
  if (next === "free" && trail.bridgeLink !== null) {
    trail.links = trail.links.filter((link) => link !== trail.bridgeLink);
    trail.bridgeLink = null;
  }
  if (next === "mended") {
    trail.attached = trail.attached === 0 ? 1 : 0;
    const end = trail.points[trail.bridgeEnd] as Point;
    const target = trail.points[trail.targets[trail.attached]] as Point;
    const link: Link = {
      a: trail.bridgeEnd,
      b: trail.targets[trail.attached],
      rest: Math.hypot(end.x - target.x, end.y - target.y),
    };
    trail.links.push(link);
    trail.bridgeLink = link;
  }
}

export function nextTarget(trail: Trail): number {
  return trail.targets[trail.attached === 0 ? 1 : 0];
}

export function stepTrail(
  trail: Trail,
  dt: number,
  pointer: { x: number; y: number } | null,
  cycle: boolean,
): void {
  const step = Math.min(dt, 1 / 30);
  if (cycle) {
    trail.clock += step;
    if (trail.clock >= PHASE_SECONDS[trail.phase]) {
      advancePhase(trail);
    }
  }
  if (trail.bridgeLink !== null && trail.bridgeLink.rest > SPACING) {
    trail.bridgeLink.rest = Math.max(
      SPACING,
      trail.bridgeLink.rest - step * 0.55,
    );
  }
  for (const point of trail.points) {
    if (point.pinned) {
      continue;
    }
    let vx = (point.x - point.px) * DAMPING;
    let vy = (point.y - point.py) * DAMPING - GRAVITY * step * step;
    if (pointer !== null) {
      const dx = point.x - pointer.x;
      const dy = point.y - pointer.y;
      const distance = Math.hypot(dx, dy);
      if (distance < PUSH_RADIUS && distance > 0.0001) {
        const push = (1 - distance / PUSH_RADIUS) * PUSH_FORCE;
        vx += (dx / distance) * push;
        vy += (dy / distance) * push;
      }
    }
    point.px = point.x;
    point.py = point.y;
    point.x += vx;
    point.y += vy;
  }
  for (let iteration = 0; iteration < ITERATIONS; iteration += 1) {
    for (const link of trail.links) {
      const a = trail.points[link.a] as Point;
      const b = trail.points[link.b] as Point;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const distance = Math.hypot(dx, dy) || 0.0001;
      const slack = (distance - link.rest) / distance;
      const shareA = a.pinned ? 0 : b.pinned ? 1 : 0.5;
      const shareB = b.pinned ? 0 : a.pinned ? 1 : 0.5;
      a.x += dx * slack * shareA;
      a.y += dy * slack * shareA;
      b.x -= dx * slack * shareB;
      b.y -= dy * slack * shareB;
    }
  }
}
