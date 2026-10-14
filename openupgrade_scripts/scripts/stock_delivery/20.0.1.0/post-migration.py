# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# Both moved from the template to the variant, and both are plain stored Char /
# Many2one on either side, so the values copy straight across.
_MOVED = ("hs_code", "country_of_origin")


@openupgrade.migrate()
def migrate(env, version):
    """hs_code and country_of_origin move from product.template to product.product.

    19.0 stored both on product.template. 20.0 stores them on product.product
    and leaves the template a *computed, non-stored* view of its single variant,
    with an inverse that writes back. So the direction reverses, and the
    template column stops being read at all.

    OpenUpgrade keeps that column, which is what makes this quiet: nothing
    raises, no constraint is missed, and every product simply comes out of the
    upgrade with no HS code and no origin. On a customs-declaring database that
    is the whole of the data.

    Every variant of a template takes the template's value, because in 19.0 the
    value applied to the template as a whole. 20.0's own compute only surfaces a
    variant value back onto the template when there is exactly one variant,
    which is a display rule rather than a reason to migrate fewer rows.

    Nothing to assert on the seed: both columns are empty there in 19.0 and in
    20.0 alike, so this is one the dataset cannot discriminate -- the evidence
    is the pair of field definitions, not a row count.
    """
    for field in _MOVED:
        if not openupgrade.column_exists(env.cr, "product_template", field):
            continue
        openupgrade.logged_query(
            env.cr,
            f"""
            UPDATE product_product pp
            SET {field} = pt.{field}
            FROM product_template pt
            WHERE pt.id = pp.product_tmpl_id
              AND pt.{field} IS NOT NULL
              AND pp.{field} IS NULL
            """,
        )
