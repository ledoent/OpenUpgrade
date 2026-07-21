from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "crm_iap_mine", "19.0.1.2/noupdate_changes.xml")
