from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.load_data(env, "l10n_ua", "19.0.1.4/noupdate_changes.xml")
