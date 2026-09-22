# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "payment_custom", "20.0.2.0/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "payment_custom",
        ["payment.payment_provider_pay_on_invoice"],
        ["done_msg"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "payment_custom",
        ["payment.payment_provider_transfer"],
        ["pending_msg"],
    )
