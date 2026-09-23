from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestPointOfSaleMigration(TransactionCase):
    """Assertions on pos.payment.method.type, now stored and required.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _method(self, name):
        return (
            self.env["pos.payment.method"]
            .with_context(active_test=False)
            .search([("name", "=", name)])
        )

    def test_type_follows_the_journal(self):
        """19.0's _compute_type reads journal_id.type, so the fill must too."""
        for name, expected in (
            ("ou19-pm-cash", "cash"),
            ("ou19-pm-bank", "bank"),
        ):
            record = self._method(name)
            self.assertTrue(record, name)
            self.assertEqual(record.type, expected, name)

    def test_a_method_with_no_journal_is_pay_later(self):
        """The branch is_cash_count cannot tell from a bank method.

        Both are False there, so a fill keyed off is_cash_count would put bank
        and pay_later in the same bucket and be wrong for one of them.
        """
        record = self._method("ou19-pm-none")
        self.assertTrue(record)
        self.assertEqual(record.type, "pay_later")

    def test_no_method_is_left_untyped(self):
        """20.0 declares type required, so nothing may be left blank.

        Asserting on the fixtures alone would pass on a fill that only touched
        the rows the test itself created.
        """
        methods = self.env["pos.payment.method"].with_context(active_test=False)
        self.assertTrue(methods.search_count([]))
        self.assertEqual(methods.search_count([("type", "=", False)]), 0)
