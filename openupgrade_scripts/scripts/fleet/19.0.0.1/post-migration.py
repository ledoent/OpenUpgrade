from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "fleet", "19.0.0.1/noupdate_changes.xml")
