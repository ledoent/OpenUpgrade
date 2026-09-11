from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestBaseMigration(TransactionCase):
    def test_server_action_child_ids(self):
        """
        Test that server action children are migrated correctly
        """
        action1 = self.env["ir.actions.server"].search(
            [("name", "=", "test server action 1")]
        )
        self.assertTrue(action1)
        self.assertItemsEqual(
            action1.child_ids.mapped("name"), ("child action 1", "child action 2")
        )
        action2 = self.env["ir.actions.server"].search(
            [("name", "=", "test server action 2")]
        )
        self.assertTrue(action2)
        self.assertItemsEqual(
            action2.child_ids.mapped("name"),
            ("child action 1", "child action 2", "child action 3"),
        )

    def test_strip_removed_search_view_attrs(self):
        """19.0 RNG-removed attrs (`expand=` on <group>/<field>,
        `string="Group By"` on <group>) are stripped from arch_db
        on search views; legitimate attrs are preserved.
        """
        view_group = self.env["ir.ui.view"].search(
            [("name", "=", "test search group_expand")]
        )
        self.assertTrue(view_group)
        arch_group = view_group.arch_db
        self.assertNotIn(
            'expand="0"',
            arch_group,
            "expand= should be stripped from <group> in search arch",
        )
        self.assertNotIn(
            'string="Group By"',
            arch_group,
            'string="Group By" should be stripped from <group>',
        )
        # Legit attrs preserved
        self.assertIn('name="country"', arch_group)
        self.assertIn('string="Country"', arch_group)

        view_field = self.env["ir.ui.view"].search(
            [("name", "=", "test search field_expand")]
        )
        self.assertTrue(view_field)
        arch_field = view_field.arch_db
        self.assertNotIn(
            'expand="1"',
            arch_field,
            "expand= should be stripped from <field> in searchpanel",
        )
        # Legit attrs preserved
        self.assertIn('select="multi"', arch_field)
        self.assertIn('name="country_id"', arch_field)
