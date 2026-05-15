# Copyright 2026 ledoent
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# The 18.0 l10n_fr module added res.partner.siret (a French SIRET tax
# identifier) plus a partner form inheritance view that exposed it. Both
# are DEL'd per upgrade_analysis.txt:
#   res.partner.siret (char)             : DEL
#   ir.ui.view: res_partner_form_l10n_fr : DEL
# Odoo's standard module upgrade does not actually prune the stale
# ir_model_fields row + the orphan view; both survive and trip
# cross-cutting view validation when later modules' data XML loads
# (reproduced on l10n_ae/data/account_tax_report_data.xml:3 with the
# error 'Field "siret" does not exist in model "res.partner"').
_obsolete_xmlids = [
    "l10n_fr.field_res_partner__siret",
    "l10n_fr.res_partner_form_l10n_fr",
]


def cleanup_obsolete_l10n_fr_siret(env):
    """
    Drop the stale res.partner.siret field metadata and the orphan
    partner-form inheritance view. See upgrade_analysis_work.txt.
    """
    openupgrade.delete_records_safely_by_xml_id(env, _obsolete_xmlids)


@openupgrade.migrate()
def migrate(env, version):
    cleanup_obsolete_l10n_fr_siret(env)
