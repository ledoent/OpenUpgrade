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

### 1. Multi-company seed — **DONE 2026-05-16**
- Phase A: `seed_18_woodbimble` built on Hetzner (CE-all, 631 modules installed, demo data on). ~20 min.
- Phase B: `scripts/seed-multicompany-orm.py` ran: Wood Manufacturing Co. parent, Wood Co. – Showroom branch (`parent_id=1`), Bimble Design Services Co. separate entity with `generic_coa` installed (8 journals). 171 partners shared via `company_id=NULL`. Admin `allowed_company_ids = [1, 119, 120]`.
- Phase C: `18.0-ledoent-mc.psql` (19 MB) uploaded to fork release. Existing assets backed up at `lab/backups/release-assets-2026-05-16/`.
- Phase D: `.github/workflows/test-migration-multicompany.yml` live; first run triggered on `ledoent` branch push.

### 1b. Multi-company LARGE seed — **DRAFTED 2026-05-16**
- `scripts/seed-multicompany-large.py` ready: 2-level branch nesting (Wood → US East → NJ Warehouse), per-branch `account.move` history, 3 intercompany draft invoices, products pinned per-branch, cross-company `res.partner.bank` rows.
- `.github/workflows/test-migration-multicompany-large.yml` wired with `workflow_dispatch` only — manual on-demand testing.
- Not yet run / dumped — runs against `seed_18_woodbimble` (after the `-mc` Phase B). Produces `18.0-ledoent-mc-large.psql`.
- **Next**: run the script on Hetzner; dump + upload; use to retest PR #5612 against the multi-company branch surface.

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
