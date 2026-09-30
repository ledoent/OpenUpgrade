from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test

ACTION_TABLES = {
    "ir.actions.act_window": "ir_act_window",
    "ir.actions.server": "ir_act_server",
    "ir.actions.client": "ir_act_client",
    "ir.actions.report": "ir_act_report_xml",
}


@openupgrade_test
class TestCrmMigration(TransactionCase):
    """The CRM root menu must not name an action 20.0 deleted.

    Asserted through SQL rather than menu.action, because the ORM resolves the
    reference and raises before a test could report what it found -- which is
    the same raise that takes the website down.
    """

    def _menu_action(self):
        menu = self.env.ref("crm.crm_menu_root", raise_if_not_found=False)
        self.assertTrue(menu, "crm.crm_menu_root is gone")
        self.env.cr.execute("SELECT action FROM ir_ui_menu WHERE id = %s", (menu.id,))
        return self.env.cr.fetchone()[0]

    def test_the_root_menu_names_nothing_that_was_deleted(self):
        action = self._menu_action()
        if not action:
            return
        model, _, res_id = action.partition(",")
        table = ACTION_TABLES.get(model)
        self.assertTrue(table, f"crm_menu_root names an unknown action model: {model}")
        self.env.cr.execute(f"SELECT 1 FROM {table} WHERE id = %s", (int(res_id),))
        self.assertTrue(
            self.env.cr.fetchone(),
            f"crm_menu_root still points at {action}, which no longer exists -- "
            "every website page, /web/login included, answers 500",
        )

    def test_the_website_layout_can_be_rendered(self):
        """The symptom, not the cause: this is what a user actually hits.

        A dangling menu action raises inside website.layout, so rendering it is
        the assertion that says the database is usable rather than merely
        consistent.
        """
        view = self.env.ref("website.layout", raise_if_not_found=False)
        if not view:
            self.skipTest("website is not installed")
        self.env["ir.ui.view"]._render_template("website.layout", {})
