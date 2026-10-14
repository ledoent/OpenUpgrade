# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    """Point existing points of sale at the default product 20.0 ships.

    pos.config.default_product_id is new in 20.0 and defaults to
    `pos_sale.default_sol_product`, a product the module itself loads. A default
    only runs for rows created after it exists, so every point of sale that
    predates the upgrade comes out with none and cannot price a productless
    sale order line -- while one created a minute later can.

    This is the case the OCA retrospective records us getting wrong last cycle:
    a default is not automatically safe, and the question is what it means on a
    row that already existed. Here it means the same as on a new one, so the
    rows are brought into line with what a fresh install would have.

    Only the empty ones: a point of sale that already names a product chose it.
    """
    product = env.ref("pos_sale.default_sol_product", raise_if_not_found=False)
    if not product:
        return
    openupgrade.logged_query(
        env.cr,
        "UPDATE pos_config SET default_product_id = %s "
        "WHERE default_product_id IS NULL",
        (product.id,),
    )
