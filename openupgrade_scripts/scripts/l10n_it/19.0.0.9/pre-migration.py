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


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
