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

    def test_the_home_menu_keeps_its_page(self):
        """Home is page-backed, and the migration must not unlink the page.

        20.0 dropped `url` from core's `website.menu_home` record, because the
        field is computed from the page now. The generated noupdate_changes.xml
        emitted it empty, and loading an empty url runs _inverse_url, whose
        first branch is `if not menu.url: menu.page_id = None`. Home then
        computed to "#" -- a navigation entry pointing nowhere, on a record no
        19.0 database has any problem with.

        Asserting on `url` as well as on page_id is deliberate: page_id alone
        would still pass if the page's own url were lost.
        """
        menu = self.env.ref("website.menu_home")
        self.assertTrue(menu.page_id, "menu_home lost its page link")
        self.assertEqual(menu.url, "/")

    def test_no_menu_was_left_pointing_nowhere(self):
        """The carry is global, not just the row the fixture planted.

        A menu with no page and no manual_url computes to "#". Counting them
        against the legacy column is what shows the script reached every one.

        Module-data menus are counted too. They used to be excluded, on the
        belief that the upgrade rewrites its own records and a migration could
        not hold a value there -- and that exclusion was hiding `menu_home`,
        which the script itself was unlinking from its page (see
        test_the_home_menu_keeps_its_page). An exclusion that happens to cover
        the one broken row is indistinguishable from no assertion.
        """
        self.env.cr.execute(
            """
            SELECT count(*) FROM website_menu m
            WHERE m.page_id IS NULL AND m.controller_page_id IS NULL
              AND coalesce(m.manual_url, '') = ''
              AND m.url IS NOT NULL AND m.url NOT IN ('', '#')
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "a menu kept its 19.0 address only in the column 20.0 stopped reading",
        )
