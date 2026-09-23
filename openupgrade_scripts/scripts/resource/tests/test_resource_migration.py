from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestResourceMigration(TransactionCase):
    """Assertions on the duration_hours backfill.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _attendance(self):
        """Found through its calendar: 20.0 drops attendance.name entirely."""
        return self.env["resource.calendar.attendance"].search(
            [("calendar_id.name", "=", "ou19-calendar")]
        )

    def test_duration_is_derived_from_the_span(self):
        """19.0 stored nothing, so the column 20.0 adds starts at zero."""
        record = self._attendance()
        self.assertTrue(record)
        self.assertEqual(len(record), 1)
        self.assertEqual(record.duration_hours, 4.0)

    def test_every_other_attendance_is_inside_the_new_range(self):
        """Asserting on the fixtures alone would pass on a backfill that only
        touched the rows the test itself created."""
        outside = self.env["resource.calendar.attendance"].search_count(
            [
                ("duration_hours", "<=", 0),
                ("duration_based", "=", False),
            ]
        )
        self.assertTrue(self.env["resource.calendar.attendance"].search_count([]))
        self.assertEqual(outside, 0)

    def _calendar(self, name):
        record = self.env.ref(f"__ou19__.{name}", raise_if_not_found=False)
        self.assertTrue(
            record, f"{name} is missing: the 19.0 fixture never reached the database"
        )
        return record

    def test_a_flexible_schedule_becomes_an_undefined_calendar(self):
        """20.0 spells 19.0's flexible_hours as calendar_type == 'undefined'.

        Read off each version's own predicate rather than off the labels:
        19.0's `flexible_hours = schedule_type == 'flexible'`, 20.0's
        `_is_flexible` returns `calendar_type == 'undefined'`.
        """
        calendar = self._calendar("ou19_calendar_flexible")
        self.assertEqual(
            calendar.calendar_type,
            "undefined",
            "a flexible calendar came out as a fixed weekly pattern it does "
            "not have, so every caller of _is_flexible now gets the wrong answer",
        )
        self.assertTrue(calendar._is_flexible())

    def test_a_two_week_calendar_becomes_a_variable_one(self):
        """The branch the seed cannot reach: it holds no two-week calendar.

        20.0's own help names "a multi-week rotation" as what 'variable' is for.
        """
        calendar = self._calendar("ou19_calendar_two_weeks")
        self.assertEqual(
            calendar.calendar_type,
            "variable",
            "a calendar in two-weeks mode came out as a single repeating week",
        )

    def test_a_fully_fixed_schedule_is_left_where_the_default_puts_it(self):
        """The half that says the mapping discriminates rather than blankets."""
        calendar = self._calendar("ou19_calendar_fully_fixed")
        self.assertEqual(calendar.calendar_type, "fixed")

    def test_no_fully_fixed_calendar_in_the_seed_was_moved(self):
        """122 of the seed's 124 are fully fixed; none of them should have moved."""
        self.env.cr.execute(
            """
            SELECT count(*) FROM resource_calendar
            WHERE calendar_type != 'fixed'
              AND coalesce(schedule_type, 'fully_fixed') != 'flexible'
              AND NOT coalesce(two_weeks_calendar, false)
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a calendar that was neither flexible nor in two-weeks mode was moved",
        )
