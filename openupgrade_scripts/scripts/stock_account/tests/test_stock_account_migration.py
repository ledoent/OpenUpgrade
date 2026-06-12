from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestStockAccountMigration(TransactionCase):
    def test_product_value_aggregated_per_move(self):
        """
        product.value is the manual-override history: _get_manual_value()
        takes the single latest row per move as the move's entire value, so
        the former layers must collapse to one summed row — otherwise the
        first recompute (e.g. posting a vendor bill) replaces a $1,050
        receipt with its $50 adjustment layer.
        """
        in_move = self.env.ref("openupgrade_test.stock_account_in_move")
        rows = self.env["product.value"].search([("move_id", "=", in_move.id)])
        self.assertEqual(
            len(rows), 1, "former valuation layers must collapse to one row"
        )
        self.assertAlmostEqual(rows.value, 1050.0)
        self.assertAlmostEqual(in_move.value, 1050.0)
        # the recompute path must agree with the migrated value
        self.assertAlmostEqual(in_move._get_value(), 1050.0)

    def test_outbound_value_is_magnitude(self):
        """
        18.0 layers carry a direction sign (deliveries negative); 19.0
        stores cost magnitudes. A negative migrated value flips the
        anglo-saxon COGS entry when the delivery is invoiced on 19.0.
        """
        out_move = self.env.ref("openupgrade_test.stock_account_out_move")
        self.assertAlmostEqual(out_move.value, 420.0)
