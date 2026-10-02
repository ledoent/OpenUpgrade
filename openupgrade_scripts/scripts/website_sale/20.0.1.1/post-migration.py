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


def _aggregate_the_category_display_flags_per_website(env):
    """Three per-category display flags become three per-website ones.

    19.0 held show_category_title, show_category_description and
    align_category_content on product.public.category
    (product_public_category.py:75-91) and read them off the browsed category.
    20.0 holds all three on website (website.py:290-308) and reads
    website.show_category_* instead.

    The ORM wrote show_category_description's default True and left the other
    two NULL, a falsy default not being written at all. So a site that unticked
    "Show Description" gets descriptions back, and one that ticked "Show Title"
    loses titles.

    A website's categories are its own plus the global ones -- 19.0's
    _get_available_category_domain is `website_id in [False, website_id]` -- and
    one website-wide flag cannot faithfully answer for categories that
    disagree. So a flag is carried only where every category that website shows
    agrees on it, and the disagreements are reported. Claiming a value nobody
    chose would be worse than saying it could not be decided.

    A NULL legacy column is read as the 19.0 default for that field -- title
    False, description True, align False -- because that is what the field
    returned for a row nobody ever wrote.
    """
    flags = {
        "show_category_title": ("show_category_title", "false"),
        "show_category_description": ("show_category_description", "true"),
        "align_category_content": ("align_category_content", "false"),
    }
    legacy = {}
    for field, (_target, _default) in flags.items():
        name = openupgrade.get_legacy_name(field)
        if not openupgrade.column_exists(env.cr, "product_public_category", name):
            return
        legacy[field] = name
    selects = []
    for field, (_target, default) in flags.items():
        column = f"coalesce(c.{legacy[field]}, {default})"
        selects.append(f"count(DISTINCT {column})")
        selects.append(f"bool_and({column})")
    env.cr.execute(
        f"""
        SELECT w.id, {", ".join(selects)}
        FROM website w
        JOIN product_public_category c
          ON c.website_id = w.id OR c.website_id IS NULL
        GROUP BY w.id
        """
    )
    carried = 0
    for row in env.cr.fetchall():
        website_id, rest = row[0], row[1:]
        values, disagreed = {}, []
        for index, (field, (target, _default)) in enumerate(flags.items()):
            distinct, agreed = rest[index * 2], rest[index * 2 + 1]
            if distinct == 1:
                values[target] = agreed
            else:
                disagreed.append(field)
        if values:
            assignments = ", ".join(f"{column} = %s" for column in values)
            openupgrade.logged_query(
                env.cr,
                f"UPDATE website SET {assignments} WHERE id = %s",
                (*values.values(), website_id),
            )
            carried += 1
        if disagreed:
            openupgrade.message(
                env.cr,
                "website_sale",
                False,
                False,
                "website %s shows categories that disagree on %s, which 20.0 "
                "keeps once per website rather than per category. The flag was "
                "left on 20.0's default rather than imposing one category's "
                "choice on the rest; set it in the shop settings",
                website_id,
                ", ".join(disagreed),
            )
    if carried:
        openupgrade.message(
            env.cr,
            "website_sale",
            False,
            False,
            "website: carried the category display flags onto %s website(s) from "
            "the categories they show; 20.0 moved the setting off "
            "product.public.category and its defaults would have re-enabled "
            "descriptions and dropped titles",
            carried,
        )


def _enable_the_reference_price_the_group_used_to_gate(env):
    """The $/kg price was gated by a group alone; 20.0 also wants a flag.

    19.0 put base_unit_price into combination_info whenever the feature group
    was on -- `_is_feature_enabled('website_sale.group_show_uom_price')`
    (product_template.py:679), a setting with no per-website dimension at all.
    20.0 keeps the group AND requires website.show_product_reference_price,
    which is a plain Boolean with no default, so it arrives False and the
    reference price disappears from every shop that was showing it.

    The group is read through core's own predicate rather than by inspecting
    implied_ids, so this says exactly what 19.0 said. Because the 19.0 setting
    was global, every website gets the flag: that is the per-website spelling of
    "on everywhere".
    """
    if not env["res.groups"]._is_feature_enabled("website_sale.group_show_uom_price"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE website SET show_product_reference_price = true
        WHERE show_product_reference_price IS NOT TRUE
        """,
    )
    if env.cr.rowcount:
        openupgrade.message(
            env.cr,
            "website_sale",
            False,
            False,
            "website: switched the product reference price on for %s website(s). "
            "19.0 showed it whenever the Show Unit Price group was enabled; 20.0 "
            "also requires a per-website flag that starts off",
            env.cr.rowcount,
        )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "website_sale", "20.0.1.1/noupdate_changes.xml")
    _reattach_variant_images(env)
    _aggregate_the_category_display_flags_per_website(env)
    _enable_the_reference_price_the_group_used_to_gate(env)
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
