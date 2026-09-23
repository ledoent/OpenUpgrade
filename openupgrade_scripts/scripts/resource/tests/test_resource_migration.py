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
