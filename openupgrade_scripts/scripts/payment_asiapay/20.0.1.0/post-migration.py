# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "payment_asiapay", "20.0.1.0/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "payment_asiapay",
        [
            "payment_method_bangkok_bank",
            "payment_method_jkopay",
            "payment_method_krungthai_bank",
            "payment_method_maybank",
            "payment_method_pace",
            "payment_method_scb",
            "payment_method_tenpay",
            "payment_method_tmb",
            "payment_method_ttb",
        ],
        ["name"],
    )
