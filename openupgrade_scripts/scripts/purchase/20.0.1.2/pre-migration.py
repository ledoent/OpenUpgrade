# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 20.0 drops the product_ prefix from the unit of measure field.
_renamed_fields = [
    ("purchase.order.line", "purchase_order_line", "product_uom_id", "uom_id"),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
