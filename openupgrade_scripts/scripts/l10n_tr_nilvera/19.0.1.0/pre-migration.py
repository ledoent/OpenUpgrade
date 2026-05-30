from openupgradelib import openupgrade


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
