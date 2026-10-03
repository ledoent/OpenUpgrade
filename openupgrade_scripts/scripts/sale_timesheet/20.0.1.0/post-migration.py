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


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "sale_timesheet", "20.0.1.0/noupdate_changes.xml")
    _carry_the_invoiced_timesheet_link_onto_its_new_column(env)
