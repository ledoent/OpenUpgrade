# Copyright 2026 Don Kendall
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


def _carry_the_invoiced_timesheet_link_onto_its_new_column(env):
    """20.0 renamed the timesheet->invoice link, across a module boundary.

    19.0  account.move.timesheet_ids = One2many(..., "timesheet_invoice_id")
    20.0  account.move.timesheet_ids = One2many(..., "reinvoice_move_id")

    The analysis cannot see that as a rename because the two halves belong to
    different modules: the DEL is reported here in sale_timesheet, while the
    NEW reinvoice_move_id is reported in sale. Nothing correlates them, so the
    old column is preserved untouched and the new one is created empty -- and
    an invoice silently shows no timesheets.

    That is not cosmetic for a timesheet-billed company. The link is what
    `_is_line_reinvoicable` consults to decide a timesheet has already been
    invoiced (sale_timesheet/models/sale_order_line.py:168), so a line that
    lost it becomes billable a second time.

    This went unnoticed because both sides were annotated NOTHING TO DO against
    a seed where no timesheet had ever been invoiced -- 0 of 531 rows. A verdict
    of "the column held nothing" is only ever as good as the data it was
    measured on; the first real database had 33.
    """
    legacy = "timesheet_invoice_id"
    if not openupgrade.column_exists(env.cr, "account_analytic_line", legacy):
        return
    openupgrade.logged_query(
        env.cr,
        f"""
        UPDATE account_analytic_line
           SET reinvoice_move_id = {legacy}
         WHERE {legacy} IS NOT NULL
           AND reinvoice_move_id IS NULL
        """,
    )


def _open_the_new_gate_on_products_that_were_already_timesheet_billed(env):
    """Keep delivered-timesheet products linking their timesheets on 20.0.

    20.0 adds product.template.reinvoice_policy, default "no", and will only
    link an invoice's analytic lines when the sale line passes
    _is_line_reinvoicable() (sale/models/sale_order_line.py), which requires
    that field to be something other than "no". 19.0 had no such gate: it
    linked by sale line alone.

    So every existing product arrives at "no" and quietly stops linking. An
    invoice posts, claims no timesheets, and anything downstream that reads
    account.move.timesheet_ids sees an empty set -- with nothing in the log.
    The hours also keep counting as still-to-invoice, because
    _timesheet_compute_delivered_quantity_domain treats a NULL
    reinvoice_move_id as not yet billed.

    Only products that were ALREADY billing from timesheets are touched --
    invoice_policy 'delivery' with service_type 'timesheet', both stored on
    both versions -- and only where the column still holds its untouched
    default, so a deliberate choice is never overwritten. "sales_price" is the
    value core's own sale_timesheet tests set for exactly this, and
    sale/models/account_analytic_line.py keys its sale-line sync on it.

    Worth knowing: the field also feeds sale_expense, sale_stock and
    sale_purchase reinvoicing. On a service product that carries no expenses
    that is inert, which is why the predicate is kept this narrow.
    """
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE product_template
           SET reinvoice_policy = 'sales_price'
         WHERE invoice_policy = 'delivery'
           AND service_type = 'timesheet'
           AND coalesce(reinvoice_policy, 'no') = 'no'
        """,
    )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "sale_timesheet", "20.0.1.0/noupdate_changes.xml")
    _carry_the_invoiced_timesheet_link_onto_its_new_column(env)
    _open_the_new_gate_on_products_that_were_already_timesheet_billed(env)
