from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestPosEventMigration(TransactionCase):
    """Assertions on the point-of-sale uuids being identities rather than one value.

    There is no 19.0 data snippet beside this file, and that is deliberate
    rather than an omission. 19.0 has no uuid column at all, so nothing can be
    planted into it, and none is needed: the seed already holds the
    discriminating rows -- 29 registrations and 12 answers, which every one of
    them came out of the upgrade sharing a single value.

    Every method asserts the table is non-empty first. `count(DISTINCT uuid)`
    over an empty table is 0 and equals its row count, so an emptied table would
    satisfy the uniqueness assertion while proving nothing.
    """

    def _uuids(self, table):
        self.env.cr.execute(
            f"SELECT count(*), count(uuid), count(DISTINCT uuid) FROM {table}"
        )
        rows, filled, distinct = self.env.cr.fetchone()
        self.assertTrue(
            rows, f"{table} is empty, so it cannot show whether uuids are unique"
        )
        return rows, filled, distinct

    def test_every_registration_has_a_uuid_of_its_own(self):
        """29 registrations shared one uuid before this; the POS matches on it."""
        rows, filled, distinct = self._uuids("event_registration")
        self.assertEqual(
            filled, rows, "a registration came out of the upgrade with no uuid"
        )
        self.assertEqual(
            distinct,
            rows,
            "registrations share a uuid, so the point of sale cannot tell them "
            "apart when it loads them",
        )

    def test_every_registration_answer_has_a_uuid_of_its_own(self):
        rows, filled, distinct = self._uuids("event_registration_answer")
        self.assertEqual(
            filled, rows, "a registration answer came out of the upgrade with no uuid"
        )
        self.assertEqual(
            distinct,
            rows,
            "registration answers share a uuid, so the point of sale cannot tell "
            "them apart when it loads them",
        )

    def test_the_two_models_do_not_share_uuids_with_each_other(self):
        """Independent generators, not one value handed to both tables.

        The pre-migration state had each table on its own single value, so a
        repair that ran once and reused its result would still pass both tests
        above.
        """
        self.env.cr.execute(
            """
            SELECT count(*) FROM event_registration r
            JOIN event_registration_answer a ON a.uuid = r.uuid
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a registration and an answer carry the same uuid",
        )
