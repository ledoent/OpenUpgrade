from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestLoyaltyMigration(TransactionCase):
    """Assertions on a loyalty line being dated when the points changed.

    There is no 19.0 data snippet beside this file and none is needed: 19.0 has
    no column to plant into, and the seed already holds the discriminating rows
    -- 39 history lines over 7 distinct create_date values, all of which came
    out sharing one timestamp.

    Every method asserts the table is non-empty first, because an empty table
    satisfies each count below while proving nothing.
    """

    def setUp(self):
        super().setUp()
        self.env.cr.execute("SELECT count(*) FROM loyalty_history")
        self.total = self.env.cr.fetchone()[0]
        self.assertTrue(self.total, "there are no loyalty history lines to check")

    def test_the_dates_are_not_all_the_same_moment(self):
        """One timestamp on every row is the fingerprint of a column default."""
        self.env.cr.execute(
            "SELECT count(DISTINCT points_changed_date) FROM loyalty_history"
        )
        self.assertGreater(
            self.env.cr.fetchone()[0],
            1,
            "every loyalty history line carries the same timestamp, so the "
            "ledger says the points all changed at once",
        )

    def test_each_line_is_dated_when_it_was_written(self):
        self.env.cr.execute(
            """
            SELECT count(*) FROM loyalty_history
            WHERE create_date IS NOT NULL
              AND points_changed_date IS DISTINCT FROM create_date
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a loyalty history line is dated differently from when it was written",
        )

    def test_nothing_was_given_an_expiry_nobody_chose(self):
        """The other half of FIFO_ORDER, deliberately left alone.

        19.0 recorded no expiry; 20.0 derives one from the programme's new
        expire_after. Filling it here would expire points on an invented date.
        """
        self.env.cr.execute(
            "SELECT count(*) FROM loyalty_history WHERE expiration_date IS NOT NULL"
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "an expiry date was invented for a line 19.0 never expired",
        )
