# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "website_slides", "20.0.2.7/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "website_slides",
        ["mail_template_slide_channel_enroll", "mail_template_slide_channel_invite"],
        ["body_html"],
    )
