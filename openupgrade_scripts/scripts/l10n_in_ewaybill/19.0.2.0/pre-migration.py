from openupgradelib import openupgrade

# l10n_in_ewaybill 19.0 is the result of three converging changes:
#
#  1. l10n_in_edi_ewaybill (the 18.0 EDI module that held the account.move
#     ewaybill fields + ewaybill types) is renamed to l10n_in_ewaybill via
#     `apriori.renamed_modules`. base/19.0.1.3/pre-migration.py runs
#     `update_module_names` over apriori — by the time THIS script runs,
#     all ir_module_module / ir_model_data rows with module='l10n_in_edi_ewaybill'
#     have been rewritten to 'l10n_in_ewaybill'. No work needed here for that
#     renaming.
#
#  2. l10n_in_ewaybill_stock KEEPS its name in 19.0 but the
#     l10n.in.ewaybill + l10n.in.ewaybill.cancel models MOVE OUT to
#     l10n_in_ewaybill. The table name `l10n_in_ewaybill` is identical
#     pre/post; only model ownership and a handful of xmlids change.
#     - update_module_moved_models for both models (transfers ir.model
#       and ir.model.fields ownership).
#     - rename_xmlids for the 6 records that ship under l10n_in_ewaybill
#       in 19.0 but were under l10n_in_ewaybill_stock in 18.0.
#
#  3. Three res.company credentials columns rename their prefix from
#     `l10n_in_edi_ewaybill_*` to `l10n_in_ewaybill_*` (the apriori
#     module rename in step 1 updated ownership in ir_model_fields, but
#     the SQL column names on res_company need rename_fields).
#
#  4. Eight DEL fields on account.move move out to the new
#     l10n.in.ewaybill rows in 19.0. PRESERVE the columns as legacy
#     names here in pre-migration; post-migration.py creates one
#     l10n.in.ewaybill row per account.move that had non-NULL ewaybill
#     data and copies the values across.

_renamed_xmlids_from_stock = [
    (
        "l10n_in_ewaybill_stock.l10n_in_ewaybill_form_action",
        "l10n_in_ewaybill.l10n_in_ewaybill_form_action",
    ),
    (
        "l10n_in_ewaybill_stock.action_report_ewaybill",
        "l10n_in_ewaybill.action_report_ewaybill",
    ),
    (
        "l10n_in_ewaybill_stock.access_l10n_in_ewaybill",
        "l10n_in_ewaybill.access_l10n_in_ewaybill",
    ),
    (
        "l10n_in_ewaybill_stock.access_l10n_in_ewaybill_cancel",
        "l10n_in_ewaybill.access_l10n_in_ewaybill_cancel",
    ),
    (
        "l10n_in_ewaybill_stock.l10n_in_ewaybill_comp_rule",
        "l10n_in_ewaybill.l10n_in_ewaybill_comp_rule",
    ),
    (
        "l10n_in_ewaybill_stock.paperformat_ewaybill",
        "l10n_in_ewaybill.paperformat_ewaybill",
    ),
]

_preserved_columns_account_move = {
    # 18.0 columns owned by l10n_in_edi_ewaybill; DEL in 19.0. We preserve
    # them as openupgrade_legacy_19_0_* so post-migration.py can spawn
    # l10n.in.ewaybill rows from them.
    "account_move": [
        ("l10n_in_distance", None),
        ("l10n_in_mode", None),
        ("l10n_in_transportation_doc_date", None),
        ("l10n_in_transportation_doc_no", None),
        ("l10n_in_transporter_id", None),
        ("l10n_in_type_id", None),
        ("l10n_in_vehicle_no", None),
        ("l10n_in_vehicle_type", None),
    ],
}

_renamed_fields_company_credentials = [
    (
        "res.company",
        "res_company",
        "l10n_in_edi_ewaybill_auth_validity",
        "l10n_in_ewaybill_auth_validity",
    ),
    (
        "res.company",
        "res_company",
        "l10n_in_edi_ewaybill_password",
        "l10n_in_ewaybill_password",
    ),
    (
        "res.company",
        "res_company",
        "l10n_in_edi_ewaybill_username",
        "l10n_in_ewaybill_username",
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    # Move the model ownership: ir.model + ir.model.fields rows that point
    # at l10n.in.ewaybill / l10n.in.ewaybill.cancel get their `module`
    # column rewritten from l10n_in_ewaybill_stock to l10n_in_ewaybill.
    # The SQL table itself is not renamed (the table name is identical).
    openupgrade.update_module_moved_models(
        env.cr, "l10n.in.ewaybill", "l10n_in_ewaybill_stock", "l10n_in_ewaybill"
    )
    openupgrade.update_module_moved_models(
        env.cr, "l10n.in.ewaybill.cancel", "l10n_in_ewaybill_stock", "l10n_in_ewaybill"
    )

    # Six XML records (action, report, two access rules, rule, paperformat)
    # ship under l10n_in_ewaybill in 19.0 but lived under
    # l10n_in_ewaybill_stock in 18.0. Rename so customer references to
    # them survive the upgrade.
    openupgrade.rename_xmlids(env.cr, _renamed_xmlids_from_stock)

    # Three res.company credential columns drop the `_edi_` segment.
    # apriori's update_module_names already moved the ir_model_fields
    # ownership; rename_fields handles the SQL column rename + filter /
    # export / translation side effects.
    openupgrade.rename_fields(env, _renamed_fields_company_credentials)

    # Preserve the 8 account.move ewaybill columns before Odoo's update_db
    # drops them. post-migration.py consumes the legacy values to spawn
    # l10n.in.ewaybill rows.
    openupgrade.rename_columns(env.cr, _preserved_columns_account_move)
