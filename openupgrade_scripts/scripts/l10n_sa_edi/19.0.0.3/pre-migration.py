from openupgradelib import openupgrade

# Two intersecting changes per upgrade_analysis.txt:
#
#  1. Two res.partner fields rename their prefix from `l10n_sa_` to
#     `l10n_sa_edi_` (number + scheme). The 18.0 field signatures match
#     the 19.0 field signatures exactly (same type, same selection_keys),
#     so a direct rename_fields preserves the data without conversion.
#
#  2. account.journal.l10n_sa_serial_number is DEL in 19.0. The field
#     held the journal's ZATCA serial — operator-configured, worth
#     preserving as `openupgrade_legacy_19_0_l10n_sa_serial_number` so
#     `database_cleanup` can prompt the admin later (standard
#     OpenUpgrade preservation pattern).

_renamed_fields = [
    (
        "res.partner",
        "res_partner",
        "l10n_sa_additional_identification_number",
        "l10n_sa_edi_additional_identification_number",
    ),
    (
        "res.partner",
        "res_partner",
        "l10n_sa_additional_identification_scheme",
        "l10n_sa_edi_additional_identification_scheme",
    ),
]

_renamed_columns = {
    "account_journal": [
        ("l10n_sa_serial_number", None),
    ],
}


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_fields(env, _renamed_fields)
    openupgrade.rename_columns(env.cr, _renamed_columns)
