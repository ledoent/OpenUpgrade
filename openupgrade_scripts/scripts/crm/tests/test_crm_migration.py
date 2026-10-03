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

    Asserted through SQL rather than menu.action because the ORM gives no answer
    either way: `action` is a Reference, so reading it browses the id without
    checking that the row exists, and a dangling one is indistinguishable from a
    live one. The raise happens later, in load_web_menus.
    """

    def _menu_action(self):
        menu = self.env.ref("crm.crm_menu_root", raise_if_not_found=False)
        self.assertTrue(menu, "crm.crm_menu_root is gone")
        self.env.cr.execute("SELECT action FROM ir_ui_menu WHERE id = %s", (menu.id,))
        return self.env.cr.fetchone()[0]

    def test_the_planted_action_was_actually_cleared(self):
        """The fixture puts an action on the menu; the migration must remove it.

        Without this, the suite passes vacuously. Its sibling returns early
        when the menu names nothing -- which is precisely the state a working
        migration leaves behind -- so on a seed whose crm_menu_root never had
        an action it asserts nothing at all, and that is the seed 19.0 core
        actually produces: crm_menu_root is declared with no action
        (addons/crm/views/crm_menu_views.xml:9-14). The defect belongs to
        databases that came up through an older version, which keep the value
        because a menuitem redeclared without an action does not clear one.

        So the fixture plants it and this asserts it is gone.
        """
        self.assertFalse(
            self._menu_action(),
            "crm_menu_root still names an action; post-migration did not clear "
            "the one the fixture planted, and 20.0 deletes it later in the run",
        )

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
            "load_web_menus raises MissingError, so /odoo is dead for every "
            "internal user",
        )

    def test_the_web_client_can_build_its_menu(self):
        """The symptom, not the cause: this is what a user actually hits.

        load_web_menus is what raises on a dangling action. Verified by planting
        a nonexistent action id on crm_menu_root and calling each candidate:
        reading `menu.action` through the ORM does NOT raise (Reference.
        convert_to_record just browses the id), while load_web_menus(False)
        raises MissingError. So this is the assertion that says the database is
        usable rather than merely self-consistent.

        An earlier version of this test rendered website.layout with an empty
        values dict instead. That can never pass -- the template's first
        statement is `lang.replace('_', '-')` and it also wants main_object --
        so it failed for a reason that had nothing to do with the migration.
        """
        self.env["ir.ui.menu"].load_web_menus(False)
