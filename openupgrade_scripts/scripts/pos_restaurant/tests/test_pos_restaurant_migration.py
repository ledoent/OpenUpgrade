from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestPosRestaurantMigration(TransactionCase):
    """Assertions on the floor plan surviving six columns becoming one JSON blob.

    There is no 19.0 data snippet beside this file and none is needed: the seed
    already holds the discriminating rows -- 27 tables over 25 distinct
    positions, all of which came out with a NULL layout. Each method asserts the
    table is non-empty first, because every count below is also satisfied by an
    empty table.
    """

    def setUp(self):
        super().setUp()
        self.env.cr.execute("SELECT count(*) FROM restaurant_table")
        self.total = self.env.cr.fetchone()[0]
        self.assertTrue(
            self.total, "there are no restaurant tables, so nothing here can fail"
        )

    def test_every_table_has_a_layout(self):
        self.env.cr.execute(
            "SELECT count(*) FROM restaurant_table WHERE floor_plan_layout IS NULL"
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a table came out with no floor_plan_layout, so the point of sale "
            "draws it from nothing",
        )

    def test_the_positions_are_still_distinct(self):
        """A plan where every table sits in the same place is not a plan.

        This is the assertion a blanket write of 20.0's default would fail: it
        would satisfy "every table has a layout" and still lose the floor.
        """
        self.env.cr.execute(
            """
            SELECT count(DISTINCT (floor_plan_layout->>'left',
                                   floor_plan_layout->>'top'))
            FROM restaurant_table
            """
        )
        distinct = self.env.cr.fetchone()[0]
        self.assertGreater(
            distinct,
            1,
            "every table came out at the same position, so the floor plan was "
            "replaced by a default rather than carried",
        )

    def test_each_table_kept_its_own_coordinates(self):
        """Read back against the 19.0 columns, which the upgrade leaves in place."""
        self.env.cr.execute(
            """
            SELECT count(*) FROM restaurant_table
            WHERE (floor_plan_layout->>'left')::float IS DISTINCT FROM position_h
               OR (floor_plan_layout->>'top')::float IS DISTINCT FROM position_v
               OR (floor_plan_layout->>'width')::float IS DISTINCT FROM width
               OR (floor_plan_layout->>'height')::float IS DISTINCT FROM height
               OR floor_plan_layout->>'shape' IS DISTINCT FROM shape
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a table's layout does not match the 19.0 columns it was built from",
        )

    def test_a_table_with_no_colour_has_no_colour_key(self):
        """Absent is not the same as present-and-null.

        20.0 spreads the layout into the record it sends the browser, so a key
        holding JSON null would arrive as a colour of null rather than as no
        colour at all. One seeded table has no colour, which is what makes this
        reachable.
        """
        self.env.cr.execute("SELECT count(*) FROM restaurant_table WHERE color IS NULL")
        uncoloured = self.env.cr.fetchone()[0]
        self.assertTrue(
            uncoloured, "no table lacks a colour, so this cannot discriminate"
        )
        self.env.cr.execute(
            """
            SELECT count(*) FROM restaurant_table
            WHERE color IS NULL AND jsonb_exists(floor_plan_layout, 'color')
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a table with no colour came out carrying a null colour key",
        )
