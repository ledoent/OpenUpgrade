from openupgradelib import openupgrade

from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestHrAttendanceMigration(TransactionCase):
    """Assertions on extra-hours approval surviving its rename.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def setUp(self):
        super().setUp()
        self.legacy = openupgrade.get_legacy_name("attendance_overtime_validation")
        self.env.cr.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'res_company' AND column_name = %s
            """,
            (self.legacy,),
        )
        self.assertTrue(
            self.env.cr.fetchone()[0],
            f"res_company.{self.legacy} is gone, so the 19.0 answer was not kept",
        )

    def _companies_on(self, value):
        self.env.cr.execute(
            f"SELECT id FROM res_company WHERE {self.legacy} = %s ORDER BY id", (value,)
        )
        return [row[0] for row in self.env.cr.fetchall()]

    def test_a_company_that_required_approval_still_requires_it(self):
        """by_manager is 20.0's manual_validation under a new name."""
        ids = self._companies_on("by_manager")
        self.assertEqual(
            len(ids), 1, "the fixture company is missing from the migrated database"
        )
        company = self.env["res.company"].browse(ids[0])
        self.assertEqual(
            company.attendance_validation,
            "manual_validation",
            "the company stopped requiring approval for extra hours",
        )

    def test_a_company_that_did_not_is_left_where_the_default_puts_it(self):
        """no_validation is what 20.0 defaults to, so nothing is written for it.

        This is the half that says the carry is targeted. A blanket write would
        pass the test above and still be wrong.
        """
        ids = self._companies_on("no_validation")
        self.assertTrue(ids, "the seed has no company on no_validation to check")
        self.env.cr.execute(
            """
            SELECT count(*) FROM res_company
            WHERE id = ANY(%s) AND attendance_validation != 'no_validation'
            """,
            (ids,),
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a company that approved extra hours automatically was changed",
        )

    def test_nothing_was_written_where_19_0_had_no_answer(self):
        """tolerance_validation is new in 20.0 and cannot be carried into."""
        self.env.cr.execute(
            "SELECT count(*) FROM res_company WHERE attendance_validation = %s",
            ("tolerance_validation",),
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a 20.0-only answer was invented for a 19.0 company",
        )
