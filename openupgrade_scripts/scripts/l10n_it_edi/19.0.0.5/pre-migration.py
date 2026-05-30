from openupgradelib import openupgrade

# l10n_it_edi_ndd folds into l10n_it_edi in 19.0; move the access rule + 22
# l10n_it.document.type records' ir_model_data ownership so customer FKs to the
# legacy document-type ids survive instead of being orphaned by a fresh install.
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
