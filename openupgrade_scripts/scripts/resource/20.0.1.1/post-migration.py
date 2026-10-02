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


def _carry_the_schedule_type_into_the_calendar_type(env):
    """19.0's schedule_type becomes 20.0's calendar_type, with a third option.

    19.0 asked one question with two answers::

        schedule_type = flexible     "Define an amount of hours to work on the week"
                      | fully_fixed  "define the days, periods and the start &
                                      end time for each period of the day"

    and carried `flexible_hours` beside it, which was not a second question --
    19.0's own compute is `calendar.flexible_hours = calendar.schedule_type ==
    'flexible'`, and its inverse writes the other way.

    20.0 asks the same question with three answers, and the third is not a
    renaming of anything::

        fixed      a weekly attendance pattern that repeats identically
        variable   attendances on specific dates rather than a repeating weekly
                   pattern, such as a one-off schedule or a multi-week rotation
        undefined  no predefined slots at all; the resource can work whenever it
                   wants, optionally up to an hours target

    The mapping is not read off the labels -- "flexible" appears in neither
    list -- but off what each version's own code treats as flexible. 20.0::

        def _is_flexible(self):
            return self.calendar_type == 'undefined'

    That is the same property 19.0 spelled `flexible_hours`: work without
    relying on the working schedule, against an hours target rather than fixed
    periods. So `flexible` maps to `undefined`, not to `variable`.

    `two_weeks_calendar` is the one that maps to 'variable': 20.0's own help
    names "a multi-week rotation" as what variable is for, and a 19.0 two-week
    calendar is exactly that. The seed contains none, so the migration test
    builds one -- without it this branch is unreachable and nothing would say so.

    `fully_fixed` maps to `fixed`, which is what the new column already
    defaults to, so nothing is written for it. That matters: 122 of the seed's
    124 calendars are fully_fixed, and a blanket write would touch every one of
    them to no effect while hiding whether the rule discriminates at all.

    Without this a flexible calendar comes out reading as a fixed weekly
    pattern it does not have, and every attendance, work entry and time-off
    computation that asks `_is_flexible` gets the wrong answer.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE resource_calendar
        SET calendar_type = CASE
            WHEN schedule_type = 'flexible' THEN 'undefined'
            ELSE 'variable'
        END
        WHERE calendar_type = 'fixed'
          AND (schedule_type = 'flexible' OR two_weeks_calendar)
        """,
    )


def _carry_the_calendar_tz_onto_the_company(env):
    """resource.calendar.tz is dropped in 20.0; the timezone is res.company.tz.

    res.company.tz is new and defaults from the company's country, so a
    database whose calendars disagreed with that default silently changes what
    a working day means. Nothing fails: the column is populated, the upgrade is
    quiet, and every computation that localises hour_from/hour_to is simply
    wrong by the offset between the two zones.

    Measured on a production copy: all five companies defaulted to UTC while
    their default calendars said US/Eastern or America/New_York, a five-hour
    shift. The visible effect was in resource_booking, whose availability is
    `calendar._work_intervals_batch(...)` intersected with the booking's own
    interval -- a 19:30 UTC booking inside a 09:00-17:00 US/Eastern day fell
    outside a 09:00-17:00 UTC one, so the interval set came back empty, the
    stored combination stopped validating, and the portal answered 422 for a
    booking that had been confirmed for months.

    Per-calendar timezones cannot survive, because 20.0 has one zone per
    company. Where a company's calendars disagree, the zone held by the MOST of
    them wins -- that is the choice that leaves the fewest calendars meaning
    something new -- with the company's default calendar breaking a tie. The
    default calendar is deliberately not preferred outright: on the copy
    measured, company 1's default calendar carried an unconfigured UTC while
    both of the calendars actually driving bookings said US/Eastern, so
    preferring it would have kept exactly the breakage this fixes. Resources are
    unaffected either way, since resource.resource.tz already existed in 19.0
    and core uses it whenever a resource is in play.
    """
    legacy_tz = openupgrade.get_legacy_name("tz")
    if not openupgrade.column_exists(env.cr, "resource_calendar", legacy_tz):
        # pre-migration did not run (a database upgraded before this script
        # existed). Say so rather than silently leaving the zones wrong.
        openupgrade.message(
            env.cr, "resource", False, False,
            "Could not carry resource.calendar.tz onto res.company.tz: the "
            "preserved column is absent. Check each company's Timezone.",
        )
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        WITH tallied AS (
            SELECT cal.company_id, cal.{legacy_tz} AS tz, count(*) AS n,
                   bool_or(cal.id = c.resource_calendar_id) AS is_default
            FROM resource_calendar cal
            JOIN res_company c ON c.id = cal.company_id
            WHERE cal.{legacy_tz} IS NOT NULL AND cal.{legacy_tz} != ''
            GROUP BY cal.company_id, cal.{legacy_tz}, c.resource_calendar_id
        ), chosen AS (
            SELECT DISTINCT ON (company_id) company_id, tz
            FROM tallied
            -- The DEFAULT calendar's zone wins, and the count only breaks ties
            -- among the rest. Ordering by count first would let three calendars
            -- in one zone outvote the calendar the company's own records are
            -- actually computed against.
            ORDER BY company_id, is_default DESC, n DESC, tz
        )
        UPDATE res_company c SET tz = chosen.tz
        FROM chosen
        WHERE chosen.company_id = c.id
          AND c.tz IS DISTINCT FROM chosen.tz
        """,
    )
    # Report only the genuinely lossy case: a company that really had more than
    # one zone across its calendars.
    env.cr.execute(
        f"""
        SELECT cal.company_id, array_agg(DISTINCT cal.{legacy_tz})
        FROM resource_calendar cal
        WHERE cal.company_id IS NOT NULL
          AND cal.{legacy_tz} IS NOT NULL AND cal.{legacy_tz} != ''
        GROUP BY cal.company_id
        HAVING count(DISTINCT cal.{legacy_tz}) > 1
        """
    )
    for company_id, zones in env.cr.fetchall():
        openupgrade.message(
            env.cr, "resource", False, False,
            "Company %s had calendars in more than one timezone (%s). 20.0 "
            "keeps one timezone per company, so the default calendar's zone "
            "was used; review the others.",
            company_id, ", ".join(sorted(zones)),
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "resource", "20.0.1.1/noupdate_changes.xml")
    # Order matters: day_period is computed from duration_hours, so the breaks
    # have to be reclassified after the durations are filled, not before.
    _fill_attendance_duration_hours(env)
    _reclassify_break_attendances(env)
    _carry_the_schedule_type_into_the_calendar_type(env)
    _carry_the_calendar_tz_onto_the_company(env)
