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

    def test_the_contact_us_url_survived_its_own_default(self):
        """contact_us_button_url -> contact_us_link_url, same default both sides.

        Both versions declare default="/contactus", so the new column is created
        already holding it. Without the rename a site that pointed the button
        anywhere else reads "/contactus" while its own value sits in a column
        20.0 never looks at -- nothing fails, the link is just wrong.
        """
        website = self.env.ref("__ou19__.ou19_website_disagreeing")
        self.assertEqual(website.contact_us_link_url, "/ou19-contact-somewhere-else")

    def test_a_website_whose_categories_agree_takes_their_flag(self):
        """The setting moved from product.public.category to website.

        show_category_description defaults True on the website, so a shop that
        had turned descriptions off gets them back. This website sees only the
        global categories, which all say False, so False is what it must read --
        a value 20.0's default cannot produce.
        """
        website = self.env.ref("__ou19__.ou19_website_agreeing")
        self.assertFalse(website.show_category_description)

    def test_a_website_whose_categories_disagree_is_left_alone(self):
        """One website-wide flag cannot answer for categories that differ.

        This website's own category says True while every global one says False.
        Imposing either would claim a choice nobody made, so the flag keeps
        20.0's default and the disagreement is reported instead.
        """
        website = self.env.ref("__ou19__.ou19_website_disagreeing")
        self.assertTrue(website.show_category_description)

    def test_the_reference_price_is_still_shown(self):
        """19.0 gated it on a group; 20.0 also needs a per-website flag.

        The flag is a plain Boolean with no default, so it arrives False and the
        $/kg price disappears from a shop that was showing it. The fixture
        enables the group, which is the whole of what 19.0 required.
        """
        self.assertTrue(
            self.env["res.groups"]._is_feature_enabled(
                "website_sale.group_show_uom_price"
            ),
            "the fixture's feature group did not survive",
        )
        websites = self.env["website"].search([])
        self.assertTrue(websites)
        self.assertEqual(
            websites.filtered(lambda w: not w.show_product_reference_price),
            self.env["website"],
            "a website stopped showing the reference price",
        )
