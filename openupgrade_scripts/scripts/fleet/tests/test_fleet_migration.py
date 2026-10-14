from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestFleetMigration(TransactionCase):
    """Assertions on a service log's date surviving its rename to date_from.

    There is no 19.0 fixture here and there does not need to be: the seed
    already holds the discriminating rows, six service logs on six different
    dates. What makes the failure invisible without a test is that `date_from`
    carries a default of today, so the wrong answer is a full column rather than
    an empty one.
    """

    def test_a_service_log_kept_the_date_it_was_executed_on(self):
        self.env.cr.execute(
            "SELECT count(*), count(DISTINCT date_from) FROM fleet_vehicle_log_services"
        )
        total, distinct = self.env.cr.fetchone()
        self.assertTrue(total, "the seed has no service logs to check")
        self.assertGreater(
            distinct,
            1,
            "every service log carries the same start date, so the history was "
            "overwritten with the day the upgrade ran",
        )

    def test_every_service_log_still_has_a_start_date(self):
        """A rename must not leave a row without the date it used to carry."""
        self.env.cr.execute(
            "SELECT count(*) FROM fleet_vehicle_log_services WHERE date_from IS NULL"
        )
        self.assertEqual(
            self.env.cr.fetchone()[0], 0, "a service log came out with no start date"
        )

    def test_the_old_column_is_gone_rather_than_left_beside_the_new_one(self):
        self.env.cr.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'fleet_vehicle_log_services' AND column_name = 'date'
            """
        )
        self.assertEqual(self.env.cr.fetchone()[0], 0, "date was copied, not renamed")
