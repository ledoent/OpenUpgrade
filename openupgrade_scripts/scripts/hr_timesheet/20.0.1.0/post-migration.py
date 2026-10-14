# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "hr_timesheet", "20.0.1.0/noupdate_changes.xml")
    openupgrade.delete_record_translations(
        env.cr,
        "hr_timesheet",
        [
            "group_hr_timesheet_approver",
            "group_hr_timesheet_user",
            "group_timesheet_manager",
        ],
        ["comment"],
    )
