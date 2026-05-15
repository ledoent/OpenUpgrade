# Copyright 2026 Tecnativa - Pilar Vargas
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# 18.0's l10n_fr added res.partner.siret plus a partner-form inheritance view
# exposing it; upgrade_analysis.txt marks both DEL. A standard module upgrade
# leaves the ir_model_fields row and the orphan view behind, and they then trip
# cross-cutting view validation when a later module's data XML loads —
# reproduced on l10n_ae/data/account_tax_report_data.xml:3 with
# 'Field "siret" does not exist in model "res.partner"'.
_obsolete_xmlids = [
    "l10n_fr.field_res_partner__siret",
    "l10n_fr.res_partner_form_l10n_fr",
]


@openupgrade.migrate()
def migrate(env, version):
    # Migrate SIRET values to company_registry without overwriting existing data.
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE res_partner
           SET company_registry = siret
         WHERE siret IS NOT NULL
           AND siret != ''
           AND (company_registry IS NULL OR company_registry = '')
        """,
    )
    # Only after the values above are preserved: drop the stale field metadata
    # and the orphan view, which a plain module upgrade leaves behind.
    openupgrade.delete_records_safely_by_xml_id(env, _obsolete_xmlids)
