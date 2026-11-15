import { Panel } from "@/components/Shell";

export const metadata = { title: "TrailMend — pricing" };

export default function PricingPage() {
  return (
    <main>
      <h1 className="text-2xl font-semibold tracking-tight">Who this is for, and what it costs</h1>

      <Panel title="The buyer">
        <p className="text-sm text-stone-300">
          The person who owns the on-call rota and the service catalogue: a platform or SRE lead at a company with
          enough services that nobody holds the whole map in their head.
        </p>
      </Panel>

      <Panel title="The pain">
        <p className="text-sm text-stone-300">
          The catalogue is wrong in ways nobody notices until an incident. A service points at a team that no longer
          owns it, a rota entry is stale, two entries describe the same person. The page goes to the wrong human and
          the incident runs long. The map is maintained by hand, so it decays between audits.
        </p>
      </Panel>

      <Panel title="The status quo">
        <p className="text-sm text-stone-300">
          A service catalogue in a wiki or a Backstage entry, and a quarterly audit. Correctness depends on someone
          remembering to edit it. Nothing uses the one signal that is always available: whether the answer it gave
          was right.
        </p>
      </Panel>

      <Panel title="Price">
        <dl className="text-sm">
          <div className="flex justify-between border-b border-stone-800 py-2">
            <dt className="text-stone-400">Unit</dt>
            <dd className="font-mono">per service in the catalogue, per month</dd>
          </div>
          <div className="flex justify-between border-b border-stone-800 py-2">
            <dt className="text-stone-400">List</dt>
            <dd className="font-mono">$4 / service / month, minimum $400 / month</dd>
          </div>
          <div className="flex justify-between border-b border-stone-800 py-2">
            <dt className="text-stone-400">Pilot</dt>
            <dd className="font-mono">6 weeks, $2,000, capped at 250 services</dd>
          </div>
        </dl>
        <p className="mt-3 text-sm text-stone-300">
          The pilot is judged on one number agreed up front: the share of &ldquo;who owns this / who do I page&rdquo;
          questions answered correctly on a held-out set your team writes, before and after six weeks of judging.
          If it does not improve, the pilot is refunded.
        </p>
      </Panel>

      <Panel title="What it is not">
        <p className="text-sm text-stone-300">
          It is not an incident-response tool, it does not replace a catalogue as the place humans edit, and it does
          not call an LLM on the answer path. The numbers on this site come from generated data, labelled as
          generated; no customer data has been measured.
        </p>
      </Panel>
    </main>
  );
}
