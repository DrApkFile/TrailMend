# Judging TrailMend

A guide so you can spend your time on the parts that matter. Ten minutes covers the claim and the demo; another twenty
lets you check the numbers and try to break it. Back to the [README](README.md) · All results:
[BENCHMARK.md](BENCHMARK.md).

## The claim, in one sentence

A graph that learns **only from whether its own answers were right** gets measurably more accurate on questions it
never saw, beats random changes of the same size, and records every change it made as a receipt you can roll back.

Three things have to be true for that to hold, and each is checkable:

| # | Claim | Where to check it |
|---|---|---|
| 1 | Held-out accuracy rises over rounds and beats the frozen graph, question by question, on every seed | [`evidence/paired_v2.json`](evidence/paired_v2.json), [`evidence/replication_v2_clean.json`](evidence/replication_v2_clean.json), [`evidence/paired_metaqa.json`](evidence/paired_metaqa.json), [`evidence/summary_v4.json`](evidence/summary_v4.json) |
| 2 | The gain comes from *targeted* change: random changes of the same number and size do not help, and a document store with no graph cannot learn at all | [`evidence/changes_v2.json`](evidence/changes_v2.json), [`evidence/plain_store_v2.json`](evidence/plain_store_v2.json), the `random_*` and `plain_store` rows in [BENCHMARK.md](BENCHMARK.md#all-results) |
| 3 | Held-out questions never reach the learner, and nothing was tuned on them | [`src/trailmend/eval/splits.py`](src/trailmend/eval/splits.py), [`tests/unit/test_round_contract.py`](tests/unit/test_round_contract.py) (`test_inv8_*`), and the preregistrations in [docs/PRD.md](docs/PRD.md) §3 |

## 10 minutes: the fast path

1. **Read the results table** at the top of the [README](README.md#the-results). Every cell is generated from
   `evidence/`.
2. **Do the live repair** on [/ask](https://trail-mend.vercel.app/ask):
   - Ask **"Who is on call for the Delta team?"** It answers *Selin Tadesse*, a stale link that three documents
     support.
   - Press **wrong** three times, waiting for each response. The link's cost rises each time, and on the third press
     it is quarantined.
   - The answer becomes *Bao Maeda*, who is the truth.
3. **Watch it learn** on the [landing page](https://trail-mend.vercel.app). It replays a real recorded run round by
   round from its tapes and receipts, not from an animation script.
4. **Inspect the fault** on [/truth](https://trail-mend.vercel.app/truth). Every fault planted in the demo graph is
   shown as it is in HydraDB *now*: still wrong, quarantined, corrected or gap-filled, with the receipts that changed
   it.
5. **Roll something back** on [/mend](https://trail-mend.vercel.app/mend). Undo any receipt; the rollback writes its
   own receipt.
6. **Follow a number to its file** on [/evidence](https://trail-mend.vercel.app/evidence). Every figure on the site is
   listed with the file it came from and that file's sha256.

The demo graph is shared. If someone judged before you, the Delta answer may already be *Bao Maeda*. The costs shown
on the page tell you which state you are in.

## 20 minutes: check the numbers yourself

No HydraDB is needed for any of these.

```bash
git clone <this repo> && cd trailmend
uv sync --frozen
make gate                                  # ruff, pyright strict, all unit tests, web typecheck, lint and build
SKIP_LIVE=1 bash scripts/presubmit.sh      # a fresh clone; also checks every evidence file against its manifest's sha256
uv run python -c "from trailmend.eval import report; report.write(); report.write_front()"
                                           # rebuild BENCHMARK.md and the README table from evidence/
git diff --stat README.md BENCHMARK.md     # should be empty: the published numbers are what the files say
```

Then open the evidence directly. Each file states its claim, the design it was measured under, and the rows:

- [`evidence/hypotheses_v2.json`](evidence/hypotheses_v2.json): run 2's eight hypotheses and the rule each was decided
  by. Two **FAIL**, and they are left as failed.
- [`evidence/paired_v2.json`](evidence/paired_v2.json): every held-out question paired against the frozen graph, with
  an exact McNemar p-value per seed.
- [`evidence/non_regression_v2.json`](evidence/non_regression_v2.json): for each round, the questions newly fixed and
  newly broken, with every break traced to the receipts on its old path.
- [`evidence/quarantine_v2.json`](evidence/quarantine_v2.json): quarantine precision and recall against the planted
  faults. This is where H4' failed.
- [`evidence/run_manifest_v2.json`](evidence/run_manifest_v2.json): the commit, the HydraDB image digest, the config
  hash, the seeds and every file's sha256.
- `evidence/runs/<run id>-s<seed>-<arm>/`: the raw tapes and receipt journals that every analysis is computed from.

Run ids are `<commit>-<config digest>`. Run 3 was measured at `9fe1e3a` (tag `run3-measured`) and run 4 at `b65058c`
(tag `run4-measured`), so `git checkout run4-measured` gives you the exact code behind a run.

To rerun the live contract tests against a real HydraDB (needs Docker):

```bash
make hydra-up && make verify && make hydra-down
```

[`tests/live/test_hydra_contract.py`](tests/live/test_hydra_contract.py) proves on a real HydraDB that a cost change
flips the route and that a quarantined edge is never searched.

## Try to break it

These are the attacks we would try first, and what should happen when you try them.

| Try this | What should happen | Where it is enforced |
|---|---|---|
| Ask a question TrailMend has no template for, or about an entity that does not exist | A named error (`invalid_request` or a seeding error), never a guessed answer | `src/trailmend/api/routes_ask.py`, `src/trailmend/search/` |
| `POST /v1/judge`, `/v1/rollback/{id}` or `/v1/demo/reset` on the API without the admin token | Refused, and the error says nothing changed. Writes from the site go through its server, which holds the token | `src/trailmend/api/auth.py` |
| Hammer `/v1/ask` | Rate-limited per client | `src/trailmend/api/state.py` |
| Press **wrong** on an answer that is actually right | That link gets dearer, but quarantine needs at least 3 blames making up 80% of its recent judgements, and never fires on a link confirmed in the same round | `tests/unit/test_mend_invariants.py` (`test_inv1_*`, `test_inv2_*`) |
| Roll back a receipt, then judge the same link again | The edge returns exactly to its recorded state (a quarantine comes back as the same active edge), the journal only grows, and the restored edge can learn again | `tests/live/test_apply_and_rollback.py` (`test_inv3_*`, `test_d1_*`), `tests/unit/test_gapfill.py` |
| Look for a way the learner could see held-out questions | There isn't one: held-out questions are a different type, the round runner only accepts `TrainQuestion`, and only the splitter can make either | `tests/unit/test_round_contract.py` (`test_inv8_*`) |
| Suspect the random control is weaker than the real Mend | Each random arm is built from the real plan of the same round, with the same number and size of changes | `tests/unit/test_mend_policies.py` (`test_inv6_*`), `evidence/changes_v2.json` |
| Suspect a quarantined edge sneaks back into search | The query builder refuses to search any `Q_` type | `tests/unit/test_graph_values.py` (`test_quarantined_types_can_never_be_searched`), the live contract test |
| Suspect gap-fill reads the answer | It reads only documents that mention the entity asked about; a document that only mentions the gold answer stays unread | `tests/unit/test_gapfill.py` (`test_inv7_*`) |
| Suspect the constants were tuned until it went up | They are in `config/` and fixed before each run; changing one changes the run id. Preregistrations are dated in [DECISIONS.md](DECISIONS.md) before the runs they describe | `config/mend.toml`, `config/run4.toml`, [docs/PRD.md](docs/PRD.md) §3 |
| Grep for an LLM on the answer path | There is none. No LLM writes to the graph or scores an answer | `src/trailmend/search/`, `src/trailmend/loop/` |

If you find something that breaks, we would like to know.

## Weak spots, stated up front

- **The company data is generated.** It has to be, so that every planted fault and its truth are known and quarantine
  precision means something. MetaQA is the public check; it is a seeded 360-question sample per seed, so its numbers
  are not comparable to full-test-set MetaQA results.
- **Not every hypothesis passed.** Run 1's headline (H1) failed. Run 2 missed quarantine precision and recall (H4')
  and a 40% cut in wrong answers (H6', it got about 30%). Run 3's abstention variant failed R1 and R2. All of them
  stay published.
- **Unweighted search scores higher than weighted search** on the same clean graph. We measured that and publish it,
  rather than hide it; run 4's learner uses hop-count search for set answers because of it.
- **Run 4's refusal gate adds nothing at the end of the run.** The matched no-gate policy has the same wrong-answer
  count and higher accuracy; the improvement comes from the repaired learner.
- **Runs 3 and 4 are Northwind only.** MetaQA was not rerun for them, and the files say `not_run`.
- **The live demo's receipt list empties on a redeploy**, while the graph keeps the changes. The recorded runs are
  unaffected: their journals are in `evidence/runs/`.
- **The first request on a fresh connection to the hosted API is slow** (about 6 s of connection setup). Later
  requests take about half a second.

The full list is in [BENCHMARK.md](BENCHMARK.md#limitations).

## Where everything is

| You want | Go to |
|---|---|
| The Mend's rules (credit, update, quarantine, promotion, receipts, rollback) | `src/trailmend/core/`, pure and property-tested |
| Every Cypher query | `src/trailmend/graph/queries.py`, the only place one exists |
| One learning round | `src/trailmend/loop/round.py` |
| How an answer is chosen from paths | `src/trailmend/search/answer.py` |
| How the experiments run and are analysed | `src/trailmend/eval/` (run 3 in `eval/v3/`, run 4 in `eval/v4/`) |
| Why a design choice was made | [DECISIONS.md](DECISIONS.md) |
| HydraDB 0.4 behaviour we verified live | [docs/REALITY_SPIKES.md](docs/REALITY_SPIKES.md) |

You can skip `docs/HANDOFF*.md`, `docs/KICKOFF_PROMPT.md`, `docs/LANDSCAPE.md` and `docs/IDEA_CHECK.md`. They are
working notes from the build.
