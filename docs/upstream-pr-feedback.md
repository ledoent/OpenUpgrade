# Posting fork-CI feedback on OCA PRs

When you've run an OCA PR through `scripts/test-upstream-pr.sh <N>`,
paste one of these templates into the OCA PR thread. Adjust the bullets
to whatever's actually relevant for that PR's surface.

The point of these comments is **real-data evidence**, not style review:
"your migration ran against cancelled-state moves, branch trees, and
cross-company partners — here's what happened." OCA reviewers see plenty
of `lgtm`; almost none of them see "tested against multi-company prod
shape."

## Both fork CI jobs green

> Ran this PR through our fork's enriched migration CI on top of the standard 18.0 seed:
>
> - **Baseline migration** ([run](LINK)) — green.
> - **Enriched migration** ([run](LINK)) — green, against `18.0-ledoent.psql` which adds:
>   - 10 `account.tax` rows with legacy `VATEX_*` selection values
>   - `crm.stage.team_id` populated on demo stages
>   - cancelled `account.move` rows (the demo has zero)
>   - archived `res.partner` + `product.template` (active=FALSE edge case)
>   - `res.partner.bank.aba_routing` populated for preservation testing
>   - `im_livechat.channel.rule.chatbot_only_if_no_operator = TRUE`
>   - `pos.payment.method` rows with `viva_wallet_*` credentials
> - *(multi-company tier coming once `18.0-ledoent-mc.psql` lands)*
>
> Code looks good to me. LGTM for the data-preservation surface.

## Fork CI red — actionable

> Pulled this PR into our fork and ran it through our enriched seed CI:
>
> - **Baseline migration** ([run](LINK)) — `STATUS_HERE`
> - **Enriched migration** ([run](LINK)) — `STATUS_HERE`
>
> The enriched run hit `<specific error>`. Reproducer in the log around line `<LINE>`. Looks like the migration assumes `<condition>` but our seed has `<counter-example>`. Repro locally with our seed dump:
>
> ```
> wget https://github.com/ledoent/OpenUpgrade/releases/download/databases/18.0-ledoent.psql
> # restore + re-run migration
> ```
>
> Happy to test any follow-up commits.

## Multi-company / branch surface (once `seed_18_woodbimble` lands)

> Tested this PR against our multi-company fork seed (`18.0-ledoent-mc.psql`) on top of the standard runs:
>
> - **Wood Manufacturing Co.** (US, generic_coa) parent
> - **Wood Co. — Showroom** (branch, `parent_id` set, shares parent COA)
> - **Bimble Design Services Co.** (separate entity, own COA install)
> - 20 partners with cross-company reach via `res_partner_res_company_rel`
> - Admin user with `allowed_company_ids` spanning all three
>
> Run: [LINK] — `STATUS`.
>
> Notable: `<observed behavior on the branch-scoped rows>` / `<cross-company partner outcome>`. Catches the surface that OCA's vanilla demo doesn't have (single flat company, zero branches).

## After OCA-stacked seed lands

> Also tested against our OCA-stacked seed (`18.0-ledoent-mc-oca.psql`) which adds the typical Ledo prod OCA stack: `account-financial-reporting`, `account-financial-tools`, `account-reconcile`, `bank-statement-import`, `mis-builder`, `reporting-engine`, `server-tools`, `server-ux`, `web`, `social`, etc. on top of multi-company.
>
> Run: [LINK] — `STATUS`.
>
> This is the closest signal we have to a real Ledo prod migration. `<observations>`.

## Tone notes

- Lead with the result (green/red), not the methodology.
- Link runs by full URL so reviewers can click without `gh` access.
- If red, **never** speculate on the fix in the comment — say what
  broke and where, let the PR author decide. Speculation reads as
  "do my thinking for me."
- Don't comment on style or conventions in these reports — that's
  OCA reviewers' job. We're providing data, not opinion.
- If their PR is already approved upstream, our comment is "extra
  signal, not a blocker." Phrase accordingly.
