from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "auth_passkey", "19.0.1.1/noupdate_changes.xml")
