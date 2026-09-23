# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # 19.0 hung an extra product image off one variant through
    # product.image.product_variant_id. 20.0 hangs every image off the template
    # and says which variants it belongs to through attribute_value_ids, so the
    # old column is the only record of which variant an image was for.
    # post-migration reads it back.
    if openupgrade.column_exists(env.cr, "product_image", "product_variant_id"):
        openupgrade.rename_columns(
            env.cr, {"product_image": [("product_variant_id", None)]}
        )
