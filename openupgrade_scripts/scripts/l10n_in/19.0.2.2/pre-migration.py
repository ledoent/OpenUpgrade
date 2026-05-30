from openupgradelib import openupgrade

# Source: openupgrade_scripts/scripts/l10n_in/19.0.2.1/upgrade_analysis.txt
#
# Without these column-adds, `odoo -u all --load=...openupgrade_framework`
# against an 18.0 source DB with l10n_in installed crashes during
# chart_template loading because account.tax.mapped(unique_tax_name_key) +
# account.account.search(...) materialize the new 19.0 fields before
# l10n_in's own install step would have created the columns.
#
# Stored computed fields (e.g. l10n_in_tax_type "is now stored",
# l10n_in_tds_feature_enabled "isfunction: function, stored") get NULL
# columns here; Odoo's _recompute_field machinery populates them after
# install. The l10n_in.pan.entity model and its relation fields are
# Category B (new model + related FKs); deferred per the campaign plan,
# but the integer FK columns on res.company / res.partner are added
# here so the registry can finish loading.
_added_fields = [
    # account.account
    (
        "l10n_in_tcs_feature_enabled",
        "account.account",
        "account_account",
        "boolean",
        None,
        "l10n_in",
        None,
    ),
    (
        "l10n_in_tds_feature_enabled",
        "account.account",
        "account_account",
        "boolean",
        None,
        "l10n_in",
        None,
    ),
    # account.move.line
    (
        "l10n_in_gstr_section",
        "account.move.line",
        "account_move_line",
        "varchar",
        None,
        "l10n_in",
        None,
    ),
    # account.tax
    (
        "l10n_in_is_lut",
        "account.tax",
        "account_tax",
        "boolean",
        None,
        "l10n_in",
        None,
    ),
    (
        "l10n_in_tax_type",
        "account.tax",
        "account_tax",
        "varchar",
        None,
        "l10n_in",
        None,
    ),
    # res.company
    (
        "l10n_in_gstin_status_feature",
        "res.company",
        "res_company",
        "boolean",
        None,
        "l10n_in",
        None,
    ),
    (
        "l10n_in_is_gst_registered",
        "res.company",
        "res_company",
        "boolean",
        None,
        "l10n_in",
        None,
    ),
    (
        "l10n_in_pan_entity_id",
        "res.company",
        "res_company",
        "integer",
        None,
        "l10n_in",
        None,
    ),
    (
        "l10n_in_tcs_feature",
        "res.company",
        "res_company",
        "boolean",
        None,
        "l10n_in",
        None,
    ),
    (
        "l10n_in_tds_feature",
        "res.company",
        "res_company",
        "boolean",
        None,
        "l10n_in",
        None,
    ),
    # res.partner
    (
        "l10n_in_pan_entity_id",
        "res.partner",
        "res_partner",
        "integer",
        None,
        "l10n_in",
        None,
    ),
    (
        "l10n_in_tan",
        "res.partner",
        "res_partner",
        "varchar",
        None,
        "l10n_in",
        None,
    ),
]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.add_fields(env, _added_fields)
