# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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
