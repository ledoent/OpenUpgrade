from openupgradelib import openupgrade

# Semantic conversion: the 18.0 res.company.l10n_tr_nilvera_environment
# selection (values 'production' / 'sandbox') is replaced in 19.0 by a
# new boolean res.company.l10n_tr_nilvera_use_test_env. The 18.0 value
# carries meaning ('sandbox' = test environment); preserve and map it
# before Odoo's update_db drops the legacy column.
#
# Steps:
#   1. Rename the legacy selection column out of the way (-> openupgrade_legacy_19_0_*)
#      so update_db doesn't reject the type-incompatible NEW column on the same name.
#   2. Add the new boolean column via add_fields (creates the column +
#      ir_model_fields entry + xmlid). Default False so non-NULL rows in
#      18.0 with NULL get the manifest default.
#   3. Map values: 'sandbox' -> True (test env), 'production' -> False (live env).
#      Rows where the legacy column is NULL are left at the column's default (False).
#
# Precedent: hr_holidays/19.0.1.6/pre-migration.py (yes/no -> boolean pattern).


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_columns(
        env.cr,
        {
            "res_company": [
                ("l10n_tr_nilvera_environment", None),
            ],
        },
    )
    openupgrade.add_fields(
        env,
        [
            (
                "l10n_tr_nilvera_use_test_env",
                "res.company",
                "res_company",
                "boolean",
                None,
                "l10n_tr_nilvera",
                False,
            ),
        ],
    )
    openupgrade.map_values(
        env.cr,
        openupgrade.get_legacy_name("l10n_tr_nilvera_environment"),
        "l10n_tr_nilvera_use_test_env",
        [("sandbox", True), ("production", False)],
        table="res_company",
    )
