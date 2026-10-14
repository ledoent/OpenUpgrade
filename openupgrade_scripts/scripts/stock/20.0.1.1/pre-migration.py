# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 20.0 drops the product_ prefix from the unit of measure field.
_renamed_fields = [
    ("stock.move", "stock_move", "product_uom", "uom_id"),
    ("stock.move.line", "stock_move_line", "product_uom_id", "uom_id"),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
