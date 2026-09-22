# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _fill_attendance_duration_hours(env):
    """resource.calendar.attendance.duration_hours becomes a stored column in 20.0.

    19.0 computed it without storing it, so the column 20.0 adds starts at 0,
    and 20.0 also adds CHECK(duration_hours > 0 AND duration_hours <= 24). The
    upgrade reports "Constraint not added: check constraint
    resource_calendar_attendance_check_duration_hours ... is violated by some
    row" and carries on without it, leaving every untouched attendance reading
    as zero hours long.

    The rule is 20.0's own _compute_duration_hours::

        if not attendance.duration_based:
            attendance.duration_hours = max(
                0, attendance.hour_to - attendance.hour_from)

    duration_based is the case where 20.0 lets the user type the duration in
    directly rather than derive it, so those rows are left alone -- the compute
    does not touch them either.

    Note the compute can itself produce a 0 that the new constraint forbids, for
    an attendance whose hours are equal. Nothing is invented for those here: a
    zero-length attendance is a 19.0 data question, not a rename, and the count
    is reported so it is visible rather than silently rewritten.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar_attendance
        SET duration_hours = greatest(0, hour_to - hour_from)
        WHERE NOT duration_based
          AND coalesce(duration_hours, 0) = 0
          AND hour_to > hour_from
        """,
    )
    env.cr.execute(
        """
        SELECT count(*) FROM resource_calendar_attendance
        WHERE NOT (duration_hours > 0 AND duration_hours <= 24)
        """
    )
    left = env.cr.fetchone()[0]
    if left:
        openupgrade.message(
            env.cr,
            "resource",
            False,
            False,
            "%s resource.calendar.attendance rows are still outside the 0-24 hour "
            "range 20.0 requires; they had no usable hour_from/hour_to to derive "
            "a duration from",
            left,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "resource", "20.0.1.1/noupdate_changes.xml")
    _fill_attendance_duration_hours(env)
