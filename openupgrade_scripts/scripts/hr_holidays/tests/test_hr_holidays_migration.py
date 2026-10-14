from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestHrHolidaysMigration(TransactionCase):
    """Assertions on the hr.leave.type fold into hr.work.entry.type.

    Every method opens by asserting the records exist. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _wet(self, name):
        return (
            self.env["hr.work.entry.type"]
            .with_context(active_test=False)
            .search([("name", "=", name)])
        )

    def test_unique_pairing_is_honoured(self):
        """A leave type linked to a work entry type of its own keeps it.

        The link is what the administrator configured in 19.0, so the merge
        follows it rather than creating a second record beside it.
        """
        solo = self._wet("ou19-wet-solo")
        self.assertTrue(solo)
        self.assertEqual(len(solo), 1)
        # The leave settings only ever existed on the leave type; a reused work
        # entry type starts with none of them.
        self.assertTrue(solo.requires_allocation)
        self.assertTrue(solo.support_document)
        self.assertEqual(solo.allocation_validation_type, "hr")
        # Its own name and payroll code are what the work entry side is known
        # by, and are left alone.
        self.assertEqual(solo.code, "OU19SOLO")

    def test_a_shared_work_entry_type_is_not_conflated(self):
        """Two leave types sharing one work entry type end up as two records.

        20.0 has one record where 19.0 had two. Letting them collapse would
        silently discard whatever differed between them -- here the request
        unit, which drives how time off is counted.
        """
        shared = self._wet("ou19-wet-shared")
        self.assertTrue(shared)
        self.assertEqual(len(shared), 1)
        # The younger of the two got a record of its own rather than the link.
        second = self._wet("ou19-leave-shared-second")
        self.assertTrue(second)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(second.id, shared.id)
        # It takes the paired type's payroll code: that is the code its time
        # off was actually paid under, so inventing one would be wrong.
        self.assertEqual(second.code, "OU19SHARED")

    def test_unlinked_type_gets_a_traceable_placeholder_code(self):
        """A leave type with no work entry type has no code to inherit."""
        unlinked = self._wet("ou19-leave-unlinked")
        self.assertTrue(unlinked)
        self.assertEqual(len(unlinked), 1)
        self.assertTrue(
            unlinked.code.startswith("LEAVE"),
            f"expected a LEAVE<id> placeholder, got {unlinked.code!r}",
        )

    def test_count_as_and_unit_of_measure_are_mapped_not_defaulted(self):
        """time_type and request_unit carry meaning the 20.0 defaults lose.

        count_as defaults to working_time, which is wrong for nearly every
        leave type, and unit_of_measure defaults to hour. Both have an exact
        19.0 source, so neither may be left at its default.
        """
        unlinked = self._wet("ou19-leave-unlinked")
        self.assertTrue(unlinked)
        # time_type 'other' is 19.0's "Worked Time".
        self.assertEqual(unlinked.count_as, "working_time")
        self.assertEqual(unlinked.unit_of_measure, "hour")

        second = self._wet("ou19-leave-shared-second")
        self.assertTrue(second)
        self.assertEqual(second.count_as, "absence")
        # 20.0 has no half day for allocation, so half_day folds to day.
        self.assertEqual(second.unit_of_measure, "day")

    def test_derived_types_are_selectable_as_time_off(self):
        """20.0 decides what may be requested from time_off_selectable.

        Only that one: 19.0's is_leave is gone from the model in 20.0, and
        OpenUpgrade keeps its column, so asserting on it would be asserting on
        a value nothing reads.
        """
        for name in ("ou19-wet-solo", "ou19-leave-unlinked"):
            record = self._wet(name)
            self.assertTrue(record, name)
            self.assertTrue(record.time_off_selectable, name)

    def test_allocations_follow_their_type(self):
        """A reference re-points onto the stand-in, including a created one."""
        allocation = self.env["hr.leave.allocation"].search(
            [("name", "=", "ou19-allocation")]
        )
        self.assertTrue(allocation)
        self.assertEqual(len(allocation), 1)
        self.assertEqual(
            allocation.work_entry_type_id, self._wet("ou19-leave-unlinked")
        )

    def test_nothing_is_left_without_a_type(self):
        """20.0 declares work_entry_type_id required on both models.

        Asserting on the fixture alone would pass even if the merge had only
        re-pointed the rows the test itself created.
        """
        for model in ("hr.leave", "hr.leave.allocation"):
            records = self.env[model].with_context(active_test=False)
            self.assertTrue(records.search_count([]), model)
            self.assertEqual(
                records.search_count([("work_entry_type_id", "=", False)]), 0, model
            )
