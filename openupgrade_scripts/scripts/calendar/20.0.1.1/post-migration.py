# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "calendar", "20.0.1.1/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "calendar",
        [
            "calendar_template_meeting_changedate",
            "calendar_template_meeting_invitation",
            "calendar_template_meeting_reminder",
            "calendar_template_meeting_update",
        ],
        ["body_html"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "calendar",
        ["calendar_template_delete_event"],
        ["body_html", "name", "subject"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "calendar",
        ["subtype_invitation"],
        ["name"],
    )
