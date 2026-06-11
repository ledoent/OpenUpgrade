from openupgradelib import openupgrade

# l10n_my_edi 19.0 converges several changes (see PR body): the myinvois.document
# model (+ two transient wizards) moves out of l10n_my_edi_pos into l10n_my_edi,
# six xmlids move with them, and the eight account.move MyInvois EDI columns are
# preserved as legacy for post-migration.py to spawn myinvois.document rows.
# The l10n_my_edi_extended -> l10n_my_edi merge is handled by apriori.

_MOVED_MODELS = [
    "myinvois.document",
    "myinvois.consolidate.invoice.wizard",
    "myinvois.document.status.update.wizard",
]

_RENAMED_XMLIDS_FROM_POS = [
    (
        "l10n_my_edi_pos.action_generate_myinvois_document_file",
        "l10n_my_edi.action_generate_myinvois_document_file",
    ),
    (
        "l10n_my_edi_pos.ir_cron_myinvois_document_sync",
        "l10n_my_edi.ir_cron_myinvois_document_sync",
    ),
    (
        "l10n_my_edi_pos.access_myinvois_consolidate_invoice_wizard_user",
        "l10n_my_edi.access_myinvois_consolidate_invoice_wizard_user",
    ),
    (
        "l10n_my_edi_pos.myinvois_document_comp_rule",
        "l10n_my_edi.myinvois_document_comp_rule",
    ),
]

# 18.0 account.move columns owned by l10n_my_edi; DEL in 19.0 (the data moves to
# myinvois.document rows). l10n_my_edi_state was a stored Selection in 18.0 and
# is a non-stored compute in 19.0, so its column is dropped too -- preserve it
# to carry the state across. l10n_my_edi_file is a binary attachment field (no
# table column -- stored in ir_attachment), so it is NOT preserved here;
# post-migration.py re-points its attachment to the new myinvois.document.
_PRESERVED_ACCOUNT_MOVE = [
    "l10n_my_edi_external_uuid",
    "l10n_my_edi_invoice_long_id",
    "l10n_my_edi_retry_at",
    "l10n_my_edi_submission_uid",
    "l10n_my_edi_validation_time",
    "l10n_my_error_document_hash",
    "l10n_my_edi_state",
]


@openupgrade.migrate()
def migrate(env, version):
    for model in _MOVED_MODELS:
        openupgrade.update_module_moved_models(
            env.cr, model, "l10n_my_edi_pos", "l10n_my_edi"
        )
    openupgrade.rename_xmlids(env.cr, _RENAMED_XMLIDS_FROM_POS)
    # Preserve only columns that actually exist (an attachment-backed field has
    # no column; a column may also be absent if its module isn't installed).
    cols = [
        (c, None)
        for c in _PRESERVED_ACCOUNT_MOVE
        if openupgrade.column_exists(env.cr, "account_move", c)
    ]
    if cols:
        openupgrade.rename_columns(env.cr, {"account_move": cols})
