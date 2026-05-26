from openupgradelib import openupgrade

# l10n_it_edi_ndd is being folded into l10n_it_edi in 19.0. The 23 records
# below ship in l10n_it_edi's data files in 19.0 but had their ir_model_data
# rows under module='l10n_it_edi_ndd' in 18.0. Without renaming the
# xmlids in pre-migration, Odoo's 19.0 install would either:
#   - create fresh ir_model_data rows pointing at new res_ids (orphaning
#     customer FKs to the legacy l10n_it.document.type ids), or
#   - upsert if the xmlid path resolved, but here `module=` differs.
#
# rename_xmlids moves the ir_model_data ownership from l10n_it_edi_ndd
# to l10n_it_edi without touching res_ids — customer FKs survive.
#
# Source: upgrade_analysis.txt — "renamed from l10n_it_edi_ndd module"
# lines paired with the matching "renamed to l10n_it_edi module" DELs.

_renamed_xmlids = [
    (
        "l10n_it_edi_ndd.access_l10n_it_document_type",
        "l10n_it_edi.access_l10n_it_document_type",
    ),
] + [
    (
        f"l10n_it_edi_ndd.l10n_it_document_type_{n:02d}",
        f"l10n_it_edi.l10n_it_document_type_{n:02d}",
    )
    # 01-09 + 16-28 per upgrade_analysis.txt (10-15 do not appear — likely
    # they were never defined or already lived under l10n_it_edi in 18.0).
    for n in list(range(1, 10)) + list(range(16, 29))
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids)
