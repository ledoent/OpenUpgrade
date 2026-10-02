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

    def test_the_version_keeps_the_timezone_instead_of_defaulting_to_utc(self):
        """hr_version.tz comes from the resource, not from the 20.0 default.

        19.0 declared hr.version.tz as related='employee_id.tz'
        (hr_version.py:153), so nothing was stored on the version -- the value
        lived in resource_resource.tz, reached through resource.mixin. 20.0
        inverts it: hr_version.tz is stored and required with a default of
        `context tz or user tz or 'UTC'` (hr_version.py:162), and
        hr.employee.tz becomes related="version_id.tz" (hr_employee.py:309).

        Without the carry the upgrade takes that default. Measured on the
        sanitised prod copy: both versions came out 'UTC' while their
        resources held 'America/New_York'. Nothing re-derives it afterwards --
        _get_tz() reads self.tz first (hr_version.py:715-717) -- so every
        working-hours and attendance calculation silently shifts.

        The fixture plants a non-UTC zone precisely because 'UTC' is the
        default: a UTC resource would assert nothing.
        """
        version = self.env["hr.version"].search(
            [("name", "=", "ou19-version-student")], limit=1
        )
        self.assertTrue(version, "the fixture's version is gone")
        self.assertEqual(version.tz, "Pacific/Auckland")
        self.assertEqual(version.tz, version.employee_id.resource_id.tz)

    def test_no_version_was_left_on_a_utc_its_resource_contradicts(self):
        """The carry is global, not just the row the fixture planted.

        Asserting on the fixture alone would pass even if the UPDATE had
        matched only the row this test created.
        """
        self.env.cr.execute(
            """
            SELECT count(*)
            FROM hr_version v
            JOIN hr_employee e ON e.id = v.employee_id
            JOIN resource_resource r ON r.id = e.resource_id
            WHERE v.tz = 'UTC' AND r.tz IS NOT NULL AND r.tz != '' AND r.tz != 'UTC'
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a version is on UTC while its resource names another zone",
        )
