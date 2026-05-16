# ledoent fork — internal roadmap

**Scope**: this lives on the `ledoent` branch only. Not for upstream.
Captures fork-only validation work, OCA review backlog, and the
multi-tier seed plan. See `docsource/contributing.rst` for the upstream-
facing contribution guide.

**Last update**: 2026-05-16. Refresh after each major batch or weekly,
whichever comes first.

## Status snapshot

| Concern | State |
|---|---|
| `ledoent` branch | rebased onto `origin/19.0@8b85f42` + 18 custom CI commits |
| `mirror-upstream` cron | **fixed** (was 403 on issues; added `issues: write` permission) |
| `test-migration` workflow | green (baseline OCA seed) |
| `test-migration-enriched` workflow | green (our `18.0-ledoent.psql` seed) |
| Fork-test branches green | 25/25 last push |
| Open OCA PRs (Ledo authored) | 5 drafts: #5633, #5634, #5635, #5636, #5637 — left as drafts per fork-only rule |

## Coverage map (post-rebase, on `ledoent`)

```
309 modules with upgrade_analysis.txt        (the upstream catalog)
   29 [MIG] PRs merged into origin/19.0       (~9%)
   48 with upgrade_analysis_work.txt on us
   36 with pre/post/end-migration scripts
  187 modules touched by our 25 fork branches  (= what we've validated on CI)
   72 truly unclaimed — see "Unclaimed list" below
```

72 = 309 (catalog) − 187 (our fork) − 50 (overlap from upstream/our drafts).
71 of those 72 are non-US `l10n_*` (deliberately skipped — see
`CLAUDE.local.md` "skip non-US l10n_*" rule). **Functional unclaimed
count = 1**.

## Active TODO

### 1. Realistic multi-company SMB seed — **DONE 2026-05-16**

Earlier in the day we built `seed_18_woodbimble` (bloated, 631 modules / 115 demo companies / 1965 picking types) and its LARGE variant. Those revealed the install-all-modules approach deforms the seed: the auto-generated route/rule/picking-type explosion has nothing to do with realistic prod shape.

Pivot to **targeted-modules-only `seed_18_woodbimble_real`**:

- `scripts/install-targeted-modules.sh` — installs 25 curated CE modules (sale/purchase/stock/mrp/account/POS/HR + l10n_us). Result: 2 companies, 24 picking types, 11 routes, 51 chart accounts, 37 locations.
- `seed-multicompany-orm.py` — Wood + Showroom branch + Bimble. Bimble gets its own `generic_coa` install (8 journals).
- `seed-stock-topology.py` — Wood = 3-step receipt + 2-step ship; Showroom = 1-step; transit locations.
- `seed-operations-volume.py` — 96 SOs / 72 POs / 38 MOs / 129 pickings on Wood; 30 SOs / 24 pickings on Showroom; 1,647 mail.message total.
- `clone-oca-18.sh` — 20 OCA repos cloned at 18.0 into `/tmp/erp-src/` (skips removed `odoo-cloud-platform`).
- `seed-oca-assets-rma.py` — 25 fixed assets + 150 depreciation lines + 3 RMA cases on Wood; `mis_builder` + `account_reconcile_oca` + `account_lock_date_update` installed.

**Dumps live on fork release**:
- `18.0-ledoent-real.psql` (6.5 MB) — CE-only realistic SMB.
- `18.0-ledoent-real-oca.psql` (7.3 MB) — same + OCA stack.

**Retired (kept on release as historical baselines, no longer in CI)**:
- `18.0-ledoent-mc.psql`, `18.0-ledoent-mc-large.psql` — bloated 115-locale demos. Workflows `test-migration-multicompany.yml` + `test-migration-multicompany-large.yml` deleted from `ledoent` branch.

**Active CI shape**:
- Auto (push): `test-migration.yml` (OCA baseline) + `test-migration-enriched.yml` (single-company edge cases on `18.0-ledoent.psql`).
- Manual (workflow_dispatch): `test-migration-real-oca.yml` against `18.0-ledoent-real-oca.psql`. Use before Ledo prod migration commitment or for OCA PR reviews where multi-company / asset / RMA depth matters.

