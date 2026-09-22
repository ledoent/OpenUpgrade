from openupgradelib import openupgrade

# 19.0 consolidated the VAT tax report: section "*_base"/sub-line xml_ids that
# were account.report.line in 18.0 are reused as account.report.expression on the
# merged lines. The data load can't overwrite a line record with expression
# values; free those xml_ids so the new expressions are created cleanly (the
# superseded 18.0 lines are residual -> database_cleanup).
_REUSED_AS_EXPRESSION = (
    "tax_report_line_adjustment_import_uae_base",
    "tax_report_line_exempt_supplies_base",
    "tax_report_line_expense_supplies_reverse_base",
    "tax_report_line_import_uae_base",
    "tax_report_line_standard_rated_expense_base",
    "tax_report_line_supplies_reverse_charge_base",
    "tax_report_line_tax_refund_tourist_base",
    "tax_report_line_zero_rated_supplies_base",
)


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE module = 'l10n_ae'
          AND model = 'account.report.line'
          AND name IN %s
        """,
        (_REUSED_AS_EXPRESSION,),
    )
