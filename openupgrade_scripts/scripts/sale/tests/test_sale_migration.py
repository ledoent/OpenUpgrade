from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestSaleMigration(TransactionCase):
    """Assertions on sale_delay becoming a company-dependent jsonb column.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _product(self, name):
        return (
            self.env["product.template"]
            .with_context(active_test=False)
            .search([("name", "=", name)])
        )

    def test_the_delay_survives_the_move_to_jsonb(self):
        """Read through the ORM, not the column.

        20.0 stores this per company in jsonb, so a test that read the raw
        column would be asserting on the storage rather than on what a user
        sees, and would pass on a value written under the wrong company key.
        """
        product = self._product("ou19-sale-delay-product")
        self.assertTrue(product)
        self.assertEqual(len(product), 1)
        self.assertEqual(product.sale_delay, 7)

    def test_the_delay_is_readable_in_every_company(self):
        """The 19.0 value was global, so it holds for each company."""
        product = self._product("ou19-sale-delay-product")
        self.assertTrue(product)
        companies = self.env["res.company"].search([], limit=3)
        self.assertTrue(companies)
        for company in companies:
            self.assertEqual(
                product.with_company(company).sale_delay, 7, company.display_name
            )

    def test_a_default_delay_stays_the_default(self):
        """Zero needs no row: a missing key reads back as the field default."""
        product = self._product("ou19-sale-delay-default")
        self.assertTrue(product)
        self.assertEqual(product.sale_delay, 0)

    def test_the_reinvoicing_policy_kept_its_19_0_answers(self):
        """expense_policy -> reinvoice_policy, proved from the seed itself.

        No fixture: the seed already holds the discriminating rows, 197 product
        templates over three distinct expense_policy values. Without the rename
        the column is created fresh and every row reads its default, so the
        whole table comes out on one value -- which is exactly what this counts.
        """
        self.env.cr.execute(
            "SELECT count(DISTINCT reinvoice_policy) FROM product_template"
        )
        self.assertGreater(
            self.env.cr.fetchone()[0],
            1,
            "every product template reads the same re-invoicing policy, so the "
            "19.0 answers were replaced by the new field's default",
        )

    def test_the_old_column_is_gone_rather_than_left_beside_the_new_one(self):
        """A rename, not a copy: two columns holding the same thing diverge."""
        self.env.cr.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'product_template' AND column_name = 'expense_policy'
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0], 0, "expense_policy was copied, not renamed"
        )
