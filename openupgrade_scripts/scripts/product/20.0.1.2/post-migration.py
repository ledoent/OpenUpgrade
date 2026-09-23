# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _carry_attribute_exclusions(env):
    """Keep the attribute combinations a template refuses to sell.

    19.0 held an exclusion as a record of its own,
    product.template.attribute.exclusion, joining the value that excludes to
    the values it excludes. 20.0 drops the model and holds the same thing as a
    many2many straight between the two values.

    Nothing carries it, so every exclusion is lost, and losing one is not
    quiet: _create_variant_ids reads excluded_value_ids to decide which
    combinations exist, so a pairing the shop deliberately refused becomes a
    variant a customer can buy.

    The direction is preserved as recorded rather than written both ways. 19.0
    stored it one way too, and adding the reverse would exclude pairings the
    template never excluded.
    """
    if not openupgrade.table_exists(env.cr, "product_template_attribute_exclusion"):
        return
    openupgrade.logged_query(
        env.cr,
        """
        INSERT INTO product_template_attribute_excluded_value_ids_rel
            (product_template_attribute_value_id,
             excluded_product_template_attribute_value_id)
        SELECT e.product_template_attribute_value_id,
               r.product_template_attribute_value_id
        FROM product_template_attribute_exclusion e
        JOIN product_attr_exclusion_value_ids_rel r
          ON r.product_template_attribute_exclusion_id = e.id
        WHERE e.product_template_attribute_value_id IS NOT NULL
          AND e.product_template_attribute_value_id
              != r.product_template_attribute_value_id
        ON CONFLICT DO NOTHING
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    """20.0 replaces the pricelist Formula rule with an explicit discount or markup.

    19.0 offered percentage ("Discount"), formula ("Formula") and fixed. 20.0
    offers discount, markup ("Surcharge") and fixed, and adds price_markup
    alongside the price_discount it keeps. A selection is enforced in Python,
    so a rule keeping an old key reads as blank and prices from neither branch.

    percentage carried the same label 20.0 gives discount, so it maps straight
    across. formula expressed both directions through the sign of
    price_discount: positive took a percentage off, negative added one on. 20.0
    splits that in two, so the sign decides which, and a negative discount
    becomes a positive markup rather than being carried over as a negative.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE product_pricelist_item
        SET price_markup = -price_discount, price_discount = 0,
            compute_price = 'markup'
        WHERE compute_price = 'formula' AND price_discount < 0
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE product_pricelist_item SET compute_price = 'discount'
        WHERE compute_price IN ('formula', 'percentage')
        """,
    )
    _carry_attribute_exclusions(env)
