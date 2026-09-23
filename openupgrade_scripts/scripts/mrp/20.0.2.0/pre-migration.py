# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 20.0 drops the product_ prefix from the unit of measure field.
_renamed_fields = [
    ("mrp.bom", "mrp_bom", "product_uom_id", "uom_id"),
    ("mrp.bom.byproduct", "mrp_bom_byproduct", "product_uom_id", "uom_id"),
    ("mrp.bom.line", "mrp_bom_line", "product_uom_id", "uom_id"),
    ("mrp.production", "mrp_production", "product_uom_id", "uom_id"),
    ("mrp.unbuild", "mrp_unbuild", "product_uom_id", "uom_id"),
    ("mrp.workcenter.capacity", "mrp_workcenter_capacity", "product_uom_id", "uom_id"),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
