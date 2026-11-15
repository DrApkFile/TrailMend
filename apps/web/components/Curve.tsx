import type { CurveRow } from "@/lib/api";
import { armsOf, bandByRound, seriesOf } from "@/lib/curve";

const WIDTH = 720;
const HEIGHT = 340;
const LEFT = 46;
const RIGHT = 12;
const TOP = 12;
const BOTTOM = 34;
const COLOURS: Record<string, string> = {
  full: "#60a5fa",
  full_v2: "#60a5fa",
  full_v1_rule: "#818cf8",
  gapfill_wide_only: "#22d3ee",
  frozen: "#a8a29e",
  plain_store: "#f472b6",
  reweight_only: "#34d399",
  quarantine_only: "#fbbf24",
  promote_only: "#c084fc",
  gapfill_only: "#22d3ee",
  random_reweight: "#fb7185",
  random_quarantine: "#f97316",
};

function colourOf(arm: string): string {
  return COLOURS[arm] ?? "#d6d3d1";
}

export function Curve({
  rows,
  arms,
  band,
}: {
  rows: CurveRow[];
  arms?: string[];
  band?: string;
}) {
  const shown = arms ?? armsOf(rows);
  const series = seriesOf(rows, shown);
  if (series.length === 0) {
    return (
      <p className="rounded border border-stone-800 bg-stone-900/40 p-4 text-sm text-stone-400">
        No run has been recorded yet, so there is no curve to draw.
      </p>
    );
  }
  const maxRound = Math.max(
    ...series.flatMap((one) => one.points.map((point) => point.round)),
  );
  const x = (round: number) =>
    LEFT + ((WIDTH - LEFT - RIGHT) * round) / (maxRound || 1);
  const y = (value: number) =>
    HEIGHT - BOTTOM - (HEIGHT - TOP - BOTTOM) * value;
  const bandPoints = band ? bandByRound(rows, band) : [];

  return (
    <figure className="w-full">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="w-full"
        role="img"
        aria-label="Held-out accuracy by round"
      >
        {[0, 0.2, 0.4, 0.6, 0.8, 1].map((value) => (
          <g key={value}>
            <line
              x1={LEFT}
              y1={y(value)}
              x2={WIDTH - RIGHT}
              y2={y(value)}
              stroke="#292524"
            />
            <text
              x={LEFT - 8}
              y={y(value) + 4}
              textAnchor="end"
              fontSize="11"
              fill="#78716c"
            >
              {(value * 100).toFixed(0)}%
            </text>
          </g>
        ))}
        {Array.from({ length: maxRound + 1 }, (_, round) => (
          <text
            key={round}
            x={x(round)}
            y={HEIGHT - 12}
            textAnchor="middle"
            fontSize="11"
            fill="#78716c"
          >
            {round}
          </text>
        ))}
        {bandPoints.length > 1 && (
          <polygon
            fill={colourOf(band ?? "full")}
            fillOpacity="0.14"
            points={[
              ...bandPoints.map(
                (point) => `${x(point.round)},${y(point.high)}`,
              ),
              ...[...bandPoints]
                .reverse()
                .map((point) => `${x(point.round)},${y(point.low)}`),
            ].join(" ")}
          />
        )}
        {series.map((one) => (
          <g key={one.arm}>
            <polyline
              fill="none"
              stroke={colourOf(one.arm)}
              strokeWidth="2"
              points={one.points
                .map((point) => `${x(point.round)},${y(point.accuracy)}`)
                .join(" ")}
            />
            {one.points.map((point) => (
              <circle
                key={point.round}
                cx={x(point.round)}
                cy={y(point.accuracy)}
                r="2.5"
                fill={colourOf(one.arm)}
              />
            ))}
          </g>
        ))}
      </svg>
      <figcaption className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-400">
        {series.map((one) => (
          <span key={one.arm} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: colourOf(one.arm) }}
            />
            <span className="font-mono">{one.arm}</span>
          </span>
        ))}
        <span>
          round on the x axis, held-out accuracy on the y axis, mean over seeds
        </span>
      </figcaption>
    </figure>
  );
}
