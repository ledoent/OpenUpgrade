from openupgradelib import openupgrade

_renamed_models = [("account_peppol.service.wizard", "peppol.config.wizard")]
_renamed_tables = [("account_peppol_service_wizard", "peppol_config_wizard")]


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_models(env.cr, _renamed_models)
    openupgrade.rename_tables(env.cr, _renamed_tables)
    # 19.0 drops the 'in_verification' key from the required proxy-state
    # selection; map mid-verification companies back to not_registered
    # (18.0's own deregistration reset).
    openupgrade.map_values(
        env.cr,
        "account_peppol_proxy_state",
        "account_peppol_proxy_state",
        [("in_verification", "not_registered")],
        table="res_company",
    )
