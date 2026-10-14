# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError

from openupgradelib import openupgrade


def _settle_in_process_payments(env):
    """19.0's payment state had an "In Process" step that 20.0 does not.

    19.0 ran draft -> in_process -> paid; 20.0 runs draft -> paid ->
    reconciled. The middle step is gone, and because the column already holds a
    value the stored compute leaves it there: the payment reads as blank in the
    interface and matches no branch of a domain over the state.

    'paid' is the honest landing point. It states only what is certainly true --
    the payment was made -- and 20.0's own _compute_state takes it from there:
    for a payment already in 'paid' or 'reconciled' it re-derives which of the
    two applies from the liquidity lines' residual. Writing 'reconciled'
    directly would assert a bank match this migration has no evidence for.
    """
    openupgrade.logged_query(
        env.cr,
        "UPDATE account_payment SET state = 'paid' WHERE state = 'in_process'",
    )


def _carry_a_deliberate_not_reviewed_into_the_review_queue(env):
    """19.0's `checked` becomes 20.0's review_state, and only part of it is real.

    19.0 carried a boolean "Reviewed". It was a stored COMPUTE with the value
    written by::

        move.checked = move.state == 'posted' and (
            move.journal_id.type == 'general' or move._is_user_able_to_review())

    and `readonly=False`, so a user could tick or untick it afterwards.

    20.0 replaces it with `review_state`, a plain stored selection of no_review
    / todo / reviewed / supervised / anomaly defaulting to 'no_review', and
    keeps an index named after the field it replaced::

        _checked_idx = models.Index(
            "(journal_id) WHERE (review_state IN ('todo', 'anomaly'))")

    which is what makes it a work queue rather than a label.

    **Only the deviation is carried.** A True that merely reproduces the compute
    records nothing a reader could not derive, and writing 'reviewed' for it
    would assert a review of every posted invoice in the database -- 7907 of the
    prod copy's 7958 moves, on the strength of a value that is really just
    "posted". A posted move whose `checked` is FALSE is the opposite: the compute
    would have set it True, so False is there because somebody put it there, and
    'todo' is what 20.0 calls that.

    Nothing is written for a draft move. 19.0 left those unchecked by the same
    formula, which says "not posted yet", not "waiting to be reviewed".

    **Measured on erp_mig20test (the sanitised prod copy) 2026-10-02:** `posted
    AND NOT checked` is **0 rows**, so the branch is unreachable on this data too
    and the migration test builds the row that reaches it. The count is reported
    either way, so a database where it does fire says so in the log rather than
    only in the data.

    `checked` is NOT simply `state = 'posted'` here, which an earlier draft of
    this docstring asserted against a 3223-move seed: 45 cancelled moves and 1
    draft carry `checked = TRUE`, because 19.0's field was `readonly=False` and a
    move can be checked and then cancelled. None of them is `posted AND NOT
    checked`, so none changes what this script writes -- but the shape is worth
    stating, because "checked == posted" is the assumption that would make
    carrying the True side look harmless.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_move
        SET review_state = 'todo'
        WHERE state = 'posted' AND NOT checked AND review_state = 'no_review'
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "account",
            False,
            False,
            "%s posted journal entr(ies) had been marked as NOT reviewed by hand "
            "in 19.0 and are now in 20.0's review queue as 'todo'; entries that "
            "merely carried the computed default were left on 'no_review'",
            env.cr.rowcount,
        )


def _modernise_reconcile_model_rule_type(env):
    """20.0 re-introduces rule_type with a new vocabulary and makes it the master.

    The field has an unusual history, and reading it as a 19->20 rename gets it
    wrong. 18.0 had `rule_type` as writeoff_button / writeoff_suggestion /
    invoice_matching. **19.0 core removed it entirely**, replacing it with
    `trigger` (manual / auto_reconcile) -- and because a removed field's column
    is left in place, the 18.0 values sat dormant in the table for the whole 19.0
    cycle. 20.0 then brings `rule_type` BACK, as matching_rule / reco_model.

    So the values being mapped here are 18.0's, not 19.0's, and 20.0 inverts
    which field is authoritative::

        @api.depends('rule_type')
        def _compute_trigger(self):
            model.trigger = ('auto_reconcile'
                             if model.rule_type == 'matching_rule' else 'manual')

    `trigger` is now a stored compute over `rule_type`, with a constraint that
    "Matching rules must be automatic". Left alone, every row takes 20.0's
    default of reco_model and every trigger recomputes to `manual` -- automatic
    bank reconciliation silently stops for rules that had been doing it.

    The mapping follows 18.0's own meaning rather than the current trigger:

        invoice_matching    -> matching_rule   (the rule that matches invoices)
        writeoff_button     -> reco_model      (a manual write-off preset)
        writeoff_suggestion -> reco_model      (a suggested write-off preset)

    `trigger` is then written to agree with what `_compute_trigger` would
    produce. That consistency is the point: leaving a reco_model row on
    auto_reconcile violates no constraint, so it would survive the upgrade and
    then flip to manual the first time anyone edited the model -- a silent change
    weeks later instead of a visible one now.
    """
    if not openupgrade.column_exists(env.cr, "account_reconcile_model", "rule_type"):
        return
    mapping = {
        "invoice_matching": ("matching_rule", "auto_reconcile"),
        "writeoff_button": ("reco_model", "manual"),
        "writeoff_suggestion": ("reco_model", "manual"),
    }
    for legacy, (rule_type, trigger) in mapping.items():
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE account_reconcile_model
            SET rule_type = %s, trigger = %s
            WHERE rule_type = %s
            """,
            (rule_type, trigger, legacy),
        )
    env.cr.execute(
        """
        SELECT count(*) FROM account_reconcile_model
        WHERE rule_type NOT IN ('matching_rule', 'reco_model')
        """
    )
    left = env.cr.fetchone()[0]
    if left:
        openupgrade.message(
            env.cr,
            "account",
            False,
            False,
            "%s account.reconcile.model row(s) hold a rule_type neither 18.0 nor "
            "20.0 declares, so they were left as they are rather than guessed at",
            left,
        )


