# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

_legacy_sale_delay = openupgrade.get_legacy_name("sale_delay")


def _release_accrued_revenue_action(env):
    """The accrued revenue entry action changed type, keeping its external id.

    19.0 shipped it as an ir.actions.act_window, 20.0 as an ir.actions.server,
    and the loader will not bind an id to a record of another model. Sweeping
    every ir.actions.server id in the 20.0 source against this database, it is
    the only one left in that state.
    """
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE module = 'sale'
          AND name = 'action_accrued_revenue_entry_sale_order_line'
          AND model = 'ir.actions.act_window'
        """,
    )


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
    _release_accrued_revenue_action(env)