**Honest caveat**: `_real-oca` has FEWER modules installed (137 vs 631 in the bloated seed). Migrations whose pre/post scripts ONLY fire on modules like `l10n_fr`, `l10n_in`, `event_*`, `website_*` won't be exercised on `_real-oca`. For upstream-PR-breadth coverage, `test-migration-enriched.yml` against `18.0-ledoent.psql` still carries the load (single-company but module-broad).

### 2. Stale fork-test branches — rebase candidates (low priority hygiene)
8 fork-test branches are `behind=5–6` vs `ledoent/aggregated` because they
predate the rollup merges. Code under test unaffected. Rebase for fresh
CI confidence only:
- `19.0-mig-test-account-trivial`
- `19.0-mig-test-auth-deps-trivial`
- `19.0-mig-test-comms-trivial`
- `19.0-mig-test-crm-delivery-sale-trivial`
- `19.0-mig-test-event-family-trivial`
- `19.0-mig-test-hr-trivial`
- `19.0-mig-test-payment-gateways`
- `19.0-mig-test-project-suite`

### 3. OCA-stacked seed (Tier 2) — planned, not started
Build `seed_18_woodbimble_oca` with the Ledo prod OCA stack
(account-financial-reporting, account-financial-tools, account-reconcile,
bank-statement-import, mis-builder, reporting-engine, server-tools,
server-ux, web, social, sale-workflow, e-commerce, dms, knowledge,
spreadsheet, storage, connector-telephony, odoo-cloud-platform, server-env,
calendar). Tracks Ledo prod surface area for migration validation.

- New script: `scripts/clone-oca-18.sh` (or aggregator config `repos-oca-18.yaml`).
- New CI: `test-migration-enriched-oca.yml`, fork-only.
- New release asset: `18.0-ledoent-mc-oca.psql`.
- Defer until CE-only seed proven through Phase D.

### 4. Mass real-prod calibration (Kencove-scale)
After both seeds prove out, dry-run on a sanitized Kencove 30 GB snapshot
via the runner. Goal: success-probability calibration before any real
prod migration commitment.

## Unclaimed upstream — review list

These have `upgrade_analysis.txt` in `origin/19.0` but **no work doc**,
**no pre/post script**, and **not touched by any of our fork branches**.
Use this list to plan the next pickup (or defer per skip-rule).

### Functional priority (non-l10n) — 1 module
| Module | Status | Action |
|---|---|---|
| `partner_autocomplete` | analysis present, no claimant | scout — likely a Tier C annotation-only batch; check upstream PR before claiming |

### Localizations skipped per fork rule — 71 modules
Non-US l10n_* are deliberately deferred. Pickup criterion: only when
Ledo onboards a customer in that locale. List preserved for completeness:

`l10n_ae`, `l10n_ar`, `l10n_ar_stock`, `l10n_ar_website_sale`, `l10n_at`,
`l10n_br`, `l10n_br_website_sale`, `l10n_cd`, `l10n_ci`, `l10n_cl`,
`l10n_cr`, `l10n_cz`, `l10n_din5008_expense`, `l10n_dk_oioubl`,
`l10n_ec`, `l10n_ec_sale`, `l10n_ee`, `l10n_eg_edi_eta`,
`l10n_es_edi_facturae`, `l10n_fr`, `l10n_fr_account`, `l10n_gcc_invoice`,
`l10n_gcc_invoice_stock_account`, `l10n_gcc_pos`, `l10n_gr`, `l10n_hu`,
`l10n_id_efaktur_coretax`, `l10n_il`, `l10n_in`, `l10n_in_edi`,
`l10n_in_ewaybill`, `l10n_in_ewaybill_irn`, `l10n_in_ewaybill_stock`,
`l10n_in_hr_holidays`, `l10n_in_pos`, `l10n_in_sale`, `l10n_iq`,
`l10n_it`, `l10n_it_edi`, `l10n_jo`, `l10n_jo_edi`, `l10n_latam_base`,
`l10n_latam_check`, `l10n_latam_invoice_document`, `l10n_lk`, `l10n_ma`,
`l10n_ml`, `l10n_mx`, `l10n_my`, `l10n_my_edi`, `l10n_my_edi_pos`,
`l10n_nl`, `l10n_pe`, `l10n_ph`, `l10n_pk`, `l10n_ro_cpv_code`,
`l10n_ro_edi`, `l10n_sa`, `l10n_sa_edi`, `l10n_sg`, `l10n_si`,
`l10n_sk`, `l10n_th`, `l10n_tr_nilvera`, `l10n_tr_nilvera_edispatch`,
`l10n_tr_nilvera_einvoice`, `l10n_tr_nilvera_einvoice_extended`,
`l10n_tw`, `l10n_ug`, `l10n_uz`.

