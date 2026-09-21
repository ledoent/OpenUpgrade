# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# pylint: disable=odoo-addons-relative-import
from odoo.addons.openupgrade_scripts.helpers import release_xmlid

_legacy_sale_delay = openupgrade.get_legacy_name("sale_delay")


@openupgrade.migrate()
def migrate(env, version):
    # product.template.sale_delay moves from stock to sale and becomes
    # company_dependent, which in 20.0 means jsonb storage on the table rather
    # than an ir.property row. Postgres cannot cast the existing integer column
    # to jsonb, so the ORM's own conversion fails; park the values under a
    # legacy name and let sale create the jsonb column cleanly. post-migration
    # puts them back.
    if openupgrade.column_exists(env.cr, "product_template", "sale_delay"):
        openupgrade.rename_columns(
            env.cr, {"product_template": [("sale_delay", _legacy_sale_delay)]}
        )
    # 19.0 shipped the accrued revenue entry action as an
    # ir.actions.act_window, 20.0 as an ir.actions.server. Sweeping every
    # ir.actions.server id in the 20.0 source against this database, it is the
    # only one left in that state.
    release_xmlid(
        env.cr,
        "sale.action_accrued_revenue_entry_sale_order_line",
        "ir.actions.act_window",
    )
