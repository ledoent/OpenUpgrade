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

    def test_bank_holder_name_is_the_holder_not_the_partner(self):
        """acc_holder_name carries, instead of being invented from the partner.

        20.0 renamed the field to holder_name and made it a stored compute whose
        body is `if not account.holder_name: account.holder_name =
        account.partner_id.name` (res_partner_bank.py:167-170). That guard means
        it never overwrites -- it fills an EMPTY column, which is what an
        unrenamed holder_name is. So without the rename the account quietly
        displays the partner's name as its holder: plausible, wrong, and
        invisible, while the real holder sits unread in the legacy column.

        Measured on the sanitised prod copy before the rename was added: 13 of
        19 accounts carried a holder and 4 disagreed with what the compute
        wrote, "Ledo Enterprises LLC" showing as "Ledo Enterprises".

        The fixture's holder differs from its partner's name, so this assertion
        fails if the rename is dropped rather than passing on the compute.
        """
        bank = self.env["res.partner.bank"].search(
            [("partner_id.name", "=", "ou19-bank-partner")]
        )
        self.assertTrue(bank)
        self.assertEqual(bank.holder_name, "ou19-holder-not-the-partner")
        self.assertNotEqual(bank.holder_name, bank.partner_id.name)

    def test_the_bank_record_was_inlined_onto_the_account(self):
        """res.bank is deleted in 20.0 and its address moves onto the account.

        The fields land in a "# bank fields" block on res.partner.bank. Nothing
        in core carries them, and the orphaned res_bank table plus the surviving
        bank_id column are the only places the values still exist -- until
        database_cleanup removes them.
        """
        bank = self.env["res.partner.bank"].search(
            [("partner_id.name", "=", "ou19-bank-partner")]
        )
        self.assertTrue(bank)
        self.assertEqual(bank.bank_name, "ou19-bank-name")
        self.assertEqual(bank.bank_bic, "OU19BICXXX")
        self.assertEqual(bank.street, "ou19-bank-street")
        self.assertEqual(bank.street2, "ou19-bank-street2")
        self.assertEqual(bank.zip, "94105")
        self.assertEqual(bank.city, "ou19-bank-city")
        self.assertEqual(bank.state_id.code, "CA")
        self.assertEqual(bank.state_id.country_id.code, "US")

    def test_the_inlined_country_is_the_banks_not_the_partners(self):
        """country_id is a precompute over the PARTNER, in a bank-address block.

        `_compute_country_id` assigns `partner_id.country_id or
        company_id.country_id or env.company.country_id`
        (res_partner_bank.py:140-143), so the upgrade fills the field from the
        account holder while the form labels it part of the bank's address. The
        fixture puts the partner in France and its bank in the United States,
        which is the only arrangement that can tell the two apart.
        """
        bank = self.env["res.partner.bank"].search(
            [("partner_id.name", "=", "ou19-bank-partner")]
        )
        self.assertTrue(bank)
        self.assertEqual(bank.country_id, self.env.ref("base.us"))
        self.assertNotEqual(bank.country_id, bank.partner_id.country_id)

    def test_the_registry_landed_under_the_countrys_own_identifier(self):
        """A value that fits FR_SIREN is filed as one, not as a generic ID.

        'OTHER' would be lossless and invisible:
        _compute_available_additional_identifiers_metadata pops it for any
        country that has an EN identifier of its own, whether or not it is
        already stored (res_partner.py:1647-1649).
        """
        partner = self.env["res.partner"].search(
            [("name", "=", "ou19-registry-structured")]
        )
        self.assertTrue(partner)
        self.assertEqual(partner.additional_identifiers.get("FR_SIREN"), "404833048")

    def test_a_registry_fitting_no_format_stays_generic(self):
        """The fallback must not write a value its own constraint rejects.

        `@api.constrains('additional_identifiers')` revalidates every key with
        validation='error' (res_partner.py:1378-1385), so filing free text under
        FR_SIREN would leave the partner permanently unsavable. 'OTHER' has no
        validator, so the value survives and the partner still saves.
        """
        partner = self.env["res.partner"].search(
            [("name", "=", "ou19-registry-unstructured")]
        )
        self.assertTrue(partner)
        self.assertEqual(
            partner.additional_identifiers.get("OTHER"), "ou19-not-a-siren"
        )
        self.assertNotIn("FR_SIREN", partner.additional_identifiers)
        # The record must still be writable, which is the whole point of the
        # fallback. Re-writing the Json itself is what proves it: @api.constrains
        # only fires for the fields it names, so touching any other field would
        # pass regardless of what is stored here.
        partner.write({"additional_identifiers": partner.additional_identifiers})

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

    def test_the_company_kept_the_table_style_of_its_19_layout(self):
        """19.0 baked the table style into the layout; 20.0 made it a field.

        The style has to be read in PRE-migration, and the fixture's choice of
        'bold' is what proves it: 20.0 does not ship external_layout_bold, so
        web's data load deletes that view and the company's
        external_report_layout_id is NULL by the time post-migration runs. A
        script reading the layout at that point would find nothing and leave
        every such company on the 'light' default, restyling its documents.
        """
        company = self.env.ref("__ou19__.ou19_layout_company", raise_if_not_found=False)
        self.assertTrue(company, "the fixture's company is gone")
        self.assertEqual(company.report_tables_id, "bold")
