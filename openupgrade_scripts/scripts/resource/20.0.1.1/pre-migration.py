# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# resource.calendar.tz is dropped in 20.0 and the timezone moves to
# res.company.tz. The value is needed after the ORM has created the new column,
# so keep it rather than relying on Odoo's habit of leaving dropped columns in
# place -- post-migration reads the legacy name.
_copied_columns = {
    "resource_calendar": [("tz", None, None)],
}


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.copy_columns(env.cr, _copied_columns)
