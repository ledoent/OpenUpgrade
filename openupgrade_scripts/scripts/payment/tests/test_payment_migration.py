from openupgradelib import openupgrade

from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestPaymentMigration(TransactionCase):
    """Assertions on the payment_method_ids many2many becoming a one2many.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _provider(self, name):
        return (
            self.env["payment.provider"]
            .with_context(active_test=False)
            .search([("name", "=", name)])
        )

    def test_the_relation_table_is_preserved_for_the_fan_out(self):
        """pre-migration keeps the 19.0 many2many, unhooked from its keys.

        It is the only record of which provider supported which method, and
        end-migration drives the fan-out from it. Keeping the table under its
        own name would not be enough: its foreign keys cascade, so deleting the
        obsolete provider-agnostic methods would empty it.
        """
        legacy = openupgrade.get_legacy_name("payment_method_payment_provider_rel")
        self.env.cr.execute("SELECT to_regclass(%s)", (legacy,))
        self.assertTrue(self.env.cr.fetchone()[0], f"{legacy} is gone")
        self.env.cr.execute(f"SELECT count(*) FROM {legacy}")
        self.assertTrue(self.env.cr.fetchone()[0], f"{legacy} is empty")
        self.env.cr.execute(
            """
            SELECT count(*) FROM pg_constraint
            WHERE conrelid = %s::regclass AND contype IN ('f', 'p')
            """,
            (legacy,),
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "the legacy relation still has keys that would cascade it empty",
        )

    def test_the_fixture_providers_are_where_the_fan_out_will_look(self):
        """One provider supported methods in 19.0 and one did not.

        The fan-out itself runs in end-migration, which Odoo executes after
        every module has loaded -- and therefore after this test, which runs
        when payment loads. So the outcome cannot be asserted here at all; what
        can is that the two cases the fan-out has to tell apart reached it
        intact. The result is checked against the migrated database instead, by
        .github/scripts/check_unapplied_constraints.py and by
        `make renames-20`'s sibling query on payment_method.provider_id.
        """
        legacy = openupgrade.get_legacy_name("payment_method_payment_provider_rel")
        for name, expected in (
            ("ou19-provider-fanout", True),
            ("ou19-provider-nolinks", False),
        ):
            provider = self._provider(name)
            self.assertTrue(provider, name)
            self.assertEqual(len(provider), 1, name)
            self.env.cr.execute(
                f"SELECT count(*) FROM {legacy} WHERE payment_provider_id = %s",
                (provider.id,),
            )
            linked = bool(self.env.cr.fetchone()[0])
            self.assertEqual(linked, expected, name)

    def test_an_enabled_provider_comes_out_in_live_mode(self):
        """19.0's state governs 20.0's is_live, which has no default.

        is_published decides whether customers are offered the provider and
        survives the upgrade untouched; is_live decides whether the payment is
        real. Left at its default an enabled provider is still offered and
        quietly takes nothing, so the two have to move together.

        Unlike the fan-out this runs in post-migration, which Odoo executes
        while payment loads and therefore before this test, so the outcome is
        assertable here.
        """
        for name, expected in (
            ("ou19-provider-live", True),
            ("ou19-provider-test", False),
        ):
            provider = self._provider(name)
            self.assertTrue(provider, name)
            self.assertEqual(len(provider), 1, name)
            self.assertEqual(provider.is_live, expected, name)

    def test_the_provider_state_is_kept_for_post_migration_to_read(self):
        """pre-migration keeps state, which 20.0 drops.

        Odoo leaves a removed field's column alone, so post-migration could
        read `state` as it stands -- until some other module declares a state
        on payment.provider and the value silently becomes that module's. The
        legacy name is the column this migration owns.
        """
        legacy = openupgrade.get_legacy_name("state")
        self.env.cr.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'payment_provider' AND column_name = %s
            """,
            (legacy,),
        )
        self.assertTrue(self.env.cr.fetchone()[0], f"payment_provider.{legacy} is gone")
        self.env.cr.execute(
            f"SELECT count(*) FROM payment_provider WHERE {legacy} = 'enabled'"
        )
        self.assertTrue(
            self.env.cr.fetchone()[0], "the enabled fixture did not reach the upgrade"
        )
