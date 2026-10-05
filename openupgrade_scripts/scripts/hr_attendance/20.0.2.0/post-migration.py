# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_validation = openupgrade.get_legacy_name("attendance_overtime_validation")


@openupgrade.migrate()
def migrate(env, version):
    """Carry whether extra hours need approving into 20.0's wider question.

    19.0 asked no_validation or by_manager. 20.0 asks no_validation,
    manual_validation or tolerance_validation, under a new name and so in a new
    column that takes the default. A company that required a manager to approve
    extra hours therefore comes out approving them automatically, and nothing
    says so: the setting is not shown as empty, it is shown as the other answer.

    Only by_manager is written. no_validation is already what the default gives,
    and tolerance_validation is 20.0's new middle ground, which no 19.0 database
    can have chosen.
    """
    if not openupgrade.column_exists(env.cr, "res_company", _legacy_validation):
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE res_company
        SET attendance_validation = 'manual_validation'
        WHERE {_legacy_validation} = 'by_manager'
        """,
    )
