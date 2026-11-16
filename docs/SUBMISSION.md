# Submission

Deadline: **2026-11-16 09:00 IST (03:30 UTC)**.

| Item | Location | State |
|---|---|---|
| Live app | https://trail-mend.vercel.app | Verified after push: landing and `/truth` load; screenshots at desktop and mobile widths in `evidence/demo/` |
| API | https://trailmend-production-ee2e07ff.up.railway.app | Verified after push: benchmark and MetaQA curve available with repository-matching hashes |
| Public repo | https://github.com/DrApkFile/TrailMend | Completed measured evidence pushed after gate and live checks |
| Loom | README table and `TRAILMEND_DEMO_URL` on Vercel | Owner must record and add URL; script: `docs/LOOM_SCRIPT.md` |
| Posts | `evidence/posts.md` | Owner must check handle, post and log URLs |
| Submission | Hackathon submission form | Owner must submit before deadline |

## Recorded results

Run 1 remains published as a failure, with its original evidence bytes. Run 2 `26b5469-580ae8dc` is published beside it, with its original hypothesis outputs, including H4' and H6' FAIL. Its conclusions are **provisional**: the later frozen baseline did not replicate, and the recorded run-2 frozen paths contain edges outside the intended G0. The reset was subsequently tightened. Do not present this as a clean replication or as an isolated weighted-versus-unweighted comparison.

MetaQA `ddf430f-2260187b` completed its graph arms and oracle ladders, followed by the document-only baseline and analysis. Verdicts: **M1 PASS; M2 PASS; M3 PASS; M4 FAIL; M5 PASS**. Its held-out sample is regional, not the official full test set; comparisons with published full-test MetaQA scores are inappropriate. Design: PRD §3.3; input hashes: `data/external/metaqa.manifest.json`.

The unweighted extension `9ae6601-580ae8dc` uses the same config digest and pinned HydraDB image as run 2, on a second local instance. It finished, was copied into this repo and is published as provisional because its frozen baseline differs. The second instance, S3 stand-in and temporary worktree were removed after copying. Diagnostics: `evidence/paired_v2_unweighted.json`.

The generated benchmark, copied from `evidence/benchmark.json`:

I tested TrailMend on 3 generated company graphs (1,165 nodes, 124 to 126 planted faults each) and on MetaQA, a public movie knowledge graph (134,741 triples, 360 held-out questions per seed, 3 seeds, half the triples withheld). The company-graph results are provisional: the extension did not reproduce run 2's frozen baseline, whose recorded paths include edges outside the intended G0 graph. The historical scores and verdicts remain published; this is not a clean replication. After 5 rounds of learning from its own answers, held-out accuracy on the company graphs rose from 77.9% to 85.7% (p < 0.001 on a paired test, every seed), and held-out Hits@1 on MetaQA rose from 55.3% to 71.5% (p < 0.001 on a paired test, every seed). It captured 69% of the gain that perfect repairs would give on the company graphs and 38% on MetaQA. Random reweighting, matched to its own targeted plan's number and size of cost changes each round, ends at 76.6% on the company graphs against 77.9% for the untouched graph, and at 55.6% on MetaQA against 55.3% for the untouched graph, and random reweighting did not significantly beat the untouched graph on any seed. The random arm reads no new documents; gap-fill alone, with no reweighting, reaches 82.9% on the company graphs. A plain document store over the same corpus stays flat at 28.3% (15.5% on MetaQA) because it has no links for the loop to repair, and with unweighted search the same loop goes from 83.3% to 89.9%, 4.2 points above the loop that searches on cost (provisional comparison: the frozen baselines differ, so the difference cannot be attributed to search alone). Wrong answers fell 30% on the company graphs and fell 9% on MetaQA, and 1,386 of 1,393 held-out questions that were right at the start were still right at the end, with every break along the way traced to a receipt. The graph did get bigger, but only by reading: the company graphs gained 158 links (3.2%), each from a withheld document and each under a receipt, and MetaQA read back 5,684 withheld triples. Reweighting and quarantine also change the graph; these results do not isolate their gain from gap-fill.

## Verification

`make gate` passed, including strict Python checks, unit tests and the production web build. Live `make verify` passed, including both `/v1/truth` tests; deployed pages/evidence and their hashes, both screenshots, hosted demo reset and local preview shutdown are verified. Evidence: `evidence/demo/final-deployment-check.json`, `landing-final-*-check.json` and `final-demo-reset.txt`. The clean-clone `scripts/presubmit.sh` audit passed at `a1b997a`: all 14 checks, including 52 live tests, with no skips. Evidence: `evidence/demo/final-verification.json` and `final-presubmit.txt`. H6 is complete with the replication limitation explicitly recorded. All figures above are generated from evidence rather than manually transcribed.

## Owner actions

1. Record `docs/LOOM_SCRIPT.md`, upload it and add the URL to the README table and Vercel `TRAILMEND_DEMO_URL`.
2. Check the current HydraDB handle, publish the post drafts and log their URLs.
3. Run the clean-clone pre-submit audit again after adding the Loom URL, then submit.

For a clean demo: `set -a; . ./.env.prod; set +a; ./scripts/demo_reset.sh`. Never print the token. Ask the Delta on-call question, press wrong three times, watch Selin Tadesse change to Bao Maeda, and inspect the fault on `/truth`.
