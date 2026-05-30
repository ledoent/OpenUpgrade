from openupgradelib import openupgrade

# l10n_in_ewaybill 19.0 converges several changes (see PR body for detail):
# the l10n.in.ewaybill[.cancel] models move out of l10n_in_ewaybill_stock,
# six xmlids move with them, three res.company credential columns drop their
# `_edi_` segment, and eight account.move ewaybill columns are preserved as
# legacy for post-migration.py to spawn l10n.in.ewaybill rows. The
# l10n_in_edi_ewaybill -> l10n_in_ewaybill module rename is already handled by
# apriori (update_module_names in base pre-migration), so it needs no work here.

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
