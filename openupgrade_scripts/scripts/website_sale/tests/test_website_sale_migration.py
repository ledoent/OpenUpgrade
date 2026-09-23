from openupgradelib import openupgrade

from odoo.tests import TransactionCase

from odoo.addons.openupgrade_framework import openupgrade_test


@openupgrade_test
class TestWebsiteSaleMigration(TransactionCase):
    """Assertions on extra variant images moving onto the template.

    Every method opens by asserting the record exists. The data snippet runs in
    a separate process through the 19.0 shell, and if its commit were lost it
    would exit 0 having written nothing -- an assertion whose empty case is a
    pass would then report success for a migration that never happened.
    """

    def _image(self, shape):
        image = (
            self.env["product.image"]
            .with_context(active_test=False)
            .search([("name", "=", f"ou19-image-{shape}")])
        )
        self.assertEqual(len(image), 1, f"the {shape} fixture image is missing")
        return image

    def test_a_combination_image_keeps_the_variant_it_was_for(self):
        """The image gets the template and the variant's attribute values.

        Both are needed. The template alone would show it on every variant of
        the product; the attribute values are what 20.0 matches against to put
        it back on the one variant 19.0 attached it to.
        """
        image = self._image("combination")
        self.assertTrue(image.product_tmpl_id, "the image has no template")
        self.assertTrue(
            image.attribute_value_ids, "the image lost the combination it was for"
        )
        self.assertTrue(
            image.has_attribute_value,
            "has_attribute_value is stored and was not recomputed",
        )
        variant = image.product_tmpl_id.product_variant_ids.filtered(
            lambda v: image.attribute_value_ids
            <= v.product_template_attribute_value_ids
        )
        self.assertTrue(variant, "no variant matches the values the image carries")
        self.assertIn(
            image,
            variant[0].variant_image_ids,
            "the image is not among the variant's images",
        )

    def test_an_only_variant_image_becomes_a_template_image(self):
        """With one variant there is no combination to be specific about.

        The template on its own says exactly what 19.0 said, so the image must
        not acquire attribute values it never had.
        """
        image = self._image("only-variant")
        self.assertTrue(image.product_tmpl_id, "the image has no template")
        self.assertFalse(
            image.attribute_value_ids,
            "the image was given a combination that 19.0 did not record",
        )
        self.assertIn(image, image.product_tmpl_id.product_template_image_ids)

    def test_an_orphan_image_is_kept_rather_than_moved_or_dropped(self):
        """An obsolete combination has nothing faithful to attach to.

        Its variant carries no attribute values but the template has others, so
        giving the image to the template would show it on every variant --
        broader than 19.0 ever showed it. It stays put and post-migration
        reports it.
        """
        image = self._image("orphan")
        self.assertFalse(
            image.product_tmpl_id,
            "the orphan image was attached to a template it was never on",
        )
        legacy = openupgrade.get_legacy_name("product_variant_id")
        self.env.cr.execute(
            f"SELECT {legacy} FROM product_image WHERE id = %s", (image.id,)
        )
        self.assertTrue(
            self.env.cr.fetchone()[0], "the variant it came from was not preserved"
        )

    def test_no_extra_image_is_left_belonging_to_nothing_by_accident(self):
        """Every image that could be carried was carried.

        The three methods above each watch one record. This one is the count:
        an image with a 19.0 variant and no template is only acceptable when it
        is one of the orphans, and anything else means a shape went unhandled.
        """
        legacy = openupgrade.get_legacy_name("product_variant_id")
        self.env.cr.execute(
            f"""
            SELECT count(*) FROM product_image i
            JOIN product_product p ON p.id = i.{legacy}
            WHERE i.product_tmpl_id IS NULL
              AND (
                EXISTS (SELECT 1 FROM product_variant_combination v
                        WHERE v.product_product_id = p.id)
                OR NOT EXISTS (SELECT 1 FROM product_product q
                               WHERE q.product_tmpl_id = p.product_tmpl_id
                                 AND q.id != p.id)
              )
            """
        )
        self.assertEqual(
            self.env.cr.fetchone()[0],
            0,
            "an image that could have been carried was left without a template",
        )
