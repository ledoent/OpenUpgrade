from openupgradelib import openupgrade

# l10n_it_edi_withholding's tax-report records move to l10n_it in 19.0. The
# apriori merge (base pre-migration update_module_names) has already renamed
# their ir_model_data module to l10n_it_edi by the time this runs, so the
# rename sources are l10n_it_edi.*; relocate them to l10n_it so customer FKs
# (e.g. account.tax tag_ids) survive instead of being orphaned by a fresh load.
_renamed_xmlids = [
    ("l10n_it_edi.withh_tax_report_it", "l10n_it.withh_tax_report_it"),
    (
        "l10n_it_edi.withh_tax_report_balance",
        "l10n_it.withh_tax_report_balance",
    ),
    (
        "l10n_it_edi.enasarco_purchase_tax_report_it_line_tag",
        "l10n_it.enasarco_purchase_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi.enasarco_sale_tax_report_it_line_tag",
        "l10n_it.enasarco_sale_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi.withh_purchase_tax_report_it_line_tag",
        "l10n_it.withh_purchase_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi.withh_sale_tax_report_it_line_tag",
        "l10n_it.withh_sale_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi.enasarco_purchase_tax_report_it_line",
        "l10n_it.enasarco_purchase_tax_report_it_line",
    ),
    (
        "l10n_it_edi.enasarco_sale_tax_report_it_line",
        "l10n_it.enasarco_sale_tax_report_it_line",
    ),
    (
        "l10n_it_edi.withh_purchase_tax_report_it_line",
        "l10n_it.withh_purchase_tax_report_it_line",
    ),
    (
        "l10n_it_edi.withh_sale_tax_report_it_line",
        "l10n_it.withh_sale_tax_report_it_line",
    ),
]


# The 2026-05 "fix annual report formulas" converted these VL lines'
# aggregation_formula SHORTHAND into explicit expression records. Shorthand
# expressions have no ir_model_data, so the 19.0 data load would CREATE a
# second balance expression on the preserved line and trip the
# (report_line_id, label) unique constraint. Bind the orphan rows to the
# new xml_ids so the load updates them in place.
_shorthand_formula_expressions = [
    ("tax_annual_report_line_vl3", "tax_annual_report_line_vl3_formula"),
    ("tax_annual_report_line_vl4", "tax_annual_report_line_vl4_formula"),
    ("tax_annual_report_line_vl32", "tax_annual_report_line_vl32_formula"),
    ("tax_annual_report_line_vl33", "tax_annual_report_line_vl33_formula"),
]


def _bind_shorthand_formula_expressions(env):
    for line_name, expr_name in _shorthand_formula_expressions:
        env.cr.execute(
            """
            SELECT 1 FROM ir_model_data
            WHERE module = 'l10n_it' AND name = %s
            """,
            (expr_name,),
        )
        if env.cr.fetchone():
            continue
        env.cr.execute(
            """
            SELECT e.id
            FROM account_report_expression e
            JOIN ir_model_data line_imd
              ON line_imd.module = 'l10n_it'
             AND line_imd.model = 'account.report.line'
             AND line_imd.name = %s
             AND line_imd.res_id = e.report_line_id
            LEFT JOIN ir_model_data expr_imd
              ON expr_imd.model = 'account.report.expression'
             AND expr_imd.res_id = e.id
            WHERE e.label = 'balance'
              AND expr_imd.id IS NULL
            """,
            (line_name,),
        )
        row = env.cr.fetchone()
        if row:
            openupgrade.add_xmlid(
                env.cr,
                "l10n_it",
                expr_name,
                "account.report.expression",
                row[0],
            )


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
    _bind_shorthand_formula_expressions(env)
