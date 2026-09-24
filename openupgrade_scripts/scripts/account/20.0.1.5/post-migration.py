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
    would assert a review of every posted invoice in the database -- 3206 of the
    seed's 3223 moves, on the strength of a value that is really just "posted".
    A posted move whose `checked` is FALSE is the opposite: the compute would
    have set it True, so False is there because somebody put it there, and
    'todo' is what 20.0 calls that.

    Nothing is written for a draft move. 19.0 left those unchecked by the same
    formula, which says "not posted yet", not "waiting to be reviewed".

    **This seed contains no such row** -- `checked` equals `state = 'posted'` on
    all 3223 of its moves -- so the branch is unreachable here and the migration
    test builds the row that reaches it. The count is reported either way, so a
    database where it does fire says so in the log rather than only in the data.
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
