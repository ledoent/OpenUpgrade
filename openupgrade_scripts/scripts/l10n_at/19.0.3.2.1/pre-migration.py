from openupgradelib import openupgrade

# 19.0 consolidated the VAT tax report: section "*_base"/sub-line xml_ids that
# were account.report.line in 18.0 are reused as account.report.expression on the
# merged lines. The data load can't overwrite a line record with expression
# values; free those xml_ids so the new expressions are created cleanly (the
# superseded 18.0 lines are residual -> database_cleanup).
_REUSED_AS_EXPRESSION = (
    "tax_report_line_at_tax_title_4_14_19",
    "tax_report_line_at_tax_title_4_28_31",
)


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.logged_query(
        env.cr,
        """
        DELETE FROM ir_model_data
        WHERE module = 'l10n_at'
          AND model = 'account.report.line'
          AND name IN %s
        """,
        (_REUSED_AS_EXPRESSION,),
    )
