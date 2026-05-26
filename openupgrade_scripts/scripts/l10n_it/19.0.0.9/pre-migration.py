from openupgradelib import openupgrade

# l10n_it_edi_withholding is being folded into l10n_it in 19.0 (the
# withholding-tax module's records consolidate into the base l10n_it
# Italian-localization module). The 10 records below ship in l10n_it's
# 19.0 data files but had their 18.0 ir_model_data rows under
# module='l10n_it_edi_withholding'.
#
# Without renaming the xmlids in pre-migration, the Odoo install would
# create fresh ir_model_data rows pointing at new res_ids — the legacy
# rows would dangle, and customer references to the previous
# tax-report records (e.g. report-line tags attached to specific
# account.tax records via tag_ids) would be orphaned.
#
# Source: upgrade_analysis.txt — "renamed from l10n_it_edi_withholding
# module" lines.
#
# NOTE: this version of l10n_it also contains a large standard
# tax-report refactor (100+ DEL / 50+ NEW account.report.line and
# account.report.expression records under l10n_it own xmlids). Those
# are handled by the standard module-upgrade flow and don't need
# pre-migration logic — they're not the subject of this script.
# See openupgrade/TODO.md §4.3.1 for the broader campaign note.

_renamed_xmlids = [
    ("l10n_it_edi_withholding.withh_tax_report_it",
     "l10n_it.withh_tax_report_it"),
    ("l10n_it_edi_withholding.withh_tax_report_balance",
     "l10n_it.withh_tax_report_balance"),
    ("l10n_it_edi_withholding.enasarco_purchase_tax_report_it_line_tag",
     "l10n_it.enasarco_purchase_tax_report_it_line_tag"),
    ("l10n_it_edi_withholding.enasarco_sale_tax_report_it_line_tag",
     "l10n_it.enasarco_sale_tax_report_it_line_tag"),
    ("l10n_it_edi_withholding.withh_purchase_tax_report_it_line_tag",
     "l10n_it.withh_purchase_tax_report_it_line_tag"),
    ("l10n_it_edi_withholding.withh_sale_tax_report_it_line_tag",
     "l10n_it.withh_sale_tax_report_it_line_tag"),
    ("l10n_it_edi_withholding.enasarco_purchase_tax_report_it_line",
     "l10n_it.enasarco_purchase_tax_report_it_line"),
    ("l10n_it_edi_withholding.enasarco_sale_tax_report_it_line",
     "l10n_it.enasarco_sale_tax_report_it_line"),
    ("l10n_it_edi_withholding.withh_purchase_tax_report_it_line",
     "l10n_it.withh_purchase_tax_report_it_line"),
    ("l10n_it_edi_withholding.withh_sale_tax_report_it_line",
     "l10n_it.withh_sale_tax_report_it_line"),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
