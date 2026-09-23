from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestProductMigration(TransactionCase):
    """Assertions on attribute exclusions becoming a direct many2many.

    No data snippet: the seed already carries exclusions, so these assert over
    all of them rather than over one planted witness. What the snippet usually
    guards against -- an empty source passing for a clean migration -- is
    guarded here by asserting the source is not empty first.
    """

    def _source_pairs(self):
        """The (value, excluded value) pairs 19.0 recorded, from its own tables.

        OpenUpgrade keeps the dropped model's table, which is what makes this
        answerable after the fact rather than only from a fixture.
        """
        self.env.cr.execute(
            """
            SELECT e.product_template_attribute_value_id,
                   r.product_template_attribute_value_id
            FROM product_template_attribute_exclusion e
            JOIN product_attr_exclusion_value_ids_rel r
              ON r.product_template_attribute_exclusion_id = e.id
            WHERE e.product_template_attribute_value_id IS NOT NULL
              AND e.product_template_attribute_value_id
                  != r.product_template_attribute_value_id
            """
        )
        return set(self.env.cr.fetchall())

    def test_the_seed_actually_holds_exclusions_to_carry(self):
        """Otherwise the test below passes on a database with nothing in it."""
        self.assertTrue(
            self._source_pairs(),
            "no 19.0 attribute exclusions in this database, so nothing proves "
            "the carry -- plant one rather than letting this pass",
        )

    def test_every_exclusion_survived_as_a_many2many_pair(self):
        """A lost exclusion is a combination the shop starts selling.

        _create_variant_ids reads excluded_value_ids to decide which variants
        exist, so this is not a cosmetic loss: a pairing the template refused
        becomes one a customer can order.
        """
        self.env.cr.execute(
            """
            SELECT product_template_attribute_value_id,
                   excluded_product_template_attribute_value_id
            FROM product_template_attribute_excluded_value_ids_rel
            """
        )
        carried = set(self.env.cr.fetchall())
        missing = self._source_pairs() - carried
        self.assertFalse(
            missing,
            f"{len(missing)} attribute exclusion(s) were not carried: {missing}",
        )

    def test_the_exclusion_is_readable_through_the_orm(self):
        """The rows have to land where 20.0 looks for them, not just in a table."""
        pairs = self._source_pairs()
        value_id, excluded_id = next(iter(sorted(pairs)))
        value = self.env["product.template.attribute.value"].browse(value_id)
        self.assertIn(
            excluded_id,
            value.excluded_value_ids.ids,
            "the pair is in the relation but the field does not report it",
        )

    def test_no_exclusion_was_invented_in_the_reverse_direction(self):
        """19.0 stored the exclusion one way and so does 20.0.

        Writing the reverse as well would refuse pairings the template never
        refused, which is the same kind of harm as losing one.
        """
        self.env.cr.execute(
            """
            SELECT count(*) FROM product_template_attribute_excluded_value_ids_rel
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            len(self._source_pairs()),
            "the carried pairs do not match the recorded ones one for one",
        )
