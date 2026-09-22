# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "website_sale", "20.0.1.1/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "website_sale",
        ["mail_template_sale_cart_recovery"],
        ["body_html", "subject"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "website_sale",
        ["ir_cron_send_availability_email"],
        ["name"],
    )
