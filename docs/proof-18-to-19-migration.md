# Proof of work — OpenUpgrade 18.0 → 19.0 on demo + Ledo realistic SMB seed

**Status**: 2026-05-16. This document captures the verifiable evidence
that the 18.0 → 19.0 OpenUpgrade migration works correctly for Ledoweb's
target customer profile.

## TL;DR

| Layer | Evidence | Result |
|---|---|---|
| Schema-level (OCA upstream demo seed) | `Test OpenUpgrade migration` fork workflow | ✅ green, 11m28s |
| Schema-level (Ledo edge-case seed) | `Test OpenUpgrade migration (enriched seed)` workflow | ✅ green, 9m03s |
| Schema-level (Ledo realistic SMB + OCA stack) | `Test OpenUpgrade migration (real SMB + OCA)` workflow | ✅ green, 5m50s |
| Behavioral AP workflow (XML-RPC) | AP-clerk migration loop, pre/post diff | ✅ NO DELTA |
| Behavioral AR workflow (XML-RPC) | AR-clerk migration loop, pre/post diff | ✅ NO DELTA |

All five gates run against the **actual** migration image
(`registry.hz.ledoweb.com/openupgrade/openupgrade:latest`) — the same
image Ledo prod migration day will use. No mocking.

## Schema-level proof — fork CI workflows

Integrated test branch `ledoent/19.0-mig-test-allopen` includes:

- `ledoent/aggregated` (origin/19.0 + our `ledoent` CI commits + all
  `19.0-fix-*` rollups) — carries 6 of our 7 open OCA PRs via cherry-picks
- hbrunn's PR #5612 `hr_recruitment` cherry-picked on top — the only
  third-party 19.0 PR currently open