def _drop_obsolete_journal_group_company_rule(env):
    """Delete a 19.0 record rule whose field 20.0 removed.

    19.0 shipped account.journal_group_comp_rule, a GLOBAL rule on
    account.journal.group with
        ['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]
    20.0 drops company_id from account.journal.group entirely -- the model has no
    company field at all now -- and deletes the rule along with it. Its
    security/ir.access.csv keeps only three plain group rows for that model.

    The rule survives the upgrade anyway, and that is not cosmetic. Every
    non-superuser search on account.journal.group then dies in domain
    optimisation with KeyError: 'company_id'. Core itself searches that model
    while building a view: account.move.line._get_view does
    `self.env['account.journal.group'].search([])` to add the Ledger filters to
    the SEARCH view. So loading any account.move.line search view raises for an
    ordinary user -- Journal Items, and anything that drills into move lines.
    Measured on a production copy: mis_builder's report preview 500s, and the
    only reason it looks like a mis_builder bug is that mis_builder is what
    happened to open the view first.

    WHY NOTHING ELSE CLEANS THIS UP, which is the part worth remembering: the
    ir.model.access + ir.rule -> ir.access conversion writes its ir_model_data
    rows with noupdate=true, and _process_end's obsolete-record sweep selects
    `COALESCE(noupdate, false) != true` (odoo/addons/base/models/ir_model.py).
    It skips noupdate records by design. So an obsolete SECURITY record can
    never be removed by the normal mechanism -- it has to be deleted here.

    Written against the field rather than the id: if a database somehow still
    has company_id on that model, its rule is still meaningful and is left
    alone.
    """
    if "company_id" in env["account.journal.group"]._fields:
        return
    rule = env.ref("account.journal_group_comp_rule", raise_if_not_found=False)
    if not rule:
        return
    openupgrade.logged_query(
        env.cr,
        "DELETE FROM ir_access WHERE id = %s",
        (rule.id,),
    )
    openupgrade.logged_query(
        env.cr,
        "DELETE FROM ir_model_data WHERE model = 'ir.access' AND res_id = %s",
        (rule.id,),
    )


