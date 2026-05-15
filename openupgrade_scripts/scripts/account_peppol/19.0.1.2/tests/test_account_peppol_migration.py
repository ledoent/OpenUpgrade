from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestAccountPeppolMigration(TransactionCase):
    def test_wizard_model_renamed(self):
        """account_peppol.service.wizard (transient) renamed to
        peppol.config.wizard. rename_models + rename_tables in pre-migration
        keeps ir_model / ir_model_data consistent.
        """
        self.assertIn("peppol.config.wizard", self.env.registry)
        self.assertNotIn("account_peppol.service.wizard", self.env.registry)

    def test_wizard_table_renamed(self):
        """The postgres table for the renamed transient model must exist
        under the new name (transients have tables even though rows are
        cleared periodically).
        """
        self.env.cr.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'peppol_config_wizard'
            """
        )
        self.assertTrue(self.env.cr.fetchone())
