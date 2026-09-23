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


def _reclassify_break_attendances(env):
    """19.0's day_period had a 'lunch' option; 20.0 has no break concept at all.

    19.0 declared day_period as a plain stored selection of morning / lunch
    ("Break") / afternoon / full_day. 20.0 drops 'lunch' and makes the field a
    stored compute over the hours, so nothing it can produce is 'lunch' -- but
    the column already holds a value, so the ORM leaves it there and the rows
    keep a key the selection no longer declares. On the seed that is 600 of the
    1825 attendances, every one of them a lunch break.

    Rewritten with 20.0's own _compute_day_period, transcribed rather than
    approximated::

        if duration_hours > 0.75 * calendar.hours_per_day or duration_based:
            'full_day'
        elif hour_from and hour_to:
            'afternoon' if hour_from > 12 or (12 - hour_from <= hour_to - 12)
            else 'morning'
        else:
            'morning'

    Only the 'lunch' rows are touched: every other value is one 20.0 still
    declares, and recomputing them would silently rewrite data the upgrade had
    no reason to change.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar_attendance a
        SET day_period = CASE
            WHEN a.duration_hours > 0.75 * coalesce(c.hours_per_day, 0)
                 OR a.duration_based THEN 'full_day'
            WHEN coalesce(a.hour_from, 0) != 0 AND coalesce(a.hour_to, 0) != 0
                 AND (a.hour_from > 12 OR (12 - a.hour_from <= a.hour_to - 12))
                THEN 'afternoon'
            ELSE 'morning'
        END
        FROM resource_calendar c
        WHERE c.id = a.calendar_id AND a.day_period = 'lunch'
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "resource", "20.0.1.1/noupdate_changes.xml")
    # Order matters: day_period is computed from duration_hours, so the breaks
    # have to be reclassified after the durations are filled, not before.
    _fill_attendance_duration_hours(env)
    _reclassify_break_attendances(env)
