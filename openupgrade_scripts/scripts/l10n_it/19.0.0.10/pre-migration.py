from openupgradelib import openupgrade

# l10n_it_edi_withholding folds into l10n_it in 19.0; move the 10 tax-report
# records' ir_model_data ownership so customer FKs (e.g. account.tax tag_ids)
# survive instead of being orphaned by a fresh install.
_renamed_xmlids = [
    ("l10n_it_edi_withholding.withh_tax_report_it", "l10n_it.withh_tax_report_it"),
    (
        "l10n_it_edi_withholding.withh_tax_report_balance",
        "l10n_it.withh_tax_report_balance",
    ),
    (
        "l10n_it_edi_withholding.enasarco_purchase_tax_report_it_line_tag",
        "l10n_it.enasarco_purchase_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi_withholding.enasarco_sale_tax_report_it_line_tag",
        "l10n_it.enasarco_sale_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi_withholding.withh_purchase_tax_report_it_line_tag",
        "l10n_it.withh_purchase_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi_withholding.withh_sale_tax_report_it_line_tag",
        "l10n_it.withh_sale_tax_report_it_line_tag",
    ),
    (
        "l10n_it_edi_withholding.enasarco_purchase_tax_report_it_line",
        "l10n_it.enasarco_purchase_tax_report_it_line",
    ),
    (
        "l10n_it_edi_withholding.enasarco_sale_tax_report_it_line",
        "l10n_it.enasarco_sale_tax_report_it_line",
    ),
    (
        "l10n_it_edi_withholding.withh_purchase_tax_report_it_line",
        "l10n_it.withh_purchase_tax_report_it_line",
    ),
    (
        "l10n_it_edi_withholding.withh_sale_tax_report_it_line",
        "l10n_it.withh_sale_tax_report_it_line",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
