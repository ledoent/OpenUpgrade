# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# pylint: disable=odoo-addons-relative-import
from odoo.addons.openupgrade_scripts.helpers import release_xmlid

_legacy_sale_delay = openupgrade.get_legacy_name("sale_delay")


def _rename_the_reinvoicing_policy(env):
    """expense_policy is renamed reinvoice_policy, and the analysis cannot say so.

    The analysis reports the two halves as unrelated lines -- `expense_policy`
    under DEL, `reinvoice_policy` under NEW -- because nothing in a schema diff
    says they are the same field. They are:

      * the selection is identical, no / cost / sales_price;
      * `visible_expense_policy` is renamed `visible_reinvoice_policy` in the
        same commit, keeping its string "Re-Invoice Policy visible";
      * 20.0's sale_expense reads `reinvoice_policy` to build the tooltip 19.0
        built from `expense_policy`, phrase for phrase -- "Expenses of this
        product may not be added to a Sales Order" for 'no', "at their actual
        cost" for 'cost', "at their sales price" for 'sales_price'.

    Renaming in pre-migration rather than copying in post is what makes it
    survive at all. `reinvoice_policy` is a STORED COMPUTE, and its compute
    assigns nothing except 'no' to products that cannot be sold::

        @api.depends("sale_ok")
        def _compute_reinvoice_policy(self):
            self.filtered(lambda t: not t.sale_ok).reinvoice_policy = "no"

    A stored computed field whose column the ORM has just created is marked to
    compute for every row; one whose column already exists is not. Renaming
    first means the column arrives populated and nothing recomputes over it.

    Without this every product set to re-invoice at cost or at sales price comes
    out reading "No" -- 197 templates in the seed, over three distinct values --
    and expenses on them stop reaching the sales order.
    """
    if openupgrade.column_exists(env.cr, "product_template", "expense_policy"):
        openupgrade.rename_fields(
            env,
            [
                (
                    "product.template",
                    "product_template",
                    "expense_policy",
                    "reinvoice_policy",
                )
            ],
        )


@openupgrade.migrate()
def migrate(env, version):
    _rename_the_reinvoicing_policy(env)
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
