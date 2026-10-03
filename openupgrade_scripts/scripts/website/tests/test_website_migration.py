from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestWebsiteMigration(TransactionCase):
    """Assertions on website.menu.url becoming a compute over manual_url.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _menu(self, name):
        return self.env["website.menu"].search([("name", "=", name)], limit=1)

    def test_a_hand_typed_menu_still_points_somewhere(self):
        """The address moves from the dropped `url` column into manual_url.

        20.0 computes `url` as `(page_id.url if page_id else manual_url) or "#"`
        (website_menu.py:73-78). With manual_url empty the expression falls
        through to "#", so the menu stays in the navigation bar and goes
        nowhere. Asserting on `url` rather than on manual_url is the point: it
        is what a visitor actually follows.
        """
        menu = self._menu("ou19-hand-typed-menu")
        self.assertTrue(menu, "the fixture's menu is gone")
        self.assertEqual(menu.manual_url, "/ou19-typed-by-hand")
        self.assertEqual(menu.url, "/ou19-typed-by-hand")
        self.assertNotEqual(menu.url, "#", "the menu became a dead link")

    def test_a_hash_menu_was_left_alone(self):
        """'#' is what the compute returns anyway, so carrying it changes nothing.

        Without this the script could copy every legacy url indiscriminately and
        still pass the test above.
        """
        menu = self._menu("ou19-hash-menu")
        self.assertTrue(menu, "the fixture's menu is gone")
        self.assertFalse(menu.manual_url, "'#' was copied into manual_url")
        self.assertEqual(menu.url, "#")

    def test_no_menu_was_left_pointing_nowhere(self):
        """The carry is global, not just the row the fixture planted.

        A menu with no page and no manual_url computes to "#". Counting them
        against the legacy column is what shows the script reached every one.

        Menus that are module data are excluded, and not to make the test pass:
        20.0 rewrites its own records during the upgrade. `website.menu_home` is
        the template menu -- no website_id, no page -- and core's data load puts
        it through _inverse_url, which writes `manual_url = ''` when the url it
        is given is falsy. Its write_date is the migration run itself. A
        migration cannot hold a value there, and the live per-website Home menus
        are page-backed anyway, so they resolve through website.page. 46 of the
        seed's 55 menus are left in scope.
        """
        self.env.cr.execute(
            """
            SELECT count(*) FROM website_menu m
            WHERE m.page_id IS NULL AND m.controller_page_id IS NULL
              AND coalesce(m.manual_url, '') = ''
              AND m.url IS NOT NULL AND m.url NOT IN ('', '#')
              AND NOT EXISTS (
                  SELECT 1 FROM ir_model_data d
                  WHERE d.model = 'website.menu' AND d.res_id = m.id
              )
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a menu kept its 19.0 address only in the column 20.0 stopped reading",
        )