def _rescale_the_deductibility_from_percent_to_fraction(env):
    """deductible_amount was 0-100; deductible_percentage is 0-1.

    19.0 stored a percentage and its consumer divided: `percentage = 1 -
    line.deductible_amount / 100` (19.0 account_move.py:1731), with a 0..100
    constraint. 20.0 renamed the idea to deductible_percentage and made it a
    FRACTION, default 1.0, constrained `< 0 or > 1`
    (account_move_line.py:480, :1973).

    The analysis reports a DEL/NEW pair rather than a rename, so the new column
    simply took its default on every row and the 19.0 figure stayed behind in
    its own. Left alone, a line a bookkeeper marked 50% deductible reads as
    fully deductible, and 20.0 claims the whole VAT on a mixed-use expense.

    Two things bound what is written. 20.0 also constrains a non-purchase
    document to exactly 1 ("Only vendor bills allow for deductibility of
    product/services.", :1971), so only in_invoice / in_refund / in_receipt
    lines -- get_purchase_types(include_receipts=True) -- are rescaled; a sales
    line carrying a stray 19.0 value is reported instead, because writing it
    would make the move unsavable. And 100 is 19.0's own default, which maps to
    20.0's, so those rows are already right and are left alone.

    Measured on the sanitised prod copy 2026-10-02: deductible_amount is 100 on
    all 16648 lines and deductible_percentage 1.0 on all 16648 -- the two
    defaults agreeing by coincidence, which is exactly why this would pass
    unnoticed. The migration test plants the row that reaches the branch.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_move_line l
        SET deductible_percentage = l.deductible_amount / 100.0
        FROM account_move m
        WHERE m.id = l.move_id
          AND m.move_type IN ('in_invoice', 'in_refund', 'in_receipt')
          AND l.deductible_amount IS NOT NULL
          AND l.deductible_amount != 100
        """,
    )
    rescaled = env.cr.rowcount
    if rescaled:
        openupgrade.message(
            env.cr,
            "account",
            False,
            False,
            "account.move.line: rescaled %s line(s) from 19.0's 0-100 "
            "deductible_amount to 20.0's 0-1 deductible_percentage; without it "
            "each would have claimed full VAT deductibility",
            rescaled,
        )
    env.cr.execute(
        """
        SELECT count(*)
        FROM account_move_line l
        JOIN account_move m ON m.id = l.move_id
        WHERE m.move_type NOT IN ('in_invoice', 'in_refund', 'in_receipt')
          AND l.deductible_amount IS NOT NULL
          AND l.deductible_amount != 100
        """
    )
    unsalvageable = env.cr.fetchone()[0]
    if unsalvageable:
        openupgrade.message(
            env.cr,
            "account",
            False,
            False,
            "account.move.line: %s line(s) carry a 19.0 deductible_amount other "
            "than 100 on a document that is not a vendor bill. 20.0 forbids "
            "deductibility there, so the value was left in the legacy column "
            "rather than written into a move that could then not be saved",
            unsalvageable,
        )


