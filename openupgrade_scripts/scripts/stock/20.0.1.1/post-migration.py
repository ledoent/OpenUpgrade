# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "stock", "20.0.1.1/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "stock",
        ["mail_template_data_delivery_confirmation"],
        ["body_html"],
    )
