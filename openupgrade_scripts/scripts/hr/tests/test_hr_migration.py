from openupgradelib import openupgrade

from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestHrMigration(TransactionCase):
    """Assertions on hr.contract.type becoming hr.employee.type.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def test_a_version_keeps_the_type_it_was_given(self):
        """contract_type_id became employee_type_id, carrying its value.

        The rename is only visible once the comodel rename is taken into
        account: hr.contract.type against hr.employee.type reads as two
        different models, so the pair is dismissed and the new field annotated
        as one that existing records should have empty.
        """
        version = (
            self.env["hr.version"]
            .with_context(active_test=False)
            .search([("name", "=", "ou19-version-contract-type")])
        )
        self.assertEqual(len(version), 1, "the fixture version is missing")
        self.assertTrue(
            version.employee_type_id,
            "the version lost the type it had as contract_type_id",
        )
        self.assertEqual(version.employee_type_id._name, "hr.employee.type")

    def test_a_job_keeps_the_type_it_was_given(self):
        """hr.job carries the same pair and is renamed with it."""
        job = self.env["hr.job"].search([("name", "=", "ou19-job-contract-type")])
        self.assertEqual(len(job), 1, "the fixture job is missing")
        self.assertTrue(job.employee_type_id, "the job lost its contract type")

    def test_the_old_column_is_gone_rather_than_left_alongside(self):
        """A rename moves the column; a drop-plus-create leaves both.

        Without this the test above passes just as well when employee_type_id
        happens to be filled from somewhere else, with contract_type_id still
        sitting there holding the real value.
        """
        for table in ("hr_version", "hr_job"):
            self.env.cr.execute(
                """
                SELECT count(*) FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'contract_type_id'
                """,
                (table,),
            )
            self.assertEqual(
                self.env.cr.fetchone()[0], 0, f"{table}.contract_type_id survived"
            )

    def test_a_chosen_employee_type_is_kept_for_the_report(self):
        """19.0's employee_type classified the person, which 20.0 drops.

        It is deliberately not mapped onto an hr.employee.type -- those describe
        the contract, and the records to map onto are 19.0's own contract types
        -- so what has to survive is the value itself, for post-migration to
        report. The column is renamed rather than read in place so that this
        migration owns it.
        """
        legacy = openupgrade.get_legacy_name("employee_type")
        self.env.cr.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'hr_version' AND column_name = %s
            """,
            (legacy,),
        )
        self.assertTrue(self.env.cr.fetchone()[0], f"hr_version.{legacy} is gone")
        self.env.cr.execute(
            f"SELECT count(*) FROM hr_version WHERE {legacy} = 'student'"
        )
        self.assertTrue(
            self.env.cr.fetchone()[0], "the chosen employee type did not survive"
        )
