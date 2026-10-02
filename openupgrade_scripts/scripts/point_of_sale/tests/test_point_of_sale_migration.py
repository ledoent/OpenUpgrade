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

    def test_the_invoice_journal_became_the_one_20_cuts_invoices_from(self):
        """19.0's invoice_journal_id is 20.0's journal_id.

        _prepare_invoice_vals reads `config_id.journal_id` in 20.0
        (pos_order.py:1557) where 19.0 read invoice_journal_id
        (19.0 pos_order.py:919). Without the swap, POS invoices are cut from
        the old CLOSING journal: on the sanitised prod copy that is POSS, which
        holds 0 moves, while all 88 POS invoices sit in the journal
        invoice_journal_id still named.
        """
        config = self.env.ref("__ou19__.ou19_pos_config")
        self.assertEqual(
            config.journal_id,
            self.env.ref("__ou19__.ou19_pos_invoice_journal"),
        )

    def test_the_closing_journal_is_the_19_one_not_a_freshly_created_one(self):
        """closing_journal_id takes 19.0's journal_id, not a new POSC journal.

        Left alone, _compute_closing_journal_id calls
        _ensure_company_closing_journal() and CREATES one -- the prod copy's
        config points at journal 88, whose create_date is the migration run
        itself.
        """
        config = self.env.ref("__ou19__.ou19_pos_config")
        self.assertEqual(
            config.closing_journal_id,
            self.env.ref("__ou19__.ou19_pos_closing_journal"),
        )

    def test_session_accounting_still_waits_for_a_close(self):
        """A pre-existing config keeps 19.0's behaviour, not 20.0's default.

        20.0 defaults session_closing_mode to 'daily' and ships
        ir_cron_pos_auto_order_invoicing active every 10 minutes, whose domain
        selects exactly that value and validates accounting on sessions that
        are still open. 19.0 posted only on close and shipped no such cron.
        """
        config = self.env.ref("__ou19__.ou19_pos_config")
        self.assertEqual(config.session_closing_mode, "closing")
