# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "payment_buckaroo", "20.0.2.0/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "payment_buckaroo",
        ["payment_method_wero"],
        ["name"],
    )
