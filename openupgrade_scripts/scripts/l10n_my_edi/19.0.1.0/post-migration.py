from openupgradelib import openupgrade

# Companion to pre-migration.py: the 18.0 account.move MyInvois EDI fields
# (preserved as openupgrade_legacy_19_0_* columns) become one myinvois.document
# row per move in 19.0, linked through the myinvois_document_invoice_rel m2m.
# 18.0 and 19.0 share the same state keys, so myinvois_state copies directly.
# company_id/currency_id are required on myinvois.document and are taken from
# the move. A scratch column maps each new document back to its source invoice
# to fill the m2m, then is dropped.

# 18.0 account.move legacy column -> 19.0 myinvois.document column. The binary
# l10n_my_edi_file is attachment-backed (no column) and is moved separately by
# re-pointing its ir_attachment rows below.
_FIELD_MAP = [
    ("myinvois_state", "l10n_my_edi_state"),
    ("myinvois_external_uuid", "l10n_my_edi_external_uuid"),
    ("myinvois_retry_at", "l10n_my_edi_retry_at"),
    ("myinvois_submission_uid", "l10n_my_edi_submission_uid"),
    ("myinvois_validation_time", "l10n_my_edi_validation_time"),
    ("myinvois_error_document_hash", "l10n_my_error_document_hash"),
]


@openupgrade.migrate()
def migrate(env, version):
    legacy_uuid = openupgrade.get_legacy_name("l10n_my_edi_external_uuid")
    if not openupgrade.column_exists(env.cr, "account_move", legacy_uuid):
        return

    legacy = {new: openupgrade.get_legacy_name(old) for new, old in _FIELD_MAP}
    # a move carries MyInvois data if any of the preserved columns is non-NULL
    any_nonnull = " OR ".join(f"am.{c} IS NOT NULL" for c in legacy.values())
    dst_cols = ", ".join(legacy.keys())
    src_cols = ", ".join(f"am.{legacy[new]}" for new in legacy)

    openupgrade.logged_query(
        env.cr, "ALTER TABLE myinvois_document ADD COLUMN _ou_src_invoice integer"
    )
    openupgrade.logged_query(
        env.cr,
        f"""
        INSERT INTO myinvois_document (
            company_id, currency_id, active, {dst_cols}, _ou_src_invoice,
            create_uid, create_date, write_uid, write_date
        )
        SELECT
            am.company_id, am.currency_id, TRUE, {src_cols}, am.id,
            COALESCE(am.write_uid, am.create_uid, 1),
            COALESCE(am.write_date, am.create_date, NOW() AT TIME ZONE 'UTC'),
            COALESCE(am.write_uid, am.create_uid, 1),
            COALESCE(am.write_date, am.create_date, NOW() AT TIME ZONE 'UTC')
        FROM account_move am
        WHERE {any_nonnull}
        """,
    )
    openupgrade.logged_query(
        env.cr,
        """
        INSERT INTO myinvois_document_invoice_rel (document_id, invoice_id)
        SELECT id, _ou_src_invoice FROM myinvois_document
        WHERE _ou_src_invoice IS NOT NULL
        """,
    )
    # The MyInvois XML file is a binary attachment field: re-point its
    # ir_attachment rows from account.move/l10n_my_edi_file to the new
    # myinvois.document/myinvois_file (no column to copy).
    openupgrade.logged_query(
        env.cr,
        """
        UPDATE ir_attachment a
        SET res_model = 'myinvois.document',
            res_field = 'myinvois_file',
            res_id = d.id
        FROM myinvois_document d
        WHERE a.res_model = 'account.move'
          AND a.res_field = 'l10n_my_edi_file'
          AND a.res_id = d._ou_src_invoice
        """,
    )
    openupgrade.logged_query(
        env.cr, "ALTER TABLE myinvois_document DROP COLUMN _ou_src_invoice"
    )
