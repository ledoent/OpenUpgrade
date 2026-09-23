# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_variant = openupgrade.get_legacy_name("product_variant_id")


def _reattach_variant_images(env):
    """Give every extra variant image back to a template, the way 20.0 holds it.

    19.0 attached the image to one variant. 20.0 attaches it to the template and
    works out which variants it is for by matching its attribute_value_ids
    against the variant's, so an image with neither a template nor attribute
    values belongs to nothing: product_template_image_ids does not contain it,
    _compute_variant_image_ids never sees it, and the image is gone from the
    shop while its row sits in the table.

    Two shapes carry exactly, and are done separately because the faithful
    answer differs:

      the variant has attribute values -- the image was for that combination, so
      it gets the template and those values, and stays specific to it

      the variant has none and is the template's only one -- there is no
      combination to be specific about, so the template alone says what 19.0
      said

    A variant with no attribute values on a template that has several is neither:
    it is an obsolete combination, archived on the seed. Giving its image to the
    template would put it on every variant, which is broader than 19.0 showed it,
    so it is left alone and reported.
    """
    if not openupgrade.column_exists(env.cr, "product_image", _legacy_variant):
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE product_image i
        SET product_tmpl_id = p.product_tmpl_id
        FROM product_product p
        WHERE p.id = i.{_legacy_variant}
          AND i.product_tmpl_id IS NULL
          AND (
            EXISTS (SELECT 1 FROM product_variant_combination v
                    WHERE v.product_product_id = p.id)
            OR NOT EXISTS (SELECT 1 FROM product_product q
                           WHERE q.product_tmpl_id = p.product_tmpl_id
                             AND q.id != p.id)
          )
        """,
    )
    openupgrade.logged_query(
        env.cr,
        f"""
        INSERT INTO product_image_attribute_value_rel
            (product_image_id, product_template_attribute_value_id)
        SELECT i.id, v.product_template_attribute_value_id
        FROM product_image i
        JOIN product_product p ON p.id = i.{_legacy_variant}
        JOIN product_variant_combination v ON v.product_product_id = p.id
        WHERE i.product_tmpl_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """,
    )
    # has_attribute_value is stored and computed from the values just inserted,
    # which no compute will be triggered for here.
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE product_image i
        SET has_attribute_value = TRUE
        WHERE NOT coalesce(i.has_attribute_value, FALSE)
          AND EXISTS (SELECT 1 FROM product_image_attribute_value_rel r
                      WHERE r.product_image_id = i.id)
        """,
    )
    # variant_image_ids is a stored computed many2many. The rows above give the
    # compute its input but nothing asks it to run, so the relation it stores
    # stays empty and the images are on the template while every variant reports
    # none -- which the SQL cannot show and the migration test did.
    env.cr.execute(
        f"""
        SELECT DISTINCT p.id
        FROM product_product p
        JOIN product_image i ON i.product_tmpl_id = p.product_tmpl_id
        WHERE i.{_legacy_variant} IS NOT NULL
        """
    )
    products = (
        env["product.product"]
        .with_context(active_test=False)
        .browse([row[0] for row in env.cr.fetchall()])
    )
    if products:
        products.invalidate_recordset(["product_template_image_ids"])
        products._compute_variant_image_ids()
        products.flush_recordset(["variant_image_ids"])
    env.cr.execute(
        f"""
        SELECT count(*) FROM product_image i
        WHERE i.{_legacy_variant} IS NOT NULL AND i.product_tmpl_id IS NULL
        """
    )
    stranded = env.cr.fetchone()[0]
    if stranded:
        openupgrade.message(
            env.cr,
            "website_sale",
            False,
            False,
            "%s extra product images were attached to a variant that carries no "
            "attribute values on a template that has several, so there is no "
            "combination to attach them to; they are kept but no longer shown, "
            "and need attaching to a product by hand",
            stranded,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "website_sale", "20.0.1.1/noupdate_changes.xml")
    _reattach_variant_images(env)
    openupgrade.delete_record_translations(
        env.cr,
        "website_sale",
        ["mail_template_sale_cart_recovery"],
        ["body_html", "subject"],
    )
    openupgrade.delete_record_translations(
        env.cr,
        "website_sale",
        ["ir_cron_send_availability_email"],
        ["name"],
    )