def _keep_archived_reports_archived(env):
    """account.report.active stops being stored, so an archived report revives.

    19.0 had a plain `active = fields.Boolean(default=True)`. 20.0 makes it
    company-dependent and non-stored: active is a compute/compute_sql/inverse
    over active_fallback and active_selection, with _compute_active returning
    `active_selection == 'True' or active_fallback`
    (account_report.py:378-381).

    20.0 names the carrier itself. Its loader refuses data writes to the field
    with "'active' field of account.report shouldn't be directly written to in
    data files. Use active_fallback." -- and active_fallback takes its default
    True on every row, so a report an administrator archived in 19.0 comes back.

    Only the False side is written. A True merely reproduces the default, and
    the 19.0 column survives untouched because the field is no longer stored,
    which is what makes it readable here at all.

    All 4 reports are active on the prod copy, so the migration test is what
    exercises this.
    """
    if not openupgrade.column_exists(env.cr, "account_report", "active"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE account_report SET active_fallback = false
        WHERE NOT active AND active_fallback
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "account",
            False,
            False,
            "account.report: kept %s report(s) archived. 20.0 reads the archive "
            "flag through active_fallback, whose default would have brought them "
            "back into every report menu",
            env.cr.rowcount,
        )


def _carry_the_gln_into_additional_identifiers(env):
    """account_add_gln is absorbed and its column stops being read.

    20.0 did what the OCA module's own 19.0 manifest promised: account now
    declares global_location_number itself (account/models/partner.py:615-620)
    as a NON-STORED compute whose body is
    `_get_additional_identifier('EAN_GLN')` (:677-679). The 19.0 column survives
    but nothing reads it, so a stored GLN becomes invisible.

    The Json key is written directly rather than through
    _set_additional_identifier, which validates with ean.validate and raises
    ValidationError on a bad check digit -- one legacy typo would abort the
    whole upgrade. Each value is probed first with
    `_validate_identifier(..., validation=False)`, which reports rather than
    raises, and anything that fails is left in the legacy column and counted.
    That matters because `@api.constrains('additional_identifiers')`
    revalidates every key on write: a bad GLN written here would make the
    partner unsavable rather than merely unmigrated.

    Unlike the country-scoped identifiers, EAN_GLN declares `countries: False`,
    so it stays visible on the form for every partner.

    NULL on all 840 partners of the prod copy, so the migration test is what
    exercises this.
    """
    if not openupgrade.column_exists(env.cr, "res_partner", "global_location_number"):
        return
    env.cr.execute(
        """
        SELECT id, global_location_number FROM res_partner
        WHERE global_location_number IS NOT NULL AND global_location_number != ''
        """
    )
    rows = env.cr.fetchall()
    if not rows:
        return
    partner_model = env["res.partner"]
    carried = rejected = 0
    for partner_id, gln in rows:
        check = partner_model._validate_identifier("EAN_GLN", gln, validation=False)
        if not check["valid"]:
            rejected += 1
            continue
        partner = partner_model.browse(partner_id)
        try:
            partner.additional_identifiers = {
                **(partner.additional_identifiers or {}),
                "EAN_GLN": check["value"],
            }
        except ValidationError:
            rejected += 1
            continue
        carried += 1
    if carried:
        openupgrade.message(
            env.cr,
            "account",
            False,
            False,
            "res.partner: carried the GLN of %s partner(s) into "
            "additional_identifiers['EAN_GLN'], which is where 20.0 reads it "
            "from now that account_add_gln is part of account",
            carried,
        )
    if rejected:
        openupgrade.message(
            env.cr,
            "account",
            False,
            False,
            "res.partner: %s partner(s) hold a global_location_number that fails "
            "20.0's EAN check digit, so it was left in the legacy column rather "
            "than written into a Json whose constraint would then block every "
            "save of the partner",
            rejected,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "account", "20.0.1.5/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "account",
        ["email_template_edi_invoice", "email_template_edi_self_billing_invoice"],
        ["body_html"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "account",
        ["mail_template_data_payment_receipt"],
        ["body_html", "subject"],
    )
    _settle_in_process_payments(env)
    _carry_a_deliberate_not_reviewed_into_the_review_queue(env)
    _modernise_reconcile_model_rule_type(env)
    _drop_obsolete_journal_group_company_rule(env)
    _rescale_the_deductibility_from_percent_to_fraction(env)
    _keep_archived_reports_archived(env)
    _carry_the_gln_into_additional_identifiers(env)
