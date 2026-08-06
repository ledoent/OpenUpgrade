from openupgradelib import openupgrade

# 18.0 attendance-based hourly accrual (frequency='hourly' +
# frequency_hourly_source='attendance') became the dedicated 'worked_hours'
# frequency key in 19.0; without the remap those levels silently degrade to
# calendar-hourly and accrue wrong amounts.


@openupgrade.migrate()
def migrate(env, version):
    if openupgrade.column_exists(
        env.cr, "hr_leave_accrual_level", "frequency_hourly_source"
    ):
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE hr_leave_accrual_level
            SET frequency = 'worked_hours'
            WHERE frequency = 'hourly'
              AND frequency_hourly_source = 'attendance'
            """,
        )
