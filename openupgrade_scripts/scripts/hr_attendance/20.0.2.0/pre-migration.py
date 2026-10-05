# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # 19.0's attendance_overtime_validation said whether extra hours needed a
    # manager's approval. 20.0 asks the same question under a different name,
    # attendance_validation, with a third answer added. Being a different
    # column, it takes its own default and the answer is not carried, so
    # post-migration reads this one back.
    if openupgrade.column_exists(
        env.cr, "res_company", "attendance_overtime_validation"
    ):
        openupgrade.rename_columns(
            env.cr, {"res_company": [("attendance_overtime_validation", None)]}
        )
