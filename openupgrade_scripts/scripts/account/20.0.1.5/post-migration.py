# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


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
