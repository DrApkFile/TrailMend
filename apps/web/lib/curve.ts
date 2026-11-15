import type { CurveRow } from "./api";

export const NOT_MEASURED = "—";

export type Point = { round: number; accuracy: number };
export type Series = { arm: string; points: Point[] };

export function armsOf(rows: CurveRow[]): string[] {
  return [...new Set(rows.map((row) => row.arm))].sort();
}

export function seedsOf(rows: CurveRow[]): number[] {
  return [...new Set(rows.map((row) => row.seed))].sort((a, b) => a - b);
}

export function meanByRound(rows: CurveRow[], arm: string): Point[] {
  const totals = new Map<number, number[]>();
  for (const row of rows) {
    if (row.arm !== arm || typeof row.held_out?.accuracy !== "number") {
      continue;
    }
    const held = totals.get(row.round) ?? [];
    held.push(row.held_out.accuracy);
    totals.set(row.round, held);
  }
  return [...totals.entries()]
    .sort(([a], [b]) => a - b)
    .map(([round, values]) => ({
      round,
      accuracy: values.reduce((sum, value) => sum + value, 0) / values.length,
    }));
}

export function bandByRound(rows: CurveRow[], arm: string): { round: number; low: number; high: number }[] {
  const totals = new Map<number, number[]>();
  for (const row of rows) {
    if (row.arm !== arm || typeof row.held_out?.accuracy !== "number") {
      continue;
    }
    const held = totals.get(row.round) ?? [];
    held.push(row.held_out.accuracy);
    totals.set(row.round, held);
  }
  return [...totals.entries()]
    .sort(([a], [b]) => a - b)
    .map(([round, values]) => ({ round, low: Math.min(...values), high: Math.max(...values) }));
}

export function seriesOf(rows: CurveRow[], arms: string[]): Series[] {
  return arms.map((arm) => ({ arm, points: meanByRound(rows, arm) })).filter((one) => one.points.length > 0);
}

export function percent(value: number | undefined): string {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : NOT_MEASURED;
}

export function delta(rows: CurveRow[], arm: string): number | undefined {
  const points = meanByRound(rows, arm);
  const first = points.at(0);
  const last = points.at(-1);
  if (first === undefined || last === undefined || points.length < 2) {
    return undefined;
  }
  return last.accuracy - first.accuracy;
}
