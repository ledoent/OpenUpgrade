# Copyright 2026 ledoent
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# Fields the 18.0 partner_autocomplete module added that no longer exist
# anywhere in 19.0 (verified: not defined on res.partner, res.company, or
# any partner_autocomplete model). Per upgrade_analysis.txt:
#   res.company.partner_gid    : DEL
#   res.partner.additional_info: DEL
#   res.partner.partner_gid    : DEL
# Odoo's standard registry rebuild does not prune the stale ir_model_fields
# rows when the donor module is upgraded; the rows + matching ir_ui_view
# records (also DEL'd in 19.0 per analysis:
#   view_partner_simple_form_inherit_partner_autocomplete
#   view_res_partner_form_inherit_partner_autocomplete) survive and trip
# cross-cutting view validation later in the same migration run
# (reproduced on l10n_ae/data/account_tax_report_data.xml).
_obsolete_view_xmlids = [
    "partner_autocomplete.view_partner_simple_form_inherit_partner_autocomplete",
    "partner_autocomplete.view_res_partner_form_inherit_partner_autocomplete",
]


def cleanup_obsolete_partner_autocomplete_records(env):
    """
    Drop the orphan ir_ui_view records for fields the 18.0
    partner_autocomplete module added that don't exist in 19.0; cascade
    to inheriting children so the helper can't silently fall back to
    noupdate=True and leave the validation trap in place. The stale
    ir_model_fields rows need no explicit delete (the helper can't
    unlink non-manual fields; the module's own update prunes them).
    See upgrade_analysis_work.txt for the full block.
    """
    openupgrade.delete_records_safely_by_xml_id(
        env, _obsolete_view_xmlids, delete_childs=True
    )


@openupgrade.migrate()
def migrate(env, version):
    cleanup_obsolete_partner_autocomplete_records(env)