All three workflows fired automatically on push to that branch; all
green. See:
[run 25966950427](https://github.com/ledoent/OpenUpgrade/actions/runs/25966950427) ·
[run 25966950429](https://github.com/ledoent/OpenUpgrade/actions/runs/25966950429) ·
[run 25966954561 (dispatch)](https://github.com/ledoent/OpenUpgrade/actions/runs/25966954561).

### Seeds used

| Asset | Size | Modules | Purpose |
|---|---|---|---|
| `18.0.psql` | 88 MB | OCA-curated | Upstream baseline |
| `18.0-ledoent.psql` | 88 MB | OCA-curated + edge cases | Catches data-preservation regressions OCA's vanilla seed misses |
| `18.0-ledoent-real.psql` | 6.5 MB | 124 CE modules | Realistic Ledo SMB CE-only shape |
| `18.0-ledoent-real-oca.psql` | 7.3 MB | 137 (CE + OCA) | What Ledo prod actually runs (full OCA stack) |

The `_real` seeds use targeted module installation (`scripts/install-targeted-modules.sh`)
instead of `--init=all` — avoids the 115-locale demo bloat that produced
1,965 picking types and 35k chart accounts on prior iterations. Resulting
DB matches realistic SMB shape: 2-3 companies, ~30 picking types, ~50
accounts, ~150 stock moves.

### Multi-company topology

`scripts/seed-multicompany-orm.py` establishes:

- **Wood Manufacturing Co.** (id=1, parent, US generic_coa)
  - **Wood Co. – Showroom** (branch, `parent_id=1`, shares parent COA)
- **Bimble Design Services Co.** (separate entity, own generic_coa install)

171 partners shared via `company_id=NULL`; admin user has
`allowed_company_ids=[1, 119, 120]`.

## Behavioral proof — `odoo-agent-clerks`

Private repo at `~/projects/ledoent/odoo-agent-clerks/`. Runs
deterministic per-role recipes against pre-migration + post-migration
DBs, diffs XML-RPC report snapshots, surfaces behavioral regressions
schema-level CI can't catch.

### AP clerk loop (2026-05-16T17:29Z)

Recipe: 3 vendor bills totaling $2,000.

```
## ap-clerk/ap-aging.csv          ✓ 4 rows match
## ap-clerk/ap-control-balance.csv ✓ 2 rows match
## ap-clerk/bills.csv             ✓ 5 rows match
## ap-clerk/payment-runs.csv      ✓ 0 rows match

Overall: ✅ NO DELTA
```

- Pre-migration: Wood AP balance = $2,000 credit on account `211000`
- Post-migration: same $2,000 credit, same aging bucket distribution
- AP control account, vendor names, payment_state, residual amounts:
  all preserved exactly

### AR clerk loop (2026-05-16T17:37Z)

Recipe: 3 customer invoices totaling $2,300.

```
## ar-clerk/invoices.csv          ✓ 4 rows match
## ar-clerk/ar-aging.csv          ✓ 3 rows match
## ar-clerk/ar-control-balance.csv ✓ 3 rows match
## ar-clerk/customer-payments.csv ✓ 6 rows match

Overall: ✅ NO DELTA
```

### Wall-clock budget per role

| Step | Time |
|---|---|
| Reset 18.0 DB from canonical seed | ~5s |
| Provision demo users | ~3s |
| Recipe execution + snapshot on 18.0 | ~10s |
| Dump + restore as `agent_test_19_target` | ~30s |
| **Run OpenUpgrade migration image** | **~3.5 min** |
| Start odoo-19 service | ~10s |
| Recipe + snapshot on 19.0 | ~10s |
| Diff | <2s |
| **Total per role** | **~5–6 min** |

## Coverage scope (honest)

### Module coverage on the fork

| Bucket | Count |
|---|---|
| `[19.0][MIG]` PRs merged into `origin/19.0` (all contributors) | 29 |
| Covered by our fork branches (not merged upstream) | ~158 |
| **Total with our coverage** | **~187 / 309** (~60%) |
| Deliberately skipped — non-US `l10n_*` (Ledo customers are US) | 71 |
| In flight upstream by others (hbrunn #5612 hr_recruitment) | 1 |
| Functional unclaimed (no fork branch, no upstream PR) | **1** — `partner_autocomplete` |

### Open OCA PRs (as of 2026-05-16)

Authored by Ledo (held as drafts per fork-only rule):

| # | Title | Status |
|---|---|---|
| #5633 | `website_*`: 31 uncharted modules | draft, CI green on fork |
| #5634 | `hr_*`: 13 simple submodules | draft, CI green on fork |
| #5635 | `hr_*`: overtime + skills refactor (4 submodules) | draft, CI green on fork |
| #5636 | `event_*`: 5 simple submodules | draft, CI green on fork |
| #5637 | `event`: slots + question m2m promotion | draft, CI green on fork |
| #5628 | `[IMP] hr`: backfill NULL create_date/write_date | draft |

Authored by others:

| # | Author | Title | State |
|---|---|---|---|
| #5612 | hbrunn | `hr_recruitment` | CI red upstream on stale `lift_constraints(cascade)` API; CI green on our fork after hbrunn's openupgradelib PR #446 was merged. Needs a rebase to re-trigger OCA CI. |

## What is NOT yet tested

Honest gap list — these would back stronger claims if we did them, but
they're separate work:

1. **UI navigation regression** — "does every menu still open and let
   the user progress a record post-migration?" We exercised XML-RPC
   recipes only. The chrome-devtools MCP UI path is Phase 5 of
   `odoo-agent-clerks` (deferred).
2. **7 of 9 behavioral roles** — only AP + AR currently have recipes
   and migration loops. Phase 3 of `odoo-agent-clerks` adds purchasing,
   production planner, inventory planner, sales, shipping, receiving,
   accounting.
3. **Parallel multi-role run** — single-role serial only. Lock
   contention and race conditions during concurrent role activity
   are surfaced by Phase 2.
4. **Real Kencove sanitized prod migration** — never executed. The
   30 GB Kencove DB is the actual prod-confidence test; this
   document covers demo + seeded SMB only.
5. **Non-US localizations** — 71 modules deferred. Any future
   non-US Ledo customer would need their locale's coverage filled in.

## Reproducing this proof

### Schema-level

```bash
# Watch the most recent run on the integrated branch
gh run list --repo ledoent/OpenUpgrade --branch 19.0-mig-test-allopen --limit 3

# Re-trigger by pushing a no-op to ledoent or re-dispatch the manual workflow:
gh workflow run test-migration-real-oca.yml \
  --repo ledoent/OpenUpgrade --ref 19.0-mig-test-allopen
```

### Behavioral

```bash
cd ~/projects/ledoent/odoo-agent-clerks
bash scripts/run-migration-loop.sh ap-clerk
bash scripts/run-migration-loop.sh ar-clerk
# Reports land in reports/migration-loop-<timestamp>.md
```

Each loop produces a `reports/diff-loop-<ts>-postwork-18-vs-postwork-19.md`
file. Green means migration preserved the role's workflow output.

## Provenance / pinning

For exact-reproducibility across future runs:

- Migration image: `registry.hz.ledoweb.com/openupgrade/openupgrade:latest`
  (built from `ledoent/aggregated` via fork's `build-image.yml`)
- Source seed: built from `odoo:18.0` Docker image
  (currently `18.0-20260513`) via `scripts/install-targeted-modules.sh`
- OCA modules at 18.0 pinned via `scripts/clone-oca-18.sh` —
  commit SHAs captured at clone time (see `/tmp/erp-src/*/` on runner)

Pinning at `:latest` is acceptable for now since we're not yet
running Ledo prod migration; pin to specific SHAs before any real
prod migration commitment.