### Likely-overlapping with `hr_recruitment` upstream PR
Already opened by hbrunn upstream as **#5612** (`19.0-hr_recruitment`).
Don't duplicate — review and watch that PR instead.

## Open OCA PRs to review

### Authored by Ledo (held as drafts per fork-only rule)
| # | Title | State | Note |
|---|---|---|---|
| #5633 | `[19.0][MIG] website_*`: 31 uncharted modules | draft | Validated on fork CI; held |
| #5634 | `[19.0][MIG] hr_*`: 13 simple submodules | draft | Validated on fork CI; held |
| #5635 | `[19.0][MIG] hr_*`: overtime + skills refactor | draft | Validated on fork CI; held |
| #5636 | `[19.0][MIG] event_*`: 5 simple submodules | draft | Validated on fork CI; held |
| #5637 | `[19.0][MIG] event`: slots + question m2m promotion | draft | Validated on fork CI; held |

### Third-party open 19.0 PRs (as of 2026-05-16)

The OCA upstream queue is quiet. **One** third-party 19.0 PR open:

| # | Author | Title | Updated | Status |
|---|---|---|---|---|
| #5612 | hbrunn | `[19.0][MIG] hr_recruitment` | 2026-05-08 | Reviewed by us 2026-05-16; OCA CI red on stale `lift_constraints(cascade)` API; fork CI **green** on current openupgradelib master (hbrunn's own openupgradelib PR #446 added cascade support post-PR). PR needs only a rebase to re-trigger OCA CI. Multi-company branch traversal in `candidate_properties_definition` merge is a real flag worth raising. |

Refresh by running:
```bash
gh pr list --repo OCA/OpenUpgrade --state open --search "19.0 in:title" \
  --json number,title,author,updatedAt
```

## CI infra reference

| Workflow | Trigger | Purpose |
|---|---|---|
| `mirror-upstream.yml` | daily 06:00 UTC | Push `origin/19.0` → `ledoent/19.0`. Open issue if `ledoent` branch drifts. **Now has `issues: write`**. |
| `aggregate.yml` | push to `ledoent` / `19.0-fix-*` | Run gitaggregator → push `aggregated` branch. |
| `test-migration.yml` | push to `19.0-mig-*` / `19.0-fix-*` / `aggregated` / `ledoent` | Baseline OCA 18.0.psql migration test. |
| `test-migration-enriched.yml` | same | Same migration but on our enriched `18.0-ledoent.psql`. |
| `build-image.yml` | repository_dispatch from aggregate | Build & push `registry.hz.ledoweb.com/openupgrade/openupgrade:latest`. |
| `generate-analysis-cron.yml` | weekly | Refresh `upgrade_analysis.txt` files. |

## Drift / hygiene rules

- Re-check `ledoent` vs `origin/19.0` drift weekly. The mirror cron now
  opens an issue automatically when behind.
- Don't open new OCA PRs (CLAUDE.local.md rule, set 2026-05-15).
  Existing drafts stay drafts.
- Don't merge orphan-cleanup migrations (pedrobaeza policy — rejected
  #5630–5632; database_cleanup handles residuals).
- Skip non-US `l10n_*` until business case appears.
