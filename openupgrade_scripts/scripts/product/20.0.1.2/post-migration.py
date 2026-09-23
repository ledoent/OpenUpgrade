# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


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
