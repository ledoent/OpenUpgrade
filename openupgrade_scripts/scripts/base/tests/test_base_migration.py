from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestBaseMigration(TransactionCase):
    """Assertions on the ir.model.access / ir.rule fold into ir.access.

    Every method opens by asserting the records exist. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _access(self, name):
        return (
            self.env["ir.access"]
            .with_context(active_test=False)
            .search([("name", "=", name)])
        )

    def test_permissions_become_operation(self):
        """The four perm_ booleans concatenate into the crud selection."""
        access_ru = self._access("ou19-access-ru")
        self.assertTrue(access_ru)
        self.assertEqual(len(access_ru), 1)
        # perm_write is "u" for update, not "w", and the letters are ordered
        # c, r, u, d regardless of which were set.
        self.assertEqual(access_ru.operation, "ru")
        self.assertEqual(access_ru.model_id, self.env.ref("base.model_res_partner"))
        self.assertEqual(access_ru.group_id, self.env.ref("base.group_user"))
        self.assertFalse(access_ru.domain)

        access_cd = self._access("ou19-access-cd")
        self.assertTrue(access_cd)
        self.assertEqual(access_cd.operation, "cd")

    def test_external_id_survives_the_rename(self):
        """Renaming the table rather than copying rows keeps ids, so xml_ids hold."""
        access = self.env.ref("__ou19__.ou19_access_ru")
        self.assertEqual(access._name, "ir.access")
        self.assertEqual(access.operation, "ru")

    def test_inactive_access_line_survives(self):
        """An archived line is migrated and stays archived."""
        access = self._access("ou19-access-inactive")
        self.assertTrue(access)
        self.assertFalse(access.active)
        self.assertEqual(access.operation, "r")

    def test_access_line_granting_nothing_is_dropped(self):
        """operation is required and has no value meaning "nothing"."""
        self.assertFalse(self._access("ou19-access-none"))
        self.assertFalse(
            self.env.ref("__ou19__.ou19_access_none", raise_if_not_found=False)
        )

    def test_rule_fans_out_one_row_per_group(self):
        rows = self._access("ou19-rule-multigroup")
        self.assertTrue(rows)
        self.assertEqual(len(rows), 3)
        self.assertItemsEqual(
            rows.mapped("group_id"),
            self.env.ref("base.group_user")
            + self.env.ref("base.group_system")
            + self.env.ref("base.group_portal"),
        )
        self.assertEqual(set(rows.mapped("operation")), {"ru"})
        # Compare the domain as a string: an eval-equal comparison would not
        # notice a silent re-serialisation.
        self.assertEqual(set(rows.mapped("domain")), {"[('id', '!=', 0)]"})

    def test_only_one_of_the_fanned_rows_keeps_the_external_id(self):
        """The script maps min(id); which row that is depends on join order."""
        rows = self._access("ou19-rule-multigroup")
        self.assertEqual(len(rows), 3)
        named = self.env.ref("__ou19__.ou19_rule_multigroup")
        self.assertEqual(named._name, "ir.access")
        self.assertIn(named, rows)
        self.assertEqual(
            self.env["ir.model.data"].search_count(
                [("model", "=", "ir.access"), ("res_id", "in", rows.ids)]
            ),
            1,
        )

    def test_rule_without_groups_becomes_one_global_row(self):
        rows = self._access("ou19-rule-global")
        self.assertTrue(rows)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows.group_id)

    def test_unnamed_rule_is_labelled_with_its_model(self):
        rows = (
            self.env["ir.access"]
            .with_context(active_test=False)
            .search([("domain", "=", "[('id', '!=', -4220)]")])
        )
        self.assertTrue(rows)
        self.assertEqual(rows.name, "res.partner")

    def test_nothing_still_points_at_the_dead_models(self):
        self.assertEqual(
            self.env["ir.model.data"].search_count(
                [("model", "in", ("ir.model.access", "ir.rule"))]
            ),
            0,
        )

    def test_bank_account_number_is_renamed_not_recreated(self):
        """acc_number and its sanitized twin carry their values into 20.0.

        Renaming the columns rather than letting the ORM add empty ones is the
        whole point: without it every bank account in the database reads as
        having no number, and the upgrade says so in a line it does not fail
        on -- "Constraint not added: column account_number of relation
        res_partner_bank contains null values".
        """
        bank = self.env["res.partner.bank"].search(
            [("partner_id.name", "=", "ou19-bank-partner")]
        )
        self.assertTrue(bank)
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank.account_number, "ou19-acct 0042/7")
        # Carried across, not recomputed from an empty column: the stored
        # sanitized value strips punctuation and upper-cases.
        self.assertEqual(bank.sanitized_account_number, "OU19ACCT00427")

    def test_no_bank_account_lost_its_number(self):
        """The rename is global, so nothing anywhere should be left blank.

        Asserting on the fixture alone would pass even if the rename had only
        caught the rows the test itself created.
        """
        self.assertTrue(self.env["res.partner.bank"].search_count([]))
        self.assertEqual(
            self.env["res.partner.bank"].search_count([("account_number", "=", False)]),
            0,
        )
