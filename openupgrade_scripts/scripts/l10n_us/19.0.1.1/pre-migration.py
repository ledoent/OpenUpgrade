from openupgradelib import openupgrade

# Preserve the 18.0 res.partner.bank.aba_routing value before Odoo's
# update_db drops the column. The standard OpenUpgrade pattern renames it
# to openupgrade_legacy_19_0_aba_routing so the data survives the upgrade
# and database_cleanup can prompt the operator later. Source:
# upgrade_analysis.txt — "aba_routing (char) : DEL".
_renamed_columns = {
    "res_partner_bank": [
        ("aba_routing", None),
    ],
}


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.rename_columns(env.cr, _renamed_columns)
