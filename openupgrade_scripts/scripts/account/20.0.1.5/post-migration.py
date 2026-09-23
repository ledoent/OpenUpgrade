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
